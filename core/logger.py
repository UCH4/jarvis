"""
core/logger.py — Sistema de logging compartido
"""
from datetime import datetime
from core.state import scan_state, state_lock

_ICONS = {"info": "·", "ok": "✓", "warn": "⚠", "error": "✗", "action": "→"}


def log(msg: str, level: str = "info") -> None:
    icon  = _ICONS.get(level, "·")
    entry = f"{datetime.now().strftime('%H:%M:%S')} {icon} {msg}"
    from core.state import save_state
    with state_lock:
        scan_state["log"].append(entry)
        save_state(scan_state)
    print(entry)
