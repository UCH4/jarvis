"""
core/config.py — Configuración global y persistencia
"""
import os
import json
from pathlib import Path

OLLAMA_URL       = os.getenv("OLLAMA_URL",          "http://localhost:11434")
ANALYSIS_MODEL   = os.getenv("JARVIS_MODEL",         "qwen2.5:14b")
# Multilingüe (español): bge-m3 o mxbai-embed-large en Ollama — requiere reindex / nueva colección
EMBEDDING_MODEL  = os.getenv("JARVIS_EMBED",         "bge-m3")
API_PORT         = int(os.getenv("JARVIS_PORT",      "5001"))
DUPLICATE_THRESH = float(os.getenv("JARVIS_DUP_THRESHOLD", "0.88"))

# Dimensión del vector del modelo de embeddings (fallback ante error de API)
_EMBEDDING_DIMS = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "mxbai-embed-large-v1": 1024,
    "bge-m3": 1024,
    "bge-large": 1024,
    "snowflake-arctic-embed": 1024,
}
EMBEDDING_DIM = int(os.getenv(
    "JARVIS_EMBED_DIM",
    str(_EMBEDDING_DIMS.get(EMBEDDING_MODEL.split(":")[0].lower(), 1024)),
))

# Colección Chroma (cambiar al migrar embeddings, p. ej. vault_notes_bge_m3)
CHROMA_COLLECTION = os.getenv("JARVIS_CHROMA_COLLECTION", "vault_notes")

# Rerank: cross_encoder (sentence-transformers) | listwise (MLX)
RERANK_BACKEND = os.getenv("JARVIS_RERANK_BACKEND", "cross_encoder")
CROSS_ENCODER_MODEL = os.getenv(
    "JARVIS_CROSS_ENCODER",
    "BAAI/bge-reranker-base",
)

# Visión PDF / manuscritos: ollama | mlx
VISION_BACKEND = os.getenv("JARVIS_VISION_BACKEND", "ollama")
MLX_VLM_MODEL = os.getenv("JARVIS_MLX_VLM", "mlx-community/Qwen2-VL-2B-Instruct-4bit")

# Obsidian Local REST API (plugin coddingtonbear/obsidian-local-rest-api)
OBSIDIAN_REST_URL = os.getenv("JARVIS_OBSIDIAN_REST_URL", "").rstrip("/")
OBSIDIAN_API_KEY = os.getenv("JARVIS_OBSIDIAN_API_KEY", "")
OBSIDIAN_VERIFY_TLS = os.getenv("JARVIS_OBSIDIAN_VERIFY_TLS", "0") == "1"

# Nougat CLI (opcional, ingest pesado)
NOUGAT_CMD = os.getenv("JARVIS_NOUGAT_CMD", "nougat")
# Evita cargar modelos MLX pesados (DeepSeek 14B) por defecto en equipos con 24GB.
ENABLE_HEAVY_REASONING = os.getenv("JARVIS_ENABLE_HEAVY_REASONING", "0") == "1"

CONFIG_FILE = Path.home() / ".jarvis_scanner_config.json"


def get_rerank_backend() -> str:
    """Lee backend de rerank: env > estado persistente > default."""
    try:
        from core.state import load_state
        st = load_state()
        b = st.get("config", {}).get("rerank_backend")
        if b in ("cross_encoder", "listwise"):
            return b
    except Exception:
        pass
    b = RERANK_BACKEND
    return b if b in ("cross_encoder", "listwise") else "cross_encoder"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"scan_path": "", "vault_path": "", "model": ANALYSIS_MODEL}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
