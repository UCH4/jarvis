# 🧠 Jarvis Academic Agent — Vault Architect & Knowledge Engine

Sistema Agente Académico Local que transforma PDFs y apuntes en un Grafo de Conocimiento estructurado en Obsidian. Optimizado específicamente para hardware Apple Silicon (Mac M4 Pro).

## 🚀 Características Principales (Jarvis Final Stable)

- **🔄 Ciclo de Agente Autónomo (ReAct):** Jarvis no solo busca, sino que actúa. Puede crear notas (`create_vault_note`), editar contenidos existentes (`edit_vault_note`) y navegar el vault (`list_vault_notes`) para generar vínculos automáticos `[[WikiLinks]]`.
- **⚡ Inferencia MLX Nativa:** Motor de texto y reranking optimizado para Apple Silicon usando el framework MLX. Inferencia de baja latencia aprovechando la Memoria Unificada.
- **🛡️ GPU Shield (Estabilidad):** Gestor de bloqueo de hardware que coordina MLX y Ollama. Previene crashes de Metal y saturación de hardware en tareas intensas.
- **📚 Modo "La Biblia" (RAG+):** Priorización absoluta de textos fundacionales y metodológicos usando el tag `#biblia`.
- **👁️ Visión OCR Dinámica:** Detección inteligente de fórmulas matemáticas y contenido gráfico usando `llama3.2-vision` solo cuando es necesario.
- **🔍 RAG+ Avanzado:**
  - **Multi-Query & HyDE:** Expansión de consultas para mayor precisión semántica.
  - **Listwise Reranking:** Evaluación de relevancia por lotes en una sola pasada de inferencia.
  - **Búsqueda Híbrida:** Fusión de BM25 (palabras clave) y Embeddings (semántica).

## 📁 Estructura del Proyecto

```
jarvis/
├── agents/             ← Agentes especializados (Rerank, etc)
├── api/                ← Endpoints REST para el Dashboard
├── core/               ← Motor central
│   ├── gpu.py          ← [NUEVO] Escudo de Hardware Metal
│   ├── mlx_inference.py← [NUEVO] Motor MLX nativo
│   ├── ollama.py       ← Integración con Ollama (Vision/Embeds)
│   ├── tools.py        ← Herramientas del Agente (Crear/Editar/Vincular)
│   └── scanner.py      ← Pipeline de procesamiento
├── static/ & dashboard.html ← Interfaz de usuario
└── jarvis_scanner.py   ← Punto de entrada principal
```

## 🛠️ Requisitos e Instalación

Para Mac M4 Pro con arquitectura ARM:

```bash
# Entorno y Dependencias
python3 -m venv venv_pro
source venv_pro/bin/activate
pip install mlx-lm requests flask flask-cors chromadb pymupdf watchdog
```

### 📡 Modelos Recomendados
- **Razonamiento/Chat:** `llama3.1:8b` (Ollama) o `mlx-community/Meta-Llama-3.1-8B-Instruct-8bit`.
- **Visión:** `llama3.2-vision:latest`.
- **Embeddings:** `nomic-embed-text`.

## 📡 Uso

```bash
# Modo Dashboard (Web + Chat)
python jarvis_scanner.py

# Scan directo desde terminal
python jarvis_scanner.py --scan /ruta/pdfs --vault /ruta/vault
```

## 📜 Licencia
Uso académico y personal. Desarrollado por Jarvis AI Team.
