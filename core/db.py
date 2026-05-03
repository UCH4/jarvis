"""
core/db.py — Manejo de Base de Datos Vectorial (ChromaDB)
"""
import os
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions

from core.config import OLLAMA_URL, EMBEDDING_MODEL

# ─── GLOBAL TIMEOUT PATCH ─────────────────────────────────────
# ChromaDB por defecto tiene un timeout muy corto para Ollama.
# Lo parcheamos quirúrgicamente para que aguante la carga del M4 Pro.
import requests
original_post = requests.post
def patched_post(*args, **kwargs):
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 120
    return original_post(*args, **kwargs)
requests.post = patched_post
# ──────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent.parent / ".chroma_db"

def get_chroma_client():
    DB_PATH.mkdir(exist_ok=True)
    return chromadb.PersistentClient(path=str(DB_PATH))

def get_embedding_function():
    # Retornamos la estándar de Chroma para evitar el error de "Conflict"
    # El parche global de 'requests' se encargará del timeout.
    return embedding_functions.OllamaEmbeddingFunction(
        url=f"{OLLAMA_URL}/api/embeddings",
        model_name=EMBEDDING_MODEL
    )

def get_collection(name: str = "vault_notes"):
    client = get_chroma_client()
    try:
        # Intentamos obtener la colección existente.
        # Al pasar la función aquí, Chroma verifica si coincide.
        # Si falla por conflicto de clase, el 'except' lo manejará.
        return client.get_collection(name=name, embedding_function=get_embedding_function())
    except Exception as e:
        if "does not exist" in str(e):
            return client.create_collection(name=name, embedding_function=get_embedding_function())
        # Si hay conflicto de función (clase distinta), la obtenemos sin especificarla.
        # Chroma usará la persistida internamente.
        return client.get_collection(name=name)

def get_collection_client():
    return get_chroma_client()
