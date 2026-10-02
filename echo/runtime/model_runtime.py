from pathlib import Path

_llm = None
_model_path = None


def load_model(model_path: str, force: bool = False, **kwargs):
    """Load a GGUF model at runtime (delayed import).

    This performs a delayed import of llama_cpp.Llama so importing
    modules that reference this file will not trigger native bindings
    loading during pytest collection.
    """
    global _llm, _model_path
    if _llm is not None:
        return _llm

    import os
    # Prevent accidental loads during pytest runs when tests set this env.
    if os.environ.get("ECHO_TESTING") and not force:
        raise RuntimeError("GGUF loading blocked during tests")

    # Delayed import.
    from llama_cpp import Llama

    p = Path(model_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"GGUF not found: {p}")

    _llm = Llama(
        model_path=str(p),
        n_ctx=kwargs.get("n_ctx", 4096),
        n_threads=kwargs.get("n_threads", 8),
        n_batch=kwargs.get("n_batch", 512),
        use_mmap=True,
        use_mlock=False,
        verbose=False,
    )
    _model_path = str(p)
    return _llm


def get_model():
    return _llm


def unload_model():
    global _llm, _model_path
    _llm = None
    _model_path = None