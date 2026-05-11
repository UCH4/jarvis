from rank_bm25 import BM25Okapi
from core.db import get_collection
from core.logger import log
import time

# Índice BM25 por vault: { vault_path -> {index, corpus, metadatas} }
_bm25_cache: dict = {}


def invalidate_bm25_index(vault_path: str = None):
    """Fuerza reconstrucción del índice BM25 para el vault dado (o todos si no se especifica)."""
    global _bm25_cache
    if vault_path:
        _bm25_cache.pop(vault_path, None)
    else:
        _bm25_cache.clear()



def build_bm25_index(vault_path: str, force: bool = False):
    global _bm25_cache

    if vault_path in _bm25_cache and not force:
        return

    log("Construyendo índice BM25 para Búsqueda Híbrida...", "info")
    t0 = time.time()

    collection = get_collection(vault_path=vault_path)
    data = collection.get()

    docs = data.get("documents", [])
    if not docs:
        log("BM25: No hay documentos en la base de datos.", "warn")
        return

    metadatas = data.get("metadatas", [])
    tokenized_corpus = [doc.lower().split() for doc in docs]
    index = BM25Okapi(tokenized_corpus)

    _bm25_cache[vault_path] = {
        "index":     index,
        "corpus":    docs,
        "metadatas": metadatas,
    }

    t1 = time.time()
    log(f"✅ Índice BM25 listo: {len(docs)} fragmentos indexados en {t1-t0:.2f}s", "info")


def get_bm25_top_k(query: str, vault_path: str, top_k: int = 15):
    global _bm25_cache

    if vault_path not in _bm25_cache:
        build_bm25_index(vault_path)
        if vault_path not in _bm25_cache:
            return []

    entry = _bm25_cache[vault_path]
    bm25_index = entry["index"]
    bm25_corpus = entry["corpus"]
    bm25_metadatas = entry["metadatas"]

    tokenized_query = query.lower().split()
    scores = bm25_index.get_scores(tokenized_query)

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            continue
        results.append({
            "snippet": bm25_corpus[idx],
            "metadata": bm25_metadatas[idx] if idx < len(bm25_metadatas) else {},
            "bm25_score": scores[idx]
        })

    return results

def reciprocal_rank_fusion(semantic_results, bm25_results, k=60, alpha=0.5):
    """
    Combina resultados semánticos (Chroma) y léxicos (BM25) usando RRF con pesos.
    alpha: peso para resultados semánticos (0.0 a 1.0). 1-alpha es para BM25.
    """
    rrf_scores = {}
    combined_docs = {}
    
    # Peso para cada canal
    w_semantic = alpha
    w_bm25 = 1.0 - alpha
    
    # Procesar resultados semánticos
    for rank, res in enumerate(semantic_results):
        snippet = res["snippet"]
        if snippet not in rrf_scores:
            rrf_scores[snippet] = 0
            combined_docs[snippet] = res
        rrf_scores[snippet] += w_semantic * (1.0 / (k + rank + 1))
        
    # Procesar resultados BM25
    for rank, res in enumerate(bm25_results):
        snippet = res["snippet"]
        if snippet not in rrf_scores:
            rrf_scores[snippet] = 0
            # Adaptamos el formato
            combined_docs[snippet] = {
                "path": res["metadata"].get("path", ""),
                "title": res["metadata"].get("title", "Documento"),
                "snippet": snippet,
                "score": 0.5
            }
        rrf_scores[snippet] += w_bm25 * (1.0 / (k + rank + 1))
        
    # Ordenar por RRF score
    sorted_snippets = sorted(rrf_scores.keys(), key=lambda s: rrf_scores[s], reverse=True)
    
    final_results = []
    for snippet in sorted_snippets:
        doc = combined_docs[snippet]
        doc["rrf_score"] = rrf_scores[snippet]
        final_results.append(doc)
        
    return final_results
