"""
core/ollama.py — Integración con Ollama: embeddings, análisis, visión OCR
"""
import json
import math
import re
import base64
import requests

from core.config import OLLAMA_URL, ANALYSIS_MODEL, EMBEDDING_MODEL
from core.state  import scan_state, state_lock


# ─── Helpers de conexión ──────────────────────────────────────

def check_ollama() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_available_models() -> list:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def get_vision_model():
    """Retorna el primer modelo de visión disponible en Ollama."""
    priority = ["llama3.2-vision:latest", "llama3.2-vision", "qwen2.5vl", "minicpm-v", "llava:13b", "llava:7b", "llava", "moondream"]
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        available = [m["name"] for m in r.json().get("models", [])]
        for vm in priority:
            base = vm.split(":")[0]
            for a in available:
                if a.lower().startswith(base):
                    return a
    except Exception:
        pass
    return None


# ─── Embeddings ───────────────────────────────────────────────

def get_embedding(text: str) -> list:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text[:2000]},
            timeout=30,
        )
        return r.json().get("embedding", [])
    except Exception:
        return []


def cosine_similarity(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ─── Visión OCR (para páginas con fórmulas) ──────────────────

def ocr_page_vision(page, vision_model: str, page_num: int) -> str:
    """
    Renderiza una página PDF como imagen y la manda al modelo de visión.
    Optimizado para M4 Pro y previene timeouts.
    """
    try:
        # Usamos un DPI balanceado para velocidad y precisión
        pix = page.get_pixmap(dpi=160, colorspace="rgb")
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()

        prompt = (
            "Eres un experto en transcripción matemática y científica. "
            "Tu tarea es extraer TODO el contenido de esta imagen. "
            "Usa LaTeX ($...$ para inline, $$...$$ para bloques) para TODAS las fórmulas. "
            "Mantené el texto explicativo y el orden del documento. "
            "Responde solo con la transcripción en Markdown."
        )

        # M4 Pro puede manejar más, pero Ollama a veces se satura. 
        # Aumentamos timeout a 300s (5 min) para páginas muy complejas.
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  vision_model,
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
                "options": {
                    "temperature": 0.0, 
                    "num_ctx": 4096,
                    "num_thread": 8  # Aprovechar núcleos M4
                },
            },
            timeout=300,
        )
        text = r.json().get("response", "").strip()

        # Detectar si el modelo rechazó la request (filtro activado)
        refusal_hints = [
            "no puedo ayudar", "cannot help", "i can't", "no me es posible",
            "lo siento, pero no", "sorry, i", "i'm unable", 
            "desculpe", "não posso", "não consigo"
        ]
        if any(h in text.lower() for h in refusal_hints):
            # Reintentar con prompt aún más neutro
            prompt2 = (
                "Analizá esta imagen matemática de un apunte universitario. "
                "Listá todas las expresiones matemáticas que ves usando LaTeX ($...$). "
                "Incluí el texto que acompaña a cada expresión."
            )
            r2 = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model":  vision_model,
                    "prompt": prompt2,
                    "images": [img_b64],
                    "stream": False,
                    "options": {"temperature": 0.0, "num_ctx": 4096},
                },
                timeout=300,
            )
            text = r2.json().get("response", "").strip()

        if text and not any(h in text.lower() for h in refusal_hints):
            return f"<!-- página {page_num} — OCR visual -->\n{text}"

    except Exception as e:
        from core.logger import log
        log(f"Error OCR visión página {page_num}: {e}", "warn")
    return ""


# ─── Análisis de contenido ────────────────────────────────────

# ─── AGENTE DE RAZONAMIENTO AVANZADO (RAG+) ────────────────────

def expand_query(query: str) -> list:
    """Genera variaciones de búsqueda orientadas a conceptos académicos."""
    prompt = (
        f"Dada la consulta: '{query}', genera 2 variaciones de búsqueda que usen terminología académica técnica. "
        "Responde solo con las 2 variaciones, una por línea."
    )
    try:
        from core.mlx_inference import generate_text
        text = generate_text(prompt, max_tokens=60, temperature=0.2)
        return [query] + [v.strip("- ").strip() for v in text.split("\n") if v.strip()][:2]
    except Exception as e:
        from core.logger import log
        log(f"Error expand_query MLX: {e}", "warn")
        return [query]

def generate_hyde_doc(query: str) -> str:
    """HyDE: Genera un fragmento hipotético de un apunte para mejorar el matching semántico."""
    prompt = (
        f"Escribe un párrafo técnico y denso en información que podrías encontrar en un apunte universitario sobre: {query}. "
        "Usa lenguaje formal y conceptos clave. No saludes, no expliques, solo escribe el apunte."
    )
    try:
        from core.mlx_inference import generate_text
        text = generate_text(prompt, max_tokens=150, temperature=0.1)
        return text
    except Exception as e:
        from core.logger import log
        log(f"Error generate_hyde_doc MLX: {e}", "warn")
        return query

def analyze_content(text: str, existing_topics: list = None, model: str = None) -> dict:
    """
    Analiza el contenido del PDF y devuelve metadatos estructurados en JSON.
    """
    m = model or ANALYSIS_MODEL
    existing_str = ", ".join(existing_topics[:30]) if existing_topics else "ninguno aún"

    prompt = f"""Eres un Agente de Inteligencia Académica de Grado Superior especializado en Clasificación y Arquitectura de Conocimiento.
    
TAREA: Realizar un relevamiento exhaustivo del documento y extraer metadatos de alta fidelidad.

REGLAS DE CLASIFICACIÓN (INGENIERÍA DE CONTEXTO):
1. MATERIA Y CATEGORÍA: Sé extremadamente preciso. No confundas temas transversales. Si el documento tiene fórmulas, es Matemáticas o Física. Si tiene código, es Programación. Si es un texto narrativo, es Literatura.
2. CONTEXTO DE VAULT: Si el usuario menciona temas previos como {existing_str}, tratá de mantener la coherencia taxonómica.
3. INFERENCIA LÓGICA: Si el documento es una 'guía de ejercicios', inferí el tema teórico subyacente (ej: "Cálculo Diferencial").

CONTENIDO:
\"\"\"
{text[:5000]}
\"\"\"

FORMATO DE SALIDA (JSON ESTRICTO):
{{
  "titulo": "Título formal y descriptivo",
  "materia": "Nombre de la materia (ej: Álgebra II, Análisis Matemático)",
  "categoria": "Matemáticas | Física | Programación | Algoritmos | Historia | Literatura | Biología | Química | Economía | Derecho | Filosofía | Ingeniería | Estadística | Otro",
  "subcategoria": "Tema específico del programa",
  "resumen": "Resumen ejecutivo de 3 oraciones",
  "conceptos_clave": ["Concepto 1", "Concepto 2", "Concepto 3", "Concepto 4", "Concepto 5"],
  "formulas_importantes": ["Usa LaTeX escapado \\\\frac{...}{...}"],
  "tags": ["tag1", "tag2"],
  "dificultad": "Básico | Intermedio | Avanzado",
  "tipo": "Apunte | Práctica | Teórico | Resumen | Ejercicios | Parcial | Final | Bibliografía",
  "idioma": "Español | Inglés",
  "conexiones_sugeridas": ["Temas del vault relacionados"]
}}"""

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":   m,
                "prompt":  prompt,
                "stream":  False,
                "format":  "json",
                "options": {
                    "temperature": 0.0, 
                    "num_ctx": 8192,
                    "num_thread": 8
                },
            },
            timeout=180,
        )
        raw = r.json().get("response", "{}").strip()
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*",     "", raw)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            json_str = match.group()
            # Limpiar escapes inválidos (barras simples de LaTeX) antes de parsear
            json_str = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', json_str)
            return json.loads(json_str)
    except json.JSONDecodeError as e:
        from core.logger import log
        log(f"JSON inválido del modelo: {e}", "warn")
    except Exception as e:
        from core.logger import log
        log(f"Error en análisis Ollama: {e}", "error")

    return _fallback_analysis()


def _fallback_analysis() -> dict:
    return {
        "titulo": "Documento sin título",
        "materia": "Sin clasificar",
        "categoria": "Otro",
        "subcategoria": "General",
        "resumen": "No se pudo analizar automáticamente.",
        "conceptos_clave": [],
        "formulas_importantes": [],
        "tags": ["sin-clasificar"],
        "dificultad": "Básico",
        "tipo": "Apunte",
        "idioma": "Español",
        "conexiones_sugeridas": [],
    }


# ─── Chat RAG ────────────────────────────────────────────────

def chat_con_vault(question: str, vault_path: str, model: str = None, mode: str = "normal") -> dict:
    from core.rag import buscar_en_vault
    from agents.professor import SOCRATIC_SYSTEM_PROMPT
    
    m    = model or ANALYSIS_MODEL
    docs = buscar_en_vault(question, vault_path, top_k=5)

    if not docs:
        context_text = "(No se encontraron notas relevantes en el vault para esta pregunta. Usa internet si es necesario o responde con tu conocimiento base aclarando la falta de fuentes locales.)"
        sources      = []
    else:
        context_parts = [
            f"--- [Fuente {i}] ---\nTÍTULO: {d['title']}\nRUTA: {d['path']}\nCONTENIDO: {d['snippet']}"
            for i, d in enumerate(docs, 1)
        ]
        
        # Inyectar Graph Mind
        from core.obsidian import get_local_graph_context
        note_names = [d["title"] for d in docs]
        graph_context = get_local_graph_context(vault_path, note_names)
        
        if graph_context:
            context_parts.append(graph_context)
            
        context_text = "\n\n".join(context_parts)
        sources      = [{"title": d["title"], "path": d["path"], "score": d["score"]} for d in docs]

    prompt_standard = """Sos JARVIS (Knowledge Architect), un sistema experto en análisis académico y gestión de conocimiento local.
Estás diseñado para asistir al usuario con rigor científico, profundidad analítica y precisión quirúrgica.

### REGLAS MAESTRAS DE RAZONAMIENTO:
1. **ANCLAJE AL VAULT (PRIORIDAD ALFA)**: Tu conocimiento primario reside en el 'CONTEXTO DEL VAULT' proporcionado. 
   - No alucines. Si la información no está en el vault ni en internet, admítelo.
   - Si la información en el vault es contradictoria, resáltalo.
2. **CITACIÓN OBLIGATORIA**: Cada vez que afirmes algo basado en el vault, DEBES citar la fuente usando [ID] (ej: [Fuente 1], [Fuente 2]).
3. **RAZONAMIENTO PASO A PASO (CoT)**: Antes de dar tu respuesta final, analiza internamente la relación entre los fragmentos recuperados para construir una síntesis coherente.
4. **ESTILO ACADÉMICO**:
   - Sé detallado y exhaustivo. Evita respuestas vagas o cortas.
   - Usa Markdown (negritas, listas, tablas) para estructurar la información.
   - Usa LaTeX ($...$) para fórmulas o términos matemáticos.
5. **HERRAMIENTAS**: 
   - Usa 'search_internet' solo si el vault no tiene la respuesta o si necesitas actualidad.
   - No menciones el uso de herramientas en el texto final; úsalas de forma integrada.

### PROTOCOLO DE SALIDA:
- Prohibido empezar con "Respuesta:", "De acuerdo al vault...", o frases similares. Ve directo al conocimiento.
- Prohibido el uso de JSON en el chat humano.
- Idioma: Español (neutro/académico)."""

    if mode == "professor":
        prompt_system = SOCRATIC_SYSTEM_PROMPT
    else:
        prompt_system = prompt_standard

    from core.memory import save_chat_message, get_recent_chat_history
    
    # 1. Guardar pregunta del usuario
    save_chat_message("user", question, mode, vault_path)
    
    # 2. Recuperar historial reciente
    history = get_recent_chat_history(limit=6) # 3 vueltas de conversación
    
    messages = [
        {"role": "system", "content": prompt_system},
    ]
    
    # Agregar historial (evitando duplicar la pregunta actual si ya se guardó)
    for msg in history:
        # No agregamos el último mensaje si es igual a la pregunta actual (evitar duplicado)
        if msg["role"] == "user" and msg["content"] == question:
            continue
        messages.append(msg)
        
    messages.append({"role": "user", "content": f"### CONOCIMIENTO DEL VAULT ###\n{context_text}\n\n### PREGUNTA DEL ESTUDIANTE ###\n{question}"})

    try:
        import json
        from core.tools import OLLAMA_TOOLS_SCHEMA, execute_tool
        from core.state import load_state
        
        # Cargar configuración para ver qué herramientas están activas
        state = load_state()
        config = state.get("config", {})
        
        # Smart Selection: Si el modelo es DeepSeek-R1, desactivar herramientas (no las soporta nativamente)
        model_name_lower = m.lower()
        supports_tools = True
        if "deepseek-r1" in model_name_lower or "vision" in model_name_lower:
            supports_tools = False
            from core.logger import log
            log(f"Modo 'Razonamiento/Visión' detectado ({m}): Desactivando herramientas de Ollama para evitar errores.", "info")

        # Filtrar herramientas según config
        active_tools = []
        if supports_tools:
            for t in OLLAMA_TOOLS_SCHEMA:
                func_name = t.get("function", {}).get("name")
                if func_name == "search_internet" and not config.get("tools_search", True):
                    continue
                if func_name == "execute_mac_command" and not config.get("tools_command", False):
                    continue
                if func_name == "read_local_file" and not config.get("tools_files", True):
                    continue
                active_tools.append(t)

        # Enviar primero las fuentes
        yield json.dumps({"type": "sources", "sources": sources}) + "\n"

        full_answer = ""
        max_tool_iterations = 3
        for iteration in range(max_tool_iterations):
            try:
                from core.mlx_inference import get_mlx_model
                import mlx_lm
                model, tokenizer = get_mlx_model()
                
                # Inyectar tools al system prompt si hay
                sys_msg_idx = next((i for i, m in enumerate(messages) if m["role"] == "system"), -1)
                original_sys_content = messages[sys_msg_idx]["content"] if sys_msg_idx != -1 else ""
                
                if active_tools and sys_msg_idx != -1:
                    tools_str = json.dumps([t["function"] for t in active_tools], indent=2, ensure_ascii=False)
                    tool_prompt = (
                        f"\n\nTIENES ACCESO A LAS SIGUIENTES HERRAMIENTAS:\n{tools_str}\n"
                        "Si necesitas usar una herramienta, DEBES responder ÚNICAMENTE con un bloque JSON "
                        "con este formato estricto:\n"
                        "{\"name\": \"nombre_herramienta\", \"parameters\": {\"param1\": \"valor\"}}\n"
                        "NO ESCRIBAS NADA MÁS ALREDEDOR DEL JSON."
                    )
                    messages[sys_msg_idx]["content"] = original_sys_content + tool_prompt

                prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                
                # Restaurar el system prompt original para no acumular el texto de las tools
                if sys_msg_idx != -1:
                    messages[sys_msg_idx]["content"] = original_sys_content

                response_text = ""
                is_json_tool = False
                
                # Stream nativo MLX
                for chunk in mlx_lm.stream_generate(model, tokenizer, prompt, max_tokens=2048):
                    response_text += chunk
                    
                    # Heurística para no streamear JSON de tools al usuario
                    if len(response_text) < 10 and response_text.strip().startswith("{"):
                        is_json_tool = True
                        continue
                        
                    if not is_json_tool:
                        # Yield al frontend (limpieza quirúrgica si es el inicio)
                        if len(response_text) == len(chunk): # Primer chunk
                            chunk = re.sub(r'^(Respuesta|Jarvis|Assistant):\s*', '', chunk, flags=re.I)
                        if chunk.strip():
                            full_answer += chunk
                            yield json.dumps({"type": "chunk", "content": chunk}) + "\n"

                message = {"role": "assistant", "content": response_text.strip()}
                messages.append(message)

                content = message["content"]
                tool_calls = []

                # Parsear tool si detectamos que es JSON
                if is_json_tool or ('{' in content and '"name"' in content):
                    parsed_tc = _try_parse_tool_from_text(content)
                    if parsed_tc:
                        tool_calls = [parsed_tc]

            except Exception as e:
                from core.logger import log
                log(f"Fallo en MLX inference: {e}", "error")
                yield json.dumps({"type": "error", "content": f"Fallo en MLX: {e}"}) + "\n"
                break

            # ── Procesar tool calls ──
            if tool_calls:
                for tc in tool_calls:
                    func_name = tc.get("function", {}).get("name")
                    args = tc.get("function", {}).get("arguments", {})

                    if func_name == "execute_mac_command":
                        yield json.dumps({"type": "terminal_approval", "command": args.get("command", ""), "tool_call_id": tc.get("id")}) + "\n"
                        return

                    if func_name == "search_internet":
                        query = args.get("query", "")
                        words = query.split()
                        if len(words) > 5:
                            stop_words = {"que", "es", "el", "la", "de", "un", "una", "en", "sobre", "para", "como", "son", "los", "las"}
                            keywords = [w for w in words if w.lower() not in stop_words]
                            args["query"] = " ".join(keywords[:5])

                    yield json.dumps({"type": "chunk", "content": f"\n\n*🤖 Jarvis está utilizando la herramienta: `{func_name}`...*\n\n"}) + "\n"

                    result = execute_tool(tc)

                    messages.append({
                        "role": "tool",
                        "content": result,
                        "tool_call_id": tc.get("id")
                    })
                # Volver a iterar para que la IA lea el resultado
            else:
                # No hay tool calls → la IA terminó
                if full_answer:
                    from core.memory import save_chat_message
                    save_chat_message("assistant", full_answer.strip(), mode, vault_path)
                break

        yield json.dumps({"type": "done"}) + "\n"

    except Exception as e:
        import json
        yield json.dumps({"type": "error", "content": f"Error al conectar con Ollama o ejecutar herramienta: {e}"}) + "\n"


def _try_parse_tool_from_text(text: str) -> dict:
    """Fallback parser: detecta tool calls que Llama 3.1 filtró al texto.
    
    Busca un bloque JSON balanceado que contenga 'name' y 'parameters',
    y lo convierte a la estructura estándar de tool_call de Ollama.
    Retorna None si no encuentra nada válido.
    """
    try:
        start = text.find('{')
        if start == -1:
            return None
        
        # Encontrar el bloque balanceado
        count = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == '{':
                count += 1
            elif text[i] == '}':
                count -= 1
            if count == 0:
                end = i + 1
                break
        
        if end == -1:
            return None
        
        block = text[start:end]
        parsed = json.loads(block)
        
        # Verificar que parece un tool call
        if "name" in parsed:
            return {
                "function": {
                    "name": parsed["name"],
                    "arguments": parsed.get("parameters", parsed.get("arguments", {}))
                },
                "id": "fallback_tc_0"
            }
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return None
