from pathlib import Path
from core.db import get_collection

def buscar_en_vault(query: str, vault_path: str, top_k: int = 5) -> list:
    """
    Busca los fragmentos más relevantes usando RAG Avanzado (HyDE + Multi-Query condicionales).
    """
    from core.ollama import expand_query, generate_hyde_doc
    from core.query_intent import classify_query_intent
    from core.logger import log
    
    try:
        # 0. Truncamiento de seguridad para la query inicial (evitar colapsar embeddings)
        query = query[:4000]
        
        collection = get_collection()
        
        intent = classify_query_intent(query)
        use_expansion = intent == "CONCEPT" and len(query.split()) > 3
        
        # 1. Expansión de Consultas (Multi-Query) — solo consultas conceptuales sustanciales
        queries = expand_query(query) if use_expansion else [query]
        
        # 2. HyDE — solo conceptual (evita latencia en preguntas factuales)
        if use_expansion:
            hyde_doc = generate_hyde_doc(query)
            queries.append(hyde_doc)
            log(f"RAG+ (CONCEPT: Multi-Query + HyDE) para: '{query[:40]}...'", "info")
        elif intent == "FACT":
            log(f"RAG modo FACT (sin HyDE/multi-query extra): '{query[:40]}...'", "info")

        # 3. Recuperación Multi-Hilo (Simulada con loop pero con deduplicación)
        all_results = []
        seen_snippets = set()
        
        for q in queries:
            try:
                # 3A. Recuperación Semántica (ChromaDB)
                results = collection.query(query_texts=[q], n_results=15)
                if results['documents'] and results['documents'][0]:
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
            except Exception as e:
                log(f"Aviso: Fallo en consulta RAG para variación: {e}", "warn")

        # 3A.2. Inyección de Texto Fundacional ("La Biblia")
        try:
            biblia_results = collection.query(
                query_texts=[query],
                n_results=2,
                where_document={"$contains": "#biblia"}
            )
            if biblia_results['documents'] and biblia_results['documents'][0]:
                for i in range(len(biblia_results['documents'][0])):
                    snippet = biblia_results['documents'][0][i]
                    if snippet in seen_snippets: continue
                    metadata = biblia_results['metadatas'][0][i]
                    
                    # Forzamos un score artificialmente alto para que la Biblia pase el reranking
                    all_results.append({
                        "path": metadata.get("path", ""),
                        "title": metadata.get("title", "Documento") + " [★ TEXTO FUNDACIONAL]",
                        "snippet": "ATENCIÓN: EL SIGUIENTE TEXTO ES UNA REGLA/METODOLOGÍA FUNDAMENTAL (#biblia) QUE DEBES APLICAR A TU RESPUESTA:\n\n" + snippet,
                        "score": 1.5 
                    })
                    seen_snippets.add(snippet)
                    log(f"Inyectado texto fundacional (#biblia) desde: {metadata.get('title', '')}", "ok")
        except Exception as e:
            log(f"Aviso: Fallo al buscar textos fundacionales (#biblia): {e}", "warn")

        # 3B. Recuperación Léxica (BM25)
        try:
            from core.hybrid_search import get_bm25_top_k, reciprocal_rank_fusion
            bm25_res = get_bm25_top_k(query, top_k=15)
            
            if bm25_res:
                # Fusión RRF optimizada para bóvedas académicas (Alpha 0.45 favorece BM25)
                all_results = reciprocal_rank_fusion(all_results, bm25_res, alpha=0.45)
                log(f"Búsqueda Híbrida completada: {len(all_results)} candidatos fusionados.", "info")
        except Exception as e:
            log(f"Error en BM25 (cayendo a búsqueda puramente semántica): {e}", "warn")

        
        # 4. Re-ranking inteligente (Funnel RAG)
        if all_results:
            from core.reranker import rerank
            
            # Ordenar por el score híbrido inicial (Vector + BM25 + Biblia)
            all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            # Tomamos solo los mejores 15 candidatos para no saturar al LLM (Optimización M4 Pro)
            funnel_candidates = all_results[:15]
            
            log(f"Reranking {len(funnel_candidates)} fragmentos de los {len(all_results)} totales...", "info")
            return rerank(query, funnel_candidates, top_k=top_k)
        
        return []

    except Exception as e:
        from core.logger import log
        log(f"Error consultando ChromaDB (RAG+): {e}", "error")
        return []
