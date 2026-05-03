"""
core/obsidian.py — Generación de notas Markdown para el vault de Obsidian
"""
import json
import re
from datetime import datetime
from pathlib import Path

from core.config import ANALYSIS_MODEL


def safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = name.strip(". ")
    return name[:100] or "sin-titulo"


def build_obsidian_note(analysis: dict, pdf_name: str, raw_text: str = "") -> str:
    """Genera el contenido Markdown de la nota Obsidian."""
    now       = datetime.now()
    tags_yaml = json.dumps(analysis.get("tags", []))
    conexiones = analysis.get("conexiones_sugeridas", [])
    conn_links = " · ".join(f"[[{c}]]" for c in conexiones) if conexiones else "_Ninguna detectada_"
    conceptos  = "\n".join(f"- {c}" for c in analysis.get("conceptos_clave", []))
    formulas   = "\n".join(f"- `{f}`" for f in analysis.get("formulas_importantes", []))

    formulas_section = f"\n## 📐 Fórmulas y Teoremas\n\n{formulas}\n" if formulas else ""

    pdf_content_section = ""
    if raw_text and raw_text.strip():
        clean_text = raw_text.replace("```", "'''")
        pdf_content_section = f"""
## 📄 Contenido del PDF

> [!note] Texto extraído automáticamente de `{pdf_name}`
> Podés editar, resaltar o agregar comentarios dentro de esta sección.

{clean_text}
"""

    return f"""---
title: "{analysis.get('titulo', 'Sin título')}"
materia: "{analysis.get('materia', '')}"
categoria: "{analysis.get('categoria', 'Otro')}"
subcategoria: "{analysis.get('subcategoria', '')}"
tipo: "{analysis.get('tipo', 'Apunte')}"
dificultad: "{analysis.get('dificultad', 'Básico')}"
idioma: "{analysis.get('idioma', 'Español')}"
tags: {tags_yaml}
fuente_pdf: "{pdf_name}"
hash_pdf: "{analysis.get('hash', '')}"
fecha_creacion: "{now.strftime('%Y-%m-%d')}"
ultima_revision: "{now.strftime('%Y-%m-%d')}"
estado: "nuevo"
revisado: false
---

# {analysis.get('titulo', 'Sin título')}

> [!abstract] Resumen
> {analysis.get('resumen', '')}

## 📚 Conceptos Clave

{conceptos if conceptos else '_Sin conceptos extraídos_'}
{formulas_section}
## 📝 Notas Personales

<!-- Escribe tus notas, aclaraciones y ejemplos propios aquí -->

## ❓ Preguntas de Repaso

<!-- 
Tip: usá Dataview para generar preguntas automáticamente:
```dataview
LIST FROM [[{analysis.get('titulo', '')}]]
```
-->

## 🔗 Conexiones

{conn_links}
{pdf_content_section}
---

> **Fuente:** `{pdf_name}` · Procesado: {now.strftime('%Y-%m-%d %H:%M')} · Modelo: {ANALYSIS_MODEL}
> _Nota generada por Jarvis Scanner_
"""


def get_vault_folder(analysis: dict) -> str:
    """Determina la subcarpeta del vault donde guardar la nota."""
    categoria = safe_filename(analysis.get("categoria", "Otro"))
    materia   = safe_filename(analysis.get("materia",   "General"))
    tipo      = safe_filename(analysis.get("tipo",      "Apunte"))
    return f"{categoria}/{materia}/{tipo}"


def get_vault_stats(vault_path: str) -> dict:
    """Estadísticas del vault Obsidian."""
    vault = Path(vault_path)
    if not vault.exists():
        return {"notes": 0, "folders": 0, "categories": {}, "recent": [], "by_type": {}, "by_difficulty": {}}

    notes   = list(vault.rglob("*.md"))
    folders = [d for d in vault.rglob("*") if d.is_dir() and not d.name.startswith(".")]
    categories, by_type, by_difficulty = {}, {}, {}

    for note in notes:
        parts = note.relative_to(vault).parts
        if parts:
            cat = parts[0]
            categories[cat] = categories.get(cat, 0) + 1
        try:
            content  = note.read_text(encoding="utf-8", errors="ignore")
            fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                tm = re.search(r'^tipo:\s*"?(.+?)"?\s*$',       fm, re.MULTILINE)
                dm = re.search(r'^dificultad:\s*"?(.+?)"?\s*$', fm, re.MULTILINE)
                if tm:
                    t = tm.group(1).strip()
                    by_type[t] = by_type.get(t, 0) + 1
                if dm:
                    d = dm.group(1).strip()
                    by_difficulty[d] = by_difficulty.get(d, 0) + 1
        except Exception:
            pass

    recent = sorted(notes, key=lambda x: x.stat().st_mtime, reverse=True)[:15]
    return {
        "notes":         len(notes),
        "folders":       len(folders),
        "categories":    categories,
        "by_type":       by_type,
        "by_difficulty": by_difficulty,
        "recent": [
            {"name": n.stem, "path": str(n.relative_to(vault)), "mtime": n.stat().st_mtime}
            for n in recent
        ],
    }


def get_existing_topics_from_vault(vault_path: str) -> list:
    vault = Path(vault_path)
    if not vault.exists():
        return []
    return [md.stem for md in vault.rglob("*.md")][:60]
