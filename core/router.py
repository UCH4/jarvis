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

def get_dynamic_model_config(query: str, manual_mode: str = None) -> dict:
    """Retorna la configuración completa según la intención detectada y modelos instalados."""
    from core.ollama import get_available_models
    available = get_available_models()
    
    intention = detect_intention(query)
    
    # Lógica de "Mejor de su clase" (PVP Automático)
    if intention == "vision":
        # Priorizar llama3.2-vision si está disponible
        if any("vision" in m for m in available):
            return AI_STRATEGIES["vision"]
            
    if intention == "reasoning":
        # Priorizar DeepSeek-R1 solo si está explícitamente habilitado (consume mucha memoria)
        if ENABLE_HEAVY_REASONING and any("deepseek-r1" in m for m in available):
            return AI_STRATEGIES["reasoning"]
        # Modo seguro por defecto: Llama 3.1 8B MLX
        return AI_STRATEGIES["general"]
            
    if intention == "concise":
        # Priorizar Gemma 2 para resúmenes (si ya terminó de descargar)
        if any("gemma2" in m for m in available):
            cfg = AI_STRATEGIES["concise"].copy()
            cfg["model"] = "gemma2:9b"
            cfg["provider"] = "ollama"
            return cfg
    
    # Respetar modo profesor
    if manual_mode == "professor":
        if ENABLE_HEAVY_REASONING and any("deepseek-r1" in m for m in available):
            return AI_STRATEGIES["reasoning"]

    # Fallback por defecto: MLX (Llama 3.1 8B) por velocidad pura en M4
    return AI_STRATEGIES.get(intention, AI_STRATEGIES["general"])
