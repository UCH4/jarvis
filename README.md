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

## Instalación (Mac M4 Pro)

Para que Jarvis funcione al 100% en tu Mac M4 Pro con la arquitectura nativa (ARM), ejecutá este comando:

```bash
python3 -m pip install --break-system-packages flask flask-cors requests beautifulsoup4 chromadb pymupdf huey watchdog
```

### 🧠 Cerebros Requeridos (Ollama)

Necesitás tener estos modelos instalados en Ollama para que el sistema funcione:

```bash
ollama pull llama3.1          # Chat y razonamiento (8b)
ollama pull llama3.2-vision   # OCR de fórmulas matemáticas
ollama pull nomic-embed-text  # Embeddings del vault (RAG)
```

### 📡 Acceso Remoto (Opcional)

Si vas a usar el flag `--tunnel` para acceder desde fuera de tu casa:

```bash
brew install cloudflared
```

## Uso

```bash
# Servidor web + túnel remoto (acceso desde cualquier red)
python3 jarvis_scanner.py --tunnel

# Solo servidor web (red local)
python3 jarvis_scanner.py

# Scan directo desde terminal
python3 jarvis_scanner.py --scan /ruta/pdfs --vault /ruta/vault

# Modo CLI interactivo
python3 jarvis_scanner.py --cli
```

## Stack Tecnológico

| Componente       | Tecnología                             |
|------------------|----------------------------------------|
| Backend          | Python 3.12 + Flask                    |
| IA Razonamiento  | Ollama (llama3.1)                      |
| IA Visión (OCR)  | Ollama (llama3.2-vision)               |
| Embeddings       | nomic-embed-text                       |
| RAG Avanzado     | HyDE + Multi-Query + LLM Reranking     |
| Base Vectorial   | ChromaDB                               |
| Acceso remoto    | Cloudflare Tunnel                      |
| Fórmulas en UI   | MathJax 3                              |

## Variables de Entorno (opcional)

```bash
export JARVIS_MODEL="qwen2.5:14b"        # Modelo de análisis
export JARVIS_EMBED="nomic-embed-text"   # Modelo de embeddings
export JARVIS_PORT="5001"                # Puerto del servidor
export JARVIS_DUP_THRESHOLD="0.92"       # Umbral de duplicados
export OLLAMA_URL="http://localhost:11434"
```
