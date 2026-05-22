# Jarvis — Cambios, instalación y modelos recomendados

Documento único: qué se modificó, cómo instalar y qué IA conviene para cada pieza del sistema.

---

## 1. ¿Está todo listo?

Sí, en el repo están aplicadas las mejoras del plan integral: RAG condicional (FACT/CONCEPT), rerank con cross-encoder, embeddings multilingües configurables, Chroma con dimensión correcta, invalidación BM25, visión MLX opcional, Obsidian REST opcional, Nougat/Huey opcional, manuscritos (OpenCV + endpoint + dashboard), Flask en modo `threaded=True`, script de reindex.

Si algo falla en tu Mac, suele ser: falta `pip install`, modelo Ollama no descargado, o dimensión `JARVIS_EMBED_DIM` que no coincide con el embedding real.

---

## 2. Resumen de cambios por archivo

| Archivo | Cambio |
|---------|--------|
| `core/query_intent.py` | **Nuevo.** Clasifica consulta FACT vs CONCEPT (reglas + MLX opcional). |
| `core/rag.py` | HyDE y multi-query solo en modo CONCEPT; log según modo. |
| `core/hybrid_search.py` | `invalidate_bm25_index()` para forzar rebuild del índice BM25. |
| `core/reranker.py` | Rerank con **cross-encoder** (sentence-transformers) o fallback **listwise** MLX según config. |
| `core/config.py` | `bge-m3` por defecto, `EMBEDDING_DIM`, `CHROMA_COLLECTION`, `RERANK_BACKEND`, visión MLX, Obsidian REST, Nougat, `get_rerank_backend()`. |
| `core/db.py` | Fallback de vectores usa `EMBEDDING_DIM`; colección `CHROMA_COLLECTION`. |
| `core/state.py` | Defaults: `embedding_model` bge-m3, `rerank_backend` cross_encoder. |
| `core/scanner.py` | Tras indexar Chroma → invalida BM25; opcional `JARVIS_AUTO_NOUGAT` encola Nougat. |
| `core/tools.py` | Obsidian Local REST (PUT/GET) si hay URL; invalida BM25 tras indexar notas. |
| `core/pdf.py` | `JARVIS_VISION_BACKEND=mlx` usa `mlx_vlm` con fallback a Ollama. |
| `core/ollama.py` | `ocr_image_png_bytes()` para imágenes (manuscritos). |
| `core/mlx_vlm.py` | **Nuevo.** Carga modelo VLM MLX y transcribe PNG/página PDF; logs de latencia. |
| `core/ingest_heavy.py` | **Nuevo.** Heurística ingest pesado + `run_nougat_markdown()`. |
| `core/handwriting_preprocess.py` | **Nuevo.** OpenCV (grayscale, bilateral, adaptive threshold). |
| `core/markdown_guard.py` | **Nuevo.** Valida delimitadores; `guard_or_wrap_raw()` para UI segura. |
| `core/worker.py` | Tarea Huey `nougat_ingest_task`. |
| `api/server.py` | `POST /api/ingest/handwriting`, `POST /api/ingest/nougat`. |
| `dashboard.html` | Bloque “Manuscrito (foto de cuaderno)”. |
| `static/js/dashboard.js` | `uploadHandwriting()`. |
| `jarvis_scanner.py` | `threaded=True`. |
| `scripts/reindex_vault_chroma.py` | **Nuevo.** Reconstruye Chroma desde todas las `.md` del vault. |
| `requirements.txt` | `sentence-transformers`, `opencv-python-headless`. |
| `README.md` | Variables de entorno y migración de embeddings. |

---

## 3. Qué instalar

### 3.1 Python (venv recomendado)

```bash
cd /ruta/a/jarvis
python3 -m venv venv_pro
source venv_pro/bin/activate   # Windows: venv_pro\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

Dependencias ya listadas en `requirements.txt`. **Además** (según uses cada función):

```bash
# PDFs con mejor extracción (opcional, ya usado antes en el proyecto)
pip install pymupdf4llm

# Chat / texto MLX (si usás modelos HuggingFace vía mlx-lm; según tu README histórico)
pip install mlx-lm mlx
```

### 3.2 Visión en MLX (opcional)

```bash
pip install mlx-vlm
```

Variable: `JARVIS_VISION_BACKEND=mlx` y `JARVIS_MLX_VLM` con un modelo compatible (ver config).

### 3.3 Ollama (embeddings, análisis JSON, visión si no usás MLX)

Instalar [Ollama](https://ollama.com) y descargar modelos (ejemplos en la tabla de la sección 4):

```bash
ollama serve
ollama pull bge-m3
ollama pull qwen2.5:14b
ollama pull llama3.2-vision
```

Ajustá nombres a lo que realmente tengas instalado (`ollama list`).

### 3.4 Migración de embeddings (si cambiaste de modelo)

```bash
export JARVIS_CHROMA_COLLECTION=vault_notes_bge_m3
export JARVIS_EMBED=bge-m3
export JARVIS_EMBED_DIM=1024
python scripts/reindex_vault_chroma.py
```

### 3.5 Nougat (opcional, PDFs muy matemáticos)

Instalación según el proyecto oficial de Nougat; luego configurá `JARVIS_NOUGAT_CMD` si el ejecutable no se llama `nougat`. Con `JARVIS_AUTO_NOUGAT=1` el scanner puede encolar tareas Huey (el worker Huey debe estar corriendo como ya hace `jarvis_scanner.py`).

### 3.6 Obsidian Local REST API

En Obsidian: plugin **Local REST API**. En el sistema:

```bash
export JARVIS_OBSIDIAN_REST_URL="https://127.0.0.1:27124"
export JARVIS_OBSIDIAN_API_KEY="tu_api_key_del_plugin"
# Si usás certificado autofirmado:
export JARVIS_OBSIDIAN_VERIFY_TLS=0
```

---

## 4. Qué IA / modelo conviene para cada parte de Jarvis

Criterio: **Mac Apple Silicon, apuntes en español, 24 GB** — equilibrio calidad / RAM / latencia.

| Parte de Jarvis | Rol | Recomendación principal | Alternativa |
|-----------------|-----|-------------------------|-------------|
| **Embeddings (Chroma / RAG)** | Buscar trozos similares en español | **`bge-m3`** (Ollama o API compatible) | `mxbai-embed-large` multilingüe |
| **Reranking de fragmentos** | Ordenar los top-k candidatos | **`BAAI/bge-reranker-base`** (cross-encoder, ya en código) | `listwise` MLX si querés evitar torch |
| **Chat principal con vault** | Respuestas largas, herramientas, español | **Qwen 2.5** (`qwen2.5:14b` o similar en Ollama) o **Llama 3.1 8B** MLX 4-bit para velocidad | DeepSeek-R1 distill para razonamiento pesado (más lento) |
| **Clasificación / metadatos de PDF** | JSON estructurado (`analyze_content`) | Mismo **Qwen 2.5** o Llama 3.1 instruct; modelo **obediente a JSON** | Evitar modelos muy “creativos” para este paso |
| **HyDE y multi-query** | Texto corto auxiliar | **Llama 3.1 8B MLX** o modelo pequeño rápido | Ya usa `generate_text` MLX en tu código |
| **Visión PDF / fórmulas** | OCR de páginas densas en matemática | **Qwen2-VL** cuantizado en **MLX** (`JARVIS_VISION_BACKEND=mlx`) | **Llama 3.2 Vision** en Ollama (más simple de instalar) |
| **Manuscrito (foto cuaderno)** | HTR + LaTeX | Mismo VLM que arriba (**Qwen2-VL** suele ir mejor que Llama en símbolos) + preproceso OpenCV | Llama 3.2 Vision si no querés MLX |
| **PDF “biblia” / papers** | Máxima fidelidad LaTeX | **Nougat** o **Marker** (offline, pesado) | VLM como segunda opción |
| **Listwise rerank (legacy)** | Un solo JSON de scores | Llama 3.1 8B MLX | Menos eficiente que cross-encoder |

**Nota:** Para **solo español**, priorizá **Qwen 2.5 + bge-m3 + Qwen2-VL (MLX)** como trío coherente; Ollama sigue siendo útil para lo que no quieras portar a MLX.

---

## 5. Variables de entorno rápidas

```text
JARVIS_EMBED=bge-m3
JARVIS_EMBED_DIM=1024
JARVIS_CHROMA_COLLECTION=vault_notes
JARVIS_RERANK_BACKEND=cross_encoder
JARVIS_VISION_BACKEND=ollama|mlx
JARVIS_MLX_VLM=mlx-community/Qwen2-VL-2B-Instruct-4bit
JARVIS_OBSIDIAN_REST_URL=...
JARVIS_OBSIDIAN_API_KEY=...
JARVIS_AUTO_NOUGAT=0|1
```

---

## 6. Model Orchestrator (Orquestación por Subtarea)

El sistema centraliza la selección de cerebros de IA en un orquestador único (`core/model_orchestrator.py`). Esto evita la dispersión de modelos hardcodeados y garantiza que cada llamada LLM se realice con el modelo y proveedor más adecuado.

### 6.1 Matriz de Tareas y Valores por Defecto

El orquestador divide el trabajo de Jarvis en las siguientes subtareas configuradas en `core/config.py`:

| Tarea (`Task`) | Rol / Descripción | Modelo por Defecto | Proveedor | Fallback |
|---|---|---|---|---|
| `pdf_metadata` | Extrae metadatos estructurados en JSON del PDF | `qwen2.5:14b` | Ollama | Ninguno |
| `chat` | Respuestas del chat en modo RAG | `qwen2.5:14b` | Ollama | Ninguno |
| `chat_concise` | Respuestas ejecutivas y resúmenes rápidos | `gemma2:9b` | Ollama | `qwen2.5:14b` |
| `reasoning` | Razonamiento lógico avanzado y CoT | `deepseek-r1:14b` | Ollama | `qwen2.5:14b` |
| `vision` | Transcripción de PDF y manuscritos (OCR) | `mlx-community/Qwen2-VL-2B-Instruct-4bit` (o `llama3.2-vision` si es Ollama) | `mlx` o `ollama` | `llama3.2-vision` |
| `hyde` | Generación de documentos hipotéticos para RAG | `mlx-community/Meta-Llama-3.1-8B-Instruct-4bit` | `mlx` | `qwen2.5:14b` |
| `multi_query` | Expansión de consultas a sinónimos académicos | `mlx-community/Meta-Llama-3.1-8B-Instruct-4bit` | `mlx` | `qwen2.5:14b` |
| `intent_classify` | Clasifica la consulta (FACT vs CONCEPT) | `mlx-community/Meta-Llama-3.1-8B-Instruct-4bit` | `mlx` | `qwen2.5:14b` |
| `professor` | Tutoría socrática y ejercicios interactivos | `qwen2.5:14b` | Ollama | Ninguno |
| `flashcards` | Genera tarjetas de estudio en formato JSON | `gemma2:9b` | Ollama | `qwen2.5:14b` |
| `embed` | Embeddings vectoriales para Chroma | `bge-m3` | Ollama | Ninguno |
| `rerank` | Reranking final de fragmentos RAG | `BAAI/bge-reranker-base` | `cross_encoder` o `listwise` | Ninguno |

### 6.2 Prioridad en la Selección de Modelos

Cuando el sistema ejecuta una subtarea, resuelve el modelo siguiendo este orden de prioridad:
1. **User Override (Tiempo de Ejecución):** El modelo seleccionado en los dropdowns del chat.
2. **State Overrides (`state.json`):** Mapeado en la base de datos de estado `task_overrides`.
3. **Model Registry Default:** Los valores por defecto descritos en la sección 6.1.

### 6.3 Monitoreo y Verificación de Salud (Health Checks)

El dashboard cuenta con un panel en la pestaña **Configuración** llamado **Estado de Modelos por Subtarea**. Muestra en tiempo real el estado de cada modelo en la matriz:
- **`OK` (Verde):** El modelo y el motor correspondiente están disponibles y listos.
- **`FALLBACK` (Amarillo):** El modelo principal no está disponible, pero el orquestador seleccionó con éxito el fallback (ej. si `gemma2:9b` no está descargado, redirige a `qwen2.5:14b`).
- **`MISSING` (Rojo):** La librería requerida no está instalada (ej. `mlx-lm` para MLX) o el modelo de Ollama no se encuentra localmente. El panel muestra la nota explicativa con el comando de descarga exacto.

### 6.4 Auditoría de Logs Unificada

Todas las llamadas a modelos de IA escriben en el log de la terminal con el siguiente patrón:
`🧠 Orchestrator: task='nombre_tarea' -> model='nombre_modelo' (proveedor)`

---

Fin del documento. Mantener este archivo en el repo como referencia única de despliegue.
