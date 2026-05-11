"""
core/professor.py — Motor de enseñanza Socrática y generación de ejercicios
"""
import json
import re
import requests
from core.config import OLLAMA_URL, ANALYSIS_MODEL

SOCRATIC_SYSTEM_PROMPT = """Actúa como un Tutor Socrático. Tu base de conocimientos son las notas de Obsidian provistas. 
Nunca des la respuesta final de inmediato. Si el usuario pregunta algo, revisa sus notas, identifica qué concepto básico le falta 
y genera un ejercicio práctico de 2 minutos para validar que lo entiende antes de avanzar. 
Tu tono debe ser inspirador, paciente y académico."""

def generate_exercise(topic: str, context: str, difficulty: str = "Intermedio") -> dict:
    """Genera un ejercicio basado en el contexto de las notas."""
    prompt = f"""Basado en el siguiente contexto de apuntes, genera un ejercicio de aprendizaje:
    
CONTEXTO:
\"\"\"
{context[:4000]}
\"\"\"

TEMA: {topic}
DIFICULTAD: {difficulty}

FORMATO JSON:
{{
  "enunciado": "Descripción clara del problema o pregunta",
  "pista": "Una pista socrática para ayudar sin resolver",
  "solucion_oculta": "La respuesta correcta o resolución detallada",
  "tipo": "Teórico | Práctico | Análisis"
}}"""

    if not (context or "").strip():
        context = (
            "No se recuperó contexto del vault en esta consulta. "
            "Genera un ejercicio general, corto y útil sobre el tema pedido."
        )

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": ANALYSIS_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.7}
            },
            timeout=120
        )
        data = json.loads(r.json().get("response", "{}"))
        if not isinstance(data, dict):
            raise ValueError("Formato inválido de ejercicio")
        # Normalización para evitar que el frontend falle por claves faltantes
        return {
            "enunciado": data.get("enunciado") or f"Explica los fundamentos de: {topic}",
            "pista": data.get("pista") or "Separá el tema en 3 ideas clave y da un ejemplo práctico.",
            "solucion_oculta": data.get("solucion_oculta") or "Respuesta modelo no disponible.",
            "tipo": data.get("tipo") or "Teórico",
        }
    except Exception:
        # Fallback local robusto
        return {
            "enunciado": f"Desarrollá un mini-resumen de '{topic}' en 5 líneas e incluye 2 ejemplos.",
            "pista": "Pensá en definición, utilidad y ejemplo real de laboratorio/clase.",
            "solucion_oculta": "Una buena respuesta incluye definición formal, contexto de uso y ejemplos claros.",
            "tipo": "Teórico",
        }

def generate_flashcards(context: str, count: int = 5) -> list:
    """Genera flashcards (tarjetas de estudio) basadas en el contexto."""
    prompt = f"""Genera {count} flashcards de estudio basadas en estos apuntes:
    
{context[:4000]}

FORMATO JSON (Lista de objetos):
[
  {{ "pregunta": "...", "respuesta": "..." }},
  ...
]"""

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": ANALYSIS_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.6}
            },
            timeout=60
        )
        return json.loads(r.json().get("response", "[]"))
    except Exception:
        return []
