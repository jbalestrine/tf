import sys
import os
from flask import Flask, jsonify, request

# Ensure Python can look in the current folder for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the core classes from your script directly, bypassing the singleton helper
from myscript import EchoChatBot, TrainingDataStore, ResponseQuality

app = Flask(__name__)

# A container to track and keep separate bot instances active in memory
# Key: Instance identifier (e.g., system_id, environment, or bot role)
bot_instances = {}

def get_or_create_bot_instance(instance_id: str) -> EchoChatBot:
    """Dynamically initializes and caches separate bot instances."""
    if instance_id not in bot_instances:
        # Step A: Optional isolation of storage locations per instance
        # This keeps files like 'training_examples.jsonl' segregated.
        custom_storage_path = os.path.join(
            os.path.dirname(__file__), "data", f"training_{instance_id}"
        )
        custom_store = TrainingDataStore(storage_path=custom_storage_path)
        
        # Step B: Instantiate a distinct, dedicated chatbot context
        bot_instances[instance_id] = EchoChatBot(training_store=custom_store)
        
        # Step C: Assign a default local model to the instance if it exists
        preferred_model = os.path.join(os.getcwd(), 'models', 'Phi-3-mini-4k-instruct-q4.gguf')
        if os.path.exists(preferred_model):
            bot_instances[instance_id].set_local_model(preferred_model)
            
    return bot_instances[instance_id]


@app.route('/echo-chat', methods=['POST'])
def echo_chat():
    """
    Communicates directly with specific EchoChatBot instances.
    
    Expects JSON payload:
    {
        "instance_id": "production-bot-1",  # Uniquely tracks the target instance context
        "message": "check date in powershell",
        "session_id": "user-session-abc"     # Passed inside the instance for thread history
    }
    """
    data = request.get_json() or {}
    
    # 1. Capture payload attributes
    instance_id = data.get('instance_id', 'default_global_instance').strip()
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', 'default_session').strip()
    
    # Optional parameters your script natively accepts via chat()
    temp = float(data.get('temperature', 0.7))
    max_tk = int(data.get('max_tokens', 256))
    
    if not user_message:
        return jsonify({"error": "Message body cannot be blank"}), 400

    try:
        # 2. Retrieve or generate the fully isolated chatbot object instance
        active_bot = get_or_create_bot_instance(instance_id)
        
        # 3. Call the internal script execution thread matching your class signature
        reply_payload = active_bot.chat(
            user_message=user_message,
            session_id=session_id,
            temperature=temp,
            max_tokens=max_tk
        )
        
        # 4. Inject structural context so your clients know who answered
        reply_payload['instance_id'] = instance_id
        
        return jsonify(reply_payload)
        
    except Exception as e:
        return jsonify({
            "error": "Execution routine failed inside target instance context",
            "details": str(e)
        }), 500


@app.route('/echo-chat/stats/<instance_id>', methods=['GET'])
def get_instance_stats(instance_id):
    """Retrieve isolated metrics specific to a single instance."""
    if instance_id not in bot_instances:
        return jsonify({"error": f"Instance '{instance_id}' has not been initialized yet"}), 404
        
    active_bot = bot_instances[instance_id]
    return jsonify({
        "instance_id": instance_id,
        "stats": active_bot.get_training_stats()
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
