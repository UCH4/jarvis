import subprocess
import os

def execute_mac_command(command: str) -> str:
    """Ejecuta un comando en la terminal de Mac de forma segura."""
    from agents.terminal import MacTerminalAgent
    agent = MacTerminalAgent()
    return agent.run_command(command)

def read_local_file(path: str) -> str:
    """Lee el contenido de un archivo local en la Mac."""
    try:
        real_path = os.path.expanduser(path)
        if not os.path.exists(real_path):
            return f"ERROR: El archivo en '{path}' NO existe en esta computadora. No intentes leer archivos inexistentes."
        if not os.path.isfile(real_path):
            return "ERROR: La ruta no es un archivo (posiblemente un directorio)."
        with open(real_path, 'r', encoding='utf-8') as f:
            return f.read()[:15000] # Ampliamos límite para M4 Pro
    except Exception as e:
        return f"Error al leer archivo: {e}"

def search_internet(query: str) -> str:
    """Realiza una búsqueda básica en internet usando duckduckgo LITE/HTML."""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        # User-Agent de Safari en macOS (M4 Pro style)
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"}
        
        # Intentamos con la versión lite que es más estable
        res = requests.get(f"https://duckduckgo.com/lite/?q={query}", headers=headers, timeout=15)
        if res.status_code != 200:
            res = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers, timeout=15)
            
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Selectores variados para máxima compatibilidad (DDG cambia seguido)
        results = (soup.select('.result-snippet') or 
                   soup.select('.result__snippet') or 
                   soup.select('.snippet') or 
                   soup.select('.result__body'))
        
        text_results = []
        for r in results[:10]:
            txt = r.get_text().strip()
            if len(txt) > 20:
                # Limpiar saltos de línea excesivos
                txt = " ".join(txt.split())
                text_results.append("- " + txt)
            
        if not text_results:
            # Fallback a títulos y links (a veces DDG Lite solo manda eso)
            links = soup.select('.result-link') or soup.select('.result__a') or soup.select('a.result-link')
            for l in links[:6]:
                txt = l.get_text().strip()
                if txt:
                    text_results.append("- " + txt)

        if not text_results:
            return "No se hallaron resultados externos relevantes. La búsqueda en DuckDuckGo no devolvió fragmentos legibles en este momento."
            
        return "\n".join(text_results)
    except Exception as e:
        return f"Error en búsqueda web (Mac Network): {e}"

# Esquema de herramientas para Ollama
OLLAMA_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_mac_command",
            "description": "Ejecuta un comando bash en la terminal de la Mac. Usalo para ver archivos, instalar cosas o consultar el sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "El comando bash a ejecutar (ej: 'ls -la', 'pwd', 'cat archivo.txt')"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_local_file",
            "description": "Lee el contenido de un archivo de texto en la Mac dada su ruta absoluta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Ruta absoluta del archivo (ej: '/Users/joaquin/texto.txt')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_internet",
            "description": "Busca información en internet para responder preguntas actuales o investigar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La consulta de búsqueda (ej: 'historia de la literatura argentina')"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def execute_tool(tool_call) -> str:
    """Ejecuta una tool_call de Ollama y devuelve el resultado como string."""
    name = tool_call.get("function", {}).get("name")
    args = tool_call.get("function", {}).get("arguments", {})
    
    if name == "execute_mac_command":
        return execute_mac_command(args.get("command", ""))
    elif name == "read_local_file":
        return read_local_file(args.get("path", ""))
    elif name == "search_internet":
        return search_internet(args.get("query", ""))
    else:
        return f"Error: Herramienta '{name}' desconocida."
