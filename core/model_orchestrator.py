"""
core/model_orchestrator.py — Selección centralizada de modelos IA por subtarea.

Resuelve subtareas a configuraciones específicas (modelo, provider, etc.)
y verifica la salud/disponibilidad de cada una.
"""
import os
import requests
from enum import Enum
from core.logger import log

class Task(str, Enum):
    PDF_METADATA    = "pdf_metadata"      # analyze_content (JSON)
    CHAT            = "chat"              # respuesta principal con RAG
    CHAT_CONCISE    = "chat_concise"      # modo quick / resúmenes
    REASONING       = "reasoning"         # razonamiento profundo
    VISION          = "vision"            # OCR PDF / manuscritos
    HYDE            = "hyde"              # texto auxiliar HyDE
    MULTI_QUERY     = "multi_query"       # expansión de consultas
    INTENT_CLASSIFY = "intent_classify"   # clasificación FACT vs CONCEPT
    PROFESSOR       = "professor"         # tutor socrático / ejercicios
    FLASHCARDS      = "flashcards"        # generación de flashcards
    EMBED           = "embed"             # embeddings de Chroma
    RERANK          = "rerank"            # reranker
    
def resolve(task: Task, user_override: str = None) -> dict:
    """
    Resuelve el modelo, proveedor, temperatura y max_tokens para una subtarea.
    
    Prioridad:
    1. user_override (si se pasa explícitamente en el llamado)
    2. state.json (si el usuario configuró un override global o por subtarea)
    3. MODEL_REGISTRY default (de config.py)
    """
    from core.config import MODEL_REGISTRY, OLLAMA_URL
    from core.state import load_state
    
    # 1. Obtener la base por defecto del registry
    if task not in MODEL_REGISTRY:
        # Fallback de seguridad extrema
        spec = {
            "model": "qwen2.5:14b",
            "provider": "ollama",
            "temperature": 0.7,
            "max_tokens": 2048,
            "fallback": None
        }
    else:
        spec = MODEL_REGISTRY[task].copy()
        
    # 2. Cargar state para buscar overrides del usuario
    state = load_state()
    user_config = state.get("config", {})
    task_overrides = state.get("task_overrides", {})
    
    # Si hay un override explícito por subtarea en state.json
    if task in task_overrides:
        override = task_overrides[task]
        if isinstance(override, dict):
            if "model" in override: spec["model"] = override["model"]
            if "provider" in override: spec["provider"] = override["provider"]
            if "temperature" in override: spec["temperature"] = float(override["temperature"])
            if "max_tokens" in override: spec["max_tokens"] = int(override["max_tokens"])

    # Overrides retrocompatibles o de configuración global en state/UI:
    if task == Task.CHAT:
        # Si config tiene chat_model (el del selector de arriba en dashboard)
        chat_model_override = user_config.get("chat_model")
        if chat_model_override:
            spec["model"] = chat_model_override
            
    if task == Task.PDF_METADATA:
        # Si config tiene analysis_model (del selector de abajo en dashboard)
        analysis_model_override = user_config.get("analysis_model")
        if analysis_model_override:
            spec["model"] = analysis_model_override

    # 3. Si se pasa un override en tiempo de ejecución (ej: el dropdown del chat)
    if user_override:
        spec["model"] = user_override
        # Si el override contiene barra / o nombre de comunidad MLX, inferir provider
        if "/" in user_override or "mlx" in user_override.lower():
            spec["provider"] = "mlx"
        else:
            spec["provider"] = "ollama"

    # 4. Verificar disponibilidad y aplicar fallbacks si es necesario
    provider = spec.get("provider", "ollama")
    model = spec.get("model")
    
    if provider == "ollama":
        from core.ollama import get_available_models
        available = get_available_models()
        # Limpieza rápida del tag ":latest" si hace falta
        available_clean = [m.split(":")[0] for m in available]
        model_clean = model.split(":")[0]
        
        if model not in available and model_clean not in available_clean:
            if spec.get("fallback"):
                log(f"⚠️ Modelo principal '{model}' no está en Ollama. Usando fallback '{spec['fallback']}' para la tarea '{task}'.", "warn")
                spec["model"] = spec["fallback"]
                # El fallback generalmente es Ollama
                spec["provider"] = "ollama"
            else:
                log(f"❌ Modelo principal '{model}' de la tarea '{task}' no está en Ollama y no hay fallback. Podría fallar.", "error")
                
    elif provider == "mlx":
        try:
            import mlx_lm
        except ImportError:
            log(f"⚠️ MLX no está instalado (mlx-lm). Usando fallback para '{task}'.", "warn")
            if spec.get("fallback"):
                spec["model"] = spec["fallback"]
                spec["provider"] = "ollama"
            else:
                # Fallback al modelo de análisis por defecto de Ollama
                from core.config import ANALYSIS_MODEL
                spec["model"] = ANALYSIS_MODEL
                spec["provider"] = "ollama"
                
    # 5. Log de selección de cerebro
    log(f"🧠 Orchestrator: task='{task}' -> model='{spec['model']}' ({spec['provider']})", "info")
    
    return spec

def get_health() -> dict:
    """
    Retorna el estado de salud y disponibilidad de todas las subtareas.
    Formato: {task_name: {status: "ok"|"fallback"|"missing", model, provider, note}}
    """
    from core.config import MODEL_REGISTRY
    from core.ollama import get_available_models
    
    health = {}
    ollama_models = get_available_models()
    ollama_models_clean = [m.split(":")[0] for m in ollama_models]
    
    # Verificar instalación de librerías MLX
    try:
        import mlx_lm
        mlx_lm_ok = True
    except ImportError:
        mlx_lm_ok = False
        
    try:
        import mlx_vlm
        mlx_vlm_ok = True
    except ImportError:
        mlx_vlm_ok = False
        
    try:
        import sentence_transformers
        sentence_transformers_ok = True
    except ImportError:
        sentence_transformers_ok = False

    for t in Task:
        task_name = t.value
        # Resolvemos el spec actual (teniendo en cuenta overrides)
        try:
            spec = resolve(t)
            provider = spec.get("provider")
            model = spec.get("model")
            status = "ok"
            note = ""
            
            if provider == "ollama":
                model_clean = model.split(":")[0]
                if model not in ollama_models and model_clean not in ollama_models_clean:
                    status = "missing"
                    note = f"Modelo '{model}' no está descargado en Ollama. Ejecutá 'ollama pull {model}'."
                    
            elif provider == "mlx":
                if not mlx_lm_ok:
                    status = "missing"
                    note = "mlx-lm no está instalado. Ejecutá 'pip install mlx-lm'."
                else:
                    # MLX descarga bajo demanda, asumimos que si la librería está ok, eventualmente andará.
                    # Pero avisamos que se descargará al primer uso.
                    note = "Librería MLX disponible. El modelo se descargará al primer uso si no está cacheado."
                    
            elif provider == "cross_encoder":
                if not sentence_transformers_ok:
                    status = "missing"
                    note = "sentence-transformers no está instalado. Reeranker no funcionará."
                    
            elif provider == "listwise":
                if not mlx_lm_ok:
                    status = "missing"
                    note = "mlx-lm no está instalado para rerank listwise."
            
            # Si el resolved difiere del registry base original, es porque se usó fallback o state override
            original_spec = MODEL_REGISTRY.get(t)
            if original_spec and status == "ok":
                original_model = original_spec.get("model")
                original_provider = original_spec.get("provider")
                if model != original_model or provider != original_provider:
                    # Si no es un override explícito del state
                    from core.state import load_state
                    state = load_state()
                    task_overrides = state.get("task_overrides", {})
                    user_config = state.get("config", {})
                    
                    is_user_override = (
                        t in task_overrides or 
                        (t == Task.CHAT and user_config.get("chat_model") == model) or
                        (t == Task.PDF_METADATA and user_config.get("analysis_model") == model)
                    )
                    
                    if not is_user_override:
                        status = "fallback"
                        note = f"Usando fallback '{model}' porque el original no estaba disponible."
            
            health[task_name] = {
                "status": status,
                "model": model,
                "provider": provider,
                "note": note
            }
        except Exception as e:
            health[task_name] = {
                "status": "missing",
                "model": "desconocido",
                "provider": "desconocido",
                "note": f"Error verificando: {e}"
            }
            
    return health
