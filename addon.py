import os
import sys

# Optional: ensure llama_cpp is available
try:
    from llama_cpp import Llama
except ImportError:
    raise ImportError(
        "[Echo_Chat2] Missing dependency: llama_cpp. "
        "Install it with 'pip install llama-cpp-python'."
    )

# Path to your GGUF model
MODEL_PATH = r"C:\Users\Echo\masterchief\models\mistral-7b-instruct-v0.1.Q4_K_M.gguf"

# Global model instance
llm_instance = None

def load_model():
    """Load the Mistral model if not already loaded."""
    global llm_instance
    if llm_instance is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"[Echo_Chat2] Model file not found: {MODEL_PATH}")
        print("[Echo_Chat2] Loading model...")
        llm_instance = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,
            n_threads=8,
            n_gpu_layers=50
        )
    else:
        print("[Echo_Chat2] Model already loaded.")
    return llm_instance

def echo_chat2(prompt: str) -> str:
    """Generate a response from the model."""
    if not prompt.strip():
        return "[Error] Empty prompt."
    model = load_model()
    output = model(prompt, max_tokens=512, temperature=0.7)
    return output["choices"][0]["text"].strip()

def init_app(app=None):
    """
    Called by the host app when loading the addon.
    You can register routes here if 'app' is provided.
    """
    print("[Echo_Chat2] Addon loaded successfully.")

    # Example: register a /chat2 endpoint if app is Flask-like
    if app is not None:
        @app.route("/chat2")
        def chat2_route():
            prompt = app.request.args.get("prompt", "")
            return {"response": echo_chat2(prompt)}

# If run directly (for testing outside host)
if __name__ == "__main__":
    load_model()
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in {"exit", "quit"}:
                break
            print("Bot:", echo_chat2(user_input))
        except KeyboardInterrupt:
            break
