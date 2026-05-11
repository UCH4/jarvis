#!/usr/bin/env python3
"""
Reconstruye la colección Chroma desde todas las notas .md del vault.
Útil al cambiar JARVIS_EMBED / JARVIS_CHROMA_COLLECTION / dimensión.

Uso:
  export JARVIS_CHROMA_COLLECTION=vault_notes_bge_m3
  export JARVIS_EMBED=bge-m3
  export JARVIS_EMBED_DIM=1024
  python scripts/reindex_vault_chroma.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import load_config, CHROMA_COLLECTION  # noqa: E402
from core.db import get_chroma_client, get_embedding_function  # noqa: E402
from core.chunker import markdown_aware_chunks  # noqa: E402


def main() -> None:
    cfg = load_config()
    vault = cfg.get("vault_path") or ""
    if not vault:
        print("Configurá vault_path en ~/.jarvis_scanner_config.json")
        sys.exit(1)
    vault_p = Path(vault).expanduser()
    if not vault_p.is_dir():
        print(f"Vault no existe: {vault_p}")
        sys.exit(1)

    client = get_chroma_client()
    try:
        client.delete_collection(CHROMA_COLLECTION)
        print(f"Colección eliminada: {CHROMA_COLLECTION}")
    except Exception as e:
        print(f"Aviso al borrar colección: {e}")

    ef = get_embedding_function()
    col = client.create_collection(name=CHROMA_COLLECTION, embedding_function=ef)

    n_docs = 0
    for md in sorted(vault_p.rglob("*.md")):
        if any(part.startswith(".") for part in md.parts):
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title = md.stem
        chunks = markdown_aware_chunks(text, title=title)
        if not chunks:
            continue
        rel = str(md.relative_to(vault_p)).replace("\\", "/")
        hid = hashlib.md5(str(md).encode("utf-8")).hexdigest()[:12]
        ids = [f"{hid}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"title": title, "path": rel, "section": c.get("section", ""), "source": md.name}
            for c in chunks
        ]
        col.add(
            documents=[c["content"] for c in chunks],
            metadatas=metadatas,
            ids=ids,
        )
        n_docs += len(chunks)

    print(f"Reindex OK: {CHROMA_COLLECTION}, fragmentos={n_docs}")


if __name__ == "__main__":
    main()
