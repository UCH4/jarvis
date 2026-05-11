from typing import List, Dict

from core.config import get_rerank_backend, CROSS_ENCODER_MODEL


_cross_encoder = None


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
    return _cross_encoder


def _rerank_cross_encoder(query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
    ce = _get_cross_encoder()
    pairs = [[query, (c.get("snippet") or "")[:512]] for c in candidates]
    scores = ce.predict(pairs)
    for i, cand in enumerate(candidates):
        cand["rerank_score"] = float(scores[i]) if i < len(scores) else 0.0
    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    for c in candidates[:top_k]:
        c.pop("rerank_score", None)
    return candidates[:top_k]


def rerank(query: str, candidates: List[Dict], model: str = None, top_k: int = 3) -> List[Dict]:
    """Rerank candidatos: cross-encoder (default) o listwise MLX según config."""
    if not candidates:
        return []

    from core.logger import log
    backend = get_rerank_backend()

    if backend == "cross_encoder":
        try:
            return _rerank_cross_encoder(query, candidates, top_k)
        except Exception as e:
            log(f"Cross-encoder rerank falló ({e}), usando listwise MLX.", "warn")

    from agents.rerank_agent import RerankAgent
    agent = RerankAgent()

    try:
        scores = agent.rank_candidates(query, candidates)
        for i, cand in enumerate(candidates):
            cand["rerank_score"] = scores[i] if i < len(scores) else 0
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        for c in candidates[:top_k]:
            c.pop("rerank_score", None)
        return candidates[:top_k]
    except Exception as e:
        log(f"Fallo en reranking listwise, devolviendo top_k original: {e}", "warn")
        return candidates[:top_k]
