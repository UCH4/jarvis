import subprocess
import os
import urllib.parse

import requests

from core.config import OBSIDIAN_REST_URL, OBSIDIAN_API_KEY, OBSIDIAN_VERIFY_TLS

def _invalidate_bm25_after_index(vault_path: str = None):
    try:
        from core.hybrid_search import invalidate_bm25_index
        invalidate_bm25_index(vault_path)
    except Exception:
        pass


def _obsidian_rest_headers():
    h = {"Content-Type": "text/markdown; charset=utf-8"}
    if OBSIDIAN_API_KEY:
        h["Authorization"] = f"Bearer {OBSIDIAN_API_KEY}"
    return h


def obsidian_rest_put_note(rel_path: str, content: str, mode: str = "replace") -> tuple:
    """
    Escribe nota vía Obsidian Local REST API (PUT /vault/{path}).
    Devuelve (ok: bool, message: str).
    """
    if not OBSIDIAN_REST_URL:
        return False, ""
    path_enc = "/".join(urllib.parse.quote(seg, safe="") for seg in rel_path.split("/"))
    url = f"{OBSIDIAN_REST_URL}/vault/{path_enc}"
    try:
        if mode == "append":
            get_url = f"{OBSIDIAN_REST_URL}/vault/{path_enc}"
            gr = requests.get(
                get_url,
                headers=_obsidian_rest_headers(),
                timeout=30,
                verify=OBSIDIAN_VERIFY_TLS,
            )
            prev = gr.text if gr.status_code == 200 else ""
            content = (prev or "") + "\n\n" + content
        r = requests.put(
            url,
            data=content.encode("utf-8"),
            headers=_obsidian_rest_headers(),
            timeout=60,
            verify=OBSIDIAN_VERIFY_TLS,
        )
        if r.status_code in (200, 204):
            return True, "Obsidian REST OK"
        return False, f"Obsidian REST HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)


def execute_mac_command(command: str) -> str:
    """Ejecuta un comando en la terminal de Mac de forma segura."""
    from agents.terminal import MacTerminalAgent
    agent = MacTerminalAgent()
    return agent.run_command(command)

def read_local_file(path: str) -> str:
    """Lee el contenido de un archivo local en la Mac."""
    try:
        real_path = os.path.expanduser(path)
        if not os.path.exists(real_path):
            return f"ERROR: El archivo en '{path}' NO existe en esta computadora. No intentes leer archivos inexistentes."
        if not os.path.isfile(real_path):
            return "ERROR: La ruta no es un archivo (posiblemente un directorio)."
        with open(real_path, 'r', encoding='utf-8') as f:
            return f.read()[:15000] # Ampliamos límite para M4 Pro
    except Exception as e:
        return f"Error al leer archivo: {e}"

def search_internet(query: str) -> str:
    """Realiza una búsqueda básica en internet usando duckduckgo LITE/HTML."""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        # User-Agent de Safari en macOS (M4 Pro style)
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"}
        
        # Intentamos con la versión lite que es más estable
        res = requests.get(f"https://duckduckgo.com/lite/?q={query}", headers=headers, timeout=15)
        if res.status_code != 200:
            res = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers, timeout=15)
            
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Selectores variados para máxima compatibilidad (DDG cambia seguido)
        results = (soup.select('.result-snippet') or 
                   soup.select('.result__snippet') or 
                   soup.select('.snippet') or 
                   soup.select('.result__body'))
        
        text_results = []
        for r in results[:10]:
            txt = r.get_text().strip()
            if len(txt) > 20:
                # Limpiar saltos de línea excesivos
                txt = " ".join(txt.split())
                text_results.append("- " + txt)
            
        if not text_results:
            # Fallback a títulos y links (a veces DDG Lite solo manda eso)
            links = soup.select('.result-link') or soup.select('.result__a') or soup.select('a.result-link')
            for l in links[:6]:
                txt = l.get_text().strip()
                if txt:
                    text_results.append("- " + txt)

        if not text_results:
            return "No se hallaron resultados externos relevantes. La búsqueda en DuckDuckGo no devolvió fragmentos legibles en este momento."
            
        return "\n".join(text_results)
    except Exception as e:
        return f"Error en búsqueda web (Mac Network): {e}"

def read_url_content(url: str) -> str:
    """Descarga y extrae el texto principal de una URL específica."""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"}
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Eliminar scripts, estilos, headers, footers
        for script in soup(["script", "style", "header", "footer", "nav", "aside"]):
            script.decompose()
            
        text = soup.get_text(separator='\n')
        # Limpiar espacios
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Truncar para no saturar contexto
        return text[:15000] 
    except Exception as e:
        return f"Error al intentar leer la URL {url}: {e}"

def read_obsidian_note(note_name: str) -> str:
    """Busca una nota en el vault por su nombre (parcial o total) y devuelve su contenido."""
    from core.config import load_config
    import os
    cfg = load_config()
    vault = cfg.get("vault_path")
    if not vault: return "Error: Vault no configurado."
    
    for root, dirs, files in os.walk(vault):
        for f in files:
            if f.endswith(".md") and (note_name.lower() in f.lower()):
                path = os.path.join(root, f)
                return read_local_file(path)
    return f"Error: No se encontró la nota '{note_name}' en el Vault."

def create_exercise(topic: str, content: str) -> str:
    """Crea un archivo Markdown en la raíz del Vault con un ejercicio o desafío."""
    from core.config import load_config
    import os
    cfg = load_config()
    vault = cfg.get("vault_path")
    if not vault: return "Error: Vault no configurado."
    
    safe_topic = "".join([c if c.isalnum() else "_" for c in topic])
    filename = f"Reto_{safe_topic}.md"
    filepath = os.path.join(vault, filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Reto de Estudio: {topic}\n\n{content}\n")
        return f"Éxito: Archivo '{filename}' creado en el Vault. Dile al usuario que lo revise en Obsidian."
    except Exception as e:
        return f"Error al crear el archivo: {e}"

def create_vault_note(title: str, content: str, folder: str = "") -> str:
    """Crea una nota Markdown en una carpeta específica del Vault."""
    from core.config import load_config
    cfg = load_config()
    vault = cfg.get("vault_path")
    if not vault: return "Error: Vault no configurado."
    
    # Limpiar el título para que sea un nombre de archivo válido
    safe_title = "".join([c if c.isalnum() or c in " -_" else "_" for c in title])
    if not safe_title.endswith(".md"):
        safe_title += ".md"
        
    target_dir = os.path.join(vault, folder) if folder else vault
    rel_path = os.path.join(folder, safe_title) if folder else safe_title
    
    try:
        if OBSIDIAN_REST_URL:
            ok, msg = obsidian_rest_put_note(rel_path.replace("\\", "/"), content, mode="replace")
            if not ok:
                return f"Error Obsidian REST: {msg}"
        else:
            os.makedirs(target_dir, exist_ok=True)
            filepath = os.path.join(target_dir, safe_title)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        
        # --- Indexar en ChromaDB inmediatamente ---
        try:
            from core.db import get_collection
            from core.chunker import markdown_aware_chunks
            collection = get_collection(vault_path=vault)
            chunks = markdown_aware_chunks(content, title=title)
            if chunks:
                ids = [f"{safe_title}_{i}" for i in range(len(chunks))]
                metadatas = [{"title": title, "path": rel_path.replace("\\", "/"), "source": "Jarvis Tool"} for _ in chunks]
                collection.add(documents=[c["content"] for c in chunks], metadatas=metadatas, ids=ids)
            _invalidate_bm25_after_index(vault)
        except Exception as ex:
            print(f"Aviso: Nota creada pero no indexada: {ex}")
            
        return f"Éxito: Nota '{safe_title}' creada en el Vault (carpeta: {folder or 'raíz'}). Ahora podés leerla o pedirle al usuario que la abra."
    except Exception as e:
        return f"Error al crear la nota: {e}"

def edit_vault_note(title: str, content: str, mode: str = "replace", folder: str = "") -> str:
    """Modifica una nota existente (reemplaza o añade al final)."""
    from core.config import load_config
    cfg = load_config()
    vault = cfg.get("vault_path")
    if not vault: return "Error: Vault no configurado."
    
    safe_title = "".join([c if c.isalnum() or c in " -_" else "_" for c in title])
    if not safe_title.endswith(".md"):
        safe_title += ".md"
        
    target_dir = os.path.join(vault, folder) if folder else vault
    filepath = os.path.join(target_dir, safe_title)
    rel_path = os.path.join(folder, safe_title) if folder else safe_title
    
    if not OBSIDIAN_REST_URL and not os.path.exists(filepath):
        return f"Error: La nota '{title}' no existe. Usá 'create_vault_note' primero."
        
    try:
        if OBSIDIAN_REST_URL:
            ok, err = obsidian_rest_put_note(rel_path.replace("\\", "/"), content, mode=mode)
            if not ok:
                return f"Error Obsidian REST: {err}"
            msg = f"Éxito: Nota '{safe_title}' actualizada vía Obsidian REST."
            full_content = content
            if mode == "append":
                try:
                    gr = requests.get(
                        f"{OBSIDIAN_REST_URL}/vault/{'/'.join(urllib.parse.quote(s, safe='') for s in rel_path.split('/'))}",
                        headers=_obsidian_rest_headers(),
                        timeout=30,
                        verify=OBSIDIAN_VERIFY_TLS,
                    )
                    full_content = gr.text if gr.status_code == 200 else content
                except Exception:
                    full_content = content
        else:
            if mode == "append":
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write("\n\n" + content)
                msg = f"Éxito: Contenido añadido al final de '{safe_title}'."
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                msg = f"Éxito: Nota '{safe_title}' actualizada (reemplazo total)."
            with open(filepath, "r", encoding="utf-8") as f:
                full_content = f.read()

        # --- Actualizar índice en ChromaDB ---
        try:
            from core.db import get_collection
            from core.chunker import markdown_aware_chunks
            collection = get_collection(vault_path=vault)
            chunks = markdown_aware_chunks(full_content, title=title)
            if chunks:
                ids = [f"{safe_title}_{i}" for i in range(len(chunks))]
                metadatas = [{"title": title, "path": rel_path.replace("\\", "/"), "source": "Jarvis Tool"} for _ in chunks]
                collection.add(documents=[c["content"] for c in chunks], metadatas=metadatas, ids=ids)
            _invalidate_bm25_after_index(vault)
        except Exception as ex:
            print(f"Aviso: Nota editada pero no re-indexada: {ex}")

        return msg
    except Exception as e:
        return f"Error al editar la nota: {e}"

def list_vault_notes() -> str:
    """Lista los títulos de las notas disponibles en el vault para poder crear enlaces [[link]]."""
    from core.config import load_config
    import os
    cfg = load_config()
    vault = cfg.get("vault_path")
    if not vault: return "Error: Vault no configurado."
    
    notes = []
    for root, dirs, files in os.walk(vault):
        for f in files:
            if f.endswith(".md"):
                notes.append(f.replace(".md", ""))
    
    if not notes:
        return "El vault está vacío o no se encontraron notas."
        
    return "Notas disponibles para enlazar:\n- " + "\n- ".join(notes[:50]) + (f"\n... y {len(notes)-50} más." if len(notes) > 50 else "")

# Esquema de herramientas para Ollama/MLX

OLLAMA_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_mac_command",
            "description": "Ejecuta un comando bash en la terminal de la Mac. Usalo para ver archivos, instalar cosas o consultar el sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "El comando bash a ejecutar (ej: 'ls -la', 'pwd', 'cat archivo.txt')"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_local_file",
            "description": "Lee el contenido de un archivo de texto en la Mac dada su ruta absoluta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Ruta absoluta del archivo (ej: '/Users/joaquin/texto.txt')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_internet",
            "description": "Busca información en internet para responder preguntas actuales o investigar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La consulta de búsqueda (ej: 'historia de la literatura argentina')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_url_content",
            "description": "Descarga y lee el texto completo de una página web específica si el usuario te proporciona un link (URL).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "La URL exacta a leer (ej: 'https://es.wikipedia.org/wiki/Literatura')"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_obsidian_note",
            "description": "Lee el contenido completo de una nota específica de Obsidian si necesitas más contexto sobre ella.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_name": {
                        "type": "string",
                        "description": "Nombre de la nota a buscar (ej: 'Física 1', 'Maimará')"
                    }
                },
                "required": ["note_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_exercise",
            "description": "Genera un archivo Markdown de Reto/Ejercicio directamente en el Vault de Obsidian del usuario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "El tema principal del reto (ej: 'Derivadas', 'Salud Pública')"
                    },
                    "content": {
                        "type": "string",
                        "description": "El contenido del ejercicio en formato Markdown con preguntas, espacios para responder, etc."
                    }
                },
                "required": ["topic", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_vault_note",
            "description": "Crea una nueva nota de Obsidian (.md) con el contenido y título que especifiques. Usalo para organizar entregas, resúmenes o consignas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Título de la nota (ej: 'Resumen Química', 'Entrega Preforo 2')"
                    },
                    "content": {
                        "type": "string",
                        "description": "El contenido completo de la nota en formato Markdown."
                    },
                    "folder": {
                        "type": "string",
                        "description": "Carpeta opcional dentro del vault (ej: 'Entregas', 'Lenguaje/TPs')"
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_vault_note",
            "description": "Modifica el contenido de una nota que ya existe. Úsalo para corregir, ampliar o refinar textos creados anteriormente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Título exacto de la nota a modificar."
                    },
                    "content": {
                        "type": "string",
                        "description": "El nuevo contenido o el fragmento a añadir."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "append"],
                        "description": "'replace' para sobrescribir todo, 'append' para añadir al final."
                    },
                    "folder": {
                        "type": "string",
                        "description": "Carpeta opcional donde se encuentra la nota."
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_vault_notes",
            "description": "Obtiene una lista de todos los títulos de notas en el vault. Úsalo para saber a qué notas puedes hacer referencia mediante [[vínculos]].",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

def execute_tool(tool_call) -> str:
    """Ejecuta una tool_call de Ollama y devuelve el resultado como string."""
    name = tool_call.get("function", {}).get("name")
    args = tool_call.get("function", {}).get("arguments", {})
    
    if name == "execute_mac_command":
        return execute_mac_command(args.get("command", ""))
    elif name == "read_local_file":
        return read_local_file(args.get("path", ""))
    elif name == "search_internet":
        return search_internet(args.get("query", ""))
    elif name == "read_url_content":
        return read_url_content(args.get("url", ""))
    elif name == "read_obsidian_note":
        return read_obsidian_note(args.get("note_name", ""))
    elif name == "create_exercise":
        return create_exercise(args.get("topic", ""), args.get("content", ""))
    elif name == "create_vault_note":
        return create_vault_note(args.get("title", ""), args.get("content", ""), args.get("folder", ""))
    elif name == "edit_vault_note":
        return edit_vault_note(args.get("title", ""), args.get("content", ""), args.get("mode", "replace"), args.get("folder", ""))
    elif name == "list_vault_notes":
        return list_vault_notes()
    else:
        return f"Error: Herramienta '{name}' desconocida."
