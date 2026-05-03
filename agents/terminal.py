"""
agents/terminal.py — Agente de Terminal Seguro para Mac
"""
import subprocess
import shlex
import os
from typing import Dict, Tuple

class MacTerminalAgent:
    def __init__(self):
        # Comandos permitidos explícitamente
        self.safe_commands = ["pip", "ls", "cd", "git", "brew", "python", "python3", "cat", "grep", "ollama"]
        # Comandos prohibidos (lista negra)
        self.blacklist = ["sudo", "rm -rf /", "mkfs", "dd", "shutdown", "reboot"]

    def is_safe(self, command: str) -> Tuple[bool, str]:
        """Verifica si el comando es seguro."""
        try:
            parts = shlex.split(command)
            if not parts:
                return False, "Comando vacío"
            
            base_cmd = parts[0].lower()
            
            # Validación de seguridad básica
            if base_cmd not in self.safe_commands and not command.startswith("python"):
                return False, f"Error: El comando '{base_cmd}' no está autorizado por seguridad."
            
            # Verificar contra lista negra explícita
            for b in self.blacklist:
                if b in command.lower():
                    return False, f"Error: El comando contiene términos prohibidos ('{b}')."
            
            return True, ""
        except Exception as e:
            return False, f"Error analizando comando: {e}"

    def run_command(self, command_str: str) -> str:
        """Ejecuta el comando en zsh y formatea la respuesta para el LLM."""
        safe, reason = self.is_safe(command_str)
        if not safe:
            return reason

        try:
            # Ejecutar en zsh (Mac default)
            process = subprocess.Popen(
                ['zsh', '-c', command_str],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin"}
            )
            stdout, stderr = process.communicate(timeout=30)
            
            if process.returncode == 0:
                return f"✅ Éxito:\n{stdout}"
            else:
                # Le devolvemos el error al LLM para que pueda corregir su acción
                return f"⚠️ Error (Código {process.returncode}):\n{stderr}"
                
        except subprocess.TimeoutExpired:
            return "❌ Error: El comando excedió el tiempo límite de 30 segundos."
        except Exception as e:
            return f"❌ Fallo crítico al ejecutar el comando: {str(e)}"
