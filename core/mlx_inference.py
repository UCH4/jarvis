import logging
from core.gpu import gpu_lock

# Diccionario para mantener los modelos cargados en memoria
_loaded_models = {}
_loaded_tokenizers = {}

def get_mlx_model(model_name: str = "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"):
    global _loaded_models, _loaded_tokenizers
    
    if model_name not in _loaded_models:
        from core.logger import log
        log(f"Cargando modelo MLX nativo: {model_name}...", "info")
        log("Esto aprovechará la Memoria Unificada del M4 Pro. Por favor, esperá...", "warn")
        try:
            import mlx_lm
            model, tokenizer = mlx_lm.load(model_name)
            _loaded_models[model_name] = model
            _loaded_tokenizers[model_name] = tokenizer
            log(f"✅ Modelo {model_name} cargado exitosamente en MLX.", "ok")
        except Exception as e:
            log(f"Error cargando MLX ({model_name}): {e}", "error")
            # Fallback al modelo base si falla uno específico
            if model_name != "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit":
                return get_mlx_model("mlx-community/Meta-Llama-3.1-8B-Instruct-4bit")
            raise e
            
    return _loaded_models[model_name], _loaded_tokenizers[model_name]

def generate_chat_stream(messages, model_name: str = None):
    """
    Genera una respuesta en stream usando MLX-LM.
    """
    import mlx_lm
    import json
    
    # Si no se especifica, usamos el default (Llama 3.1 8B 4bit)
    target_model = model_name or "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
    model, tokenizer = get_mlx_model(target_model)
    
    with gpu_lock(f"MLX Stream ({target_model})"):
        try:
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            prompt = ""
            for m in messages:
                prompt += f"<|start_header_id|>{m['role']}<|end_header_id|>\n\n{m['content']}<|eot_id|>\n"
            prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"

        for chunk in mlx_lm.stream_generate(model, tokenizer, prompt, max_tokens=2048):
            yield chunk

def generate_text(prompt, model_name: str = None, max_tokens=500, temperature=0.1):
    """
    Genera texto de una sola vez para tareas internas (rerank, hyde).
    """
    import mlx_lm
    target_model = model_name or "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
    model, tokenizer = get_mlx_model(target_model)
    
    with gpu_lock(f"MLX Text ({target_model})"):
        try:
            # mlx_lm usa 'temp' o 'temperature' según versión
            return mlx_lm.generate(model, tokenizer, prompt, max_tokens=max_tokens, temp=temperature).strip()
        except TypeError:
            return mlx_lm.generate(model, tokenizer, prompt, max_tokens=max_tokens).strip()
