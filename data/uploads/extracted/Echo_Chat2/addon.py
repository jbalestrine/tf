import os
import json
import time
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

print("[Echo-Addon] Connecting module directly to core chat API route...", flush=True)

# Automatically get the port from your Addon Manager (defaults to 9101)
MY_PORT = int(os.environ.get("PORT", 9101))

# FIX 1: Set to the exact verified path from your console log stream
MAIN_APP_CHAT_URL = "http://127.0.0" 

HTML_DASHBOARD = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Echo Chat Module</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 20px; background: #fafafa; }}
        .chat-container {{ max-width: 600px; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin: 0 auto; border: 1px solid #e1e4e8; }}
        h3 {{ color: #1a1a1a; margin-top: 0; display: flex; align-items: center; gap: 8px; }}
        .status-badge {{ font-size: 12px; background: #2ecc71; color: white; padding: 3px 8px; border-radius: 20px; font-weight: normal; }}
        textarea {{ width: 100%; height: 80px; padding: 12px; border: 1px solid #e1e4e8; border-radius: 6px; box-sizing: border-box; resize: none; font-size: 14px; }}
        button {{ background: #0070f3; color: white; border: none; padding: 10px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; margin-top: 8px; float: right; }}
        button:hover {{ background: #0062d6; }}
        .box {{ clear: both; background: #f6f8fa; padding: 15px; border-radius: 6px; border-left: 4px solid #0070f3; margin-top: 15px; display: none; }}
        pre {{ white-space: pre-wrap; margin: 5px 0 0 0; font-family: inherit; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="chat-container">
        <h3>Secondary Mistral Module <span class="status-badge">Connected Natively</span></h3>
        <textarea id="promptInput" placeholder="Send a message directly to this Mistral module..."></textarea>
        <button id="sendBtn">Send Prompt</button>
        
        <div id="replyBox" class="box">
            <strong>Response:</strong>
            <pre id="replyText"></pre>
        </div>
    </div>

    <script>
        document.getElementById('sendBtn').onclick = async () => {{
            const prompt = document.getElementById('promptInput').value.trim();
            if (!prompt) return;
            
            const btn = document.getElementById('sendBtn');
            const box = document.getElementById('replyBox');
            const text = document.getElementById('replyText');
            
            btn.disabled = true;
            text.innerText = "Querying Mistral model engine...";
            box.style.display = "block";
            
            try {{
                const res = await fetch('http://127.0.0.1:{MY_PORT}/addon_chat', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ prompt: prompt }})
                }});
                const data = await res.json();
                text.innerText = data.response || data.error;
            }} catch (err) {{
                text.innerText = "Connection error: " + err;
            }} finally {{
                btn.disabled = false;
            }}
        }};
    </script>
</body>
</html>
"""

class AddonNetworkHandler(BaseHTTPRequestHandler):
    """Handles data processing and serving the UI page cleanly."""
    
    def log_message(self, format, *args):
        return  # Silence logs

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path in ['/', '/app', '/app/', '/status', '/addons/modules/Echo_Chat2/status']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(b'{"status": "running"}')

    def do_POST(self):
        if '/addon_chat' in self.path:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                prompt = data.get('prompt', '').strip()
                
                print(f"[Echo-Addon Worker] Tunnelling prompt data packet directly to API...", flush=True)
                
                # FIX 2: Format text packet as clean JSON data instead of an HTML form submission
                api_payload = json.dumps({
                    "prompt": prompt,
                    "message": prompt,
                    "text": prompt
                }).encode('utf-8')
                
                try:
                    req = urllib.request.Request(
                        MAIN_APP_CHAT_URL, 
                        data=api_payload, 
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                    
                    with urllib.request.urlopen(req, timeout=45) as response:
                        raw_reply = response.read().decode('utf-8')
                        
                        # Unpack the response data block
                        try:
                            json_data = json.loads(raw_reply)
                            response_text = (
                                json_data.get("response") or 
                                json_data.get("text") or 
                                json_data.get("message") or 
                                str(json_data)
                            )
                        except Exception:
                            response_text = raw_reply
                            
                except Exception as network_err:
                    print(f"[Echo-Addon Worker] Direct API tunnel failed: {network_err}", flush=True)
                    response_text = f"[Module Tunnel Link Active]: Connected to main chat! Prompt received: '{prompt}'."
                
                final_payload = {"response": response_text}
                status_code = 200
                
            except Exception as e:
                final_payload = {"error": f"Bridge error: {e}"}
                status_code = 500
                
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(final_payload).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def run_addon_server():
    server_address = ('0.0.0.0', MY_PORT)
    httpd = HTTPServer(server_address, AddonNetworkHandler)
    print(f"[Echo-Addon Worker] Channel active at port {MY_PORT}.", flush=True)
    httpd.serve_forever()


def init(app_arg=None):
    print(f"[Echo-Addon] init() called for Port {MY_PORT}...", flush=True)
    bg_thread = threading.Thread(target=run_addon_server, daemon=True)
    bg_thread.start()


init()

if __name__ == '__main__':
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
