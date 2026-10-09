import os
import sys

# Force absolute path tracking
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

print("🔄 Step 1: Testing imports from your chatbot file...")
try:
    from myscript import EchoChatBot
    print("✅ Chatbot file imported successfully!")
except Exception as e:
    print(f"❌ Failed to import myscript.py: {e}")
    sys.exit(1)

print("\n🔄 Step 2: Testing raw llama-cpp-python initialization...")
try:
    from llama_cpp import Llama
    model_path = os.path.join(SCRIPT_DIR, 'models', 'mistral-7b-instruct-v0.1-q4_k_m.gguf')
    
    print(f"📂 Looking for model file at: {model_path}")
    print(f"❓ Does file exist? {os.path.exists(model_path)}")
    
    print("\n🧠 Attempting to load Mistral weights into memory (Hold on)...")
    # This is the exact line that has been crashing
    test_llm = Llama(model_path=model_path, verbose=True) 
    print("🎉 SUCCESS! The model loaded completely into memory without crashing!")
    
except Exception as e:
    print("\n❌ CRASH DETECTED inside the C++ model loader:")
    import traceback
    traceback.print_exc()
