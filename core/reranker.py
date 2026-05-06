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
    
    from agents.rerank_agent import RerankAgent
    agent = RerankAgent()
    
    try:
        # Una sola pasada de inferencia para todos los candidatos
        scores = agent.rank_candidates(query, candidates)
        
        # Asignar los scores y ordenar
        for i, cand in enumerate(candidates):
            cand["rerank_score"] = scores[i] if i < len(scores) else 0
            
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        # Limpiar y devolver top_k
        for c in candidates[:top_k]:
            c.pop("rerank_score", None)
            
        return candidates[:top_k]
        
    except Exception as e:
        from core.logger import log
        log(f"Fallo en reranking listwise, devolviendo top_k original: {e}", "warn")
        return candidates[:top_k]
