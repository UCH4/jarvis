"""
agents/rerank_agent.py — Agente especializado en evaluación de relevancia por lotes (Listwise).
Optimizado para reducir latencia en M4 Pro pasando de N inferencias a 1 sola.
"""
import json
import re
from typing import List, Dict
from core.mlx_inference import generate_text

class RerankAgent:
    def __init__(self, model_name: str = None):
        self.model_name = model_name

    def rank_candidates(self, query: str, candidates: List[Dict]) -> List[float]:
        """
        Recibe una lista de candidatos y devuelve una lista de scores (0-10) 
        generada en una sola pasada de inferencia.
        """
        if not candidates:
            return []

        # Construir el bloque de candidatos para el prompt
        candidates_text = ""
        for i, cand in enumerate(candidates):
            title = cand.get("title", "Sin título")
            snippet = cand.get("snippet", "")[:400] # Limitar para no saturar ventana
            candidates_text += f"ID {i} | TITULO: {title} | FRAGMENTO: {snippet}\n---\n"

        prompt = f"""### SISTEMA: Sos el Agente de Relevancia de JARVIS.
Tu tarea es evaluar qué fragmentos de texto son más útiles para responder la consulta del usuario.

### CONSULTA: {query}

### LISTA DE CANDIDATOS:
{candidates_text}

### INSTRUCCIÓN:
Asigna un puntaje de 0 a 10 a cada fragmento según su relevancia exacta para la consulta.
Responde ÚNICAMENTE con un objeto JSON plano donde la llave es el ID y el valor es el puntaje.

EJEMPLO DE SALIDA:
{{ "0": 9.5, "1": 2.0, "2": 8.0 }}

### RESPUESTA (JSON):"""

        try:
            # Una sola inferencia para evaluar hasta 15 candidatos
            response = generate_text(prompt, max_tokens=150, temperature=0.0)
            
            # Limpiar posibles bloques de código markdown
            clean_response = re.sub(r"```json\s*", "", response)
            clean_response = re.sub(r"```\s*", "", clean_response)
            
            # Buscar el objeto JSON en la respuesta
            match = re.search(r"\{.*\}", clean_response, re.DOTALL)
            if match:
                scores_dict = json.loads(match.group())
                # Convertir el dict de strings/ints a una lista de floats alineada con candidates
                final_scores = []
                for i in range(len(candidates)):
                    score = float(scores_dict.get(str(i), 0))
                    final_scores.append(score)
                return final_scores
        except Exception as e:
            from core.logger import log
            log(f"Error en RerankAgent (Listwise): {e}", "warn")
            
        # Fallback: score neutro si falla la IA
        return [1.0] * len(candidates)
