"""
api/server.py — Servidor Flask: endpoints REST para el dashboard
"""
from pathlib  import Path
from threading import Thread

try:
    from flask      import Flask, jsonify, request, send_from_directory
    from flask_cors import CORS

    from core.config   import load_config, save_config, API_PORT, ANALYSIS_MODEL
    from core.state    import load_state, save_state, scan_state, state_lock
    from core.scanner  import run_full_scan, process_single_pdf
    from core.ollama   import check_ollama, get_available_models, chat_con_vault
    from core.obsidian import get_vault_stats, get_existing_topics_from_vault, get_vault_graph
    from core.network  import get_local_ip, get_tunnel_url

    # El dashboard y los estáticos están en ../static/
    _BASE = Path(__file__).parent.parent
    app   = Flask(__name__, static_folder=str(_BASE / "static"))
    CORS(app)

    # ─── Raíz ─────────────────────────────────────────────────
    @app.route("/")
    def index():
        return send_from_directory(str(_BASE), "dashboard.html")

    # ─── Error Handlers ───────────────────────────────────────
    @app.errorhandler(500)
    def handle_500_error(e):
        """Asegura que los errores del servidor devuelvan JSON."""
        import logging
        logging.error(f"Error interno del servidor: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Error interno del servidor al procesar la solicitud.",
            "details": str(e)
        }), 500

    @app.errorhandler(404)
    def handle_404_error(e):
        return jsonify({
            "status": "error",
            "message": "Recurso no encontrado."
        }), 404

    # ─── Estado del scan ──────────────────────────────────────
    @app.route("/api/status")
    def api_status():
        from core.state import load_state
        return jsonify(load_state())

    # ─── Scan en lote ─────────────────────────────────────────
    @app.route("/api/scan", methods=["POST"])
    def api_scan():
        data       = request.get_json() or {}
        scan_path  = data.get("scan_path",  "").strip()
        vault_path = data.get("vault_path", "").strip()
        model      = data.get("model", ANALYSIS_MODEL)

        if not scan_path or not vault_path:
            return jsonify({"error": "scan_path y vault_path son requeridos"}), 400
        if not Path(scan_path).exists():
            return jsonify({"error": f"Carpeta no existe: {scan_path}"}), 400

        with state_lock:
            if scan_state["status"] == "running":
                return jsonify({"error": "Hay un scan en curso"}), 409

        cfg = load_config()
        cfg.update({"scan_path": scan_path, "vault_path": vault_path, "model": model})
        save_config(cfg)

        from core.worker import run_full_scan_task
        # Encolar la tarea en Huey en lugar de usar Thread manual
        run_full_scan_task(scan_path, vault_path, model)
        
        return jsonify({"message": "Scan encolado en background", "status": "running"})

    # ─── Scan de un PDF ───────────────────────────────────────
    @app.route("/api/scan/single", methods=["POST"])
    def api_scan_single():
        data       = request.get_json() or {}
        pdf_path   = data.get("pdf_path",   "").strip()
        vault_path = data.get("vault_path", "").strip()
        model      = data.get("model", ANALYSIS_MODEL)

        if not pdf_path or not vault_path:
            return jsonify({"error": "pdf_path y vault_path son requeridos"}), 400
        if not Path(pdf_path).exists():
            return jsonify({"error": f"Archivo no existe: {pdf_path}"}), 400

        registry = {"hashes": {}, "embeddings": {}, "topics": []}
        existing = get_existing_topics_from_vault(vault_path)
        result   = process_single_pdf(pdf_path, vault_path, registry, existing, model)
        return jsonify(result)

    # ─── Estadísticas del vault ───────────────────────────────
    @app.route("/api/vault-stats")
    def api_vault_stats():
        vault_path = request.args.get("vault_path", "").strip()
        if not vault_path:
            vault_path = load_config().get("vault_path", "")
        return jsonify(get_vault_stats(vault_path))

    # ─── Modelos disponibles ──────────────────────────────────
    @app.route("/api/models")
    def api_models():
        return jsonify({"models": get_available_models()})

    # ─── Configuración ────────────────────────────────────────
    @app.route("/api/config", methods=["GET", "POST"])
    def api_config():
        from core.state import load_state, save_state
        if request.method == "GET":
            # Combinamos config.yaml con el estado persistente
            cfg = load_config()
            state = load_state()
            cfg["user_config"] = state.get("config", {})
            return jsonify(cfg)
        
        data = request.get_json() or {}
        # Si vienen campos de user_config, los guardamos en el estado persistente
        if "user_config" in data:
            with state_lock:
                state = load_state()
                state["config"].update(data["user_config"])
                save_state(state)
            del data["user_config"]
        
        # El resto va al config.yaml
        cfg = load_config()
        cfg.update(data)
        save_config(cfg)
        return jsonify(cfg)

    @app.route("/api/files", methods=["GET"])
    def api_list_files():
        """Lista archivos markdown en el vault."""
        import os
        import time
        cfg = load_config()
        vault_path = cfg.get("vault_path")
        if not vault_path or not os.path.exists(vault_path):
            return jsonify([])

        files = []
        try:
            for root, dirs, filenames in os.walk(vault_path):
                # Ignorar carpetas ocultas, .obsidian o carpeta de limpieza
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != "_Limpieza_Duplicados"]
                for f in filenames:
                    if f.endswith('.md') and not f.startswith('._'):
                        abs_path = os.path.join(root, f)
                        rel_path = os.path.relpath(abs_path, vault_path)
                        mtime = os.path.getmtime(abs_path)
                        files.append({
                            "name": f,
                            "path": rel_path,
                            "abs_path": abs_path,
                            "date": time.strftime('%Y-%m-%d %H:%M', time.localtime(mtime))
                        })
            # Ordenar por fecha desc
            files.sort(key=lambda x: x["date"], reverse=True)
            return jsonify(files[:60]) # Top 60
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/cleanup", methods=["POST"])
    def api_cleanup():
        """Limpia duplicados en el vault."""
        try:
            from core.cleanup import clean_vault_duplicates
            cfg = load_config()
            vault_path = cfg.get("vault_path")
            if not vault_path:
                return jsonify({"status": "error", "message": "Vault no configurado"}), 400
            
            report = clean_vault_duplicates(vault_path)
            # Aseguramos que el reporte tenga un status
            if "error" in report:
                return jsonify({"status": "error", "message": report["error"]}), 500
            
            report["status"] = "success"
            return jsonify(report)
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Fallo crítico en la limpieza: {str(e)}"
            }), 500

    # ─── Estado de Ollama ─────────────────────────────────────
    @app.route("/api/ollama-status")
    def api_ollama_status():
        from core.config import OLLAMA_URL
        return jsonify({"running": check_ollama(), "url": OLLAMA_URL})

    # ─── Chat RAG ─────────────────────────────────────────────
    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        data       = request.get_json() or {}
        question   = data.get("question", "").strip()
        # Cargar modelo desde el estado si no viene en el request
        state = load_state()
        model = data.get("model") or state.get("config", {}).get("chat_model") or ANALYSIS_MODEL
        mode  = data.get("mode", "normal")

        if not question:
            return jsonify({"error": "question es requerido"}), 400

        cfg        = load_config()
        vault_path = data.get("vault_path") or cfg.get("vault_path", "")

        if not vault_path or not Path(vault_path).exists():
            import json
            def error_stream():
                yield json.dumps({"type": "error", "content": "No encontré un vault configurado. Configurá la ruta del vault primero."}) + "\n"
            from flask import Response, stream_with_context
            return Response(stream_with_context(error_stream()), content_type='application/x-ndjson')

        from flask import Response, stream_with_context
        
        def safe_chat_generator():
            try:
                for chunk in chat_con_vault(question, vault_path, model, mode):
                    yield chunk
            except Exception as e:
                import traceback
                traceback.print_exc()
                import json
                yield json.dumps({"type": "error", "content": f"Fallo interno del servidor: {str(e)}"}) + "\n"
        
        return Response(stream_with_context(safe_chat_generator()), content_type='application/x-ndjson')

    # ─── Modo Profesor: Ejercicios y Flashcards ───────────────
    @app.route("/api/exercise", methods=["POST"])
    def api_exercise():
        from agents.professor import generate_exercise
        from core.rag import buscar_en_vault
        data    = request.get_json() or {}
        topic   = data.get("topic", "Temas generales")
        cfg     = load_config()
        vault_path = cfg.get("vault_path", "")
        
        # Obtener contexto para el ejercicio
        docs = buscar_en_vault(topic, vault_path, top_k=3)
        context = "\n\n".join([d["snippet"] for d in docs])
        
        exercise = generate_exercise(topic, context)
        return jsonify(exercise)

    @app.route("/api/flashcards", methods=["POST"])
    def api_flashcards():
        from agents.professor import generate_flashcards
        from core.rag import buscar_en_vault
        data    = request.get_json() or {}
        topic   = data.get("topic", "Conceptos clave")
        cfg     = load_config()
        vault_path = cfg.get("vault_path", "")
        
        # Obtener contexto
        docs = buscar_en_vault(topic, vault_path, top_k=5)
        context = "\n\n".join([d["snippet"] for d in docs])
        
        cards = generate_flashcards(context)
        return jsonify({"flashcards": cards})

    @app.route("/api/terminal/execute", methods=["POST"])
    def api_terminal_execute():
        from agents.terminal import MacTerminalAgent
        data = request.get_json() or {}
        command = data.get("command", "")
        if not command:
            return jsonify({"status": "error", "message": "No se proporcionó un comando"}), 400
        
        agent = MacTerminalAgent()
        output = agent.run_command(command)
        return jsonify({"status": "success" if "✅" in output else "error", "output": output})

    # ─── Info de red ──────────────────────────────────────────
    @app.route("/api/network-info")
    def api_network_info():
        return jsonify({
            "local_ip":   get_local_ip(),
            "port":       API_PORT,
            "tunnel_url": get_tunnel_url(),
        })

    @app.route("/api/tunnel-status")
    def api_tunnel_status():
        url = get_tunnel_url()
        return jsonify({"active": bool(url), "url": url, "type": "cloudflare" if url else "none"})

    @app.route("/api/vaults")
    def api_vaults():
        import os
        import json
        obsidian_json_path = os.path.expanduser("~/Library/Application Support/obsidian/obsidian.json")
        vaults = []
        if os.path.exists(obsidian_json_path):
            try:
                with open(obsidian_json_path, 'r') as f:
                    data = json.load(f)
                    for key, vault in data.get("vaults", {}).items():
                        if "path" in vault:
                            vaults.append({
                                "id": key,
                                "path": vault["path"],
                                "name": os.path.basename(vault["path"])
                            })
            except Exception as e:
                pass
        return jsonify({"vaults": vaults})

    @app.route("/api/graph")
    def api_graph():
        vault_path = request.args.get("vault_path", "").strip()
        if not vault_path:
            vault_path = load_config().get("vault_path", "")
        return jsonify(get_vault_graph(vault_path))

    # ─── Estáticos ────────────────────────────────────────────
    @app.route("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(str(_BASE / "static"), filename)

    FLASK_AVAILABLE = True

except ImportError:
    FLASK_AVAILABLE = False
    app = None
