import json
import os
from pathlib import Path
from threading import Lock
from tempfile import NamedTemporaryFile

# Archivo de estado persistente (compartido entre procesos)
STATE_FILE = Path.home() / ".jarvis_scan_state.json"

state_lock = Lock()

INITIAL_STATE = {
    "status":       "idle",
    "progress":     0,
    "total":        0,
    "processed_n":  0,
    "duplicates_n": 0,
    "errors_n":     0,
    "current_file": "",
    "processed":    [],
    "errors":       [],
    "log":          [],
    "started_at":   None,
    "finished_at":  None,
    # Registro de archivos para evitar duplicados persistente
    "registry": {
        "hashes": {},
        "embeddings": {}
    },
    # Overrides de modelos específicos por subtarea
    "task_overrides": {},
    # Configuración persistente del usuario
    "config": {
        "auto_sync":     False,
        "tools_search":  True,
        "tools_command": False,
        "tools_files":   True,
        "analysis_model": "qwen2.5:14b",
        "chat_model":     "qwen2.5:14b",
        "embedding_model": "bge-m3",
        "rerank_backend": "cross_encoder",
        "duplicate_threshold": 0.88,
        "prefix_cache":  True
    }
}

def save_state(state: dict):
    """Guarda el estado en disco de forma atómica."""
    try:
        with NamedTemporaryFile('w', dir=STATE_FILE.parent, delete=False) as f:
            json.dump(state, f, indent=2)
            temp_name = f.name
        os.replace(temp_name, STATE_FILE)
    except Exception as e:
        print(f"Error guardando estado: {e}")

def load_state() -> dict:
    """Carga el estado desde el disco con merge inteligente."""
    import copy
    state = copy.deepcopy(INITIAL_STATE)
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                saved = json.load(f)
                # Fusionamos config y task_overrides para no perder campos nuevos
                if "config" in saved:
                    state["config"].update(saved["config"])
                    del saved["config"]
                if "task_overrides" in saved:
                    state["task_overrides"].update(saved["task_overrides"])
                    del saved["task_overrides"]
                # El resto sobreescribe
                state.update(saved)
        except Exception:
            pass
    return state

# En memoria, para compatibilidad con código existente (aunque se sincronizará con disco)
scan_state: dict = load_state()
