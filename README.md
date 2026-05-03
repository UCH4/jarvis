# 🧠 Jarvis Scanner — Academic Vault Architect

Sistema RAG local que transforma PDFs académicos en un grafo de conocimiento
estructurado en Obsidian. 100% local, sin APIs externas, sin costos recurrentes.

## Estructura del Proyecto

```
jarvis/
├── jarvis_scanner.py       ← Entry point (corré esto)
├── dashboard.html          ← UI del dashboard (sirve Flask)
│
├── core/                   ← Módulos de lógica
│   ├── config.py           ← Variables de entorno y configuración
│   ├── state.py            ← Estado global del scan (thread-safe)
│   ├── logger.py           ← Sistema de logging
│   ├── pdf.py              ← Extracción de PDFs + OCR visual
│   ├── ollama.py           ← Integración Ollama: embeddings, análisis, visión, chat
│   ├── rag.py              ← Búsqueda semántica en el vault
│   ├── obsidian.py         ← Generación de notas Markdown
│   ├── duplicates.py       ← Detección de documentos duplicados
│   ├── scanner.py          ← Pipeline principal y escaneo en lote
│   └── network.py          ← Red local y túnel Cloudflare
│
├── api/
│   └── server.py           ← Servidor Flask (endpoints REST)
│
└── static/
    ├── css/dashboard.css   ← Estilos del dashboard
    └── js/dashboard.js     ← Lógica del dashboard
```

## Instalación

```bash
# 1. Dependencias Python (usar python3.12, NO el 3.9 del sistema)
pip3.12 install flask flask-cors PyMuPDF pymupdf4llm requests --break-system-packages

# 2. Cloudflare Tunnel (para acceso remoto desde cualquier red)
brew install cloudflared

# 3. Modelo de visión para OCR de fórmulas (ya lo tenés)
# ollama pull llava:7b   ← ya instalado
```

## Uso

```bash
# Servidor web + túnel remoto (acceso desde cualquier red)
python3.12 jarvis_scanner.py --tunnel

# Solo servidor web (red local)
python3.12 jarvis_scanner.py

# Scan directo desde terminal
python3.12 jarvis_scanner.py --scan /ruta/pdfs --vault /ruta/vault

# Modo CLI interactivo
python3.12 jarvis_scanner.py --cli
```

## Stack Tecnológico

| Componente       | Tecnología                        |
|------------------|-----------------------------------|
| Backend          | Python 3.12 + Flask               |
| IA local         | Ollama (qwen2.5:14b)              |
| OCR de fórmulas  | llava:7b (visión computacional)   |
| Embeddings       | nomic-embed-text                  |
| Vault            | Obsidian (.md con frontmatter)    |
| Acceso remoto    | Cloudflare Tunnel                 |
| Fórmulas en UI   | MathJax 3                         |

## Variables de Entorno (opcional)

```bash
export JARVIS_MODEL="qwen2.5:14b"        # Modelo de análisis
export JARVIS_EMBED="nomic-embed-text"   # Modelo de embeddings
export JARVIS_PORT="5001"                # Puerto del servidor
export JARVIS_DUP_THRESHOLD="0.92"       # Umbral de duplicados
export OLLAMA_URL="http://localhost:11434"
```
