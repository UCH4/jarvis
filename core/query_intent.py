"""
core/query_intent.py — Clasificación liviana FACT vs CONCEPT para RAG condicional.
"""
import re
from typing import Literal

Intent = Literal["FACT", "CONCEPT"]


def classify_query_intent(query: str, use_llm: bool = True) -> Intent:
    """
    Heurísticas rápidas primero; opcionalmente confirma con MLX (barato, pocos tokens).
    FACT: fechas, páginas, datos puntuales, definiciones cerradas.
    CONCEPT: teoría, explicación, razonamiento amplio.
    """
    q = (query or "").strip()
    if not q:
        return "FACT"

    ql = q.lower()
    words = q.split()

    # Corta → suele ser factual o lookup
    if len(words) <= 3:
        return "FACT"

    fact_patterns = [
        r"\b\d{4}\b",  # año
        r"\baño\b",
        r"\bpágina\b",
        r"\bpag\.?\b",
        r"\bqu[eé] (año|fecha)",
        r"\bcu[aá]ndo\b",
        r"\bd[oó]nde\b",
        r"\bqui[eé]n (escribi[oó]|public[oó])\b",
        r"\bvalor de\b",
        r"\bdefin[ií] (exactamente|formalmente)\b",
        r"\blista de\b",
        r"\bnombre del\b",
        r"\bt[ií]tulo del (paper|art[ií]culo|libro)\b",
        r"\bhow many\b",
        r"\bwhat year\b",
    ]
    for pat in fact_patterns:
        if re.search(pat, ql):
            return "FACT"

    concept_patterns = [
        r"\bexplic(a|á|ame)\b",
        r"\bteor[ií]a\b",
        r"\bpor qu[eé]\b",
        r"\bdemostr(a|á)\b",
        r"\bintuici[oó]n\b",
        r"\brelaci[oó]n entre\b",
        r"\bcompar(a|á)\b",
        r"\bdiferencia conceptual\b",
        r"\bpaso a paso\b",
        r"\brazona\b",
        r"\banaliza\b",
    ]
    for pat in concept_patterns:
        if re.search(pat, ql):
            return "CONCEPT"

    if not use_llm or len(words) < 5:
        return "FACT"

    try:
        from core.model_orchestrator import resolve, Task
        spec = resolve(Task.INTENT_CLASSIFY)
        prompt = (
            f'Clasificá la consulta en UNA palabra: FACT o CONCEPT.\n'
            f'- FACT: dato puntual, fecha, cita, página, quién/cuándo/cuánto.\n'
            f'- CONCEPT: explicar teoría, intuición, demostración, comparar ideas.\n'
            f'Consulta: "{q[:500]}"\n'
            f'Respondé solo: FACT o CONCEPT'
        )
        if spec["provider"] == "mlx":
            from core.mlx_inference import generate_text
            out = generate_text(prompt, model_name=spec["model"], max_tokens=spec["max_tokens"], temperature=spec["temperature"]).strip().upper()
        else:
            from core.ollama import generate_response
            out = generate_response(prompt, spec["model"], temperature=spec["temperature"], max_tokens=spec["max_tokens"]).strip().upper()
            
        if "CONCEPT" in out:
            return "CONCEPT"
    except Exception:
        pass
    return "FACT"
