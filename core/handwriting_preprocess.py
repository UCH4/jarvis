"""
core/handwriting_preprocess.py — Preproceso OpenCV para fotos de cuaderno.
"""
from __future__ import annotations


def preprocess_handwriting_image(file_bytes: bytes) -> bytes:
    """
    Escala de grises, suavizado opcional, umbral adaptativo. Retorna PNG bytes.
    """
    import cv2
    import numpy as np

    arr = np.frombuffer(file_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
    th = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10,
    )
    ok, buf = cv2.imencode(".png", th)
    if not ok:
        raise RuntimeError("Fallo imencode PNG")
    return buf.tobytes()
