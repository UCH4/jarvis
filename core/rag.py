from pathlib import Path
from core.db import get_collection

def buscar_en_vault(query: str, vault_path: str, top_k: int = 5) -> list:
    """
    Busca los fragmentos más relevantes usando RAG Avanzado (HyDE + Multi-Query).
    """
    from core.ollama import expand_query, generate_hyde_doc
    from core.logger import log
    
    try:
        collection = get_collection()
        
        # 1. Expansión de Consultas (Multi-Query) - Solo si la pregunta es sustancial
        is_complex = len(query.split()) > 3
        queries = expand_query(query) if is_complex else [query]
        
        # 2. HyDE (Solo para preguntas complejas)
        if is_complex:
            hyde_doc = generate_hyde_doc(query)
            queries.append(hyde_doc)
            log(f"RAG+ activado (Multi-Query + HyDE) para: '{query[:30]}...'", "info")

        # 3. Recuperación Multi-Hilo (Simulada con loop pero con deduplicación)
        all_results = []
        seen_snippets = set()
        
        for q in queries:
            # Pedimos más resultados de los necesarios para que el reranker tenga material
            results = collection.query(query_texts=[q], n_results=max(10, top_k * 2))
            if not results['documents'] or not results['documents'][0]:
                continue
                
            for i in range(len(results['documents'][0])):
                snippet  = results['documents'][0][i]
                if snippet in seen_snippets: continue
                
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i] if 'distances' in results and results['distances'] else 0
                score    = round(1.0 / (1.0 + distance), 3)

                all_results.append({
                    "path": metadata.get("path", ""),
                    "title": metadata.get("title", "Documento"),
                    "snippet": snippet,
                    "score": score
                })
                seen_snippets.add(snippet)
        
        # 4. Re-ranking (LLM-as-a-judge)
        if all_results:
            from core.reranker import rerank
            log(f"Reranking {len(all_results)} fragmentos...", "info")
            return rerank(query, all_results, top_k=top_k)
        
        return []

    except Exception as e:
        from core.logger import log
        log(f"Error consultando ChromaDB (RAG+): {e}", "error")
        return []
