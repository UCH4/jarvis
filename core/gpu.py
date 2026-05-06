"""
core/gpu.py — Control de acceso concurrente a la GPU (Metal).
Previene que MLX y Ollama colisionen en el hardware M4 Pro.
"""
from threading import Lock
from contextlib import contextmanager
from core.logger import log

# Bloqueo global para cualquier operación que toque Metal/GPU
_metal_lock = Lock()

@contextmanager
def gpu_lock(label="GPU Operation"):
    """
    Context manager para asegurar uso exclusivo de la GPU.
    """
    # log(f"Esperando acceso a GPU: {label}...", "debug")
    with _metal_lock:
        # log(f"GPU Adquirida: {label}", "debug")
        try:
            yield
        finally:
            # log(f"GPU Liberada: {label}", "debug")
            pass
