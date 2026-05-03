"""
core/pdf.py — Extracción de texto de PDFs con OCR visual para fórmulas
"""
import re
import hashlib
from pathlib import Path
from core.logger import log

# ─── Limpieza de texto ────────────────────────────────────────

_ACCENT_MAP = [
    (r"´a", "á"), (r"´e", "é"), (r"´i", "í"), (r"´o", "ó"), (r"´u", "ú"),
    (r"´A", "Á"), (r"´E", "É"), (r"´I", "Í"), (r"´O", "Ó"), (r"´U", "Ú"),
    (r"`a", "à"), (r"`e", "è"), (r"`i", "ì"), (r"`o", "ò"), (r"`u", "ù"),
    (r"~n", "ñ"), (r"~N", "Ñ"), (r'¨u', "ü"), (r'¨U', "Ü"), ("ı", "i"),
    ("ﬁ", "fi"), ("ﬀ", "ff"), ("ﬂ", "fl"), ("ﬃ", "ffi"), ("ﬄ", "ffl"),
    ("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'),
    ("\u2013", "-"), ("\u2014", "-"),
    ("\u2208", "∈"), ("\u2200", "∀"), ("\u2203", "∃"), ("\u2227", "∧"),
    ("\u2228", "∨"), ("\u00ac", "¬"), ("\u21d2", "⇒"), ("\u21d4", "⇔"),
    ("\u2264", "≤"), ("\u2265", "≥"), ("\u2260", "≠"), ("\u221e", "∞"),
    ("\u221a", "√"), ("\u03b1", "α"), ("\u03b2", "β"), ("\u03b8", "θ"),
    ("\u03c0", "π"), ("\u03c3", "σ"), ("\u03bb", "λ"), ("\u03bc", "μ"),
]

from core.vision import has_high_math_density


def limpiar_texto_pdf(text: str) -> str:
    if not text:
        return text
    for broken, fixed in _ACCENT_MAP:
        text = text.replace(broken, fixed)
    text = re.sub(r"-\n([a-záéíóúüñA-ZÁÉÍÓÚÜÑ])", r"\1",   text)
    text = re.sub(r"([a-záéíóúüñ])\n([a-záéíóúüñ])", r"\1\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ",  text)
    text = re.sub(r"(?m)^\s*\d{1,3}\s*$", "", text)
    return text.strip()


def _run_marker_pdf(pdf_path: str) -> str:
    """Intenta extraer el PDF usando marker-pdf si está instalado (alta fidelidad)."""
    import subprocess
    import tempfile
    try:
        if subprocess.run(["marker_single", "--help"], capture_output=True).returncode != 0:
            return ""
    except FileNotFoundError:
        return ""

    log("Iniciando extracción Marker (OCR Matemático de alta fidelidad)...", "action")
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            res = subprocess.run(
                ["marker_single", pdf_path, "--output_dir", temp_dir],
                capture_output=True, text=True, timeout=600
            )
            if res.returncode == 0:
                out_path = Path(temp_dir) / Path(pdf_path).stem / f"{Path(pdf_path).stem}.md"
                if out_path.exists():
                    log("Extracción Marker completada con éxito.", "ok")
                    return out_path.read_text(encoding="utf-8")
        except Exception as e:
            log(f"Marker falló: {e}", "warn")
    return ""


# ─── Extracción inteligente ───────────────────────────────────

def extract_pdf_text(pdf_path: str, max_chars: int = 0) -> str:
    """
    Extrae texto de un PDF de forma inteligente:
    1. pymupdf4llm (mejor markdown para LaTeX)
    2. Para páginas con fórmulas rotas → OCR visual con llava
    3. Fallback: PyMuPDF texto plano + limpieza
    """
    try:
        import fitz
    except ImportError:
        import os
        os.system("pip3.12 install PyMuPDF --break-system-packages -q")
        import fitz

    # Detectar modelo de visión una sola vez
    from core.ollama import get_vision_model, ocr_page_vision
    vision_model = get_vision_model()
    if vision_model:
        log(f"Modelo de visión disponible: {vision_model}", "info")
    else:
        log("Sin modelo de visión. Para OCR de fórmulas: ollama pull llava:7b", "warn")

    # ── Intento 0: Marker-PDF (Mejor calidad matemática) ──────
    marker_text = _run_marker_pdf(pdf_path)
    if marker_text and len(marker_text.strip()) > 50:
        return marker_text[:max_chars] if max_chars else marker_text

    # ── Intento 1: pymupdf4llm + LLM Visión ───────────────────
    try:
        import pymupdf4llm
        doc    = fitz.open(pdf_path)
        pages  = []
        for i, page in enumerate(doc):
            raw = page.get_text("text").strip()
            if vision_model and has_high_math_density(raw):
                ocr = ocr_page_vision(page, vision_model, i + 1)
                if ocr:
                    pages.append(ocr)
                    continue
            clean = limpiar_texto_pdf(raw)
            if clean:
                pages.append(f"<!-- página {i+1} -->\n{clean}")
        doc.close()
        full = "\n\n".join(pages)
        if len(full.strip()) > 50:
            return full[:max_chars] if max_chars else full
    except ImportError:
        log("pymupdf4llm no instalado. pip3.12 install pymupdf4llm --break-system-packages", "info")
    except Exception as e:
        log(f"Error en pymupdf4llm: {e}", "warn")

    # ── Intento 2: PyMuPDF estándar ───────────────────────────
    try:
        from core.ollama import get_vision_model, ocr_page_vision
        doc   = fitz.open(pdf_path)
        pages = []
        for i, page in enumerate(doc):
            raw   = page.get_text("text").strip()
            clean = limpiar_texto_pdf(raw) if raw else ""
            if vision_model and has_high_math_density(clean):
                ocr = ocr_page_vision(page, vision_model, i + 1)
                if ocr:
                    pages.append(ocr)
                    continue
            if clean:
                pages.append(f"<!-- página {i+1} -->\n{clean}")
        doc.close()
        full = "\n\n".join(pages)
        return full[:max_chars] if max_chars else full
    except Exception as e:
        log(f"Error extrayendo PDF {Path(pdf_path).name}: {e}", "error")
        return ""


def compute_file_hash(path: str) -> str:
    """SHA256 del archivo para detectar duplicados exactos."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
