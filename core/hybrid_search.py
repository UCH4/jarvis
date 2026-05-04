from rank_bm25 import BM25Okapi
from core.db import get_collection
from core.logger import log
import time

_bm25_index = None
_bm25_corpus = []
_bm25_metadatas = []

def build_bm25_index(force=False):
    global _bm25_index, _bm25_corpus, _bm25_metadatas
    
    if _bm25_index is not None and not force:
        return
        
    log("Construyendo índice BM25 para Búsqueda Híbrida...", "info")
    t0 = time.time()
    
    collection = get_collection()
    data = collection.get() # Obtiene todos los documentos
    
    docs = data.get("documents", [])
    if not docs:
        log("BM25: No hay documentos en la base de datos.", "warn")
        return
        
    _bm25_corpus = docs
    _bm25_metadatas = data.get("metadatas", [])
    
    # Tokenización simple por espacios y paso a minúsculas
    tokenized_corpus = [doc.lower().split() for doc in docs]
    _bm25_index = BM25Okapi(tokenized_corpus)
    
    t1 = time.time()
    log(f"✅ Índice BM25 listo: {len(docs)} fragmentos indexados en {t1-t0:.2f}s", "info")

def get_bm25_top_k(query: str, top_k: int = 15):
    global _bm25_index, _bm25_corpus, _bm25_metadatas
    
    if _bm25_index is None:
        build_bm25_index()
        if _bm25_index is None:
            return []
            
    tokenized_query = query.lower().split()
    scores = _bm25_index.get_scores(tokenized_query)
    
    # Obtener los índices de los top_k
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    
    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            continue
        results.append({
            "snippet": _bm25_corpus[idx],
            "metadata": _bm25_metadatas[idx] if idx < len(_bm25_metadatas) else {},
            "bm25_score": scores[idx]
        })
        
    return results

def reciprocal_rank_fusion(semantic_results, bm25_results, k=60):
    """
    Combina resultados semánticos (Chroma) y léxicos (BM25) usando RRF.
    """
    rrf_scores = {}
    combined_docs = {}
    
    # Procesar resultados semánticos
    for rank, res in enumerate(semantic_results):
        snippet = res["snippet"]
        if snippet not in rrf_scores:
            rrf_scores[snippet] = 0
            combined_docs[snippet] = res
        rrf_scores[snippet] += 1.0 / (k + rank + 1)
        
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
                "score": 0.5 # Default score for sorting later if needed
            }
        rrf_scores[snippet] += 1.0 / (k + rank + 1)
        
    # Ordenar por RRF score
    sorted_snippets = sorted(rrf_scores.keys(), key=lambda s: rrf_scores[s], reverse=True)
    
    final_results = []
    for snippet in sorted_snippets:
        doc = combined_docs[snippet]
        doc["rrf_score"] = rrf_scores[snippet]
        final_results.append(doc)
        
    return final_results
