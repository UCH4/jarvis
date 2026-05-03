"""
core/scanner.py — Pipeline de procesamiento de PDFs y escaneo en lote
"""
from datetime import datetime
from pathlib  import Path

from core.config     import ANALYSIS_MODEL
from core.state      import scan_state, state_lock, save_state
from core.logger     import log
from core.pdf        import extract_pdf_text, compute_file_hash
from core.ollama     import get_embedding, analyze_content
from core.obsidian   import build_obsidian_note, get_vault_folder, safe_filename, get_existing_topics_from_vault
from core.duplicates import check_duplicate
from core.db         import get_collection





def process_single_pdf(pdf_path: str, vault_path: str, registry: dict,
                        existing_topics: list, model: str = None) -> dict:
    """
    Pipeline completo para un PDF:
    extracción → hash → embedding → duplicado → análisis → nota → guardado
    """
    p = Path(pdf_path)
    log(f"Procesando: {p.name}", "action")

    # Saltar metadatos de macOS
    if p.name.startswith("._"):
        log(f"Saltando archivo de metadatos macOS: {p.name}", "warn")
        return {"file": p.name, "status": "skip", "reason": "metadata_macos"}

    # 1. Extraer texto completo
    full_text = extract_pdf_text(pdf_path)
    if len(full_text.strip()) < 20:
        log(f"Muy poco texto en {p.name} (¿PDF escaneado sin capa de texto?)", "warn")
        return {"file": p.name, "status": "skip", "reason": "poco_texto"}

    text_for_analysis = full_text[:8000]

    # 2. Hash del archivo
    file_hash = compute_file_hash(pdf_path)

    # 3. Embedding semántico
    log("Calculando embedding...", "info")
    embedding = get_embedding(text_for_analysis)

    # 4. Chequear duplicados
    is_dup, dup_path, similarity = check_duplicate(embedding, file_hash, registry)
    if is_dup:
        log(f"DUPLICADO ({similarity:.0%} similar) — omitiendo {p.name}", "warn")
        return {"file": p.name, "status": "duplicate", "similar_to": str(dup_path), "similarity": round(similarity, 3)}

    # 5. Analizar con Ollama
    log("Analizando contenido con Ollama...", "info")
    analysis = analyze_content(text_for_analysis, existing_topics, model)
    log(f"Clasificado: {analysis.get('categoria')} › {analysis.get('materia')} › {analysis.get('titulo')}", "ok")

    # 6. Generar nota Obsidian con el texto completo
    note_md = build_obsidian_note(analysis, p.name, raw_text=full_text)

    # 7. Guardar en vault
    folder   = get_vault_folder(analysis)
    base_title = analysis.get("titulo", p.stem)
    # Incluir el nombre original del archivo para evitar colisiones semánticas y pérdida de datos
    title    = safe_filename(f"{base_title} - {p.stem}")
    note_dir = Path(vault_path) / folder
    note_dir.mkdir(parents=True, exist_ok=True)

    note_path = note_dir / f"{title}.md"
    if note_path.exists():
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        note_path = note_dir / f"{title}_{ts}.md"

    note_path.write_text(note_md, encoding="utf-8")
    log(f"Nota creada: {folder}/{note_path.name}", "ok")

    # 8. Actualizar registro en memoria
    registry.setdefault("hashes",    {})[file_hash]        = str(note_path)
    registry.setdefault("embeddings", {})[str(note_path)]  = embedding
    registry.setdefault("topics",    []).append(analysis.get("titulo", ""))

    # 9. Inyectar en ChromaDB (Vector DB)
    try:
        collection = get_collection()
        # Generate context-aware chunks with title and section metadata
        chunks = markdown_aware_chunks(full_text, title=analysis.get("titulo", p.stem))
        # Extract just the content for vector store
        chunk_texts = [c["content"] for c in chunks]
        if chunks:
            # Identificadores únicos para cada chunk
            ids = [f"{note_path.stem}_{i}" for i in range(len(chunks))]
            rel_path = str(note_path.relative_to(Path(vault_path)))
            # Include section info from each chunk's metadata
            metadatas = [{"title": title,
                         "section": c.get("section", ""),
                         "path": rel_path,
                         "source": p.name} for c in chunks]
            collection.add(documents=chunk_texts, metadatas=metadatas, ids=ids)
        log(f"Vectorizados {len(chunks)} fragmentos en ChromaDB", "info")
    except Exception as e:
        log(f"Error indexando en Vector DB: {e}", "warn")

    return {
        "file":      p.name,
        "status":    "created",
        "note_path": str(note_path),
        "folder":    folder,
        "analysis":  analysis,
    }


def run_full_scan(scan_path: str, vault_path: str, model: str = None) -> None:
    """Escaneo completo de una carpeta. Diseñado para ejecutarse en un hilo."""
    from core.ollama import check_ollama

    with state_lock:
        scan_state.update({
            "status": "running", "progress": 0, "total": 0,
            "processed_n": 0, "duplicates_n": 0, "errors_n": 0,
            "current_file": "", "processed": [], "errors": [],
            "log": [], "started_at": datetime.now().isoformat(), "finished_at": None,
        })
        save_state(scan_state)

    log("═══ Jarvis Scanner iniciado ═══", "action")

    if not check_ollama():
        log("Ollama no está corriendo. Ejecutá: ollama serve", "error")
        with state_lock:
            scan_state["status"] = "error"
            save_state(scan_state)
        return

    # Buscar PDFs (ignorar carpetas ocultas)
    pdfs = []
    for p in Path(scan_path).rglob("*"):
        if p.suffix.lower() == ".pdf" and not any(part.startswith('.') for part in p.parts):
            pdfs.append(p)
    
    # Eliminar duplicados de rutas (resolve)
    pdfs = list({p.resolve(): p for p in pdfs}.values())

    if not pdfs:
        log(f"No se encontraron PDFs en: {scan_path}", "warn")
        with state_lock:
            scan_state["status"] = "done"
        return

    with state_lock:
        st = load_state()
        registry = st.get("registry", {"hashes": {}, "embeddings": {}})
        # Asegurar que topics esté pero no es crítico persistirlo si se saca del vault
        registry["topics"] = [] 
        
    log(f"Memoria persistente cargada: {len(registry.get('hashes', {}))} archivos conocidos.", "info")
    
    with state_lock:
        scan_state["total"] = len(pdfs)
        save_state(scan_state)
    log(f"Encontrados {len(pdfs)} PDFs válidos en '{scan_path}'", "ok")

    existing_topics = get_existing_topics_from_vault(vault_path)
    log(f"Temas existentes en vault: {len(existing_topics)}", "info")

    for i, pdf_path in enumerate(pdfs):
        with state_lock:
            scan_state["progress"]     = int((i / len(pdfs)) * 100)
            scan_state["current_file"] = Path(pdf_path).name
            save_state(scan_state)

        try:
            result = process_single_pdf(
                str(pdf_path), vault_path, registry,
                registry.get("topics", []) + existing_topics, model
            )
            with state_lock:
                scan_state["processed"].append(result)
                if result["status"] == "created":
                    scan_state["processed_n"] += 1
                    # Persistir el registro inmediatamente para no perderlo
                    st = load_state()
                    st["registry"] = registry
                    save_state(st)
                elif result["status"] == "duplicate":
                    scan_state["duplicates_n"] += 1
                save_state(scan_state)
        except Exception as e:
            log(f"Error fatal procesando {Path(pdf_path).name}: {e}", "error")
            with state_lock:
                scan_state["errors"].append({"file": Path(pdf_path).name, "error": str(e)})
                scan_state["errors_n"] += 1
                save_state(scan_state)

    with state_lock:
        scan_state["progress"]    = 100
        scan_state["status"]      = "done"
        scan_state["finished_at"] = datetime.now().isoformat()
        save_state(scan_state)

    log(
        f"═══ Completado: {scan_state['processed_n']} creadas, "
        f"{scan_state['duplicates_n']} duplicadas, "
        f"{scan_state['errors_n']} errores ═══", "ok",
    )
