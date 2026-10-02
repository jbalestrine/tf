import model_registry

class ChatBot:
    def __init__(self):
        if model_registry.llm_instance is None:
            raise RuntimeError("Model not loaded in model_registry.")
        self.llm = model_registry.llm_instance

    def chat(self, prompt: str):
        if not prompt.strip():
            return "[Error] Empty prompt."
        output = self.llm(prompt, max_tokens=512, temperature=0.7)
        return output["choices"][0]["text"].strip()
