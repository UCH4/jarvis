import logging
from core.gpu import gpu_lock

_model = None
_tokenizer = None

def get_mlx_model():
    global _model, _tokenizer
    if _model is None:
        from core.logger import log
        log("Cargando modelo MLX en Memoria Unificada (Llama-3.1-8B-Instruct-8bit)...", "info")
        log("Si es la primera vez, se descargará el modelo (~8GB). Por favor, esperá...", "warn")
        try:
            import mlx_lm
            _model, _tokenizer = mlx_lm.load("mlx-community/Meta-Llama-3.1-8B-Instruct-8bit")
            log("✅ Modelo MLX cargado exitosamente.", "info")
        except Exception as e:
            log(f"Error cargando MLX: {e}", "error")
            raise e
    return _model, _tokenizer

def generate_chat_stream(messages, tools=None):
    """
    Genera una respuesta en stream usando MLX-LM y el chat_template del modelo.
    """
    import mlx_lm
    model, tokenizer = get_mlx_model()
    
    # Manejo de tools: Llama 3.1 soporta tools nativamente si se le inyecta el esquema adecuado,
    # pero como es un modelo instruct básico en MLX, lo mejor es inyectar un System Prompt fuerte
    # para que responda con JSON si necesita usar una tool.
    
    # Si hay tools, las inyectamos en el system prompt
    if tools:
        sys_msg = next((m for m in messages if m["role"] == "system"), None)
        tools_str = json.dumps([t["function"] for t in tools], indent=2, ensure_ascii=False)
        tool_prompt = (
            f"\n\nTIENES ACCESO A LAS SIGUIENTES HERRAMIENTAS:\n{tools_str}\n"
            "Si necesitas usar una herramienta, DEBES responder ÚNICAMENTE con un bloque JSON "
            "con este formato estricto:\n"
            "{\"name\": \"nombre_herramienta\", \"parameters\": {\"param1\": \"valor\"}}\n"
            "NO ESCRIBAS NADA MÁS."
        )
        if sys_msg:
            sys_msg["content"] += tool_prompt
        else:
            messages.insert(0, {"role": "system", "content": tool_prompt})

    with gpu_lock("MLX Chat Stream"):
        try:
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception as e:
            # Fallback si el tokenizer no soporta chat templates
            prompt = ""
            for m in messages:
                prompt += f"<|start_header_id|>{m['role']}<|end_header_id|>\n\n{m['content']}<|eot_id|>\n"
            prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"

        for chunk in mlx_lm.stream_generate(model, tokenizer, prompt, max_tokens=2048):
            yield chunk

def generate_text(prompt, max_tokens=500, temperature=0.1):
    """
    Genera texto de una sola vez (ideal para reranker, hyde, etc).
    """
    import mlx_lm
    model, tokenizer = get_mlx_model()
    
    with gpu_lock("MLX Text Gen"):
        # Intentar con 'temp' primero, luego 'temperature', luego sin nada
        try:
            return mlx_lm.generate(model, tokenizer, prompt, max_tokens=max_tokens, temp=temperature).strip()
        except TypeError:
            try:
                return mlx_lm.generate(model, tokenizer, prompt, max_tokens=max_tokens, temperature=temperature).strip()
            except TypeError:
                return mlx_lm.generate(model, tokenizer, prompt, max_tokens=max_tokens).strip()
