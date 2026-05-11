"""
core/mlx_vlm.py — Visión con mlx-vlm (Apple Silicon). Opcional: pip install mlx-vlm
"""
from __future__ import annotations

import io
import time
from typing import Optional

from core.config import MLX_VLM_MODEL
from core.gpu import gpu_lock
from core.logger import log

_model_cache = None
_processor_cache = None
_config_cache = None


def _load_mlx_vlm():
    global _model_cache, _processor_cache, _config_cache
    if _model_cache is not None:
        return _model_cache, _processor_cache, _config_cache
    from mlx_vlm import load
    try:
        from mlx_vlm.utils import load_config as _load_cfg
    except ImportError:
        _load_cfg = None

    t0 = time.perf_counter()
    model, processor = load(MLX_VLM_MODEL)
    cfg = None
    if _load_cfg is not None:
        try:
            cfg = _load_cfg(MLX_VLM_MODEL)
        except Exception:
            cfg = None
    load_ms = (time.perf_counter() - t0) * 1000
    log(f"MLX-VLM cargado ({MLX_VLM_MODEL}) en {load_ms:.0f} ms", "info")
    _model_cache, _processor_cache, _config_cache = model, processor, cfg
    return model, processor, cfg


def transcribe_image_png(
    png_bytes: bytes,
    prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> str:
    """
    Transcribe/describe una imagen PNG en memoria. Retorna cadena vacía si mlx-vlm no está instalado.
    """
    try:
        from PIL import Image
        from mlx_vlm import generate
    except ImportError as e:
        log(f"MLX-VLM no disponible (pip install mlx-vlm): {e}", "warn")
        return ""

    try:
        from mlx_vlm.prompt_utils import apply_chat_template
    except ImportError:
        apply_chat_template = None

    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    images = [image]

    with gpu_lock(f"MLX VLM ({MLX_VLM_MODEL})"):
        t_load = time.perf_counter()
        model, processor, cfg = _load_mlx_vlm()
        load_ms = (time.perf_counter() - t_load) * 1000

        formatted = prompt
        if apply_chat_template is not None and cfg is not None:
            try:
                formatted = apply_chat_template(
                    processor, cfg, prompt, num_images=len(images)
                )
            except Exception:
                formatted = prompt

        t_inf = time.perf_counter()
        out = None
        for kwargs in (
            {"verbose": False, "max_tokens": max_tokens, "temp": temperature},
            {"verbose": False, "max_tokens": max_tokens},
            {"verbose": False},
        ):
            try:
                out = generate(model, processor, formatted, images, **kwargs)
                break
            except TypeError:
                continue
        if out is None:
            try:
                out = generate(model, processor, prompt, images, verbose=False)
            except Exception as e:
                log(f"MLX-VLM generate falló: {e}", "warn")
                return ""
        infer_ms = (time.perf_counter() - t_inf) * 1000
        log(
            f"MLX-VLM infer: load_window={load_ms:.0f}ms infer={infer_ms:.0f}ms",
            "info",
        )

    if isinstance(out, str):
        return out.strip()
    if hasattr(out, "text"):
        return str(out.text).strip()
    return str(out).strip()


def transcribe_pdf_page_fitz(page, page_num: int, prompt: Optional[str] = None) -> str:
    """Renderiza página PyMuPDF y transcribe con MLX-VLM."""
    pix = page.get_pixmap(dpi=160, colorspace="rgb")
    png_bytes = pix.tobytes("png")
    if prompt is None:
        prompt = (
            "Eres un experto en transcripción matemática. Extrae TODO el contenido. "
            "Usa LaTeX ($...$ inline, $$...$$ bloque) para fórmulas. "
            "Solo Markdown, sin saludos."
        )
    text = transcribe_image_png(png_bytes, prompt)
    if text:
        return f"<!-- página {page_num} — OCR MLX-VLM -->\n{text}"
    return ""
