import json
import re
from typing import List, Dict

from core.config import ANALYSIS_MODEL, OLLAMA_URL


def rerank(query: str, candidates: List[Dict], model: str = None, top_k: int = 3) -> List[Dict]:
    """Rerank a list of candidate documents using an LLM as a judge.

    Parameters
    ----------
    query: str
        The original user query.
    candidates: List[Dict]
        Each candidate dict should contain at least ``title``, ``path`` and ``snippet`` keys.
    model: str, optional
        The Ollama model to use for scoring. Defaults to the analysis model.
    top_k: int, optional
        Number of top results to return after reranking.
    """
    if not candidates:
        return []
    model = model or ANALYSIS_MODEL
    scored = []
    for cand in candidates:
        snippet = cand.get("snippet", "")
        title = cand.get("title", "")
        path = cand.get("path", "")
        prompt = (
            f"### SISTEMA: Sos un Evaluador de Relevancia Crítico.\n"
            f"### CONSULTA DEL USUARIO: {query}\n"
            f"### DOCUMENTO: {title} ({path})\n"
            f"### FRAGMENTO: {snippet}\n\n"
            "INSTRUCCIÓN: Evalúa si este fragmento contiene información específica, hechos o datos para responder a la consulta."
            "\n0: Irrelevante / Ruido / Sin datos."
            "\n5: Relacionado pero vago o incompleto."
            "\n10: Contiene la respuesta exacta o datos clave."
            "\nResponde SOLO con el número (0-10)."
        )
        try:
            import requests
            r = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 5},
                },
                timeout=30,
            )
            resp = r.json().get("response", "").strip()
            # Extract first integer found
            match = re.search(r"(\d+)", resp)
            score = int(match.group(1)) if match else 0
        except Exception:
            score = 0
        cand_copy = cand.copy()
        cand_copy["rerank_score"] = score
        scored.append(cand_copy)
    # Sort by rerank_score descending
    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    # Return top_k without the auxiliary field
    for c in scored[:top_k]:
        c.pop("rerank_score", None)
    return scored[:top_k]
