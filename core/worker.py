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
