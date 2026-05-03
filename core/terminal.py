"""
core/terminal.py — Ejecución segura de comandos con patrón ReAct y sandboxing básico.
"""
import subprocess
import shlex
import os
from typing import Dict, List, Tuple

BLACKlisted_COMMANDS = {
    'rm', 'mkfs', 'dd', 'shutdown', 'reboot', 'format', 'fdisk', 'parted',
    'sudo', 'su', 'chown', 'chmod', 'mv', 'wget', 'curl'
}

# Comandos de 'mv' y 'rm' permitidos solo dentro del vault si son seguros (opcional)
# Por ahora, bloqueo total de comandos destructivos.

class TerminalTool:
    def __init__(self):
        self.history = []

    def is_safe(self, command: str) -> Tuple[bool, str]:
        """Verifica si un comando es seguro según la lista negra."""
        try:
            parts = shlex.split(command)
            if not parts:
                return False, "Comando vacío"
            
            base_cmd = parts[0].lower()
            if base_cmd in BLACKlisted_COMMANDS:
                return False, f"El comando '{base_cmd}' está bloqueado por seguridad."
            
            # Bloquear redirecciones peligrosas o pipes a archivos de sistema
            if '>' in command or '>>' in command:
                if '/etc/' in command or '/var/' in command or '/usr/' in command:
                    return False, "Escritura en directorios de sistema bloqueada."
            
            return True, ""
        except Exception as e:
            return False, f"Error analizando comando: {e}"

    def execute(self, command: str) -> Dict:
        """Ejecuta un comando de forma segura."""
        safe, reason = self.is_safe(command)
        if not safe:
            return {"status": "error", "output": reason}

        try:
            from core.memory import save_terminal_command
            # Ejecución con timeout para evitar procesos colgados
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
                env={**os.environ, "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"}
            )
            
            output = result.stdout if result.returncode == 0 else result.stderr
            status = "success" if result.returncode == 0 else "error"
            
            # Guardar en memoria
            save_terminal_command(command, output, status)
            
            return {
                "status": status,
                "output": output.strip() or "(sin salida)",
                "code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "output": "Tiempo de ejecución excedido (15s)"}
        except Exception as e:
            return {"status": "error", "output": f"Error de ejecución: {e}"}

    def plan_react(self, task: str) -> str:
        """
        Lógica para el system prompt cuando el agente decide usar la terminal.
        Instruye al modelo a seguir el patrón Plan -> Action -> Observation.
        """
        return f"""Vas a ejecutar una tarea técnica: '{task}'.
Sigue estrictamente el patrón ReAct:
1. PENSAMIENTO: ¿Qué necesito hacer exactamente? ¿Qué comando es el más seguro?
2. ACCIÓN: Ejecuta un comando (solo uno a la vez).
3. OBSERVACIÓN: Lee el resultado y decide si terminaste o necesitas otro paso.

REGLAS:
- No borres archivos importantes.
- No accedas a carpetas privadas del usuario fuera de Documentos/Escritorio/Vault.
- Si fallas 3 veces en un comando, detente y pide ayuda."""
