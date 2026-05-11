"""
core/markdown_guard.py — Validación liviana de delimitadores antes de guardar notas.
"""
from __future__ import annotations


def _balance(chars: str, pairs: dict[str, str]) -> bool:
    stack: list[str] = []
    for c in chars:
        if c in pairs:
            stack.append(pairs[c])
        elif c in pairs.values():
            if not stack or stack[-1] != c:
                return False
            stack.pop()
    return len(stack) == 0


def validate_markdown_math(text: str) -> tuple[bool, str]:
    """
    Verifica balance básico de ()[]{} y $ \\[ \\(.
    Retorna (ok, mensaje).
    """
    if not text:
        return True, ""

    if not _balance(text, {"(": ")", "[": "]", "{": "}"}):
        return False, "Paréntesis/corchetes/llaves desbalanceados."

    d = text.count("$")
    if d % 2 != 0:
        return False, "Delimitadores $ desbalanceados (cantidad impar)."

    open_b = text.count("\\[")
    close_b = text.count("\\]")
    if open_b != close_b:
        return False, "Delimitadores \\[ \\] desbalanceados."

    open_p = text.count("\\(")
    close_p = text.count("\\)")
    if open_p != close_p:
        return False, "Delimitadores \\( \\) desbalanceados."

    return True, ""


def guard_or_wrap_raw(text: str, title: str = "Transcripción") -> str:
    """Si falla validación, envuelve en bloque _raw para no romper el vault."""
    ok, _ = validate_markdown_math(text)
    if ok:
        return text
    return (
        f"# {title}\n\n"
        f"> Jarvis: el texto no pasó validación de delimitadores; revisá el bloque raw.\n\n"
        f"```_raw\n{text}\n```\n"
    )
