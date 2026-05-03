"""
core/network.py — Detección de red local y túnel Cloudflare
"""
import re
import shutil
import socket
import subprocess
import time

from core.logger import log

_tunnel_url     = ""
_tunnel_process = None


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_tunnel_url() -> str:
    return _tunnel_url


def start_cloudflare_tunnel(port: int) -> str:
    """
    Inicia un túnel Cloudflare que expone el servidor Flask a internet.
    Requiere: brew install cloudflared
    """
    global _tunnel_url, _tunnel_process

    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        log("cloudflared no encontrado. Instalá con: brew install cloudflared", "warn")
        return ""

    try:
        log("Iniciando túnel Cloudflare...", "action")
        proc = subprocess.Popen(
            [cloudflared, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _tunnel_process = proc
        url_re  = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")
        deadline = time.time() + 40

        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.2)
                continue
            m = url_re.search(line)
            if m:
                _tunnel_url = m.group()
                log(f"Túnel activo: {_tunnel_url}", "ok")
                return _tunnel_url

        log("No se pudo obtener la URL del túnel en 20s", "warn")
        return ""
    except Exception as e:
        log(f"Error iniciando túnel Cloudflare: {e}", "error")
        return ""
