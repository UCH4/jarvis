"""
core/ingest_heavy.py — Ingest pesado opcional (Nougat) y heurísticas #biblia / densidad.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from core.config import NOUGAT_CMD
from core.logger import log
from core.vision import has_high_math_density


def analysis_suggests_heavy_ingest(analysis: dict, sample_text: str) -> bool:
    """True si conviene segunda pasada pesada (Nougat / Marker ya intentado en pdf.py)."""
    tags = analysis.get("tags") or []
    tag_str = " ".join(tags).lower()
    if "#biblia" in tag_str or "biblia" in tag_str:
        return True
    if has_high_math_density(sample_text[:8000]):
        return True
    return False


def run_nougat_markdown(pdf_path: str, timeout_sec: int = 3600) -> str:
    """
    Ejecuta Nougat CLI si existe. Retorna markdown o cadena vacía.
    """
    if not pdf_path or not Path(pdf_path).is_file():
        return ""
    cmd = os.getenv("JARVIS_NOUGAT_CMD", NOUGAT_CMD).strip()
    if not cmd:
        return ""
    try:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            out_dir.mkdir()
            args = [cmd, pdf_path, "-o", str(out_dir)]
            log(f"Nougat: ejecutando {' '.join(args[:3])}...", "info")
            r = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            if r.returncode != 0:
                log(f"Nougat stderr: {r.stderr[:500]}", "warn")
                return ""
            mds = list(out_dir.rglob("*.mmd")) + list(out_dir.rglob("*.md"))
            if not mds:
                log("Nougat: no se generaron .md/.mmd", "warn")
                return ""
            return mds[0].read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        log("Nougat CLI no encontrado. Instalá nougat o definí JARVIS_NOUGAT_CMD.", "warn")
    except subprocess.TimeoutExpired:
        log("Nougat: timeout", "warn")
    except Exception as e:
        log(f"Nougat error: {e}", "warn")
    return ""
