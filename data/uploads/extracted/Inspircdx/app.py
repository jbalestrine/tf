"""
Web application for Inspircdx
irc chat integration.
"""

from flask import Flask, render_template_string, jsonify, request
import json
from pathlib import Path

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "irc_config.json"

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {"server": "localhost", "port": 6667, "channels": [], "nick": "Masterchief"}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    cfg = load_config()
    return render_template_string("""
<h1>🌐 Inspircdx – IRC Integration</h1>
<p>Server: <b>{{ cfg.server }}:{{ cfg.port }}</b></p>
<p>Nick: <b>{{ cfg.nick }}</b></p>
<p>Channels: <b>{{ cfg.channels | join(', ') or '#echo' }}</b></p>
<br>
<a href="/status">📊 Status</a> &nbsp;
<a href="/config">⚙️ Config</a>
""", cfg=cfg)

# ── Add new routes below this line ────────────────────────────────────────────

@app.route('/status')
def status():
    """IRC server status"""
    cfg = load_config()
    return jsonify({
        "status": "ok",
        "server": cfg.get("server"),
        "port": cfg.get("port"),
        "nick": cfg.get("nick"),
        "channels": cfg.get("channels", [])
    })

@app.route('/config', methods=['GET', 'POST'])
def config_view():
    """View or update IRC config"""
    if request.method == 'POST':
        body = request.get_json() or {}
        cfg = load_config()
        cfg.update(body)
        save_config(cfg)
        return jsonify({"saved": True, "config": cfg})
    return jsonify(load_config())

# ── END of routes ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5050)
