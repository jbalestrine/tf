import os
import sys

class ConversationMemory:
    def __init__(self, system_prompt):
        self.system_prompt = system_prompt
        self.history = []

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})

    def get_formated_context(self):
        context = [{"role": "system", "content": self.system_prompt}]
        recent_history = self.history[-10:] if len(self.history) > 10 else self.history
        context.extend(recent_history)
        return context

SYSTEM_BEHAVIOR = "You are deeply synchorized AI Companion"
model_path = r"models\mistral-7b-instruct-v0.1.Q4_K_M.gguf"

if not os.path.exists(model_path):
    print(f"Error: model missing")
    sys.exit(1)

try:
    import llama_cpp
    print("init local engine tensor")
    llama = llama_cpp.Llama(model_path=model_path, chat_format="llama-2", verbose=False)
    memory = ConversationMemory(system_prompt=SYSTEM_BEHAVIOR)
    print("Sys ready")
except ImportError:
    print("Error: llama-cpp is not installed")
    sys.exit(1)
while True:
    user_input = input("You: ").strip()
    if user_input.lower() == 'exit':
        break
    if not user_input:
        continue

    memory.add_message("user", user_input)
    payload = memory.get_formated_context()

    print("she: ", end="", flush=True)

    response = llama.create_chat_completion(messages=payload, stream=True)
    full_reply = ""
    for chunk in response:
        if 'content' in chunk['choices'][0]['delta']:
            token = chunk['choices'][0]['delta']['content']
            full_reply += token
            print(token, end="", flush=True)
    print("\n")
    memory.add_messages("assistant", full_reply)
