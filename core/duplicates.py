"""
core/duplicates.py — Detección de documentos duplicados
"""
from core.config  import DUPLICATE_THRESH
from core.ollama  import cosine_similarity


def check_duplicate(embedding: list, file_hash: str, registry: dict, threshold: float = DUPLICATE_THRESH):
    """
    Verifica si el contenido ya existe en el vault.
    1. Hash exacto (duplicado bit a bit)
    2. Similitud semántica por embedding
    Retorna (is_dup, similar_to, similarity)
    """
    if file_hash in registry.get("hashes", {}):
        return True, registry["hashes"][file_hash], 1.0

    if embedding:
        for path, emb in registry.get("embeddings", {}).items():
            sim = cosine_similarity(embedding, emb)
            if sim >= threshold:
                return True, path, sim

    return False, None, 0.0
