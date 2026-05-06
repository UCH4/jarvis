"""
core/vision.py — OCR Multimodal y Detección Matemática
"""
import re
from core.logger import log

_BROKEN_MATH = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]"
    r"|(?:[^\w\s.,;:¿?¡!()\[\]{}<>=+\-*/^áéíóúüñÁÉÍÓÚÜÑ]{3,})"
)

def has_high_math_density(text: str) -> bool:
    """
    Detecta si una página tiene alta densidad matemática
    o si los caracteres extraídos están rotos (indicador de error del parser).
    """
    if not text or len(text) < 10:
        return True
        
    bad_chars = len(_BROKEN_MATH.findall(text))
    
    # Heurística para matemáticas: operadores vs palabras
    math_symbols = sum(text.count(c) for c in "+=∑∫√∞≤≥≠∀∃∈∉⊂⊆∪∩")
    words = max(1, len(text.split()))
    
    # Umbrales más estrictos para evitar disparar visión por ruido simple
    is_broken = bad_chars > max(5, words * 0.05)
    is_math_heavy = math_symbols > max(10, words * 0.15)
    
    return is_broken or is_math_heavy
