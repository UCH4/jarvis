"""
core/db.py — Manejo de Base de Datos Vectorial (ChromaDB)
"""
import os
from pathlib import Path
import chromadb

from core.config import OLLAMA_URL, EMBEDDING_MODEL, EMBEDDING_DIM, CHROMA_COLLECTION

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

class CustomOllamaEmbeddingFunction:
    def __init__(self, url, model_name):
        self.url = url
        self.model_name = model_name

    def __call__(self, input):
        # Maneja tanto string único como lista de strings
        texts = [input] if isinstance(input, str) else input
        embeddings = []
        import requests
        from core.logger import log
        
        for text in texts:
            try:
                # Truncamiento quirúrgico para evitar "input length exceeds context length"
                # nomic-embed-text y la mayoría soportan ~8k, pero Ollama por defecto usa menos
                safe_text = text[:6000] 
                
                r = requests.post(
                    self.url,
                    json={"model": self.model_name, "prompt": safe_text},
                    timeout=60
                )
                if r.status_code == 400:
                    log(f"Embeddings: Error 400 (Posible exceso de contexto) con modelo {self.model_name}", "warn")
                    embeddings.append([0.0] * EMBEDDING_DIM)
                    continue
                    
                r.raise_for_status()
                embeddings.append(r.json().get("embedding", []))
            except Exception as e:
                log(f"Embeddings: Fallo al obtener vector: {e}", "warn")
                embeddings.append([0.0] * EMBEDDING_DIM)
        return embeddings

def get_embedding_function():
    return CustomOllamaEmbeddingFunction(
        url=f"{OLLAMA_URL}/api/embeddings",
        model_name=EMBEDDING_MODEL
    )

def get_collection(name: str = None):
    if name is None:
        name = CHROMA_COLLECTION
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
