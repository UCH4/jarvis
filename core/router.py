"""
core/router.py — Enrutador Dinámico de Inteligencia Artificial.
Detecta la intención del usuario y elige el modelo/parámetros óptimos para el M4 Pro.
"""
import re
from core.config import ANALYSIS_MODEL, ENABLE_HEAVY_REASONING

# Mapeo de intenciones a configuraciones recomendadas
AI_STRATEGIES = {
    "concise": {
        "model": "mlx-community/gemma-2-9b-it-4bit",
        "provider": "mlx",
        "system_prompt": "Sos un asistente de respuesta rápida y ejecutiva. Respondé de forma ultra-concisa, usando bullet points y máximo 100 palabras.",
        "temperature": 0.3
    },
    "reasoning": {
        "model": "mlx-community/DeepSeek-R1-Distill-Qwen-14B-4bit",
        "provider": "mlx",
        "system_prompt": "Sos un experto en razonamiento lógico y académico. Analizá paso a paso, resolviendo dudas complejas con rigor científico.",
        "temperature": 0.5
    },
    "vision": {
        "model": "llama3.2-vision:latest",
        "provider": "ollama",
        "system_prompt": "Sos un experto en transcripción y análisis visual. Describí y transcribí el contenido de la imagen con precisión.",
        "temperature": 0.0
    },
    "general": {
        "model": "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        "provider": "mlx",
        "system_prompt": "Sos JARVIS, un Knowledge Architect académico. Brindá respuestas detalladas y fundamentadas en el Vault.",
        "temperature": 0.7
    }
}

def detect_intention(query: str) -> str:
    """Analiza la query para determinar la mejor estrategia de IA."""
    q = query.lower()
    
    # Intención: Visión (si menciona imágenes o fórmulas complejas)
    if any(k in q for k in ["mira", "imagen", "foto", "ocr", "fórmula", "grafico", "pdf", "dibujo"]):
        return "vision"
    
    # Intención: Razonamiento profundo
    if any(k in q for k in ["analiza", "razona", "por qué", "lógica", "paso a paso", "deduci", "demostra", "explica"]):
        return "reasoning"
    
    # Intención: Mini Respuestas / Conciso
    if any(k in q for k in ["mini", "resumen", "corto", "breve", "puntos", "flash", "resumi", "conclui", "en pocas palabras"]):
        return "concise"
    
    return "general"

def get_dynamic_model_config(query: str, manual_mode: str = None, user_override: str = None) -> dict:
    """Retorna la configuración completa según la intención detectada y el orchestrator."""
    from core.model_orchestrator import resolve, Task
    
    intention = detect_intention(query)
    
    # 1. Mapear manual_mode o intención a Task
    if manual_mode == "quick":
        task = Task.CHAT_CONCISE
        system_prompt = "Sos un asistente de respuesta rápida y ejecutiva. Respondé de forma ultra-concisa, usando bullet points y máximo 100 palabras."
    elif manual_mode == "professor":
        task = Task.PROFESSOR
        from agents.professor import SOCRATIC_SYSTEM_PROMPT
        system_prompt = SOCRATIC_SYSTEM_PROMPT
    elif manual_mode == "deep_context":
        task = Task.CHAT
        system_prompt = "Sos JARVIS, un Knowledge Architect académico. Brindá respuestas detalladas y fundamentadas en el Vault."
    else:
        # Si no hay manual_mode, o es normal, decidimos por intención detectada
        if intention == "vision":
            task = Task.VISION
            system_prompt = "Sos un experto en transcripción y análisis visual. Describí y transcribí el contenido de la imagen con precisión."
        elif intention == "reasoning":
            task = Task.REASONING
            system_prompt = "Sos un experto en razonamiento lógico y académico. Analizá paso a paso, resolviendo dudas complejas con rigor científico."
        elif intention == "concise":
            task = Task.CHAT_CONCISE
            system_prompt = "Sos un asistente de respuesta rápida y ejecutiva. Respondé de forma ultra-concisa, usando bullet points y máximo 100 palabras."
        else:
            task = Task.CHAT
            system_prompt = "Sos JARVIS, un Knowledge Architect académico. Brindá respuestas detalladas y fundamentadas en el Vault."

    # 2. Resolver con el orchestrator
    spec = resolve(task, user_override=user_override)
    
    # Ajustes finos basados en intención/modo
    if manual_mode == "deep_context":
        spec["temperature"] = 0.3 # Bajar temperatura para precisión/contexto profundo

    spec["system_prompt"] = system_prompt
    spec["intent"] = intention
    
    return spec
