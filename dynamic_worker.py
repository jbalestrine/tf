import os
import sys
import socket
import traceback
from flask import Flask, jsonify, request
from llama_cpp import Llama  # Natively communicates with GGUF weights

# Force absolute system directory matching
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CURRENT_MODEL_PATH = os.path.join(SCRIPT_DIR, 'models', 'mistral-7b-instruct-v0.1-q4_k_m.gguf')

class EchoChatBot:
    def __init__(self, training_store=None):
        self.conversation_history = {}
        self.model_path = CURRENT_MODEL_PATH
    def set_local_model(self, path):
        pass
    def chat(self, user_message, session_id):
        return {"response": "Tracked"}

app = Flask(__name__)
worker_bot = EchoChatBot()

# This global variable will hold our running model weights structure in memory
llm_instance = None

def load_local_llm(model_path):
    """Loads the mistral model file using conservative defaults for Windows stability."""
    global llm_instance
    if llm_instance is None:
        print(f"📦 Initializing Mistral weights into memory from: {model_path}...")
        # Stripped thread locks to allow the underlying C++ to auto-optimize hardware
        llm_instance = Llama(
            model_path=model_path,
            verbose=False
        )
    return llm_instance

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json() or {}
    prompt = data.get('prompt', '')
    max_tokens = int(data.get('max_tokens', 64)) 
    temperature = float(data.get('temperature', 0.7))

    try:
        # Load or retrieve active model weights mapping
        model = load_local_llm(CURRENT_MODEL_PATH)
        
        print(f"🧠 Mistral LLM is processing generation arrays...")
        output = model(
            prompt=f"<s>[INST] {prompt} [/INST]", 
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["</s>", "[INST]"]              
        )
        
        # 🟢 VERIFIED OPENAI-COMPLIANT DICTIONARY PARSING KEY
        # Notice index [0] is added here to accurately strip the selection block array
        text_output = output['choices'][0]['text'].strip()
        
        if not text_output:
            text_output = "Mistral execution processed, but generated token frames were empty."
            
        return jsonify({"text": text_output})

    except Exception as e:
        error_log_path = os.path.join(SCRIPT_DIR, "worker_error.txt")
        with open(error_log_path, "w", buffering=1) as error_file:
            traceback.print_exc(file=error_file)
            error_file.flush()
        return jsonify({"error": "Internal inference tokenization failure", "details": str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(CURRENT_MODEL_PATH):
        print(f"❌ Error: Mistral binary asset missing at {CURRENT_MODEL_PATH}")
        sys.exit(1)
    
    # Secure an open port on the host network layer
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    random_port = s.getsockname()[1]
    s.close()
    
    print(f"LLM Dynamic Worker Online -> http://localhost:{random_port}")
    app.run(host='127.0.0.1', port=random_port, debug=False)
