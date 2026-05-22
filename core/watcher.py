import os
import time
from threading import Thread
from core.logger import log
from core.worker import run_full_scan_task
from core.config import load_config

class VaultWatcher:
    def __init__(self, scan_path, vault_path):
        self.scan_path = scan_path
        self.vault_path = vault_path
        self.known_files = set()
        self.running = False
        
    def _get_files(self):
        try:
            pdfs = set()
            for root, _, files in os.walk(self.scan_path):
                for f in files:
                    if f.lower().endswith('.pdf') and not f.startswith('._'):
                        rel_path = os.path.relpath(os.path.join(root, f), self.scan_path)
                        pdfs.add(rel_path)
            return pdfs
        except Exception:
            return set()

    def start(self):
        if self.running: return
        self.running = True
        # Inicializar con los archivos actuales
        self.known_files = self._get_files()
        Thread(target=self._watch_loop, daemon=True).start()
        log(f"Auto-Sync activo: vigilando nuevas notas en {self.scan_path}", "ok")

    def _watch_loop(self):
        while self.running:
            try:
                time.sleep(15) # Chequear cada 15 segundos
                
                # RECARGAR ESTADO para ver si el usuario desactivó el switch
                from core.state import load_state
                state = load_state()
                if not state.get("config", {}).get("auto_sync", False):
                    continue

                current_files = self._get_files()
                new_files = current_files - self.known_files
                
                if new_files:
                    log(f"Auto-Sync: detectados {len(new_files)} archivos nuevos. Encolando...", "info")
                    # Encolar tarea de escaneo
                    run_full_scan_task(self.scan_path, self.vault_path)
                    self.known_files = current_files
            except Exception as e:
                log(f"Error en Auto-Sync: {e}", "error")
                time.sleep(30)

_watcher_instance = None

def start_auto_sync(scan_path, vault_path):
    global _watcher_instance
    if not _watcher_instance:
        _watcher_instance = VaultWatcher(scan_path, vault_path)
        _watcher_instance.start()
