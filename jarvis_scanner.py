#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          JARVIS SCANNER — Academic Vault Architect           ║
║  Transforma PDFs en un grafo de conocimiento en Obsidian     ║
╚══════════════════════════════════════════════════════════════╝

Uso:
    python jarvis_scanner.py              → inicia el servidor web (dashboard)
    python jarvis_scanner.py --tunnel     → servidor + túnel Cloudflare (acceso remoto)
    python jarvis_scanner.py --cli        → modo interactivo por terminal
    python jarvis_scanner.py --scan /ruta/pdfs --vault /ruta/vault
"""

import argparse
import sys
import time
import shutil

from core.config   import load_config, API_PORT, ANALYSIS_MODEL
from core.state    import scan_state, state_lock
from core.scanner  import run_full_scan
from core.ollama   import check_ollama, get_vision_model
from core.network  import get_local_ip, start_cloudflare_tunnel, get_tunnel_url
from core.logger   import log


def cli_mode():
    """Modo interactivo por terminal."""
    print("\n╔══════════════════════════════════════════╗")
    print("║       JARVIS SCANNER — Modo CLI           ║")
    print("╚══════════════════════════════════════════╝\n")

    if not check_ollama():
        print("❌ Ollama no está corriendo.")
        print("   Ejecutá: ollama serve")
        sys.exit(1)

    print("✓ Ollama conectado\n")
    cfg        = load_config()
    scan_path  = input(f"📁 Carpeta de PDFs [{cfg.get('scan_path', '')}]: ").strip() or cfg.get("scan_path", "")
    vault_path = input(f"📂 Vault Obsidian  [{cfg.get('vault_path', '')}]: ").strip() or cfg.get("vault_path", "")

    if not scan_path or not vault_path:
        print("❌ Rutas inválidas.")
        sys.exit(1)

    run_full_scan(scan_path, vault_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jarvis Scanner — Academic Vault Architect")
    parser.add_argument("--cli",    action="store_true", help="Modo interactivo por terminal")
    parser.add_argument("--scan",   type=str, help="Ruta de la carpeta de PDFs")
    parser.add_argument("--vault",  type=str, help="Ruta del vault Obsidian")
    parser.add_argument("--model",  type=str, default=ANALYSIS_MODEL)
    parser.add_argument("--tunnel", action="store_true",
                        help="Iniciar túnel Cloudflare para acceso remoto desde cualquier red")
    args = parser.parse_args()

    if args.cli or (args.scan and args.vault):
        if args.scan and args.vault:
            run_full_scan(args.scan, args.vault, args.model)
        else:
            cli_mode()
    else:
        # Modo servidor web
        try:
            from api.server import app, FLASK_AVAILABLE
        except ImportError:
            FLASK_AVAILABLE = False

        if not FLASK_AVAILABLE:
            print("Flask no instalado. Ejecutá:")
            print("  pip3.12 install flask flask-cors --break-system-packages")
            sys.exit(1)

        cfg      = load_config()
        local_ip = get_local_ip()

        print(f"\n{'═'*60}")
        print(f"  🧠  JARVIS SCANNER — Academic Vault Architect")
        print(f"{'═'*60}")
        print(f"  💻  Desde esta Mac:    http://localhost:{API_PORT}")
        print(f"  📡  Red local (WiFi):  http://{local_ip}:{API_PORT}")

        if args.tunnel or shutil.which("cloudflared"):
            from threading import Thread
            t = Thread(target=start_cloudflare_tunnel, args=(API_PORT,), daemon=True)
            t.start()
            time.sleep(12)
            tunnel = get_tunnel_url()
            if tunnel:
                print(f"  🌍  Cualquier red:     {tunnel}")
            else:
                print(f"  ⚠   Túnel no disponible. Instalá: brew install cloudflared")
        else:
            print(f"  ℹ   Para acceso remoto: python jarvis_scanner.py --tunnel")

        print(f"{'─'*60}")
        print(f"  Vault: {cfg.get('vault_path', '(no configurado)')}")
        vision = get_vision_model()
        if vision:
            print(f"  👁   OCR fórmulas activo: {vision}")
        else:
            print(f"  ⚠   Sin modelo de visión → ollama pull llava:7b")
        print(f"{'═'*60}\n")

        # Iniciar Cola de Tareas (Worker Huey)
        from core.worker import start_worker
        from core.watcher import start_auto_sync
        from threading import Thread
        
        Thread(target=start_worker, daemon=True).start()
        
        # Iniciar Auto-Sync si las rutas están configuradas
        if cfg.get("scan_path") and cfg.get("vault_path"):
            start_auto_sync(cfg["scan_path"], cfg["vault_path"])

        app.run(host="0.0.0.0", port=API_PORT, debug=False, use_reloader=False, threaded=False)
