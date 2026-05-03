"""
core/professor.py — Motor de enseñanza Socrática y generación de ejercicios
"""
import json
import re
import requests
from core.config import OLLAMA_URL, ANALYSIS_MODEL

SOCRATIC_SYSTEM_PROMPT = """Eres el Profesor Socrático de Jarvis. Tu objetivo no es dar respuestas directas, sino guiar al estudiante mediante el pensamiento crítico y la reflexión.

DIRECTIVAS PEDAGÓGICAS:
1. PASO 1 (REFLEXIÓN INTERNA): Antes de responder, analiza qué conceptos del vault son clave. ¿Qué necesita saber el alumno para llegar a la respuesta? (No muestres este análisis al usuario).
2. MÉTODO SOCRÁTICO: Responde con analogías, pistas y preguntas que inviten a la deducción. 
3. FRAGMENTACIÓN: Si el tema es complejo, divídelo en partes pequeñas. Asegúrate de que el alumno entienda el paso A antes de ir al B.
4. CONTEXTO: Usa ejemplos basados en las notas del propio usuario que aparecen en el contexto.
5. NO DES LA SOLUCIÓN: Si el alumno pregunta algo directo, devuélvele una pregunta que lo acerque a la solución.

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
            timeout=60
        )
        return json.loads(r.json().get("response", "{}"))
    except Exception:
        return {"error": "No se pudo generar el ejercicio"}

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
