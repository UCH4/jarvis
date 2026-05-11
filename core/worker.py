"""
core/worker.py — Gestor de tareas asíncronas con Huey (SQLite)
"""
from pathlib import Path
from huey import SqliteHuey

# Base de datos local para persistir la cola
db_path = Path(__file__).parent.parent / ".huey.sqlite"
huey = SqliteHuey(filename=str(db_path))

@huey.task()
def run_full_scan_task(scan_path: str, vault_path: str, model: str = None):
    """Ejecuta el escaneo completo en segundo plano (worker process)"""
    from core.scanner import run_full_scan
    run_full_scan(scan_path, vault_path, model)


@huey.task()
def nougat_ingest_task(pdf_path: str, output_md_path: str):
    """Ingest pesado con Nougat CLI (opcional). Escribe markdown en output_md_path."""
    from pathlib import Path
    from core.ingest_heavy import run_nougat_markdown
    from core.logger import log

    md = run_nougat_markdown(pdf_path)
    if md:
        out = Path(output_md_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        log(f"Nougat guardado en {output_md_path}", "ok")
    else:
        log("Nougat no produjo salida (¿CLI instalado?)", "warn")

def start_worker():
    """Inicia el consumidor en un subproceso (no bloqueante) para evitar problemas de señales de hilos."""
    import subprocess
    import sys
    try:
        from core.logger import log
        log("Iniciando Worker de Huey en subproceso...", "info")
        # Corre huey_consumer.py como un proceso independiente, sin bloquear
        subprocess.Popen(
            [sys.executable, "-m", "huey.bin.huey_consumer", "core.worker.huey", "-w", "2", "-k", "thread"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"Error iniciando Worker: {e}")
