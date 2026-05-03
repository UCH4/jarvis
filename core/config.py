"""
core/config.py — Configuración global y persistencia
"""
import os
import json
from pathlib import Path

OLLAMA_URL       = os.getenv("OLLAMA_URL",          "http://localhost:11434")
ANALYSIS_MODEL   = os.getenv("JARVIS_MODEL",         "qwen2.5:14b")
EMBEDDING_MODEL  = os.getenv("JARVIS_EMBED",         "nomic-embed-text")
API_PORT         = int(os.getenv("JARVIS_PORT",      "5001"))
DUPLICATE_THRESH = float(os.getenv("JARVIS_DUP_THRESHOLD", "0.88"))

CONFIG_FILE = Path.home() / ".jarvis_scanner_config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"scan_path": "", "vault_path": "", "model": ANALYSIS_MODEL}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
