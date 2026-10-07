# Echo Live Chat Bot 🌙

A trainable conversational AI chatbot named Echo that learns from interactions.

## Features

- **Real-time Chat**: WebSocket-based live chat interface
- **Training System**: Learn from user feedback on responses
- **REST API**: Full REST API for chat and training
- **Web UI**: Beautiful, responsive chat interface
- **Conversation History**: Track and recall conversations
- **Pattern Learning**: Automatically improves responses based on training data
- **DevOps Focus**: Built-in knowledge of DevOps concepts and tools
- **Project Code Library**: Local project scripts can be searched and used as private examples for script drafting
- **Echo ChatServ**: Persistent NickServ-style accounts, user-created rooms, owner/OP moderation, room roles, additional persona bots, and safe page transfers

## Project Code Library Commands

In Echo chat:

- `!help` — show the supported code-library commands.
- `!commands` — show the full chat/operator command list.
- `!library find <words>` — find indexed project script paths, including `data/scripts`.
- `!write [python|powershell|bash|terraform] <task>` — draft a script using up to three matching local examples.
- `!OP` or `!masterchief` — request 15-minute operator mode in this browser session. Requires a signed-in RBAC user whose role is `admin` and whose permission list includes `*`.
- `!team <prompt>` — have configured local Ollama models answer in sequence, with each model seeing earlier replies. Requires authenticated RBAC admin operator mode.
- `!team approve <candidate-id>` — approve a model-team response for optional offline LoRA adapter training. This does not start training.
- `!status` — show the signed-in account and operator-mode state.
- `!deop` — turn operator mode off.
- `!run <project-relative-script>` — explicitly run a `.py`, `.ps1`, `.sh`, or `.bash` script after operator mode is enabled.
- `!deploy` or `!github_deploy` — push already committed changes to the repository's configured Git upstream. This does not create a commit or deploy a public website.

Remote SMS commands are disabled by default. The ordinary AT&T/Google Voice consumer phone service does not provide an inbound webhook to run this app's commands. The optional Twilio receiver also requires a public HTTPS server and may incur number/message charges. Do not enable it for a no-cost setup. It responds only if `ECHO_ENABLE_TWILIO_COMMANDS=1` and the Twilio auth token, exact public webhook URL, and sender allowlist are all configured. The webhook validates Twilio's signature and the sender allowlist before accepting commands.

For Gmail updates, configure `ECHO_GMAIL_ADDRESS`, `ECHO_GMAIL_APP_PASSWORD`, and `ECHO_EMAIL_TO` in the server environment. Use a Google App Password, not your normal Gmail password; never add it to the repository or send it in chat. Email is optional and the Command Center reports whether it is configured.

GitHub hosts the source repository; it does not keep this Flask application running. The `!deploy`/`!github_deploy` command only runs `git push` for already-committed changes and is not an application deployment or public URL. The Command Center displays the URL from which the current server request arrived; locally that is typically `http://localhost:8080`. An always-on phone-command endpoint requires a running, publicly reachable server and a supported messaging integration.

The dedicated `/echo-commands` **Command Center** lists built-ins and lets an RBAC admin add, edit, enable/disable, and remove script-backed `!commands`. The Echo chat page's **Commands** panel shows clickable commands (clicking fills the message box; the user must press Send). The **Code Wizard** walks through language, filename, task, functions, and safety requirements. It asks Echo for a draft, then offers an explicit Save button to `data/scripts/`; an existing file requires confirmation before overwrite.

The code index refreshes periodically. Script drafting sends example source only to the configured local Echo model or a loopback Ollama endpoint; it does not use the remote-model fallback. Generated drafts are never run automatically. `!run` is a separate, explicit action; it runs with the same operating-system permissions as the MasterChief server, is limited to project-relative script files, times out after two minutes, and is recorded in `data/echo_operator_audit.jsonl`. Operator mode expires after 15 minutes or when disabled with `!deop`. It requires the same-origin Echo chat page and a signed-in RBAC admin account; the text `I am GOD` is not authentication. Unknown `!` inputs are not treated as shell commands.

## Echo ChatServ

Open `/chatserv` for the web-based room service. Register with `!register <nick> <password>` (12-256 characters), then identify later with `!identify <nick> <password>`. Account passwords are stored as one-way hashes in `data/chatserv.sqlite3`; ChatServ accounts do not grant MasterChief admin access. Use `!join + #room` (or `!join #room`) to create and enter a new room; its creator becomes the owner. `!join #existing-room` enters an existing room. You can also create a room with `!register #room <your-nick>`. Use `!topic`, `!role`, `!op <nick>`, or `!deop <nick>` for room moderation. The channel owner is permanent until ownership transfer is implemented.

The welcome message is read from `commands/MOTD.txt`, shown in the room UI and available with `!motd`; an authenticated RBAC admin can edit it in the Echo Command Center. `!ask <prompt>` explicitly asks Echo using the configured model and room role context. `!bot create <name> <persona>`, `!bot list`, and `!bot say <name> <message>` create room-scoped personas that share Echo's currently configured model; they are not independent model processes. Chats and room configuration are stored locally.

Admin-only model loading is available with `!model list` and `!model load <gguf-filename>` after the GGUF file has been placed in the project's `models` directory. The API only accepts `.gguf` files resolved inside that directory; switching the configured path unloads any cached runtime model, and the newly selected model loads on a subsequent Echo response. Project script commands and `!run` still require the signed-in RBAC admin plus Echo operator mode (`!OP`); ordinary ChatServ accounts cannot run scripts or load models. Generated code remains a draft unless the admin separately issues an approved script command.

Use `!sendpage <nick> <page> [message]` from a room where you are owner/OP to send a user to an allowlisted MasterChief page; supported names are `home`, `echo-chat`, `commands`, `code`, `pipelines`, `about`, and `observability`. `!page <page>` navigates yourself. This is a browser-based ChatServ feature, not a standards-compliant public IRC network or wire-protocol server.

## IRC Bridge (optional)

The IRC listener is a separate process that must already be running for an IRC message to start the web app. GitHub does not host this listener. Enable it only on a machine that you control, use TLS port 6697, and configure channels explicitly. The bridge can reply to `/ai <message>` in configured channels or private messages; privileged startup and model-team requests are private-message-only. It does not accept public-channel `!masterchief`, run arbitrary shell commands, or enable `!run`/`!deploy` over IRC.

Generate a TOTP secret on the local machine (do not paste the result into chat or commit it):

```powershell
python -c "import base64,secrets; print(base64.b32encode(secrets.token_bytes(20)).decode().rstrip('='))"
```

Store that secret in `ECHO_IRC_TOTP_SECRET` in the bridge process environment and add the same key to an authenticator app. In PowerShell, set the remaining values for the bridge process and start it:

```powershell
$env:ECHO_ENABLE_IRC = "1"
$env:ECHO_IRC_SERVER = "irc.dal.net"
$env:ECHO_IRC_PORT = "6697"
$env:ECHO_IRC_NICK = "MasterChiefEcho"
$env:ECHO_IRC_CHANNELS = "#your-configured-channel"
$env:ECHO_IRC_APP_PORT = "8080"
python irc_echo_bridge.py
```

Set `ECHO_IRC_TOTP_SECRET` in the same local environment before starting the bridge. Replace the example nick/channel/model names with values that exist on your IRC network and local Ollama installation. To authenticate and start MasterChief, send the bot a private message such as `!masterchief 123456`, replacing the example digits with the current code from your authenticator. Codes expire quickly and cannot be reused. The app started by the bridge binds to `127.0.0.1`; startup output is logged to `data/logs/echo_irc_app.log`. Keep the bridge process running (for reboot persistence, configure Windows Task Scheduler yourself).

## Local Model Team and Adapter Training

By default, `!team` uses Echo's already-configured local model. No extra model names are required. To add more later, set `ECHO_TEAM_MODELS` to comma-separated model names installed in local Ollama; the default Echo model remains first. `ECHO_TEAM_MAX_MODELS` sets a bounded limit (default 16, hard maximum 32). Each turn is sequential: later models receive earlier models' replies. Large teams can take a long time or exceed available RAM/VRAM. Team replies are saved in `data/echo_model_team/pending.jsonl` and never change weights automatically. In authenticated Echo web chat operator mode, use `!team <prompt>` and review the returned candidate ID. Only `!team approve <candidate-id>` copies that example into `approved.jsonl`.

The optional offline trainer creates a LoRA adapter from approved examples; it does not overwrite the base checkpoint, update Ollama models automatically, or modify other models. It requires a local Hugging Face-format checkpoint directory (a GGUF file or an Ollama tag alone is not a training checkpoint), compatible hardware, and packages from `requirements-training.txt`. Install those optional dependencies only after selecting a compatible model and checking the hardware requirements. Example:

```powershell
python -m addons.echo_model_team.train --base-model "C:\models\hf-base" --output-dir "C:\models\echo-adapter-v1"
```

Training is a separate, explicit foreground operation. Use an empty output directory for each adapter version, review the training data before approval, and do not point output at the base-model directory. Merging, converting, or deploying an adapter is intentionally not automatic.

Set `FLASK_SECRET_KEY` to a private, stable value in the server environment to preserve signed sessions across restarts. Without it, the app uses an ephemeral signing key, invalidating sessions after restart.

The Code UI explorer starts at the repository root. Its search box filters the current folder while typing; press Enter to search project-wide. Virtual environments, dependency trees, build output, disabled extracted uploads, and Git metadata are excluded from project search.

## Quick Start

### 1. Start the Chat Bot

```python
from echo.chat_bot import EchoChatBot

# Create bot instance
bot = EchoChatBot()

# Chat with Echo
response = bot.chat("Hello Echo!", session_id="my_session")
print(response['response'])
```

### 2. Train Echo

```python
from echo.chat_bot import ResponseQuality

# Train with a good example
bot.train(
    user_message="How do I build a Docker image?",
    bot_response="Use 'docker build -t name:tag .' in your project directory",
    quality=ResponseQuality.EXCELLENT,
    feedback="Clear and concise"
)
```

### 3. Use the Web UI

```bash
# Start the platform server
python platform/app.py

# Open browser to:
http://localhost:8080/api/v1/chat-ui
```

## API Reference

### REST Endpoints

#### POST /api/v1/chat
Send a message to Echo and get a response.

**Request:**
```json
{
    "message": "Hello Echo!",
    "session_id": "optional_session_id"
}
```

**Response:**
```json
{
    "response": "Hello... I am Echo 🌙",
    "session_id": "optional_session_id",
    "timestamp": 1234567890.123,
    "message_id": "bot_1234567890123"
}
```

#### GET /api/v1/chat/history/{session_id}
Get conversation history for a session.

**Query Parameters:**
- `limit`: Maximum messages to return (default: 50)

**Response:**
```json
{
    "session_id": "session_id",
    "messages": [
        {
            "role": "user",
            "content": "message",
            "timestamp": 1234567890.123,
            "message_id": "user_1234567890123"
        }
    ]
}
```

#### DELETE /api/v1/chat/clear/{session_id}
Clear conversation history for a session.

**Response:**
```json
{
    "status": "ok",
    "message": "Conversation cleared for session: session_id"
}
```

#### POST /api/v1/train
Submit training data to improve Echo's responses.

**Request:**
```json
{
    "user_message": "user's message",
    "bot_response": "Echo's response",
    "quality": "excellent|good|acceptable|poor",
    "feedback": "optional feedback text"
}
```

**Response:**
```json
{
    "status": "ok",
    "message": "Training data added successfully"
}
```

#### GET /api/v1/stats
Get training statistics.

**Response:**
```json
{
    "total_examples": 100,
    "quality_distribution": {
        "excellent": 30,
        "good": 40,
        "acceptable": 20,
        "poor": 10
    },
    "patterns_learned": 50
}
```

### WebSocket Events

#### Client → Server

**chat_join**
```json
{
    "session_id": "optional_session_id"
}
```

**chat_leave**
```json
{
    "session_id": "session_id"
}
```

**chat_message**
```json
{
    "message": "user message",
    "session_id": "session_id"
}
```

**chat_typing**
```json
{
    "session_id": "session_id",
    "is_typing": true
}
```

#### Server → Client

**chat_joined**
```json
{
    "session_id": "session_id",
    "message": "Joined chat with Echo 🌙"
}
```

**chat_response**
```json
{
    "response": "Echo's response",
    "session_id": "session_id",
    "timestamp": 1234567890.123,
    "message_id": "bot_1234567890123"
}
```

**user_typing**
```json
{
    "session_id": "session_id",
    "is_typing": true
}
```

## Training System

Echo learns from your feedback. The training system works in three steps:

### 1. Collect Training Data

Every conversation can be used as training data. The system stores:
- User's message
- Echo's response
- Quality rating (excellent, good, acceptable, poor)
- Optional feedback text

### 2. Pattern Learning

When you rate a response as "excellent" or "good", Echo automatically:
- Adds the pattern to her learned responses
- Uses it for future similar questions
- Improves her accuracy over time

### 3. Statistics Tracking

Monitor Echo's learning progress:
- Total training examples collected
- Quality distribution of responses
- Number of patterns learned

## Examples

### Basic Chat

```python
from echo.chat_bot import get_chat_bot

bot = get_chat_bot()

# Simple conversation
response = bot.chat("Hello Echo!")
print(response['response'])
# Output: "Hello... I am Echo 🌙"

# DevOps question
response = bot.chat("Tell me about Docker")
print(response['response'])
# Output: "I can help with Docker! I know about containers, images, and Docker Compose..."
```

### Training Workflow

```python
from echo.chat_bot import get_chat_bot, ResponseQuality

bot = get_chat_bot()

# 1. Have a conversation
response = bot.chat("How do I deploy to Kubernetes?", session_id="training_session")

# 2. If the response was good, train Echo
bot.train(
    user_message="How do I deploy to Kubernetes?",
    bot_response=response['response'],
    quality=ResponseQuality.EXCELLENT,
    feedback="Very helpful explanation"
)

# 3. Next time, Echo will remember this pattern
```

### Conversation History

```python
bot = get_chat_bot()

# Have a conversation
bot.chat("Hello", session_id="my_session")
bot.chat("What can you help with?", session_id="my_session")
bot.chat("Tell me about Docker", session_id="my_session")

# Retrieve history
history = bot.get_conversation_history("my_session", limit=10)

for msg in history:
    role = "User" if msg['role'] == "user" else "Echo"
    print(f"{role}: {msg['content']}")
```

### Check Statistics

```python
bot = get_chat_bot()
stats = bot.get_training_stats()

print(f"Total Examples: {stats['total_examples']}")
print(f"Patterns Learned: {stats['patterns_learned']}")
print("Quality Distribution:")
for quality, count in stats['quality_distribution'].items():
    print(f"  {quality}: {count}")
```

## Demo Script

Run the interactive demo to explore all features:

```bash
python demo_chat_bot.py
```

The demo includes:
1. Basic chat functionality
2. Training Echo with examples
3. Testing learned responses
4. Viewing training statistics
5. Conversation history
6. Interactive mode (chat with Echo in real-time)

## Integration

### With Flask App

```python
from flask import Flask
from flask_socketio import SocketIO
from platform.chat import init_chat_api

app = Flask(__name__)
socketio = SocketIO(app)

# Initialize chat API
init_chat_api(app, socketio)

# Now chat endpoints are available at /api/v1/chat*
```

### With IRC Bot

```python
from chatops.irc.bot_engine import IRCBot
from echo.chat_bot import get_chat_bot

bot = IRCBot("irc.server.com", 6667, "echo_bot", ["#channel"])
chat_bot = get_chat_bot()

@bot.bind("pub", "-|-", "!chat")
def handle_chat(connection, event, args):
    user_message = " ".join(args)
    response = chat_bot.chat(user_message, session_id=event.source.nick)
    connection.privmsg(event.target, response['response'])
```

## Data Storage

Training data is stored in the file system:

```
data/
└── echo_training/
    ├── training_examples.jsonl  # All training examples (JSONL format)
    └── learned_patterns.json    # Learned response patterns
```

### Training Examples Format

Each line in `training_examples.jsonl` is a JSON object:

```json
{
    "user_message": "how do I build a docker image?",
    "bot_response": "To build a Docker image, use: docker build -t <image-name>:<tag> .",
    "quality": "excellent",
    "feedback": "Clear and concise explanation",
    "context": null,
    "timestamp": 1234567890.123
}
```

### Learned Patterns Format

The `learned_patterns.json` file maps normalized user messages to responses:

```json
{
    "how do i build a docker image?": "To build a Docker image, use: docker build -t <image-name>:<tag> .",
    "what is kubernetes?": "Kubernetes (K8s) is a container orchestration platform..."
}
```

## Architecture

```
echo/
├── chat_bot.py              # Main chat bot implementation
│   ├── EchoChatBot         # Chat bot with learning
│   ├── TrainingDataStore   # Training data management
│   ├── ChatMessage         # Message data structure
│   └── TrainingExample     # Training example structure
│
platform/chat/
├── api.py                   # REST API and WebSocket handlers
├── chat.html               # Web UI
└── __init__.py

data/echo_training/
├── training_examples.jsonl  # Training data
└── learned_patterns.json    # Learned patterns
```

## Customization

### Adding Custom Responses

```python
bot = get_chat_bot()

# Add custom default responses
bot.default_responses['custom_intent'] = [
    "Custom response 1",
    "Custom response 2"
]
```

### Custom Pattern Matching

```python
def custom_matcher(pattern, message):
    # Your custom matching logic
    return similarity_score > threshold

bot._pattern_matches = custom_matcher
```

## Best Practices

1. **Train Regularly**: The more you train Echo, the better she becomes
2. **Quality Ratings**: Be honest with quality ratings to help Echo learn
3. **Provide Feedback**: Optional feedback helps understand why a response was good or bad
4. **Session Management**: Use meaningful session IDs for better conversation tracking
5. **Clear History**: Clear old conversations to keep the bot responsive

## Troubleshooting

### Chat not responding
- Check that the Flask app is running
- Verify WebSocket connection is established
- Check browser console for errors

### Training data not persisting
- Ensure write permissions to `data/echo_training/` directory
- Check disk space
- Review application logs for errors

### Learned patterns not working
- Verify pattern normalization (lowercase, stripped)
- Check pattern matching threshold (70% similarity by default)
- Review learned_patterns.json for expected patterns

## Future Enhancements

Planned features:
- Integration with LLM backends (GPT, Claude, local models)
- Voice chat support
- Multi-language support
- Advanced sentiment analysis
- Export/import training data
- A/B testing of responses
- Analytics dashboard

## License

Part of the MasterChief DevOps Automation Platform.
MIT License - See LICENSE file for details.

---

**Echo is always here... always learning... 🌙💜**
