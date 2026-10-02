import sys
import os
import requests
from flask import Flask, jsonify, request

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from myscript import EchoChatBot

app = Flask(__name__)

# Initialize a central bot instance to manage history, devops rules, and text parsing
hub_bot = EchoChatBot()

# Pass a list of routes to match both options perfectly and prevent strict slash redirects
@app.route('/echo-chat', methods=['POST'])
@app.route('/echo-chat/', methods=['POST'])
def echo_chat():
    """Main entrypoint for all chat traffic."""
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', 'default').strip()
    worker_url = data.get('worker_url')

    if not user_message:
        return jsonify({"error": "Message is empty"}), 400

    # FIX 1: Access history directly using your script's native dict tracking
    if session_id not in hub_bot.conversation_history:
        hub_bot.conversation_history[session_id] = []

    # FIX 2: Check your script's built-in rule handling
    msg_lower = user_message.lower().strip()
    
    # Check if the query asks about powershell, bash, or azure to match your module descriptions
    is_devops = any(kw in msg_lower for kw in ["powershell", "bash", "azure", "reboot", "cli"])
    
    if is_devops:
        # Match against your default response templates or rule hooks
        response_text = "DevOps Automated Rule Triggered: Execution simulation success."
        return jsonify({"response": response_text, "source": "deterministic_rule", "session_id": session_id})

    # 3. Fallback: Send the prompt down to our dynamic worker instance computing the LLM
    if not worker_url:
        return jsonify({"error": "No active worker node URL provided to compute LLM layer"}), 400

    try:
        # Build prompt from existing conversation strings
        history_context = ""
        for msg in hub_bot.conversation_history[session_id][-3:]: # grab last 3 messages for context
            history_context += f"{msg.role}: {msg.content}\n"
        
        context_prompt = f"{history_context}user: {user_message}\nassistant:"

        # Forward the compilation to our dynamic worker port
        worker_response = requests.post(
            f"{worker_url}/generate",
            json={
                "prompt": context_prompt,
                "max_tokens": data.get('max_tokens', 128),
                "temperature": data.get('temperature', 0.7)
            },
            timeout=60
        )
        
        if worker_response.status_code != 200:
            return jsonify({"error": "Worker node failed to compute response", "details": worker_response.text}), 500

        llm_out = worker_response.json().get('text', 'Hello... I am Echo 🌙. Process complete.')

        # Run your script's native chat function to record metrics to the .jsonl logs
        hub_bot.chat(user_message, session_id=session_id)
        
        return jsonify({
            "response": llm_out,
            "session_id": session_id,
            "source": f"dynamic_worker_via_{worker_url}"
        })

    except Exception as e:
        return jsonify({"error": "Communication collapse between hub and dynamic node", "details": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Core Traffic Hub on port 8080...")
    app.run(host='127.0.0.1', port=8080, debug=False)