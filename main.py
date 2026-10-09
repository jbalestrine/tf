#!/usr/bin/env python3

"""MasterChief Flask Web Application - All-in-One File"""

import sys
print("DEBUG: main.py is starting", file=sys.stderr)

import sys
import os
import secrets
import random

# Pre-import stdlib 'platform' before our local platform/ directory enters sys.path,
# so that third-party libraries (azure-identity, etc.) get the real stdlib module.
import platform as _stdlib_platform  # noqa: F401

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, continue without it

# Ensure script directory is not in sys.path to avoid conflicts
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir in sys.path:
    sys.path.remove(_script_dir)

# Import feature manager (before sys.path manipulation)
try:
    import sys
    import os
    _current_dir = os.getcwd()
    if _current_dir not in sys.path:
        sys.path.insert(0, _current_dir)
    from features.manager import init_feature_manager, get_feature_manager
    import importlib
    import features.manager
    importlib.reload(features.manager)
    from features.manager import init_feature_manager, get_feature_manager
    with open('debug.log', 'a') as f:
        f.write(f"DEBUG: Successfully imported init_feature_manager from features.manager, module file: {init_feature_manager.__module__}\n")
    FEATURE_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Warning: Failed to initialize feature manager: {e}")
    FEATURE_MANAGER_AVAILABLE = False

import json

import time

import difflib

import threading

import uuid

import io

import tempfile

from pathlib import Path

import psutil

import subprocess
import textwrap
import zipfile
import shutil
import shlex
import smtplib
import ssl
import html
from datetime import datetime
from email.message import EmailMessage

from werkzeug.utils import secure_filename

import base64

import hashlib

import requests
from core.roku_playlist import (
    MAX_PLAYLIST_ENTRIES,
    classify_entry as _classify_roku_entry,
    group_entries as _group_roku_entries,
    normalize_group_key as _normalize_group_key,
    parse_json_playlist as _parse_roku_json_playlist,
    parse_m3u_playlist as _parse_roku_m3u_playlist,
)
from core.roku_settings import get_roku_settings

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None

# Import our utility modules
from utils import (
    _interpreter_cmd_for_path,
    _start_cleanup_thread,
    _env_bool,
    _parse_bool_val,
    _start_output_cleanup_thread,
    get_default_model_path,
    _safe_script_path,
    load_enabled_modules
)
from utils.ide_files import resolve_project_file
from utils.code_archetypes import with_archetype_client as _with_archetype_client
from core.remote_text import is_allowed_sender, is_twilio_enabled, verify_twilio_signature
from core.site_branding import add_global_site_brand
from utils.terraform import EnterpriseTerraformGenerator
from templates.base import HTML_TEMPLATE
from templates.pages import (
    DASHBOARD_TEMPLATE,
    SCRIPTS_TEMPLATE,
    SCRIPT_VIEW_TEMPLATE,
    SCRIPT_EXECUTE_TEMPLATE,
    MODULES_TEMPLATE,
    MODULE_MANAGER_TEMPLATE
)


# Add script dir back for local imports

sys.path.insert(0, _script_dir)

from echo.chat_bot import get_chat_bot, ResponseQuality, TrainingExample

from echo.conversation_storage import get_storage

import re

from collections import Counter


from echo.identity import Echo

# Remove it again to avoid conflicts

sys.path.remove(_script_dir)

# Core authentication must not depend on optional cloud-provider SDKs.
try:
    from auth_config import auth_config
    from auth_module import init_auth, requires_permission
    AUTH_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Authentication modules not available: {e}")
    AUTH_MODULES_AVAILABLE = False

    from functools import wraps
    from flask import abort

    def requires_permission(permission):
        def decorator(f):
            @wraps(f)
            def authentication_unavailable(*args, **kwargs):
                abort(503, description='Authentication is unavailable; protected access is disabled.')
            return authentication_unavailable
        return decorator

# Cloud integrations are optional and must not disable RBAC login.
try:
    from azure_integration import azure_integration
    from github_integration import github_integration
    from app_management import app_management
except ImportError as e:
    print(f"Warning: Optional cloud integrations not available: {e}")

# Import setup wizard (works with or without auth modules)
try:
    from setup_wizard import init_setup_wizard
    SETUP_WIZARD_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Failed to initialize setup wizard: {e}")
    SETUP_WIZARD_AVAILABLE = False

# Import feature manager
try:
    print("DEBUG: About to import feature manager")
    from features.manager import init_feature_manager, get_feature_manager
    print("DEBUG: Feature manager imported successfully")
    FEATURE_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Warning: Failed to initialize feature manager: {e}")
    FEATURE_MANAGER_AVAILABLE = False

from flask import Flask, render_template, render_template_string, request, jsonify, redirect, url_for, flash, get_flashed_messages, send_file, session

from flask_cors import CORS

from flask_login import current_user, login_required

# Import TF Wizard modules
try:
    import sys
    import os
    current_dir = os.getcwd()
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from tf_wizard.generator import generate_module_zip, tf_type_from_spec
    import tf_wizard.app as tf_wizard_app
    TF_WIZARD_AVAILABLE = True
    print("SUCCESS: TF Wizard modules imported successfully")
except ImportError as e:
    print(f"WARNING: TF Wizard not available: {e}")
    TF_WIZARD_AVAILABLE = False
    import traceback
    print(f"TF Wizard import traceback: {traceback.format_exc()}")

app=Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') or secrets.token_urlsafe(48)
if not os.environ.get('FLASK_SECRET_KEY'):
    app.logger.warning('FLASK_SECRET_KEY is unset; using an ephemeral key and expiring sessions at restart')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    "supports_credentials": True,
}})

@app.after_request
def _add_cors_headers(response):
    origin = request.headers.get('Origin')
    response.headers['Access-Control-Allow-Origin'] = origin or '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, Origin, X-Requested-With'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    response = add_global_site_brand(response)
    if response.mimetype == 'text/html' and response.status_code != 304 and not response.is_streamed:
        body = response.get_data()
        modified = False
        if request.args.get('chatserv_notice') and b'id="chatserv-transfer-notice"' not in body:
            notice_text = html.escape(request.args.get('chatserv_notice', '')[:300], quote=True).encode('utf-8')
            notice = (
                b'<aside id="chatserv-transfer-notice" role="status" '
                b'style="position:fixed;z-index:99999;top:16px;right:16px;max-width:min(420px,90vw);'
                b'padding:12px 16px;border:1px solid #6d5aa6;border-radius:8px;'
                b'background:#211c32;color:#f2edff;font:14px/1.5 Segoe UI,Arial,sans-serif;'
                b'box-shadow:0 8px 24px #0008;">' + notice_text + b'</aside>'
            )
            body_start = body.lower().find(b'<body')
            insert_at = body.find(b'>', body_start) + 1 if body_start >= 0 else -1
            if insert_at > 0:
                body = body[:insert_at] + notice + body[insert_at:]
            else:
                body = notice + body
            modified = True
        if session.get('chatserv_user_id') and b'id="chatserv-transfer-monitor"' not in body:
            transfer_monitor = (
                b'<script id="chatserv-transfer-monitor">'
                b'(function(){let busy=false;async function poll(){if(busy)return;busy=true;try{'
                b'const r=await fetch("/api/chatserv/transfers/consume",{method:"POST",'
                b'credentials:"same-origin",headers:{"Content-Type":"application/json"},body:"{}"});'
                b'if(!r.ok)return;const d=await r.json();const t=(d.transfers||[])[0];if(t&&t.page){'
                b'const u=new URL(t.page,location.origin);u.searchParams.set("chatserv_notice",t.message||"Page transfer");'
                b'location.assign(u.pathname+u.search)}}catch(e){console.warn("ChatServ transfer check failed",e)}finally{busy=false}}'
                b'poll();setInterval(poll,2500)})();'
                b'</script>'
            )
            lower_body = body.lower()
            closing_body = lower_body.find(b'</body')
            if closing_body >= 0:
                body = body[:closing_body] + transfer_monitor + body[closing_body:]
            else:
                body += transfer_monitor
            modified = True
        if b'id="masterchief-site-footer"' not in body:
            footer = (
                b'<footer id="masterchief-site-footer" role="contentinfo" '
                b'style="margin-top:24px;padding:10px 16px;text-align:center;'
                b'font:12px/1.5 Segoe UI,Arial,sans-serif;color:#9ca3af;'
                b'background:#171717;border-top:1px solid #374151;">'
                b'MASTERCHIEF - ECHO STARLITE - DevOps Suite | JOSEPH BALESTRINE - 2026. | '
                b'<a href="https://linkedin.com/in/x122" target="_blank" '
                b'rel="noopener noreferrer" style="color:#8ae2a0;">'
                b'https://linkedin.com/in/x122</a></footer>'
            )
            lower_body = body.lower()
            closing_body = lower_body.find(b'</body')
            closing_html = lower_body.find(b'</html')
            insert_at = closing_body if closing_body >= 0 else closing_html
            if insert_at >= 0:
                body = body[:insert_at] + footer + body[insert_at:]
            else:
                body += footer
            modified = True
        if modified:
            response.set_data(body)
            response.headers.pop('ETag', None)
    return response


def _fetch_remote_playlist_text(url, timeout=30):
    """Fetch one HTTP(S) playlist without silently changing protocols or disabling TLS checks."""
    if not url:
        raise ValueError('Playlist URL is required')
    from urllib.parse import urlsplit

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname:
        raise ValueError('Playlist URL must use HTTP or HTTPS.')
    with requests.get(
        url,
        headers={
            'User-Agent': 'MasterChief-Roku/1.0',
            'Accept': 'application/vnd.apple.mpegurl, application/octet-stream, text/plain, */*',
        },
        timeout=(5, timeout),
        allow_redirects=True,
        stream=True,
        verify=True,
    ) as response:
        response.raise_for_status()
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > 50 * 1024 * 1024:
            raise ValueError('Playlist exceeds the 50 MiB download limit.')
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > 50 * 1024 * 1024:
                raise ValueError('Playlist exceeds the 50 MiB download limit.')
            chunks.append(chunk)
        encoding = response.encoding or 'utf-8'
        return b''.join(chunks).decode(encoding, errors='replace'), response.url

# Mount TF Wizard static files if available
if TF_WIZARD_AVAILABLE:
    from flask import send_from_directory
    import os
    tf_wizard_static = os.path.join(os.path.dirname(tf_wizard_app.__file__), 'static')
    @app.route('/tf_wizard/static/<path:filename>')
    def tf_wizard_static_files(filename):
        return send_from_directory(tf_wizard_static, filename)

app.jinja_env.filters['b64encode'] = lambda s: base64.urlsafe_b64encode(s.encode()).decode()

app.config['ADMIN_TOKEN'] = os.environ.get('ADMIN_TOKEN') or None

app.config['BASIC_AUTH_USER'] = os.environ.get('BASIC_AUTH_USER') or None

app.config['BASIC_AUTH_PASS'] = os.environ.get('BASIC_AUTH_PASS') or None

_data_dir=Path(__file__).parent/'data'

app.config['UPLOAD_FOLDER']=_data_dir/'uploads'

app.config['SCRIPTS_FOLDER']=_data_dir/'scripts'

app.config['MAX_CONTENT_LENGTH']=100*1024*1024

app.config['RBAC_DB'] = _data_dir / 'rbac.json'
app.config['VAULT_DB'] = _data_dir / 'vault.json'
app.config['VAULT_KEY'] = _data_dir / 'vault.key'
app.config['NOTIFICATIONS_DB'] = _data_dir / 'notifications.json'
app.config['NOTIFICATION_CHANNELS_DB'] = _data_dir / 'notification_channels.json'
app.config['NOTIFICATION_RULES_DB'] = _data_dir / 'notification_rules.json'
app.config['PIPELINES_DB'] = _data_dir / 'pipelines.json'
app.config['PIPELINE_RUNS_DB'] = _data_dir / 'pipeline_runs.json'
app.config['CLOUD_DB'] = _data_dir / 'cloud_accounts.json'
app.config['MARKETPLACE_DB'] = _data_dir / 'marketplace.json'
app.config['MEMORIES_PATH'] = _data_dir / 'echo_memories.jsonl'
app.config['MEMORY_INDEX_PATH'] = _data_dir / 'echo_memory_index.json'
app.config['VAULT_AUDIT_DB'] = _data_dir / 'vault_audit.json'
app.config['MODULES_CONFIG'] = _data_dir / 'modules.json'
app.config['RBAC_ENABLED'] = True

# Image generation config
app.config['IMAGE_PROVIDER'] = os.environ.get('IMAGE_PROVIDER', 'local')
app.config['IMAGE_RATE_LIMIT_PER_MIN'] = int(os.environ.get('IMAGE_RATE_LIMIT_PER_MIN', '6'))
app.config['IMAGE_CACHE_TTL'] = int(os.environ.get('IMAGE_CACHE_TTL', '86400'))

# In-memory image state (cache, rate-limiting, async job tracker)
IMAGE_CACHE = {}   # cache_key -> {'path': str, 'ts': float}
IMAGE_RATE  = {}   # rl_key   -> [timestamps]
IMAGE_JOBS  = {}   # job_id   -> {'status', 'progress', 'path', 'error'}


ENABLED_MODULES = load_enabled_modules()

@app.context_processor
def inject_ui_modules():
    """Inject pinned addon modules into every template so they appear in the nav."""
    try:
        from utils.navigation import visible_pinned_modules

        ui_modules_file = app.config['UPLOAD_FOLDER'] / 'ui_modules.json'
        if ui_modules_file.exists():
            with open(ui_modules_file, 'r') as _f:
                configured_modules = json.load(_f)
        else:
            configured_modules = {}
        return {
            'ui_modules': visible_pinned_modules(
                configured_modules, app.config['UPLOAD_FOLDER']
            )
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        app.logger.exception('Failed to load pinned add-on navigation entries')
        return {'ui_modules': {}}

for folder in [app.config['UPLOAD_FOLDER'],app.config['SCRIPTS_FOLDER'],_data_dir]:

    folder.mkdir(parents=True,exist_ok=True)


# Initialize authentication modules if available
if AUTH_MODULES_AVAILABLE:
    try:
        # Initialize authentication
        init_auth(app)

        print("SUCCESS: Authentication modules initialized successfully")
    except Exception as e:
        print(f"WARNING: Failed to initialize authentication modules: {e}")
        AUTH_MODULES_AVAILABLE = False
else:
    print("INFO: Authentication modules not available - running without authentication")

# Initialize setup wizard if available
if SETUP_WIZARD_AVAILABLE:
    try:
        init_setup_wizard(app)
        print("SUCCESS: Setup wizard initialized successfully")
    except Exception as e:
        print(f"WARNING: Failed to initialize setup wizard: {e}")
        SETUP_WIZARD_AVAILABLE = False

# Initialize feature manager if available
with open('debug.log', 'a') as f:
    f.write(f"DEBUG: Checking FEATURE_MANAGER_AVAILABLE: {FEATURE_MANAGER_AVAILABLE}\n")
if FEATURE_MANAGER_AVAILABLE:
    with open('debug.log', 'a') as f:
        f.write("DEBUG: Initializing feature manager...\n")
    try:
        init_feature_manager(app)
        with open('debug.log', 'a') as f:
            f.write("SUCCESS: Feature manager initialized successfully\n")
    except Exception as e:
        with open('debug.log', 'a') as f:
            f.write(f"WARNING: Failed to initialize feature manager: {e}\n")
        import traceback
        with open('debug.log', 'a') as f:
            f.write(f"Traceback: {traceback.format_exc()}\n")
        FEATURE_MANAGER_AVAILABLE = False

# Manually register GitHub integration routes
try:
    from features.handlers.github_integration import register_routes
    print("DEBUG: About to call register_routes", file=sys.stderr)
    register_routes(app)
    print("DEBUG: Successfully called register_routes", file=sys.stderr)
except Exception as e:
    print(f"ERROR: Failed to register GitHub routes: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
else:
    with open('debug.log', 'a') as f:
        f.write("DEBUG: Feature manager not available\n")

with open('debug.log', 'a') as f:
    f.write("DEBUG: About to init chat...\n")


# Helpers: environment boolean and generic value->bool parser

def _env_bool(name, default=False):

    v = os.environ.get(name)

    if v is None:

        return default

    return str(v).strip().lower() in ('1', 'true', 'yes', 'on')


def _parse_bool_val(v, default=None):

    if v is None:

        return default

    if isinstance(v, bool):

        return v

    try:

        s = str(v).strip().lower()

        if s in ('1', 'true', 'yes', 'on'):

            return True

        if s in ('0', 'false', 'no', 'off'):

            return False

    except Exception:

        pass

    return default


# Default for auto-continue (can be overridden by ECHO_AUTO_CONTINUE env var)

app.config['ECHO_AUTO_CONTINUE'] = _env_bool('ECHO_AUTO_CONTINUE', True)

app.config['ECHO_CONTINUE_PROMPT'] = os.environ.get('ECHO_CONTINUE_PROMPT', 'Continue the previous answer to the user\'s question. Stay strictly on that topic and do not introduce unrelated facts or change the subject.')


    # Async image job tracker: job_id -> {'status','progress','path','error'}
IMAGE_JOBS = {}


def _start_output_cleanup_thread(retention_days=None, interval_hours=24):

    retention_days = retention_days if retention_days is not None else app.config.get('ECHO_OUTPUT_RETENTION_DAYS', 30)

    def runner():

        outdir = Path(__file__).parent / 'data' / 'echo_chat_outputs'

        while True:

            try:

                if outdir.exists():

                    for p in outdir.glob('*.txt'):

                        try:

                            age_days = (time.time() - p.stat().st_mtime) / (60*60*24)

                            if age_days > retention_days:

                                p.unlink()

                        except Exception:

                            app.logger.exception('Failed to prune old echo output %s', p)

                time.sleep(interval_hours * 3600)

            except Exception:

                app.logger.exception('Echo output cleanup thread error')

                time.sleep(3600)

    t = threading.Thread(target=runner, daemon=True)

    t.start()


# start cleanup thread

try:

    _start_output_cleanup_thread()

except Exception:

    app.logger.exception('Failed to start echo output cleanup thread')


# Optionally force a default model for debugging via ECHO_FORCE_MODEL.

# If set (or the chosen fallback exists), persist it to data/echo_model.json

# so `/api/echo/preload_model` and the bot prefer this model.

try:

    forced_model = os.environ.get('ECHO_FORCE_MODEL') or None

    # sensible fallback for debugging (update if you prefer another model)

    if not forced_model:

        forced_model = str(Path.cwd() / 'models' / 'mistral-7b-instruct-v0.1.Q4_K_M.gguf')

    # resolve to absolute path

    p = Path(forced_model)

    if not p.is_absolute():

        p = Path.cwd() / p

    if p.exists():

        cfg = Path(__file__).parent / 'data' / 'echo_model.json'

        cfg.parent.mkdir(parents=True, exist_ok=True)

        cfg.write_text(json.dumps({'model': str(p)}), encoding='utf-8')

        app.logger.info(f'Forced default model set to: {p}')

    else:

        app.logger.info(f'Forced model not found, skipping: {p}')

except Exception:

    app.logger.exception('Failed to set forced default model')

# If user explicitly requests an immediate forced GGUF load, do it now.

# This bypasses the test-time guard and will load the model into memory.

try:

    if os.environ.get('ECHO_FORCE_LOAD') == '1':

        # determine model path: prefer explicit env, then persisted config

        model_path = os.environ.get('ECHO_FORCE_MODEL')

        if not model_path:

            cfg = Path(__file__).parent / 'data' / 'echo_model.json'

            if cfg.exists():

                try:

                    model_path = json.loads(cfg.read_text(encoding='utf-8')).get('model')

                except Exception:

                    model_path = None

        if model_path:

            try:

                from echo.runtime import model_runtime

                model_runtime.load_model(model_path, force=True)

                app.logger.info(f'Force-loaded GGUF model at startup: {model_path}')

            except Exception:

                app.logger.exception('Failed to force-load GGUF model')

        else:

            app.logger.warning('ECHO_FORCE_LOAD=1 but no model path found')

except Exception:

    app.logger.exception('Force model load check failed')

# Sessions index file (persistent metadata for chat sessions)


# Runtime chat/model initialization

chatbot = None


def get_default_model_path():

    cfg = Path(__file__).parent / 'data' / 'echo_model.json'

    if cfg.exists():

        try:

            return json.loads(cfg.read_text(encoding='utf-8')).get('model')

        except Exception:

            return None

    # sensible fallback (do not force existence here)

    candidate = Path.cwd() / 'models' / 'Phi-3-mini-4k-instruct-q4.gguf'

    return str(candidate) if candidate.exists() else None


def init_chat():

    """Initialize the Echo chat bot and (optionally) load the GGUF at runtime.


    Loading the heavy GGUF model is performed here so pytest collection

    and import-time operations never import native bindings.

    """

    global chatbot

    try:

        from echo.chat_bot import get_chat_bot

        from echo.runtime import model_runtime

        from echo.conversation_storage import get_storage as _get_storage

        chatbot = get_chat_bot()

        # Pre-warm conversation storage so the first API request isn't slow

        try:

            _get_storage()

        except Exception:

            app.logger.exception('Failed to pre-warm conversation storage')

        model_path = get_default_model_path()

        if model_path:

            # set the preferred model path on the bot (no load yet)

            try:

                chatbot.set_local_model(model_path)

            except Exception:

                pass

            # perform explicit runtime load of the model

            try:

                model_runtime.load_model(model_path)

                app.logger.info(f'Runtime model loaded: {model_path}')

            except Exception:

                app.logger.exception('Failed to runtime-load model')

    except Exception:

        app.logger.exception('Chat initialization failed')


    except Exception:

        return None


enterprise_tf_gen = EnterpriseTerraformGenerator(_data_dir / 'terraform_enterprise')

ENTERPRISE_TF_JOBS = {}  # job_id -> generated project path


# ---------------------------------------------------------------------------
#  Enterprise TF Wizard Routes
# ---------------------------------------------------------------------------


###############################################################################


@app.route('/api/tf/apply', methods=['POST'])
def api_tf_apply():
    data = request.get_json(silent=True) or {}
    main_tf = data.get('main', '')
    variables_tf = data.get('variables', '')
    if not main_tf:
        return jsonify({'ok': False, 'error': 'main terraform code required'}), 400
    
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'main.tf').write_text(main_tf, encoding='utf-8')
            if variables_tf:
                Path(tmpdir, 'variables.tf').write_text(variables_tf, encoding='utf-8')
            
            # Init and apply
            proc = subprocess.run(['terraform', 'init', '-input=false'], cwd=tmpdir, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return jsonify({'ok': False, 'error': proc.stderr}), 500
            
            proc = subprocess.run(['terraform', 'apply', '-auto-approve', '-input=false'], cwd=tmpdir, capture_output=True, text=True, timeout=300)
            return jsonify({'ok': True, 'output': proc.stdout + proc.stderr}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/tf/import', methods=['POST'])
def api_tf_import():
    data = request.get_json(silent=True) or {}
    address = data.get('address')
    resource_id = data.get('id')
    if not address or not resource_id:
        return jsonify({'ok': False, 'error': 'address and id required'}), 400
    
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = subprocess.run(['terraform', 'import', address, resource_id], cwd=tmpdir, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return jsonify({'ok': False, 'output': proc.stderr}), 200
            return jsonify({'ok': True, 'output': proc.stdout}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/tf/state')
def api_tf_state():
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            return jsonify({'ok': False, 'error': 'state show not implemented for demo - requires state file'}), 501
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/tf/backup')
def api_tf_backup():
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy state file for demo
            state_content = '{"version": 4, "terraform_version": "1.0.0", "resources": []}'
            Path(tmpdir, 'terraform.tfstate').write_text(state_content, encoding='utf-8')
            return send_file(Path(tmpdir, 'terraform.tfstate'), as_attachment=True, download_name='terraform.tfstate.backup')
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------  
#  Enterprise TF Wizard Routes
# ---------------------------------------------------------------------------

@app.route('/api/terraform/enterprise/generate', methods=['POST'])
def api_tf_enterprise_generate():
    try:
        config = request.get_json(silent=True) or {}
        job_id, job_record = enterprise_tf_gen.generate(config, jobs_registry=ENTERPRISE_TF_JOBS)
        return jsonify({'ok': True, 'result': {'job_id': job_id, 'download_url': f'/api/terraform/enterprise/download/{job_id}'}})
    except Exception as e:
        app.logger.exception('Enterprise TF generation failed')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/terraform/enterprise/validate', methods=['POST'])
def api_tf_enterprise_validate():
    try:
        config = request.get_json(silent=True) or {}
        issues = enterprise_tf_gen.validate(config)
        return jsonify({'ok': True, 'result': issues})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/terraform/enterprise/download/<job_id>', methods=['GET'])
def api_tf_enterprise_download(job_id):
    try:
        job = ENTERPRISE_TF_JOBS.get(job_id)
        if not job:
            return jsonify({'ok': False, 'error': 'Job not found'}), 404
        zip_path = Path(job['path'])
        if zip_path.exists():
            return send_file(str(zip_path), as_attachment=True, download_name=zip_path.name)
        return jsonify({'ok': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/terraform/enterprise/deploy_to_project', methods=['POST'])
def api_tf_enterprise_deploy_to_project():
    try:
        config = request.get_json(silent=True) or {}
        job_id, job_record = enterprise_tf_gen.generate(config, jobs_registry=ENTERPRISE_TF_JOBS)
        return jsonify({'ok': True, 'result': {'job_id': job_id, 'project_dir': job_record['project_dir']}})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ---------------- Azure Resource Manager / Storage / ADO hooks ---------------------------------

def _az_cli_available():

    return shutil.which('az') is not None


@app.route('/api/azure/groups')

def api_azure_groups():

    """List Azure resource groups (uses `az group list` if available)."""

    if not _az_cli_available():

        return jsonify({'ok': False, 'error': 'az CLI not available on server'}), 501

    try:

        proc = subprocess.run(['az', 'group', 'list', '--output', 'json'], capture_output=True, text=True, timeout=30)

        if proc.returncode != 0:

            return jsonify({'ok': False, 'error': proc.stderr}), 500

        data = json.loads(proc.stdout)

        return jsonify({'ok': True, 'groups': data})

    except Exception as e:

        app.logger.exception('az group list failed')

        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/azure/resources')

def api_azure_resources():

    """List Azure resources (optionally filter by resource group via ?rg=name or subscription via ?subscription=id)."""

    rg = request.args.get('rg')

    subscription = request.args.get('subscription')

    if not _az_cli_available():

        return jsonify({'ok': False, 'error': 'az CLI not available on server'}), 501

    try:

        cmd = ['az', 'resource', 'list', '--output', 'json']

        if subscription:

            cmd.extend(['--subscription', subscription])

        if rg:

            cmd.extend(['--resource-group', rg])

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if proc.returncode != 0:

            return jsonify({'ok': False, 'error': proc.stderr}), 500

        data = json.loads(proc.stdout)

        return jsonify({'ok': True, 'resources': data})

    except Exception as e:

        app.logger.exception('az resource list failed')

        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/azure/storage/accounts')

def api_azure_storage_accounts():

    """List storage accounts."""

    if not _az_cli_available():

        return jsonify({'ok': False, 'error': 'az CLI not available on server'}), 501

    try:

        proc = subprocess.run(['az', 'storage', 'account', 'list', '--output', 'json'], capture_output=True, text=True, timeout=30)

        if proc.returncode != 0:

            return jsonify({'ok': False, 'error': proc.stderr}), 500

        data = json.loads(proc.stdout)

        return jsonify({'ok': True, 'accounts': data})

    except Exception as e:

        app.logger.exception('az storage account list failed')

        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/azure/storage/containers', methods=['POST'])

def api_azure_storage_containers():

    """List or create containers. POST JSON: { account: name, action: 'list'|'create', container: name }

    Note: requires appropriate az login and RBAC on server or using SAS/key parameters (not implemented).

    """

    data = request.get_json(silent=True) or {}

    account = data.get('account')

    action = data.get('action') or 'list'

    container = data.get('container')

    if not account:

        return jsonify({'ok': False, 'error': 'account required'}), 400

    if not _az_cli_available():

        return jsonify({'ok': False, 'error': 'az CLI not available on server'}), 501

    try:

        if action == 'list':

            proc = subprocess.run(['az', 'storage', 'container', 'list', '--account-name', account, '--output', 'json'], capture_output=True, text=True, timeout=30)

            if proc.returncode != 0:

                return jsonify({'ok': False, 'error': proc.stderr}), 500

            return jsonify({'ok': True, 'containers': json.loads(proc.stdout)})

        elif action == 'create':

            if not container:

                return jsonify({'ok': False, 'error': 'container required for create'}), 400

            proc = subprocess.run(['az', 'storage', 'container', 'create', '--account-name', account, '--name', container, '--output', 'json'], capture_output=True, text=True, timeout=30)

            if proc.returncode != 0:

                return jsonify({'ok': False, 'error': proc.stderr}), 500

            return jsonify({'ok': True, 'result': json.loads(proc.stdout)})

        else:

            return jsonify({'ok': False, 'error': 'unknown action'}), 400

    except Exception as e:

        app.logger.exception('az storage container operation failed')

        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/azure/create_rg', methods=['POST'])

def api_azure_create_rg():

    data = request.get_json(silent=True) or {}

    name = data.get('name')

    location = data.get('location') or 'eastus'

    if not name:

        return jsonify({'ok': False, 'error': 'name required'}), 400

    if not _az_cli_available():

        return jsonify({'ok': False, 'error': 'az CLI not available on server'}), 501

    try:

        proc = subprocess.run(['az', 'group', 'create', '--name', name, '--location', location, '--output', 'json'], capture_output=True, text=True, timeout=30)

        if proc.returncode != 0:

            return jsonify({'ok': False, 'error': proc.stderr}), 500

        return jsonify({'ok': True, 'result': json.loads(proc.stdout)})

    except Exception as e:

        app.logger.exception('az group create failed')

        return jsonify({'ok': False, 'error': str(e)}), 500


# Simple CRUD for 3rd-party service hooks (Azure DevOps) stored locally and optionally executed via az devops

HOOKS_FILE = Path(__file__).resolve().parent / 'data' / 'azure_hooks.json'


def _load_hooks():

    try:

        if HOOKS_FILE.exists():

            return json.loads(HOOKS_FILE.read_text(encoding='utf-8'))

    except Exception:

        app.logger.exception('Failed to read hooks file')

    return {}


def _save_hooks(h):

    try:

        HOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)

        HOOKS_FILE.write_text(json.dumps(h, indent=2), encoding='utf-8')

    except Exception:

        app.logger.exception('Failed to save hooks file')


@app.route('/api/ado/hooks', methods=['GET','POST','DELETE'])

def api_ado_hooks():

    if request.method == 'GET':

        return jsonify({'ok': True, 'hooks': _load_hooks()})

    data = request.get_json(silent=True) or {}

    hooks = _load_hooks()

    if request.method == 'POST':

        # add or update hook

        hid = data.get('id') or uuid.uuid4().hex

        hooks[hid] = data

        _save_hooks(hooks)

        return jsonify({'ok': True, 'id': hid})

    if request.method == 'DELETE':

        hid = data.get('id')

        if hid and hid in hooks:

            hooks.pop(hid)

            _save_hooks(hooks)

            return jsonify({'ok': True})

        return jsonify({'ok': False, 'error': 'id not found'}), 404

    return jsonify({'ok': True, 'hooks': hooks})


@app.route('/api/ide/load', methods=['POST'])
@requires_permission('web_ide')

def api_ide_load():

    data = request.get_json(silent=True) or (request.form if request.form else {})

    filename = data.get('filename') if isinstance(data, dict) else None

    if not filename:

        return jsonify({'ok': False, 'error': 'filename required'}), 400

    try:
        path = resolve_project_file(Path(__file__).resolve().parent, filename)
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    if not path.is_file():
        return jsonify({'ok': False, 'error': 'file not found'}), 404

    try:

        content = path.read_text(encoding='utf-8')

        return jsonify({'ok': True, 'content': content})

    except Exception as e:

        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/ide/save', methods=['POST'])
@requires_permission('web_ide')

def api_ide_save():

    data = request.get_json(silent=True) or (request.form if request.form else {})

    filename = data.get('filename') if isinstance(data, dict) else None

    content = data.get('content','') if isinstance(data, dict) else (request.form.get('content','') if request.form else '')

    if not filename:

        return jsonify({'ok': False, 'error': 'filename required'}), 400

    try:

        file_path = resolve_project_file(Path(__file__).resolve().parent, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return jsonify({'ok': True, 'filename': filename})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/ide/execute', methods=['POST'])
@requires_permission('web_ide')

def api_ide_execute():

    data = request.get_json(silent=True) or (request.form if request.form else {})

    filename = data.get('filename') if isinstance(data, dict) else None

    content = data.get('content') if isinstance(data, dict) else None

    shell = data.get('shell') if isinstance(data, dict) else None

    remote = bool(data.get('remote')) if isinstance(data, dict) else False

    if remote:

        return jsonify({'ok': False, 'error': 'remote execution not implemented'}), 501

    try:

        if filename:

            path = resolve_project_file(Path(__file__).resolve().parent, filename)
            if not path.is_file():

                if content:

                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding='utf-8')

                else:

                    return jsonify({'ok': False, 'error': 'file not found'}), 404

            elif content is not None:
                path.write_text(content, encoding='utf-8')

            cmd = _interpreter_cmd_for_path(path, requested_shell=shell)

            if not cmd:

                return jsonify({'ok': False, 'error': 'no suitable interpreter found; specify shell explicitly (python,powershell,bash)'}), 500

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(Path(__file__).resolve().parent),
            )

            return jsonify({'ok': True, 'stdout': proc.stdout, 'stderr': proc.stderr, 'returncode': proc.returncode})

        elif content:

            # Choose a sensible default extension when the client didn't specify a shell.

            # Heuristics: if content looks like Python, use .py; on Windows prefer PowerShell.

            ext = None

            if shell == 'python':

                ext = '.py'

            elif shell in ('powershell','ps1'):

                ext = '.ps1'

            elif shell in ('bash','sh'):

                ext = '.sh'

            else:

                # simple python heuristics

                snippet = (content or '').strip()

                if snippet.startswith('#!') and 'python' in snippet.splitlines()[0].lower():

                    ext = '.py'

                elif any(token in snippet for token in ('print(', 'def ', 'import ', 'if __name__', 'class ')):

                    ext = '.py'

                else:

                    # On Windows default to PowerShell script to avoid missing bash/wsl

                    if sys.platform.startswith('win'):

                        ext = '.ps1'

                    else:

                        ext = '.sh'

            fd, tmp = tempfile.mkstemp(suffix=ext, prefix='masterchief_exec_', dir=str(app.config['SCRIPTS_FOLDER']))

            os.close(fd)

            with open(tmp,'w',encoding='utf-8') as f:

                f.write(content)

            os.chmod(tmp, 0o755)

            p = Path(tmp)

            # Choose interpreter-aware command where possible

            cmd = _interpreter_cmd_for_path(p, requested_shell=shell)

            if not cmd:

                # No suitable interpreter found for this platform/type

                return jsonify({'ok': False, 'error': 'no suitable interpreter found for script on this platform; specify shell explicitly (python,powershell,bash)'}), 500

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            out = proc.stdout

            err = proc.stderr

            rc = proc.returncode

            try:

                p.unlink()

            except Exception:

                pass

            return jsonify({'ok': True, 'stdout': out, 'stderr': err, 'returncode': rc})

        else:

            return jsonify({'ok': False, 'error': 'no filename or content provided'}), 400

    except subprocess.TimeoutExpired:

        return jsonify({'ok': False, 'error':'execution timed out'}), 500

    except Exception as e:

        return jsonify({'ok': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
#  Marketplace API Routes
# ---------------------------------------------------------------------------
#  Marketplace API Routes
# ---------------------------------------------------------------------------
#  Marketplace API Routes
# ---------------------------------------------------------------------------

# Remote credential storage for IDE remote execution (basic, stored in data/ide_creds.json)
# Remote credential storage for IDE remote execution (basic, stored in data/ide_creds.json)

CREDS_FILE = Path(__file__).resolve().parent / 'data' / 'ide_creds.json'


@app.route('/api/ide/remote/creds', methods=['POST'])

def api_ide_remote_creds_save():

    data = request.get_json(silent=True) or (request.form if request.form else {})

    target = data.get('target') if isinstance(data, dict) else (request.form.get('target') if request.form else None)

    username = data.get('username') if isinstance(data, dict) else (request.form.get('username') if request.form else None)

    password = data.get('password') if isinstance(data, dict) else (request.form.get('password') if request.form else None)

    if not target or not username or not password:

        return jsonify({'ok': False, 'error':'target,username,password required'}), 400

    try:

        d = {}

        if CREDS_FILE.exists():

            try:

                d = json.loads(CREDS_FILE.read_text(encoding='utf-8'))

            except Exception:

                d = {}

        d[target] = {'username': username, 'password': password, 'saved_at': datetime.now().isoformat()}

        CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)

        CREDS_FILE.write_text(json.dumps(d, indent=2), encoding='utf-8')

        return jsonify({'ok': True})

    except Exception as e:

        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/ide/remote/creds', methods=['GET'])

def api_ide_remote_creds_get():

    target = request.args.get('target')

    if not target:

        return jsonify({'ok': False, 'error': 'target required'}), 400

    try:

        if not CREDS_FILE.exists():

            return jsonify({'ok': True, 'cred': None})

        d = json.loads(CREDS_FILE.read_text(encoding='utf-8'))

        return jsonify({'ok': True, 'cred': d.get(target)})

    except Exception as e:

        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/ide/log', methods=['POST'])

def api_ide_log():

    """Receive lightweight client-side logs from the Web IDE for debugging.

    POST JSON: { event: str, detail: any }

    """

    data = request.get_json(silent=True) or {}

    event = data.get('event')

    detail = data.get('detail')

    try:

        outdir = Path(__file__).parent / 'data' / 'ide_logs'

        outdir.mkdir(parents=True, exist_ok=True)

        fn = outdir / (datetime.utcnow().strftime('%Y-%m-%d') + '.log')

        with open(fn, 'a', encoding='utf-8') as f:

            f.write(json.dumps({'ts': datetime.utcnow().isoformat(), 'event': event, 'detail': detail}) + '\n')

        app.logger.info('IDE client log: %s %s', event, json.dumps(detail)[:200])

        return jsonify({'ok': True})

    except Exception as e:

        app.logger.exception('Failed to write IDE client log')

        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/ide/tree')
@requires_permission('web_ide')

def api_ide_tree():

    rel = request.args.get('path','')

    try:

        base = Path(__file__).resolve().parent
        target = resolve_project_file(base, rel)
        if not target.exists():
            return jsonify({'ok': False, 'error': f'directory not found: {rel or "."}'}), 404
        if not target.is_dir():
            return jsonify({'ok': False, 'error': 'path is not a directory'}), 400

        nodes = []

        try:
            paths = list(target.iterdir())
        except PermissionError:
            return jsonify({'ok': False, 'error': f'permission denied reading directory: {rel or "."}'}), 403
        except OSError as e:
            app.logger.exception('Failed to read IDE directory %s', target)
            return jsonify({'ok': False, 'error': f'cannot read directory {rel or "."}: {e}'}), 500

        for p in sorted(paths, key=lambda x: x.name):

            try:
                if p.name in {
                    '.git', '.venv', 'venv', 'venv310', 'env', 'node_modules',
                    'build', 'dist', '__pycache__', '.pytest_cache',
                }:
                    continue
                if target == base / 'data' / 'uploads' and (
                    p.name == 'extracted' or p.name.startswith('_extracted_disabled')
                ):
                    continue

                if p.is_dir():
                    nodes.append({'type':'dir','name':p.name,'path':str(p.relative_to(base))})
                else:
                    stat = p.stat()
                    nodes.append({'type':'file','name':p.name,'path':str(p.relative_to(base)),'size':stat.st_size,'modified':datetime.fromtimestamp(stat.st_mtime).isoformat()})
            except (OSError, PermissionError):
                # Skip files/directories we can't access
                continue

        return jsonify({'ok':True,'path':str(target.relative_to(base)) if rel else '','nodes':nodes})

    except ValueError as e:

        return jsonify({'ok':False,'error':str(e)}),400

    except Exception as e:

        app.logger.exception('Failed to list IDE directory')
        return jsonify({'ok':False,'error':str(e)}),500


@app.route('/api/ide/search')
@requires_permission('web_ide')
def api_ide_search():
    query = (request.args.get('q') or '').strip().casefold()
    if not query:
        return jsonify({'ok': False, 'error': 'search query required'}), 400

    root = Path(__file__).resolve().parent
    ignored_dirs = {
        '.git', '.venv', 'venv', 'venv310', 'env', 'node_modules', 'build',
        'dist', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
        'site-packages', '.tox', 'htmlcov',
    }
    code_extensions = {
        '.py', '.pyw', '.ps1', '.psm1', '.sh', '.bash', '.bat', '.cmd',
        '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss', '.java',
        '.go', '.rs', '.rb', '.php', '.sql', '.tf', '.hcl', '.json',
        '.yaml', '.yml', '.toml', '.ini', '.cfg', '.c', '.h', '.cpp',
        '.hpp', '.cs', '.fs', '.r', '.lua', '.pl', '.ex', '.exs',
    }
    matches = []
    total = 0

    try:
        for directory, child_dirs, filenames in os.walk(root, onerror=lambda error: app.logger.warning(
            'Skipping unreadable IDE search directory %s: %s', error.filename, error
        )):
            relative_dir = Path(directory).relative_to(root)
            child_dirs[:] = sorted(
                d for d in child_dirs
                if d not in ignored_dirs and not d.startswith('_extracted_disabled')
                and not (relative_dir == Path('data/uploads') and d == 'extracted')
            )
            current = Path(directory)
            for filename in filenames:
                path = current / filename
                if path.suffix.lower() not in code_extensions:
                    continue
                relative = path.relative_to(root).as_posix()
                if query not in relative.casefold():
                    continue
                total += 1
                if len(matches) < 200:
                    try:
                        stat = path.stat()
                        matches.append({
                            'type': 'file',
                            'name': filename,
                            'path': relative,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        })
                    except OSError:
                        app.logger.warning('Skipping IDE search result that became inaccessible: %s', path)

        return jsonify({'ok': True, 'query': query, 'total': total, 'truncated': total > len(matches), 'nodes': matches})
    except OSError as e:
        app.logger.exception('IDE project search failed')
        return jsonify({'ok': False, 'error': f'project search failed: {e}'}), 500


@app.route('/api/ide/exec_async', methods=['POST'])
@requires_permission('web_ide')

def api_ide_exec_async():

    data = request.get_json(silent=True) or {}

    try:
        filename = data.get('filename')
        content = data.get('content')
        shell = data.get('shell')
        if not filename:
            return jsonify({'ok': False, 'error': 'filename required'}), 400

        path = resolve_project_file(Path(__file__).resolve().parent, filename)
        if content is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        if not path.is_file():
            return jsonify({'ok': False, 'error': 'file not found'}), 404

        command = _interpreter_cmd_for_path(path, requested_shell=shell)
        if not command:
            return jsonify({'ok': False, 'error': 'no suitable interpreter for this file'}), 400

        requested_cwd = data.get('cwd')
        if requested_cwd:
            cwd = resolve_project_file(Path(__file__).resolve().parent, requested_cwd)
            if not cwd.is_dir():
                return jsonify({'ok': False, 'error': 'working directory not found'}), 404
        else:
            cwd = Path(__file__).resolve().parent

        exec_id = uuid.uuid4().hex
        EXEC_JOBS[exec_id] = {
            'id': exec_id,
            'status': 'queued',
            'cmd': command,
            'pid': None,
            'returncode': None,
            'started_at': None,
            'finished_at': None,
            'cwd': str(cwd),
        }
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    except OSError as e:
        app.logger.exception('Unable to prepare IDE script for asynchronous execution')
        return jsonify({'ok': False, 'error': f'unable to prepare script: {e}'}), 500

    _start_job_thread(exec_id, command, cwd=str(cwd))

    return jsonify({'ok':True,'exec_id':exec_id})


@app.route('/api/ide/exec_status')
@requires_permission('web_ide')

def api_ide_exec_status():

    exec_id = request.args.get('exec_id')

    if not exec_id:

        return jsonify({'ok':False,'error':'exec_id required'}),400

    job = EXEC_JOBS.get(exec_id)

    if not job:

        return jsonify({'ok':False,'error':'not found'}),404

    # attach small output preview

    out=''

    err=''

    base = Path(app.config['SCRIPTS_FOLDER']).resolve()

    stdout_path = base / f"{exec_id}.stdout"

    stderr_path = base / f"{exec_id}.stderr"

    try:

        if stdout_path.exists():

            out = stdout_path.read_text(encoding='utf-8', errors='ignore')

        if stderr_path.exists():

            err = stderr_path.read_text(encoding='utf-8', errors='ignore')

    except Exception:

        pass

    res = dict(job)

    res.update({'stdout': out, 'stderr': err})

    return jsonify({'ok':True,'job':res})


def _resource_id_for(category: str, filename: str) -> str:

        # stable id to reference resources in index

        return f"{category}:{filename}"


# Resources storage location and helpers

RESOURCES_DIR = Path(__file__).resolve().parent / 'data' / 'resources'

RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

RESOURCES_INDEX_FILE = RESOURCES_DIR / 'index.json'

INGEST_TASKS_FILE = RESOURCES_DIR / 'ingest_tasks.json'


# Sessions index (persisted minimal session metadata)

SESSIONS_INDEX_FILE = Path(__file__).resolve().parent / 'data' / 'sessions.json'

SESSIONS_META_FILE = Path(__file__).resolve().parent / 'data' / 'sessions_meta.json'


def _load_resources_index():

    try:

        if RESOURCES_INDEX_FILE.exists():

            try:

                return json.loads(RESOURCES_INDEX_FILE.read_text(encoding='utf-8'))

            except Exception:

                # corrupt index file -> rebuild empty

                return {}

        # build initial index by scanning data/resources categories

        idx = {}

        for cat_dir in RESOURCES_DIR.iterdir():

            if not cat_dir.is_dir():

                continue

            for p in cat_dir.iterdir():

                if p.is_file():

                    rid = _resource_id_for(cat_dir.name, p.name)

                    # Treat files as persona only when stored in a 'personality' category.

                    is_persona = (cat_dir.name.lower() == 'personality')

                    idx[rid] = {'id': rid, 'filename': p.name, 'category': cat_dir.name, 'path': str(p), 'persona': is_persona, 'uploaded_at': datetime.fromtimestamp(p.stat().st_mtime).isoformat()}

        # persist initial index

        _save_resources_index(idx)

        return idx

    except Exception:

        return {}


def _save_resources_index(idx: dict):

    try:

        RESOURCES_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

        RESOURCES_INDEX_FILE.write_text(json.dumps(idx, indent=2), encoding='utf-8')

    except Exception:

        app.logger.exception('Failed to save resources index')


def _load_ingest_tasks():

    try:

        if INGEST_TASKS_FILE.exists():

            try:

                return json.loads(INGEST_TASKS_FILE.read_text(encoding='utf-8'))

            except Exception:

                return {}

        return {}

    except Exception:

        return {}


def _save_ingest_tasks(tasks: dict):

    try:

        INGEST_TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)

        INGEST_TASKS_FILE.write_text(json.dumps(tasks, indent=2), encoding='utf-8')

    except Exception:

        app.logger.exception('Failed to save ingest tasks')


def _load_sessions_index():

    try:

        if SESSIONS_INDEX_FILE.exists():

            try:

                return json.loads(SESSIONS_INDEX_FILE.read_text(encoding='utf-8'))

            except Exception:

                return {}

        return {}

    except Exception:

        return {}


def _save_sessions_index(idx: dict):

    try:

        SESSIONS_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

        SESSIONS_INDEX_FILE.write_text(json.dumps(idx, indent=2), encoding='utf-8')

    except Exception:

        app.logger.exception('Failed to save sessions index')


def _upsert_session_meta(sid: str, title: str = None):

    """Ensure a minimal session metadata entry exists and return it.


    Creates or updates `data/sessions.json` with `session_id`, `title`,

    `created` and `last_updated` fields.

    """

    try:

        idx = _load_sessions_index()

        entry = idx.get(sid) or {}

        now_iso = datetime.now().isoformat()

        if not entry.get('session_id'):

            entry['session_id'] = sid

        if title:

            entry['title'] = title

        entry.setdefault('created', now_iso)

        entry['last_updated'] = now_iso

        # ensure favorite flag present

        entry.setdefault('favorite', False)

        idx[sid] = entry

        _save_sessions_index(idx)

        # also persist a richer meta file for backward-compatibility

        try:

            SESSIONS_META_FILE.parent.mkdir(parents=True, exist_ok=True)

            meta = {}

            if SESSIONS_META_FILE.exists():

                try:

                    meta = json.loads(SESSIONS_META_FILE.read_text(encoding='utf-8'))

                except Exception:

                    meta = {}

            meta[sid] = {'session_id': sid, 'updated': time.time(), 'topic_state': entry.get('topic_state')}

            SESSIONS_META_FILE.write_text(json.dumps(meta, indent=2), encoding='utf-8')

        except Exception:

            pass

        return entry

    except Exception:

        app.logger.exception('Upsert session meta failed')

        return {'session_id': sid, 'title': title or sid}


# ---------------------------------------------------------------------------
#  Pipeline Manager
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
#  Dynamic Module Loading
###############################################################################

managers = {}
_managers_dir = Path(__file__).resolve().parent / 'managers'
for name, config in ENABLED_MODULES.items():
    print(f"DEBUG: Processing module {name}, enabled={config.get('enabled', False)}")
    if not config.get('enabled', False):
        managers[name] = None
        continue
    try:
        # Try importlib.import_module first (works when installed as package)
        try:
            module = importlib.import_module(f'managers.{name}')
        except ImportError:
            # Fallback: load from file path (works in dev when running from repo)
            _mgr_path = _managers_dir / f'{name}.py'
            spec = importlib.util.spec_from_file_location(f"{name}_manager", str(_mgr_path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        register_func = getattr(module, f'register_{name}_module')
        # Remove 'enabled' from config for kwargs
        kwargs = {k: v for k, v in config.items() if k != 'enabled'}
        print(f"DEBUG: Calling register_{name}_module with kwargs={kwargs}")
        managers[name] = register_func(app, **kwargs)
        print(f"DEBUG: Loaded module {name}")
    except Exception as e:
        print(f"Failed to load module {name}: {e}")
        managers[name] = None

# Set global manager variables for backward compatibility
rbac_mgr = managers.get('rbac')
vault_mgr = managers.get('vault')
notification_mgr = managers.get('notification')
pipeline_mgr = managers.get('pipeline')
cloud_mgr = managers.get('cloud')
memory_mgr = managers.get('memory')
marketplace_mgr = managers.get('marketplace')
script_mgr = managers.get('script')

# Store managers on the Flask app so auth_module (and others) can access
# them via current_app without the broken `from main import rbac_mgr` pattern.
app.config['_managers'] = managers
app.config['_rbac_mgr'] = rbac_mgr

# Register blueprints
from blueprints import (
    azure,
    chatserv_routes,
    core_scripts,
    diagnostics_routes,
    feature_routes,
    iac_routes,
    ide,
    manager,
    mock,
    observability_routes,
    ops_routes,
    roku_routes,
    scm_routes,
    terraform,
    ui_pages,
    wizard,
)
from renderers import render_resources_page, render_addons_modules_page, render_module_manager_page, render_addons_module_config_page, render_echo_training_page
from blueprints import deploy_routes
app.register_blueprint(deploy_routes.deploy_bp)
app.register_blueprint(ide.ide_bp)
app.register_blueprint(terraform.terraform_bp)
app.register_blueprint(iac_routes.iac_bp)
app.register_blueprint(roku_routes.roku_bp)
app.register_blueprint(mock.mock_bp)
app.register_blueprint(observability_routes.observability_bp)
app.register_blueprint(azure.azure_bp)
app.register_blueprint(manager.manager_bp)
app.register_blueprint(core_scripts.core_scripts_bp)
app.register_blueprint(ui_pages.ui_pages_bp)
app.register_blueprint(feature_routes.feature_routes_bp)
app.register_blueprint(ops_routes.ops_bp)
app.register_blueprint(diagnostics_routes.diagnostics_bp)
app.register_blueprint(scm_routes.scm_bp)
app.register_blueprint(wizard.wizard_bp)
chatserv_routes.init_chatserv(app, Path(__file__).resolve().parent)


def get_system_stats():

    cpu_percent=psutil.cpu_percent(interval=1)

    memory=psutil.virtual_memory()

    try:

        disk_path='C:\\' if sys.platform=='win32' else '/'

        disk=psutil.disk_usage(disk_path)

    except:

        disk=psutil.disk_usage('.')

    return {'cpu':{'percent':cpu_percent,'count':psutil.cpu_count()},'memory':{'total':memory.total,'available':memory.available,'percent':memory.percent,'used':memory.used},'disk':{'total':disk.total,'used':disk.used,'free':disk.free,'percent':disk.percent},'uptime':time.time()-psutil.boot_time()}

def get_processes():

    processes=[]

    for proc in psutil.process_iter(['pid','name','cpu_percent','memory_percent','status']):

        try:

            processes.append(proc.info)

        except (psutil.NoSuchProcess,psutil.AccessDenied):

            pass

    return sorted(processes,key=lambda x:x.get('cpu_percent',0),reverse=True)[:50]

def get_windows_services():

    if sys.platform!='win32':

        return []

    services=[]

    try:

        result=subprocess.run(['sc','query'],capture_output=True,text=True)

        lines=result.stdout.split('\n')

        service={}

        for line in lines:

            line=line.strip()

            if line.startswith('SERVICE_NAME:'):

                if service:

                    services.append(service)

                service={'name':line.split(':',1)[1].strip()}

            elif line.startswith('DISPLAY_NAME:'):

                service['display_name']=line.split(':',1)[1].strip()

            elif line.startswith('STATE'):

                service['state']=line.split(':',1)[1].strip()

        if service:

            services.append(service)

    except Exception:

        pass

    return services

# Execution jobs store for async/parallel execution

EXEC_JOBS = {}

# Training jobs store

TRAIN_JOBS = {}

TRAIN_JOBS_FILE = Path(__file__).parent / 'data' / 'models_output' / 'train_jobs.json'


def _load_train_jobs():

    try:

        if TRAIN_JOBS_FILE.exists():

            return json.loads(TRAIN_JOBS_FILE.read_text(encoding='utf-8'))

    except Exception:

        app.logger.exception('Failed to load train jobs file')

    return {}


def _start_cleanup_thread(retention_days=30):

    def runner():

        while True:

            try:

                base = Path(__file__).parent / 'data' / 'models_output'

                if base.exists():

                    for d in base.iterdir():

                        if not d.is_dir():

                            continue

                        # skip train_jobs.json

                        if d.name == 'train_jobs.json':

                            continue

                        mtime = d.stat().st_mtime

                        age_days = (time.time() - mtime) / (60*60*24)

                        if age_days > retention_days:

                            try:

                                shutil.make_archive(str(d), 'zip', root_dir=str(d))

                                shutil.rmtree(d)

                            except Exception:

                                app.logger.exception('Failed to archive old job %s', d)

                # sleep between scans

                time.sleep(60*60*6)

            except Exception:

                app.logger.exception('Cleanup thread error')

                time.sleep(60*60)

    thread = threading.Thread(target=runner, daemon=True)

    thread.start()


def _save_train_jobs():

    try:

        TRAIN_JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)

        TRAIN_JOBS_FILE.write_text(json.dumps(TRAIN_JOBS, indent=2), encoding='utf-8')

    except Exception:

        app.logger.exception('Failed to save train jobs file')


def _start_job_thread(exec_id, cmd, cwd=None):

    def runner():

        job = EXEC_JOBS.get(exec_id)

        if not job:

            return

        job['status'] = 'running'

        job['started_at'] = time.time()

        try:

            # run as subprocess and capture to files

            stdout_path = Path(app.config['SCRIPTS_FOLDER']) / f"{exec_id}.stdout"

            stderr_path = Path(app.config['SCRIPTS_FOLDER']) / f"{exec_id}.stderr"

            with open(stdout_path, 'wb') as out_f, open(stderr_path, 'wb') as err_f:

                proc = subprocess.Popen(cmd, cwd=cwd or str(app.config['SCRIPTS_FOLDER']), stdout=out_f, stderr=err_f, shell=isinstance(cmd, str))

                job['pid'] = proc.pid

                # Do not store the Popen object in the job dict (not JSON-serializable).

                proc.wait()

                job['returncode'] = proc.returncode

        except Exception as e:

            job['error'] = str(e)

            job['status'] = 'error'

        else:

            job['status'] = 'finished'

        finally:

            job['finished_at'] = time.time()


    t = threading.Thread(target=runner, daemon=True)

    t.start()


def _start_train_job(job_id, cmd, cwd=None):

    def runner():

        job = TRAIN_JOBS.get(job_id)

        if not job:

            return

        job['status'] = 'running'

        job['started_at'] = time.time()

        _save_train_jobs()

        try:

            outdir = Path(__file__).parent / 'data' / 'models_output' / job_id

            outdir.mkdir(parents=True, exist_ok=True)

            log_path = outdir / 'train.log'

            with open(log_path, 'wb') as log_f:

                proc = subprocess.Popen(cmd, cwd=cwd or str(Path.cwd()), stdout=log_f, stderr=log_f, shell=isinstance(cmd, str))

                job['pid'] = proc.pid

                proc.wait()

                job['returncode'] = proc.returncode

        except Exception as e:

            job['error'] = str(e)

            job['status'] = 'error'

        else:

            job['status'] = 'finished'

        finally:

            job['finished_at'] = time.time()

            _save_train_jobs()


    t = threading.Thread(target=runner, daemon=True)

    t.start()


def load_template(name):
    """HTML for a page lives in templates/<name>.html. See docs/template_map.json for which app uses which file."""
    import os
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', name + '.html'), encoding='utf-8') as fh:
        return fh.read()


HTML_TEMPLATE = load_template('layout')


SCRIPTS_TEMPLATE = load_template('scripts')

SCRIPT_VIEW_TEMPLATE = load_template('script_view')

SCRIPT_EXECUTE_TEMPLATE = load_template('script_execute')

SCRIPT_EDIT_TEMPLATE = load_template('script_edit')

PROCESSES_TEMPLATE = load_template('processes')

SERVICES_TEMPLATE = load_template('services')

ADDONS_TEMPLATE = load_template('addons')

ECHO_CHAT_TEMPLATE = load_template('echo_chat')

MODULES_TEMPLATE = load_template('modules')

@app.route('/')

@requires_permission('dashboard')
def dashboard():
    stats=get_system_stats()

    return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}',DASHBOARD_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')),stats=stats,request=request,get_flashed_messages=get_flashed_messages)


@app.route('/modules')
@requires_permission('dashboard')
def modules_page():
    return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}', MODULES_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')), enabled_modules=ENABLED_MODULES, managers=managers, request=request, get_flashed_messages=get_flashed_messages)


@app.route('/google-services')
@requires_permission('dashboard')
def google_services_page():
    page = Path(__file__).resolve().parent / 'google_services.html'
    return send_file(page)

@app.route('/archetypes')
def code_archetypes_page():
    page = Path(__file__).resolve().parent / 'archetypes.html'
    return send_file(page)

@app.route('/api/code-archetypes', methods=['GET', 'POST'])
def api_code_archetypes():
    from core.code_archetypes import list_archetypes, save_custom_archetype
    if request.method == 'GET':
        try:
            return jsonify({'archetypes': list_archetypes()})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            app.logger.exception('Failed to load code archetypes')
            return jsonify({'error': f'Could not load archetypes: {exc}'}), 500

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'A JSON archetype object is required.'}), 400
    try:
        archetype = save_custom_archetype(payload)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except OSError as exc:
        app.logger.exception('Failed to save custom code archetype')
        return jsonify({'error': f'Could not save archetype: {exc}'}), 500
    return jsonify({'archetype': archetype}), 201


@app.route('/api/modules/toggle', methods=['POST'])
@requires_permission('dashboard')
def api_modules_toggle():
    module = request.form.get('module')
    if module not in ENABLED_MODULES:
        return jsonify({'ok': False, 'error': 'Module not found'}), 400
    ENABLED_MODULES[module]['enabled'] = not ENABLED_MODULES[module]['enabled']
    # Save to file
    app.config['MODULES_CONFIG'].write_text(json.dumps(ENABLED_MODULES, indent=2), encoding='utf-8')
    return jsonify({'ok': True, 'enabled': ENABLED_MODULES[module]['enabled']})

@app.route('/api/test')
def api_test():
    return jsonify({'ok': True, 'message': 'API is working', 'script_mgr': str(type(script_mgr)), 'enterprise_tf_gen': str(type(enterprise_tf_gen))})

@app.route('/api/stats')

def api_stats():

    return jsonify(get_system_stats())


def _b64_encode_path(p: str) -> str:

    return base64.urlsafe_b64encode(p.encode()).decode()


def _b64_decode_path(s: str) -> str:

    try:

        return base64.urlsafe_b64decode(s.encode()).decode()

    except Exception:

        return ''


@app.route('/scripts/edit/<b64path>')

@requires_permission('scripts')
def scripts_edit(b64path):

    path = _b64_decode_path(b64path)

    if not path:

        flash('Invalid path','error')

        return redirect(url_for('scripts_list'))

    try:

        with open(path,'r', encoding='utf-8') as f:

            content=f.read()

    except Exception as e:

        flash(f'Failed to read file: {e}','error')

        return redirect(url_for('scripts_list'))

    return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}',SCRIPT_EDIT_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')),content=content,filepath=path,b64path=b64path,message=None,request=request,get_flashed_messages=get_flashed_messages)


@app.route('/scripts/save/<b64path>', methods=['POST'])

@requires_permission('scripts')
def scripts_save(b64path):

    path = _b64_decode_path(b64path)

    if not path:

        flash('Invalid path','error')

        return redirect(url_for('scripts_list'))

    content=request.form.get('content','')

    try:

        # create backup before overwrite

        backups_dir = Path(__file__).resolve().parent / 'data' / 'backups' / 'scripts'

        backups_dir.mkdir(parents=True, exist_ok=True)

        try:

            if Path(path).exists():

                ts = datetime.now().strftime('%Y%m%d-%H%M%S')

                bak_name = f"{Path(path).name}.{ts}.bak"

                shutil.copy2(path, str(backups_dir / bak_name))

        except Exception:

            # non-fatal

            pass

        # auto-approve - write file directly

        with open(path,'w', encoding='utf-8') as f:

            f.write(content)

        flash(f'Saved {path} (backup created)','success')

    except Exception as e:

        flash(f'Failed to save file: {e}','error')

    return redirect(url_for('scripts_list'))


@app.route('/scripts/backup/<b64path>', methods=['POST'])

@requires_permission('scripts')
def scripts_backup(b64path):

    path = _b64_decode_path(b64path)

    if not path:

        return jsonify({'success':False,'error':'Invalid path'})

    try:

        backups_dir = Path(__file__).resolve().parent / 'data' / 'backups' / 'scripts'

        backups_dir.mkdir(parents=True, exist_ok=True)

        if Path(path).exists():

            ts = datetime.now().strftime('%Y%m%d-%H%M%S')

            bak_name = f"{Path(path).name}.{ts}.bak"

            bak_path = backups_dir / bak_name

            shutil.copy2(path, str(bak_path))

            return jsonify({'success':True,'backup':str(bak_path)})

        return jsonify({'success':False,'error':'File not found'})

    except Exception as e:

        return jsonify({'success':False,'error':str(e)})


    # --- Minimal Web IDE API endpoints -----------------------------------------------------

    def _safe_script_path(filename: str):

        try:

            fname = secure_filename(filename)

            if not fname:

                return None

            return Path(app.config['SCRIPTS_FOLDER']) / fname

        except Exception:

            return None


    @app.route('/api/ide/load', methods=['POST'])

    def api_ide_load():

        data = request.get_json(silent=True) or (request.form if request.form else {})

        filename = data.get('filename') if isinstance(data, dict) else None

        if not filename:

            return jsonify({'ok': False, 'error': 'filename required'}), 400

        path = _safe_script_path(filename)

        if not path or not path.exists():

            return jsonify({'ok': False, 'error': 'file not found'}), 404

        try:

            content = path.read_text(encoding='utf-8')

            return jsonify({'ok': True, 'content': content})

        except Exception as e:

            return jsonify({'ok': False, 'error': str(e)}), 500


    @app.route('/api/ide/save', methods=['POST'])

    def api_ide_save():

        data = request.get_json(silent=True) or (request.form if request.form else {})

        filename = data.get('filename') if isinstance(data, dict) else None

        content = data.get('content','') if isinstance(data, dict) else (request.form.get('content','') if request.form else '')

        if not filename:

            return jsonify({'ok': False, 'error': 'filename required'}), 400

        try:

            script_mgr.add_script(filename, content)

            return jsonify({'ok': True, 'filename': filename})

        except Exception as e:

            return jsonify({'ok': False, 'error': str(e)}), 500


    @app.route('/api/ide/execute', methods=['POST'])

    def api_ide_execute():

        data = request.get_json(silent=True) or (request.form if request.form else {})

        filename = data.get('filename') if isinstance(data, dict) else None

        content = data.get('content') if isinstance(data, dict) else None

        shell = data.get('shell') if isinstance(data, dict) else None

        remote = bool(data.get('remote')) if isinstance(data, dict) else False

        if remote:

            return jsonify({'ok': False, 'error': 'remote execution not implemented'}), 501

        try:

            if filename:

                path = _safe_script_path(filename)

                if not path or not path.exists():

                    if content:

                        try:

                            path.write_text(content, encoding='utf-8')

                        except Exception:

                            pass

                    else:

                        return jsonify({'ok': False, 'error': 'file not found'}), 404

                if content and path and path.exists():

                    try:

                        path.write_text(content, encoding='utf-8')

                    except Exception:

                        pass

                cmd = _interpreter_cmd_for_path(path, requested_shell=shell)

                if not cmd:

                    return jsonify({'ok': False, 'error': 'no suitable interpreter found; specify shell explicitly (python,powershell,bash)'}), 500

                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                return jsonify({'ok': True, 'stdout': proc.stdout, 'stderr': proc.stderr, 'returncode': proc.returncode})

            elif content:

                ext = '.sh'

                if shell == 'python':

                    ext = '.py'

                elif shell in ('powershell','ps1'):

                    ext = '.ps1'

                fd, tmp = tempfile.mkstemp(suffix=ext, prefix='masterchief_exec_', dir=str(app.config['SCRIPTS_FOLDER']))

                os.close(fd)

                with open(tmp,'w',encoding='utf-8') as f:

                    f.write(content)

                os.chmod(tmp, 0o755)

                p = Path(tmp)

                if p.suffix == '.py':

                    cmd = [sys.executable, str(p)]

                elif p.suffix == '.ps1':

                    cmd = ['powershell','-ExecutionPolicy','Bypass','-File', str(p)]

                else:

                    cmd = [str(p)]

                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                out = proc.stdout

                err = proc.stderr

                rc = proc.returncode

                try:

                    p.unlink()

                except Exception:

                    pass

                return jsonify({'ok': True, 'stdout': out, 'stderr': err, 'returncode': rc})

            else:

                return jsonify({'ok': False, 'error': 'no filename or content provided'}), 400

        except subprocess.TimeoutExpired:

            return jsonify({'ok': False, 'error':'execution timed out'}), 500

        except Exception as e:

            return jsonify({'ok': False, 'error': str(e)}), 500


    # Remote credential storage for IDE remote execution (basic, stored in data/ide_creds.json)

    CREDS_FILE = Path(__file__).resolve().parent / 'data' / 'ide_creds.json'


    @app.route('/api/ide/remote/creds', methods=['POST'])

    def api_ide_remote_creds_save():

        data = request.get_json(silent=True) or (request.form if request.form else {})

        target = data.get('target') if isinstance(data, dict) else (request.form.get('target') if request.form else None)

        username = data.get('username') if isinstance(data, dict) else (request.form.get('username') if request.form else None)

        password = data.get('password') if isinstance(data, dict) else (request.form.get('password') if request.form else None)

        if not target or not username or not password:

            return jsonify({'ok': False, 'error':'target,username,password required'}), 400

        try:

            d = {}

            if CREDS_FILE.exists():

                try:

                    d = json.loads(CREDS_FILE.read_text(encoding='utf-8'))

                except Exception:

                    d = {}

            d[target] = {'username': username, 'password': password, 'saved_at': datetime.now().isoformat()}

            CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)

            CREDS_FILE.write_text(json.dumps(d, indent=2), encoding='utf-8')

            return jsonify({'ok': True})

        except Exception as e:

            return jsonify({'ok': False, 'error': str(e)}), 500


    @app.route('/api/ide/remote/creds', methods=['GET'])

    def api_ide_remote_creds_get():

        target = request.args.get('target')

        if not target:

            return jsonify({'ok': False, 'error': 'target required'}), 400

        try:

            if not CREDS_FILE.exists():

                return jsonify({'ok': True, 'cred': None})

            d = json.loads(CREDS_FILE.read_text(encoding='utf-8'))

            return jsonify({'ok': True, 'cred': d.get(target)})

        except Exception as e:

            return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/scripts/suggest_commit/<b64path>', methods=['GET'])

@requires_permission('scripts')
def scripts_suggest_commit(b64path):

    path = _b64_decode_path(b64path)

    if not path:

        return jsonify({'success':False,'error':'Invalid path'})

    try:

        p = Path(path)

        if not p.exists():

            return jsonify({'success':False,'error':'File not found'})

        text = p.read_text(encoding='utf-8')

        # simple heuristic: use first non-empty line as summary

        first_line = ''

        for ln in text.splitlines():

            s = ln.strip()

            if s:

                first_line = s

                break

        if first_line:

            summary = f"Edit {p.name}: {first_line[:120]}"

        else:

            summary = f"Edit {p.name}: updated content"

        # escape

        summary = html.escape(summary)

        return jsonify({'success':True,'suggestion':summary})

    except Exception as e:

        return jsonify({'success':False,'error':str(e)})


@app.route('/scripts/diff/<b64path>', methods=['POST'])

@requires_permission('scripts')
def scripts_diff(b64path):

    path = _b64_decode_path(b64path)

    if not path:

        return jsonify({'success':False,'error':'Invalid path'})

    content=request.json.get('content','') if request.is_json else request.form.get('content','')

    try:

        p=Path(path)

        if p.exists():

            original = p.read_text(encoding='utf-8').splitlines()

        else:

            original = []

        new = content.splitlines()

        diff_lines = list(difflib.unified_diff(original, new, fromfile=str(p), tofile=str(p)+' (new)', lineterm=''))

        diff_text = '\n'.join(diff_lines)

        return jsonify({'success':True,'diff':diff_text})

    except Exception as e:

        return jsonify({'success':False,'error':str(e)})


@app.route('/scripts/exec_path/<b64path>', methods=['POST','GET'])

@requires_permission('scripts')
def scripts_exec_path(b64path):

    path = _b64_decode_path(b64path)

    if not path:

        return jsonify({'success':False,'error':'Invalid path'})

    args=request.form.get('args','') if request.method=='POST' else request.args.get('args','')

    try:

        cmd=[]

        p=Path(path)

        if p.suffix=='.py':

            cmd=[sys.executable,str(p)]

        elif p.suffix=='.ps1':

            cmd=['powershell','-ExecutionPolicy','Bypass','-File',str(p)]

        else:

            cmd=[str(p)]

        if args:

            cmd.extend(args.split())

        result=subprocess.run(cmd,capture_output=True,text=True,timeout=300)

        return jsonify({'success':result.returncode==0,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})

    except subprocess.TimeoutExpired:

        return jsonify({'success':False,'error':'Script execution timed out'})

    except Exception as e:

        return jsonify({'success':False,'error':str(e)})

@app.route('/processes')

@requires_permission('processes')
def processes_list():

    processes=get_processes()

    return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}',PROCESSES_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')),processes=processes,request=request,get_flashed_messages=get_flashed_messages)

@app.route('/processes/kill/<int:pid>')

def processes_kill(pid):

    try:

        proc=psutil.Process(pid)

        proc.terminate()

        flash(f'Process {pid} terminated successfully!','success')

    except psutil.NoSuchProcess:

        flash(f'Process {pid} not found','error')

    except psutil.AccessDenied:

        flash(f'Access denied to terminate process {pid}','error')

    except Exception as e:

        flash(f'Failed to terminate process: {str(e)}','error')

    return redirect(url_for('processes_list'))

@app.route('/services')

@requires_permission('services')
def services_list():

    is_windows=sys.platform=='win32'

    services=get_windows_services() if is_windows else []

    return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}',SERVICES_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')),services=services,is_windows=is_windows,request=request,get_flashed_messages=get_flashed_messages)

@app.route('/services/start/<service_name>')

def services_start(service_name):

    if sys.platform=='win32':

        try:

            subprocess.run(['sc','start',service_name],check=True)

            flash(f'Service {service_name} started successfully!','success')

        except Exception as e:

            flash(f'Failed to start service: {str(e)}','error')

    return redirect(url_for('services_list'))

@app.route('/services/stop/<service_name>')

def services_stop(service_name):

    if sys.platform=='win32':

        try:

            subprocess.run(['sc','stop',service_name],check=True)

            flash(f'Service {service_name} stopped successfully!','success')

        except Exception as e:

            flash(f'Failed to stop service: {str(e)}','error')

    return redirect(url_for('services_list'))

@app.route('/services/restart/<service_name>')

def services_restart(service_name):

    if sys.platform=='win32':

        try:

            subprocess.run(['sc','stop',service_name],check=False)

            time.sleep(2)

            subprocess.run(['sc','start',service_name],check=True)

            flash(f'Service {service_name} restarted successfully!','success')

        except Exception as e:

            flash(f'Failed to restart service: {str(e)}','error')

    return redirect(url_for('services_list'))

@app.route('/addons')

@requires_permission('addons')
def addons_list():

    uploaded_files=[]

    upload_folder = app.config['UPLOAD_FOLDER']

    if upload_folder.exists():

        zip_files = list(upload_folder.glob('*.zip'))

        for file in zip_files:

            uploaded_files.append({'name':file.name,'size':file.stat().st_size,'modified':datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')})

    return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}',ADDONS_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')),uploaded_files=uploaded_files,request=request,get_flashed_messages=get_flashed_messages)

@app.route('/addons/upload',methods=['POST'])

def addons_upload():

    if 'file' not in request.files:

        flash('No file selected','error')

        return redirect(url_for('addons_list'))

    file=request.files['file']

    if file.filename=='':

        flash('No file selected','error')

        return redirect(url_for('addons_list'))

    if file and file.filename.endswith('.zip'):

        filename=secure_filename(file.filename)

        filepath=app.config['UPLOAD_FOLDER']/filename

        file.save(filepath)

        # Automatically extract the zip file

        try:

            extract_dir=app.config['UPLOAD_FOLDER']/'extracted'/filename.replace('.zip','')

            extract_dir.mkdir(parents=True,exist_ok=True)

            with zipfile.ZipFile(filepath,'r') as zip_ref:

                zip_ref.extractall(extract_dir)

            flash(f'✅ File {filename} uploaded and automatically extracted to modules!', 'success')

            flash(f'📁 Module available at: /addons/modules/{filename.replace(".zip","")}', 'info')

        except Exception as e:

            flash(f'⚠️ File uploaded but extraction failed: {str(e)}', 'warning')

            flash(f'📁 You can manually extract and access via: /addons/modules/{filename.replace(".zip","")}', 'info')

    else:

        flash('Only .zip files are allowed','error')

    return redirect(url_for('addons_list'))

@app.route('/addons/create_blank_module', methods=['POST'])
def addons_create_blank_module():
    """Create a blank module with empty directory structure."""
    try:
        data = request.get_json() or {}
        module_name = data.get('name', '').strip()
        module_type = data.get('type', 'python')
        description = data.get('description', '').strip()
        capabilities = data.get('capabilities', [])
        auto_load = bool(data.get('auto_load', False))

        if not module_name:
            return jsonify({'success': False, 'error': 'Module name is required'}), 400

        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', module_name):
            return jsonify({'success': False, 'error': 'Module name must start with a letter and contain only letters, numbers, underscores, and hyphens'}), 400

        # Create module directory structure
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
        source_dir = extract_dir  # For blank modules, source_dir is the same as extract_dir

        # Create basic directory structure
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Create basic files based on module type
        if module_type == 'python':
            # Create __init__.py
            (extract_dir / '__init__.py').write_text(f'''"""
{module_name} - {description or 'A custom Python module'}
"""

__version__ = "0.1.0"
__author__ = "MasterChief"
''', encoding='utf-8')

            # Create main.py — a real Flask dev server so Start works out of the box
            (extract_dir / 'main.py').write_text(f'''"""
Main server for {module_name}
{description or ''}
Run directly:  python main.py
Or load via the addon system which calls addon.py init().
"""
from flask import Flask, jsonify, render_template_string
import os

app = Flask(__name__)

INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{module_name}</title>
  <style>
    body {{background:#1a1a1a;color:#e0e0e0;font-family:Arial,sans-serif;padding:40px;text-align:center;}}
    h1 {{color:#4CAF50;}} a {{color:#7B1FA2;}}
  </style>
</head>
<body>
  <h1>🧩 {module_name}</h1>
  <p>{description or 'Custom module — edit main.py or addon.py to get started.'}</p>
  <p><a href="/api/status">API Status</a></p>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/api/status')
def status():
    return jsonify({{'module': '{module_name}', 'status': 'ok', 'version': '0.1.0'}})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'[MC] Running on http://localhost:{{port}}', flush=True)
    app.run(host='0.0.0.0', port=port, debug=False)
''', encoding='utf-8')

            # Create config.py
            (extract_dir / 'config.py').write_text(f'''"""
Configuration for {module_name}
"""

# Module configuration
MODULE_NAME = "{module_name}"
MODULE_VERSION = "0.1.0"
MODULE_DESCRIPTION = "{description or 'A custom Python module'}"

# Add your configuration variables here
DEBUG = True
''', encoding='utf-8')

        elif module_type == 'web':
            # Create basic web structure
            (extract_dir / 'app.py').write_text(f'''"""
Web application for {module_name}
{description or ''}
"""

from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def home():
    return f"<h1>Welcome to {module_name}!</h1><p>{description or 'A custom web application'}</p>"

if __name__ == "__main__":
    app.run(debug=True)
''', encoding='utf-8')

            (extract_dir / 'templates').mkdir(exist_ok=True)
            (extract_dir / 'static').mkdir(exist_ok=True)

        elif module_type == 'api':
            # Create basic API structure
            (extract_dir / 'api.py').write_text(f'''"""
API service for {module_name}
{description or ''}
"""

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/health')
def health():
    return jsonify({{"status": "ok", "module": "{module_name}"}})

@app.route('/api/info')
def info():
    return jsonify({{
        "name": "{module_name}",
        "version": "0.1.0",
        "description": "{description or 'A custom API service'}"
    }})

if __name__ == "__main__":
    app.run(debug=True)
''', encoding='utf-8')

        else:
            # Generic/other type - just create a basic README
            (extract_dir / 'README.md').write_text(f'''# {module_name}

{description or 'A custom module'}

## Getting Started

Add your code and documentation here.

## Usage

Customize this module according to your needs.
''', encoding='utf-8')

        # Create README.md for all types
        readme_path = extract_dir / 'README.md'
        if not readme_path.exists():
            readme_path.write_text(f'''# {module_name}

{description or f'A custom {module_type} module'}

## Description

{description or 'This module was created as a blank template and can be customized as needed.'}

## Files

This module includes the following files:
- Main implementation files
- Configuration files
- Documentation

## Getting Started

1. Add your custom code to the module files
2. Configure any settings in the config files
3. Use the Build and Load buttons to activate the module
4. Register features to make them available system-wide

## Development

Edit files directly through the web interface or upload additional files as needed.
''', encoding='utf-8')

        # ── Capability scaffolding ────────────────────────────────────────
        # Always generate addon.py (blueprint stub) when any integration cap selected
        integration_caps = {'web_ui', 'rest_api', 'echo_hook', 'rbac', 'settings_page'}
        need_addon = bool(set(capabilities) & integration_caps)

        if need_addon or 'web_ui' in capabilities or 'rest_api' in capabilities:
            bp_routes = ''
            if 'web_ui' in capabilities:
                (extract_dir / 'templates').mkdir(exist_ok=True)
                bp_routes += f'''
@bp.route('/')
def index():
    return render_template_string(open(Path(__file__).parent / 'templates' / 'index.html').read())
'''
                (extract_dir / 'templates' / 'index.html').write_text(f'''<!DOCTYPE html>
<html>
<head><title>{module_name}</title></head>
<body style="background:#1a1a1a;color:#e0e0e0;font-family:sans-serif;padding:40px;">
<h1>🧩 {module_name}</h1>
<p>{description or 'Custom module UI — edit templates/index.html'}</p>
</body>
</html>
''', encoding='utf-8')
            if 'rest_api' in capabilities:
                bp_routes += f'''
@bp.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({{'module': '{module_name}', 'status': 'ok'}})

@bp.route('/api/action', methods=['POST'])
def api_action():
    payload = request.get_json() or {{}}
    # TODO: implement action logic
    return jsonify({{'success': True, 'payload': payload}})
'''
            rbac_import = ''
            rbac_check = ''
            if 'rbac' in capabilities:
                rbac_import = '\nfrom functools import wraps'
                rbac_check = '''

def require_role(*roles):
    """Decorator: require the current user to have one of the given roles."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import session, abort
            user_role = session.get('role', 'guest')
            if user_role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator
'''
            echo_hook_code = ''
            if 'echo_hook' in capabilities:
                echo_hook_code = f'''

def register_echo_hook(chatbot):
    """Register an intent handler with the Echo chatbot."""
    def handle_intent(message, context=None):
        # TODO: detect and handle intents
        if '{module_name.lower()}' in message.lower():
            return f'Module {module_name} received: {{message}}'
        return None
    try:
        chatbot.register_plugin('{module_name}', handle_intent)
    except Exception:
        pass
'''
            _echo_call = ('\n    register_echo_hook(app.extensions.get(\'chatbot\'))' if 'echo_hook' in capabilities else '')
            settings_code = ''
            if 'settings_page' in capabilities:
                settings_code = f'''

_settings_defaults = {{
    'enabled': True,
    # add more default settings here
}}

@bp.route('/settings', methods=['GET', 'POST'])
def settings():
    import json as _json
    settings_file = Path(__file__).parent / 'settings.json'
    cfg = dict(_settings_defaults)
    if settings_file.exists():
        try:
            cfg.update(_json.loads(settings_file.read_text()))
        except Exception:
            pass
    if request.method == 'POST':
        for k in _settings_defaults:
            val = request.form.get(k, '')
            cfg[k] = val
        settings_file.write_text(_json.dumps(cfg, indent=2), encoding='utf-8')
    html = """<h2>⚙️ Settings</h2><form method=post>"""
    for k, v in cfg.items():
        html += f'<label>{{k}}: <input name="{{k}}" value="{{v}}"></label><br>'
    html += '<button type=submit>Save</button></form>'
    return html
'''
            (extract_dir / 'addon.py').write_text(f'''"""addon.py — MasterChief Blueprint for {module_name}"""
from flask import Blueprint, jsonify, request, render_template_string, session, abort
from pathlib import Path{rbac_import}

bp = Blueprint('{module_name}', __name__, url_prefix='/modules/{module_name}'){rbac_check}{echo_hook_code}{settings_code}{bp_routes}

def init(app):
    """Called by MasterChief to register this module."""
    app.register_blueprint(bp){_echo_call}
    print(f'Module {module_name} registered at /modules/{module_name}')
''', encoding='utf-8')

        if 'background_jobs' in capabilities:
            (extract_dir / 'jobs.py').write_text(f'''"""Background job runner for {module_name}"""
import threading
import time

_jobs = {{}}

def start_job(job_id, func, *args):
    """Run func(*args) in a daemon thread, tracked by job_id."""
    def _wrapped():
        _jobs[job_id] = {{'status': 'running', 'result': None}}
        try:
            result = func(*args)
            _jobs[job_id] = {{'status': 'done', 'result': result}}
        except Exception as e:
            _jobs[job_id] = {{'status': 'error', 'result': str(e)}}
    t = threading.Thread(target=_wrapped, daemon=True)
    t.start()
    return job_id

def get_job(job_id):
    return _jobs.get(job_id, {{'status': 'not_found'}})

def list_jobs():
    return dict(_jobs)
''', encoding='utf-8')

        if 'scheduled_task' in capabilities:
            (extract_dir / 'scheduler.py').write_text(f'''"""Scheduler for {module_name} — uses a background thread."""
import threading
import time

_stop_event = threading.Event()

def _task_loop(interval_seconds=60):
    while not _stop_event.wait(interval_seconds):
        try:
            run_task()
        except Exception as e:
            print(f"[{module_name}] Scheduled task error: {{e}}")

def run_task():
    """TODO: implement your scheduled logic here."""
    print(f"[{module_name}] tick")

def start_scheduler(interval_seconds=60):
    """Start the background scheduler. Call from addon.py init()."""
    _stop_event.clear()
    t = threading.Thread(target=_task_loop, args=(interval_seconds,), daemon=True)
    t.start()
    return t

def stop_scheduler():
    _stop_event.set()
''', encoding='utf-8')

        if 'sqlite' in capabilities:
            (extract_dir / 'db.py').write_text(f'''"""SQLite helper for {module_name}"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'data.db'

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    key     TEXT NOT NULL,
    value   TEXT,
    created TEXT DEFAULT (datetime('now'))
);
"""

def get_db():
    """Return a new SQLite connection to this module\'s database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they don\'t exist."""
    with get_db() as conn:
        conn.executescript(SCHEMA)

def set_value(key, value):
    with get_db() as conn:
        conn.execute('INSERT OR REPLACE INTO entries (key, value) VALUES (?, ?)', (key, str(value)))

def get_value(key, default=None):
    with get_db() as conn:
        row = conn.execute('SELECT value FROM entries WHERE key=? ORDER BY id DESC LIMIT 1', (key,)).fetchone()
    return row['value'] if row else default

# Auto-init on import
try:
    init_db()
except Exception:
    pass
''', encoding='utf-8')
            # Write db_config.json so DB Manager can discover this module
            import json as _json_w
            (extract_dir / 'db_config.json').write_text(_json_w.dumps({
                'module': module_name,
                'db_file': 'data.db',
                'tables': ['entries']
            }, indent=2), encoding='utf-8')

        # ── Auto-load registration ────────────────────────────────────────────
        if auto_load:
            autoload_file = app.config['UPLOAD_FOLDER'] / 'modules_autoload.json'
            try:
                if autoload_file.exists():
                    autoload_list = json.loads(autoload_file.read_text(encoding='utf-8'))
                else:
                    autoload_list = []
                if module_name not in autoload_list:
                    autoload_list.append(module_name)
                autoload_file.write_text(json.dumps(autoload_list, indent=2), encoding='utf-8')
            except Exception as _ae:
                app.logger.warning(f'Could not update modules_autoload.json: {_ae}')

        # Store module info
        module_info = {
            'name': module_name,
            'extract_dir': str(extract_dir),
            'source_dir': str(source_dir),
            'installed_at': datetime.now().isoformat(),
            'type': module_type,
            'description': description,
            'is_blank_module': True,
            'capabilities': capabilities,
            'auto_load': auto_load
        }

        # Save module info
        modules_file = app.config['UPLOAD_FOLDER'] / 'modules.json'
        try:
            if modules_file.exists():
                with open(modules_file, 'r') as f:
                    modules = json.load(f)
            else:
                modules = {}

            modules[module_name] = module_info

            with open(modules_file, 'w') as f:
                json.dump(modules, f, indent=2)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Could not save module info: {str(e)}'}), 500

        return jsonify({
            'success': True,
            'message': f'Blank module "{module_name}" created successfully',
            'module': module_info
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/addons/install/<filename>', methods=['GET', 'POST'])

def addons_install(filename):

    filepath=app.config['UPLOAD_FOLDER']/secure_filename(filename)

    if not filepath.exists():

        flash('File not found','error')

        return redirect(url_for('addons_list'))

    # Get source directory from form

    source_dir = request.form.get('source_dir', '').strip()

    try:

        extract_dir=app.config['UPLOAD_FOLDER']/'extracted'/filename.replace('.zip','')

        extract_dir.mkdir(parents=True,exist_ok=True)

        with zipfile.ZipFile(filepath,'r') as zip_ref:

            zip_ref.extractall(extract_dir)

        # Determine the actual project root (handle zips with top-level folder)
        project_root = extract_dir
        subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        files_at_root = [f for f in extract_dir.iterdir() if f.is_file()]
        
        if len(subdirs) == 1 and not files_at_root:
            # Zip has a single top-level directory, use that as project root
            project_root = subdirs[0]
        
        # Apply source directory if specified
        final_source_dir = project_root
        if source_dir:
            potential_src = project_root / source_dir
            if potential_src.exists() and potential_src.is_dir():
                final_source_dir = potential_src
                flash(f'📁 Using source directory: {source_dir}', 'info')
            else:
                flash(f'⚠️ Source directory "{source_dir}" not found in {project_root.name}, using project root', 'warning')
        

        # Store the source directory info for this module

        module_name = filename.replace('.zip', '')

        module_info = {

            'name': module_name,

            'extract_dir': str(extract_dir),

            'source_dir': str(final_source_dir),

            'installed_at': datetime.now().isoformat()

        }

        

        # Save module info (you might want to store this in a file or database)

        modules_file = app.config['UPLOAD_FOLDER'] / 'modules.json'

        try:

            if modules_file.exists():

                with open(modules_file, 'r') as f:

                    modules = json.load(f)

            else:

                modules = {}

            modules[module_name] = module_info

            with open(modules_file, 'w') as f:

                json.dump(modules, f, indent=2)

        except Exception as e:

            flash(f'⚠️ Could not save module info: {str(e)}', 'warning')

        # --- Auto-launch: detect entry point and start the application ---
        launch_result = launch_addon(module_name, extract_dir)
        if launch_result['status'] == 'started':
            flash(f'🚀 Auto-launched {launch_result["entry_point"]} (PID {launch_result["pid"]})', 'success')
            # Persist entry point info
            try:
                modules[module_name]['entry_point'] = launch_result['entry_point']
                modules[module_name]['entry_type'] = launch_result['type']
                with open(modules_file, 'w') as f:
                    json.dump(modules, f, indent=2)
            except Exception:
                pass
        elif launch_result['status'] == 'html':
            flash(f'🌐 Static app detected — open via <a href="{launch_result["url"]}">{launch_result["entry_point"]}</a>', 'info')
            try:
                modules[module_name]['entry_point'] = launch_result['entry_point']
                modules[module_name]['entry_type'] = 'html'
                modules[module_name]['html_url'] = launch_result['url']
                with open(modules_file, 'w') as f:
                    json.dump(modules, f, indent=2)
            except Exception:
                pass
        elif launch_result['status'] == 'no_entry_point':
            flash('ℹ️ No entry point found (main.py / index.py / index.html / index.php / etc.) — use the module manager to add files', 'info')
        else:
            flash(f'⚠️ Could not auto-launch: {launch_result["message"]}', 'warning')

        flash(f'✅ Addon {filename} installed successfully', 'success')

        flash(f'📁 Module available at: /addons/modules/{module_name}', 'info')

        if source_dir:

            flash(f'🔧 Source directory set to: {source_dir}', 'info')

    except Exception as e:

        flash(f'❌ Failed to install addon: {str(e)}','error')

    return redirect(url_for('addons_list'))

@app.route('/addons/build/<filename>')
def addons_build(filename):
    """Analyze a zip file for build commands without full installation"""
    filepath = app.config['UPLOAD_FOLDER'] / secure_filename(filename)
    
    if not filepath.exists():
        flash('File not found', 'error')
        return redirect(url_for('addons_list'))
    
    try:
        # Create temporary extraction directory
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Extract zip file temporarily
            with zipfile.ZipFile(filepath, 'r') as zip_ref:
                zip_ref.extractall(temp_path)
            
            # Find the actual project directory (handle zips with top-level folder)
            extract_dir = temp_path
            subdirs = [d for d in temp_path.iterdir() if d.is_dir()]
            files_at_root = [f for f in temp_path.iterdir() if f.is_file()]
            
            if len(subdirs) == 1 and not files_at_root:
                # Zip has a single top-level directory, use that as project root
                extract_dir = subdirs[0]
            
            # Analyze for build commands
            project_info = detect_project_type(extract_dir)
            build_commands = detect_build_commands(extract_dir, project_info)
            
            if build_commands:
                flash(f'🔨 {filename} contains buildable source code ({project_info["type"]})', 'info')
                flash(f'📋 Detected {len(build_commands)} build step(s). Install first, then use Build option.', 'info')
                if project_info['frameworks']:
                    flash(f'🛠️ Frameworks: {", ".join(project_info["frameworks"])}', 'info')
            else:
                flash(f'ℹ️ {filename} does not appear to contain buildable source code', 'info')
                
    except Exception as e:
        flash(f'Failed to analyze addon: {str(e)}', 'error')
    
    return redirect(url_for('addons_list'))

@app.route('/addons/delete/<filename>')

def addons_delete(filename):

    filepath=app.config['UPLOAD_FOLDER']/secure_filename(filename)

    if filepath.exists():

        filepath.unlink()

        flash(f'File {filename} deleted successfully!','success')

    else:

        flash('File not found','error')

    return redirect(url_for('addons_list'))

@app.route('/addons/load/<addon_name>')

def addons_load(addon_name):

    """Load an installed addon by importing its main module"""

    try:

        # Check if addon is installed

        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / addon_name

        if not extract_dir.exists():

            flash(f'Addon {addon_name} is not installed','error')

            return redirect(url_for('addons_list'))

        

        # Detect project type

        project_info = detect_project_type(extract_dir)

        

        if project_info['has_python']:

            # Handle Python addon

            # Look for addon.py or __init__.py in the extracted directory

            addon_file = extract_dir / 'addon.py'

            init_file = extract_dir / '__init__.py'

            

            if addon_file.exists():

                # Import the addon module

                import importlib.util

                spec = importlib.util.spec_from_file_location(f"addon_{addon_name}", str(addon_file))

                if spec and spec.loader:

                    addon_module = importlib.util.module_from_spec(spec)

                    spec.loader.exec_module(addon_module)

                    

                    # Call init function if it exists

                    if hasattr(addon_module, 'init'):

                        addon_module.init(app)

                    

                    flash(f'Python addon {addon_name} loaded successfully!','success')

                else:

                    flash(f'Failed to load Python addon {addon_name}: invalid module','error')

            elif init_file.exists():

                # Try loading as a package

                import sys

                if str(extract_dir) not in sys.path:

                    sys.path.insert(0, str(extract_dir))

                

                try:

                    addon_module = __import__(addon_name)

                    if hasattr(addon_module, 'init'):

                        addon_module.init(app)

                    flash(f'Python addon {addon_name} loaded successfully!','success')

                except ImportError as e:

                    flash(f'Failed to import Python addon {addon_name}: {str(e)}','error')

            else:

                flash(f'Python addon {addon_name} does not have a valid entry point (addon.py or __init__.py)','error')

        elif project_info['has_php']:

            # Handle PHP web application — locate/download PHP then launch server
            primary_type = 'PHP'
            if project_info['has_nodejs']:
                primary_type = 'Node.js/PHP'
            elif len([k for k in ['has_java', 'has_csharp', 'has_cpp', 'has_go', 'has_rust'] if project_info.get(k)]) > 0:
                primary_type = 'PHP/Multi-language'

            try:
                _find_php()  # locates or auto-downloads PHP 8.3 — raises RuntimeError if it fails
                result = launch_addon(addon_name, extract_dir)
                if result.get('status') == 'started':
                    flash(f'✅ PHP addon {addon_name} started (PID {result["pid"]}, port {result["port"]})', 'success')
                    flash(f'🌐 Access at: /addons/modules/{addon_name}/app/', 'info')
                elif result.get('status') == 'html':
                    flash(f'🌐 PHP/HTML addon {addon_name} ready — open via /addons/modules/{addon_name}/', 'info')
                else:
                    flash(f'⚠️ PHP addon {addon_name}: {result.get("message", "unknown")}', 'warning')
            except RuntimeError as _php_e:
                flash(f'❌ PHP not available: {_php_e}', 'error')
            except Exception as _php_e:
                flash(f'❌ Failed to launch PHP addon {addon_name}: {_php_e}', 'error')

            flash(f'Type: {primary_type} — Frameworks: {", ".join(project_info["frameworks"]) if project_info["frameworks"] else "None detected"}', 'info')

        else:

            # Handle other types or unknown

            flash(f'Addon {addon_name} loaded as {project_info["type"]} application','success')

            if project_info['frameworks']:

                flash(f'Detected frameworks: {", ".join(project_info["frameworks"])}','info')

            

    except Exception as e:

        flash(f'Failed to load addon {addon_name}: {str(e)}','error')

    

    return redirect(url_for('addons_list'))

@app.route('/addons/register_features/<addon_name>')

def addons_register_features(addon_name):

    """Register features from a loaded addon"""

    try:

        # Check if addon is installed

        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / addon_name

        if not extract_dir.exists():

            flash(f'Addon {addon_name} is not installed','error')

            return redirect(url_for('addons_list'))

        

        # Detect project type

        project_info = detect_project_type(extract_dir)

        

        if project_info['has_python']:

            # Handle Python addon features

            features_file = extract_dir / 'features.json'

            if features_file.exists():

                import json

                with open(features_file, 'r') as f:

                    features_data = json.load(f)

                

                # Register features (this would integrate with the feature manager)

                # For now, just acknowledge the features file exists

                flash(f'Features registered for Python addon {addon_name} ({len(features_data.get("features", []))} features)','success')

            else:

                flash(f'No features.json found for Python addon {addon_name}','warning')

        elif project_info['has_php']:

            # PHP web applications don't have features to register

            flash(f'PHP web application {addon_name} does not have features to register','info')

        else:

            # Other types

            flash(f'Addon {addon_name} ({project_info["type"]}) does not support feature registration','info')

            

    except Exception as e:

        flash(f'Failed to register features for addon {addon_name}: {str(e)}','error')

    

    return redirect(url_for('addons_list'))

@app.route('/addons/modules')
def addons_modules():
    """List and manage installed addon modules"""
    installed_modules = []
    
    # Check both current workspace and the cool-elbakyan workspace
    extract_dirs = [
        app.config['UPLOAD_FOLDER'] / 'extracted',
        Path(__file__).parent / '.claude' / 'worktrees' / 'cool-elbakyan' / 'data' / 'uploads' / 'extracted'
    ]
    
    for extract_dir in extract_dirs:
        if extract_dir.exists():
            for module_dir in extract_dir.iterdir():
                if module_dir.is_dir():
                    try:
                        # Get module info with basic file scanning
                        config_files = []
                        readme_files = []
                        setup_scripts = []
                        requirements_files = []
                        language = 'unknown'
                        total_files = 0
                        total_size = 0
                        
                        # Quick scan of files (limit to avoid performance issues)
                        try:
                            for file_path in module_dir.rglob('*'):
                                if file_path.is_file():
                                    total_files += 1
                                    try:
                                        total_size += file_path.stat().st_size
                                    except:
                                        pass
                                    
                                    # Limit scanning for performance
                                    if total_files > 500:
                                        break
                                    
                                    name = file_path.name.lower()
                                    rel_path = str(file_path.relative_to(module_dir))
                                    
                                    # Categorize files
                                    if any(name.endswith(ext) for ext in ['.conf', '.config', '.ini', '.cfg', '.json', '.yml', '.yaml']):
                                        if len(config_files) < 10:
                                            config_files.append(rel_path)
                                    elif name in ['readme', 'readme.txt', 'readme.md', 'install.txt', 'setup.txt']:
                                        if len(readme_files) < 5:
                                            readme_files.append(rel_path)
                                    elif any(name.endswith(ext) for ext in ['.sh', '.bat', '.ps1', '.py', '.php']) or any(name.startswith(prefix) for prefix in ['setup.', 'install.', 'configure.']) or any(name in ['install.php', 'setup.php', 'installer.php', 'wizard.php']):
                                        if len(setup_scripts) < 10:  # Increased limit
                                            setup_scripts.append(rel_path)
                                    elif name in ['requirements.txt', 'package.json', 'composer.json', 'gemfile', 'cargo.toml', 'pyproject.toml']:
                                        requirements_files.append(rel_path)
                                    
                                    # Detect language
                                    if language == 'unknown':
                                        if name.endswith(('.py', '__init__.py')):
                                            language = 'python'
                                        elif name.endswith(('.php', 'composer.json')):
                                            language = 'php'
                                        elif name.endswith(('.cs', '.csproj')):
                                            language = 'csharp'
                                        elif name.endswith(('.js', 'package.json')):
                                            language = 'javascript'
                                        elif name.endswith(('.c', '.cpp', '.h')):
                                            language = 'c/c++'
                        except:
                            # If scanning fails, continue with basic info
                            pass
                        
                        # Load module info to get source directory
                        modules_file = app.config['UPLOAD_FOLDER'] / 'modules.json'
                        source_dir = module_dir
                        if modules_file.exists():
                            try:
                                with open(modules_file, 'r') as f:
                                    modules = json.load(f)
                                if module_dir.name in modules:
                                    stored_source = modules[module_dir.name].get('source_dir')
                                    if stored_source and Path(stored_source).exists():
                                        source_dir = Path(stored_source)
                            except Exception:
                                pass
                        
                        # Detect project type and build commands using source_dir
                        project_info = detect_project_type(source_dir)
                        build_commands = detect_build_commands(source_dir, project_info)
                        
                        module_info = {
                            'name': module_dir.name,
                            'path': str(source_dir) if source_dir != module_dir else str(module_dir),
                            'size': total_size,
                            'files': total_files,
                            'modified': datetime.fromtimestamp(module_dir.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                            'config_files': config_files,
                            'readme_files': readme_files,
                            'setup_scripts': setup_scripts,
                            'requirements_files': requirements_files,
                            'language': language,
                            'project_type': project_info['type'],
                            'frameworks': project_info['frameworks'],
                            'build_commands': build_commands
                        }
                        
                        installed_modules.append(module_info)
                        
                    except (OSError, PermissionError) as e:
                        # Skip modules with access issues
                        continue
    
    # Load pinned modules so the template can show pin state
    ui_modules = {}
    try:
        ui_modules_file = app.config['UPLOAD_FOLDER'] / 'ui_modules.json'
        if ui_modules_file.exists():
            with open(ui_modules_file, 'r') as _f:
                ui_modules = json.load(_f)
    except Exception:
        pass

    return render_addons_modules_page(installed_modules, ui_modules=ui_modules)

@app.route('/addons/modules/<module_name>/manager')
def module_manager(module_name):
    """Module file manager and editor interface"""
    try:
        # Get module directory
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
        if not extract_dir.exists():
            flash(f'Module "{module_name}" not found', 'error')
            return redirect('/addons/modules')
        
        # Get all files in the module
        files = []
        def scan_directory(path, relative_path=''):
            try:
                for item in sorted(path.iterdir()):
                    if item.is_file():
                        try:
                            size = item.stat().st_size
                            modified = datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                            files.append({
                                'name': item.name,
                                'path': item.relative_to(extract_dir).as_posix(),
                                'size': size,
                                'modified': modified,
                                'type': 'file',
                                'extension': item.suffix.lower()
                            })
                        except:
                            pass
                    elif item.is_dir():
                        try:
                            files.append({
                                'name': item.name,
                                'path': item.relative_to(extract_dir).as_posix(),
                                'size': 0,
                                'modified': datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                'type': 'directory',
                                'extension': ''
                            })
                            scan_directory(item)
                        except:
                            pass
            except:
                pass
        
        scan_directory(extract_dir)
        
        # Get module info
        module_info = {
            'name': module_name,
            'path': str(extract_dir),
            'file_count': len([f for f in files if f['type'] == 'file']),
            'dir_count': len([f for f in files if f['type'] == 'directory']),
            'total_size': sum(f['size'] for f in files if f['type'] == 'file')
        }
        
        return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}', MODULE_MANAGER_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')), 
                                    module=module_info, files=files, request=request, get_flashed_messages=get_flashed_messages)
        
        return render_module_manager_page(module_info)
        
    except Exception as e:
        flash(f'Error loading module manager: {str(e)}', 'error')
        return redirect('/addons/modules')

@app.route('/addons/modules/<module_name>/config/<path:config_file>')
def addons_module_config(module_name, config_file):
    """View/edit config files for a module"""
    try:
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
        config_path = extract_dir / config_file
        
        if not config_path.exists() or not config_path.is_file():
            flash(f'Config file not found: {config_file}', 'error')
            return redirect(url_for('addons_modules'))
        
        with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return render_addons_module_config_page(module_name, config_file, content)
    
    except Exception as e:
        flash(f'Error reading config file: {str(e)}', 'error')
        return redirect(url_for('addons_modules'))

@app.route('/addons/modules/<module_name>/config/<path:config_file>', methods=['POST'])
def addons_module_config_save(module_name, config_file):
    """Save changes to a config file"""
    try:
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
        config_path = extract_dir / config_file
        
        if not config_path.exists():
            flash(f'Config file not found: {config_file}', 'error')
            return redirect(url_for('addons_modules'))
        
        content = request.form.get('content', '')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        flash(f'Config file saved successfully: {config_file}', 'success')
        return redirect(url_for('addons_module_config', module_name=module_name, config_file=config_file))
    
    except Exception as e:
        flash(f'Error saving config file: {str(e)}', 'error')
        return redirect(url_for('addons_module_config', module_name=module_name, config_file=config_file))

@app.route('/addons/modules/<module_name>/install_deps', methods=['POST'])
def addons_module_install_deps(module_name):
    """Install dependencies for a module with verbose output"""
    try:
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name

        if not extract_dir.exists():
            flash(f'Module not found: {module_name}', 'error')
            return redirect(url_for('addons_modules'))

        # Check if this is a zip file that needs extraction
        zip_file = app.config['UPLOAD_FOLDER'] / f"{module_name}.zip"
        if zip_file.exists() and not extract_dir.exists():
            try:
                import zipfile
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                flash(f'📦 Extracted {module_name}.zip successfully', 'info')
            except Exception as e:
                flash(f'❌ Failed to extract zip file: {str(e)}', 'error')
                return redirect(url_for('addons_modules'))

        success_messages = []
        error_messages = []
        verbose_output = []

        # Detect project type and dependencies
        project_info = detect_project_type(extract_dir)
        verbose_output.append(f"🔍 Detected project type: {project_info['type']}")
        verbose_output.append(f"📁 Project files: {len(list(extract_dir.rglob('*')))} total files")

        # Python dependencies
        if project_info['has_python']:
            req_files = list(extract_dir.glob('requirements*.txt')) + list(extract_dir.glob('pyproject.toml')) + list(extract_dir.glob('setup.py'))
            for req_file in req_files:
                try:
                    verbose_output.append(f"🐍 Found Python dependency file: {req_file.name}")
                    if req_file.name == 'requirements.txt' or req_file.name.startswith('requirements'):
                        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req_file)],
                                              capture_output=True, text=True, cwd=str(extract_dir), timeout=300)
                    elif req_file.name == 'pyproject.toml':
                        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-e', '.'],
                                              capture_output=True, text=True, cwd=str(extract_dir), timeout=300)
                    elif req_file.name == 'setup.py':
                        result = subprocess.run([sys.executable, str(req_file), 'develop'],
                                              capture_output=True, text=True, cwd=str(extract_dir), timeout=300)

                    if result.returncode == 0:
                        success_messages.append(f'✅ Python dependencies installed from {req_file.name}')
                        if result.stdout.strip():
                            verbose_output.append(f"📤 pip output: {result.stdout.strip()[:200]}...")
                    else:
                        error_messages.append(f'❌ Failed to install Python dependencies from {req_file.name}')
                        verbose_output.append(f"📤 pip error: {result.stderr.strip()[:200]}...")
                except subprocess.TimeoutExpired:
                    error_messages.append(f'⏰ Timeout installing Python dependencies from {req_file.name}')
                except Exception as e:
                    error_messages.append(f'❌ Error installing Python dependencies: {str(e)}')

        # Node.js dependencies
        if project_info['has_nodejs']:
            package_files = list(extract_dir.glob('package*.json'))
            for package_file in package_files:
                try:
                    verbose_output.append(f"📦 Found Node.js package file: {package_file.name}")
                    result = subprocess.run(['npm', 'install'], capture_output=True, text=True, cwd=str(extract_dir), timeout=300)
                    if result.returncode == 0:
                        success_messages.append('✅ Node.js dependencies installed successfully')
                        if result.stdout.strip():
                            verbose_output.append(f"📤 npm output: {result.stdout.strip()[:200]}...")
                    else:
                        error_messages.append(f'❌ Failed to install Node.js dependencies')
                        verbose_output.append(f"📤 npm error: {result.stderr.strip()[:200]}...")
                except subprocess.TimeoutExpired:
                    error_messages.append('⏰ Timeout installing Node.js dependencies')
                except Exception as e:
                    error_messages.append(f'❌ Error installing Node.js dependencies: {str(e)}')

        # PHP Composer dependencies
        if project_info['has_php']:
            composer_files = list(extract_dir.glob('composer*.json'))
            for composer_file in composer_files:
                try:
                    verbose_output.append(f"🐘 Found PHP composer file: {composer_file.name}")
                    result = subprocess.run(['composer', 'install', '--no-interaction'], capture_output=True, text=True, cwd=str(extract_dir), timeout=300)
                    if result.returncode == 0:
                        success_messages.append('✅ PHP dependencies installed successfully')
                        if result.stdout.strip():
                            verbose_output.append(f"📤 composer output: {result.stdout.strip()[:200]}...")
                    else:
                        error_messages.append(f'❌ Failed to install PHP dependencies')
                        verbose_output.append(f"📤 composer error: {result.stderr.strip()[:200]}...")
                except subprocess.TimeoutExpired:
                    error_messages.append('⏰ Timeout installing PHP dependencies')
                except Exception as e:
                    error_messages.append(f'❌ Error installing PHP dependencies: {str(e)}')

        # Build/compile processes
        build_commands = detect_build_commands(extract_dir, project_info)
        for cmd_info in build_commands:
            try:
                verbose_output.append(f"🔨 Running build command: {' '.join(cmd_info['command'])}")
                result = subprocess.run(cmd_info['command'], capture_output=True, text=True, cwd=str(extract_dir), timeout=600)
                if result.returncode == 0:
                    success_messages.append(f"✅ Build completed: {cmd_info['description']}")
                    if result.stdout.strip():
                        verbose_output.append(f"📤 build output: {result.stdout.strip()[:200]}...")
                else:
                    error_messages.append(f"❌ Build failed: {cmd_info['description']}")
                    verbose_output.append(f"📤 build error: {result.stderr.strip()[:200]}...")
                    # Don't continue with other build steps if one fails
                    break
            except subprocess.TimeoutExpired:
                error_messages.append(f"⏰ Build timeout: {cmd_info['description']}")
                break
            except Exception as e:
                error_messages.append(f"❌ Build error: {str(e)}")
                break

        # Show verbose output
        for msg in verbose_output[:10]:  # Limit to first 10 messages to avoid overwhelming
            flash(msg, 'info')

        if success_messages:
            flash('🎉 Installation completed successfully!', 'success')
            for msg in success_messages:
                flash(msg, 'success')
        if error_messages:
            flash('⚠️ Some installation steps failed:', 'warning')
            for msg in error_messages:
                flash(msg, 'error')

        if not success_messages and not error_messages:
            flash('ℹ️ No dependencies or build processes detected for this module', 'info')

    except Exception as e:
        flash(f'❌ Critical error during installation: {str(e)}', 'error')

    return redirect(url_for('addons_modules'))

def detect_project_type(extract_dir):
    """Detect the type of project and its characteristics"""
    project_info = {
        'type': 'Unknown',
        'has_python': False,
        'has_nodejs': False,
        'has_php': False,
        'has_java': False,
        'has_csharp': False,
        'has_cpp': False,
        'has_go': False,
        'has_rust': False,
        'frameworks': []
    }

    # Check for various project files
    try:
        files = list(extract_dir.rglob('*'))
        file_names = []
        for f in files[:1000]:  # Limit to first 1000 files for performance
            try:
                if f.is_file():
                    file_names.append(f.name.lower())
            except:
                continue  # Skip files we can't access
    except Exception as e:
        file_names = []

    # Python detection
    python_indicators = ['requirements.txt', 'setup.py', 'pyproject.toml', 'pipfile', '__init__.py', '.py']
    if any(ind in ' '.join(file_names) for ind in python_indicators):
        project_info['has_python'] = True
        project_info['type'] = 'Python'
        if any('django' in f.lower() for f in file_names):
            project_info['frameworks'].append('Django')
        if any('flask' in f.lower() for f in file_names):
            project_info['frameworks'].append('Flask')
        if any('fastapi' in f.lower() for f in file_names):
            project_info['frameworks'].append('FastAPI')

    # Node.js detection
    nodejs_indicators = ['package.json', 'node_modules', '.js', '.ts', 'webpack.config.js', 'gulpfile.js']
    if any(ind in ' '.join(file_names) for ind in nodejs_indicators):
        project_info['has_nodejs'] = True
        if project_info['type'] == 'Unknown':
            project_info['type'] = 'Node.js'
        else:
            project_info['type'] += '/Node.js'
        if any('react' in f.lower() for f in file_names):
            project_info['frameworks'].append('React')
        if any('vue' in f.lower() for f in file_names):
            project_info['frameworks'].append('Vue.js')
        if any('angular' in f.lower() for f in file_names):
            project_info['frameworks'].append('Angular')

    # PHP detection
    php_indicators = ['composer.json', 'composer.lock', '.php', 'artisan', 'wp-config.php', 'index.php']
    if any(ind in ' '.join(file_names) for ind in php_indicators):
        project_info['has_php'] = True
        if project_info['type'] == 'Unknown':
            project_info['type'] = 'PHP'
        else:
            project_info['type'] += '/PHP'
        if any('laravel' in f.lower() for f in file_names) or 'artisan' in file_names:
            project_info['frameworks'].append('Laravel')
        if 'wp-config.php' in file_names:
            project_info['frameworks'].append('WordPress')
        if any('symfony' in f.lower() for f in file_names):
            project_info['frameworks'].append('Symfony')

    # Java detection
    java_indicators = ['pom.xml', 'build.gradle', 'build.gradle.kts', '.java', 'mvnw', 'gradlew']
    if any(ind in ' '.join(file_names) for ind in java_indicators):
        project_info['has_java'] = True
        if project_info['type'] == 'Unknown':
            project_info['type'] = 'Java'
        else:
            project_info['type'] += '/Java'
        if 'pom.xml' in file_names:
            project_info['frameworks'].append('Maven')
        if 'build.gradle' in file_names:
            project_info['frameworks'].append('Gradle')

    # C#/.NET detection
    csharp_indicators = ['.csproj', '.sln', '.cs', 'packages.config', 'project.json']
    if any(ind in ' '.join(file_names) for ind in csharp_indicators):
        project_info['has_csharp'] = True
        if project_info['type'] == 'Unknown':
            project_info['type'] = 'C#'
        else:
            project_info['type'] += '/C#'

    # C/C++ detection
    cpp_indicators = ['CMakeLists.txt', 'Makefile', 'configure', '.cpp', '.c', '.h', '.hpp']
    if any(ind in ' '.join(file_names) for ind in cpp_indicators):
        project_info['has_cpp'] = True
        if project_info['type'] == 'Unknown':
            project_info['type'] = 'C/C++'
        else:
            project_info['type'] += '/C/C++'

    # Go detection
    go_indicators = ['go.mod', 'go.sum', '.go', 'main.go']
    if any(ind in ' '.join(file_names) for ind in go_indicators):
        project_info['has_go'] = True
        if project_info['type'] == 'Unknown':
            project_info['type'] = 'Go'
        else:
            project_info['type'] += '/Go'

    # Rust detection
    rust_indicators = ['Cargo.toml', 'Cargo.lock', '.rs', 'src/main.rs']
    if any(ind in ' '.join(file_names) for ind in rust_indicators):
        project_info['has_rust'] = True
        if project_info['type'] == 'Unknown':
            project_info['type'] = 'Rust'
        else:
            project_info['type'] += '/Rust'

    return project_info

def detect_build_commands(extract_dir, project_info):
    """Detect appropriate build commands for the project"""
    build_commands = []

    # Python builds
    if project_info['has_python']:
        if (extract_dir / 'setup.py').exists():
            build_commands.append({
                'command': [sys.executable, 'setup.py', 'build'],
                'description': 'Python setup.py build'
            })
        if (extract_dir / 'pyproject.toml').exists():
            build_commands.append({
                'command': [sys.executable, '-m', 'build'],
                'description': 'Python build package'
            })

    # PHP builds
    if project_info['has_php']:
        if (extract_dir / 'composer.json').exists():
            build_commands.append({
                'command': ['composer', 'install'],
                'description': 'Composer install dependencies'
            })

    # Node.js builds
        if (extract_dir / 'package.json').exists():
            package_json = extract_dir / 'package.json'
            try:
                import json
                with open(package_json, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    if 'scripts' in package_data:
                        scripts = package_data['scripts']
                        if 'build' in scripts:
                            build_commands.append({
                                'command': ['npm', 'run', 'build'],
                                'description': 'npm build script'
                            })
                        if 'compile' in scripts:
                            build_commands.append({
                                'command': ['npm', 'run', 'compile'],
                                'description': 'npm compile script'
                            })
            except:
                pass

    # Java/Maven builds
    if project_info['has_java']:
        if (extract_dir / 'pom.xml').exists():
            build_commands.append({
                'command': ['mvn', 'compile'],
                'description': 'Maven compile'
            })
        if (extract_dir / 'build.gradle').exists():
            build_commands.append({
                'command': ['./gradlew', 'build'],
                'description': 'Gradle build'
            })

    # C/C++ builds
    if project_info['has_cpp']:
        if (extract_dir / 'CMakeLists.txt').exists():
            # CMake build - need to run cmake first, then make
            build_commands.append({
                'command': ['C:\\Program Files\\CMake\\bin\\cmake.exe', '-S', '.', '-B', 'build'],
                'description': 'CMake configure'
            })
            build_commands.append({
                'command': ['C:\\Program Files\\CMake\\bin\\cmake.exe', '--build', 'build'],
                'description': 'CMake build'
            })
        elif (extract_dir / 'Makefile').exists():
            build_commands.append({
                'command': ['make'],
                'description': 'Make build'
            })
        elif (extract_dir / 'configure').exists():
            # Autotools build
            build_commands.append({
                'command': ['./configure'],
                'description': 'Configure build'
            })
            build_commands.append({
                'command': ['make'],
                'description': 'Make build'
            })

    # Go builds
    if project_info['has_go']:
        if (extract_dir / 'go.mod').exists():
            build_commands.append({
                'command': ['go', 'build', './...'],
                'description': 'Go build'
            })

    # Rust builds
    if project_info['has_rust']:
        if (extract_dir / 'Cargo.toml').exists():
            build_commands.append({
                'command': ['cargo', 'build', '--release'],
                'description': 'Cargo build release'
            })

    return build_commands

@app.route('/addons/modules/<module_name>/run_setup/<path:setup_script>', methods=['POST'])
def addons_module_run_setup(module_name, setup_script):
    """Run a setup script for a module with enhanced support"""
    try:
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
        script_path = extract_dir / setup_script

        if not script_path.exists():
            flash(f'❌ Setup script not found: {setup_script}', 'error')
            return redirect(url_for('addons_modules'))

        import subprocess
        verbose_output = []

        # Handle different script types
        if setup_script.endswith('.py'):
            verbose_output.append(f'🐍 Running Python script: {setup_script}')
            result = subprocess.run([sys.executable, str(script_path)],
                                  capture_output=True, text=True, cwd=str(extract_dir), timeout=300)
        elif setup_script.endswith('.sh'):
            verbose_output.append(f'🐚 Running shell script: {setup_script}')
            result = subprocess.run(['bash', str(script_path)],
                                  capture_output=True, text=True, cwd=str(extract_dir), timeout=300)
        elif setup_script.endswith('.bat') or setup_script.endswith('.ps1'):
            verbose_output.append(f'⚡ Running PowerShell script: {setup_script}')
            result = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', str(script_path)],
                                  capture_output=True, text=True, cwd=str(extract_dir), timeout=300)
        elif setup_script.endswith('.php'):
            # PHP web-based setup scripts
            verbose_output.append(f'🐘 PHP setup script detected: {setup_script}')
            verbose_output.append(f'🌐 This appears to be a web-based installer')
            _mc_url = app.config.get('MC_BASE_URL', 'http://127.0.0.1:8080')
            verbose_output.append(f'💡 Access it via: {_mc_url}/addons/modules/{module_name}/web/{setup_script}')

            # Use _find_php() which will auto-download PHP 8.3 if not installed
            try:
                verbose_output.append('🔍 Locating PHP (will auto-download if needed)...')
                php_bin = _find_php()
                php_ver = subprocess.run([php_bin, '--version'], capture_output=True, text=True, timeout=10)
                ver_line = php_ver.stdout.splitlines()[0] if php_ver.stdout else 'PHP'
                verbose_output.append(f'✅ {ver_line}')

                if (extract_dir / 'composer.json').exists() or (extract_dir / 'index.php').exists():
                    # Actually execute the setup script with the located PHP binary
                    php_result = subprocess.run(
                        [php_bin, str(script_path)],
                        capture_output=True, text=True,
                        cwd=str(extract_dir), timeout=120
                    )
                    if php_result.returncode == 0:
                        verbose_output.append('✅ PHP setup script ran successfully')
                        if php_result.stdout.strip():
                            verbose_output.append(f'Output: {php_result.stdout.strip()[:200]}')
                        flash(f'✅ PHP setup script executed: {setup_script}', 'success')
                    else:
                        err = php_result.stderr.strip()[:300] or php_result.stdout.strip()[:300]
                        verbose_output.append(f'⚠️ PHP script exited {php_result.returncode}: {err}')
                        flash(f'⚠️ PHP setup finished with errors (exit {php_result.returncode})', 'warning')
                else:
                    flash(f'ℹ️ PHP binary ready at: {php_bin}', 'info')
                    flash(f'💡 Run manually if needed: php {setup_script}', 'info')

            except RuntimeError as _php_err:
                verbose_output.append(f'❌ {_php_err}')
                flash(f'❌ PHP unavailable: {_php_err}', 'error')
            except Exception as _php_err:
                verbose_output.append(f'❌ PHP error: {_php_err}')
                flash(f'❌ PHP setup failed: {_php_err}', 'error')

            # Show verbose output and return
            for msg in verbose_output[:5]:
                flash(msg, 'info')
            return redirect(url_for('addons_modules'))
        else:
            # Try to detect if it's executable
            if script_path.stat().st_mode & 0o111:  # Check if executable
                verbose_output.append(f'⚙️ Running executable script: {setup_script}')
                result = subprocess.run([str(script_path)],
                                      capture_output=True, text=True, cwd=str(extract_dir), timeout=300)
            else:
                flash(f'❌ Unsupported or non-executable script type: {setup_script}', 'error')
                return redirect(url_for('addons_modules'))

        # Process results for executable scripts
        if result.returncode == 0:
            flash(f'✅ Setup script executed successfully: {setup_script}', 'success')
            verbose_output.append('✅ Script completed with exit code 0')
            if result.stdout.strip():
                flash(f'📤 Output: {result.stdout.strip()[:500]}...', 'info')
                verbose_output.append(f'📤 stdout: {result.stdout.strip()[:100]}...')
        else:
            flash(f'❌ Setup script failed (exit code {result.returncode}): {setup_script}', 'error')
            verbose_output.append(f'❌ Script failed with exit code {result.returncode}')
            if result.stderr.strip():
                flash(f'📤 Error: {result.stderr.strip()[:500]}...', 'error')
                verbose_output.append(f'📤 stderr: {result.stderr.strip()[:100]}...')

        # Show verbose output
        for msg in verbose_output[:5]:
            flash(msg, 'info')

    except subprocess.TimeoutExpired:
        flash(f'⏰ Setup script timed out: {setup_script}', 'error')
    except Exception as e:
        flash(f'❌ Error running setup script: {str(e)}', 'error')

    return redirect(url_for('addons_modules'))

@app.route('/addons/modules/<module_name>/build', methods=['POST'])
def addons_module_build(module_name):
    """Build/compile a source code module"""
    try:
        # Load module info to get source directory
        modules_file = app.config['UPLOAD_FOLDER'] / 'modules.json'
        source_dir = None
        if modules_file.exists():
            try:
                with open(modules_file, 'r') as f:
                    modules = json.load(f)
                if module_name in modules:
                    source_dir = Path(modules[module_name].get('source_dir'))
            except Exception:
                pass
        
        # Find the actual module directory if source_dir not set
        if not source_dir or not source_dir.exists():
            extract_dirs = [
                app.config['UPLOAD_FOLDER'] / 'extracted',
                Path(app.root_path) / '.claude' / 'worktrees' / 'cool-elbakyan' / 'data' / 'uploads' / 'extracted'
            ]
            
            extract_dir = None
            for base_dir in extract_dirs:
                if base_dir.exists():
                    # First try exact match
                    candidate = base_dir / module_name
                    if candidate.exists() and candidate.is_dir():
                        extract_dir = candidate
                        break
                    
                    # Then try case-insensitive match
                    for item in base_dir.iterdir():
                        if item.is_dir() and item.name.lower() == module_name.lower():
                            extract_dir = item
                            break
                    
                    if extract_dir:
                        break
            
            if not extract_dir:
                flash(f'❌ Module not found: {module_name}', 'error')
                return redirect(url_for('addons_modules'))
            
            source_dir = extract_dir

        # Detect project type and build commands
        project_info = detect_project_type(source_dir)
        build_commands = detect_build_commands(source_dir, project_info)
        
        if not build_commands:
            flash(f'❌ No build commands detected for {module_name} ({project_info["type"]})', 'error')
            return redirect(url_for('addons_modules'))

        import subprocess
        verbose_output = []
        success_count = 0
        
        verbose_output.append(f'🔨 Building {module_name} ({project_info["type"]})')
        verbose_output.append(f'📁 Build directory: {source_dir}')
        
        # Execute build commands sequentially
        for i, build_cmd in enumerate(build_commands, 1):
            cmd_desc = build_cmd['description']
            cmd_args = build_cmd['command']
            
            verbose_output.append(f'⚙️ Step {i}/{len(build_commands)}: {cmd_desc}')
            verbose_output.append(f'💻 Command: {" ".join(cmd_args)}')
            
            try:
                # Set up environment for build
                env = os.environ.copy()
                env['PATH'] = os.environ.get('PATH', '')
                
                result = subprocess.run(
                    cmd_args,
                    cwd=str(source_dir),
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout for builds
                    env=env
                )
                
                if result.returncode == 0:
                    success_count += 1
                    verbose_output.append(f'✅ Step {i} completed successfully')
                    if result.stdout.strip():
                        # Show first few lines of output
                        stdout_lines = result.stdout.strip().split('\n')[:3]
                        for line in stdout_lines:
                            if line.strip():
                                verbose_output.append(f'📤 {line.strip()[:100]}')
                else:
                    verbose_output.append(f'❌ Step {i} failed with exit code {result.returncode}')
                    if result.stderr.strip():
                        # Show error output
                        stderr_lines = result.stderr.strip().split('\n')[:3]
                        for line in stderr_lines:
                            if line.strip():
                                verbose_output.append(f'📤 ERROR: {line.strip()[:100]}')
                    break  # Stop on first failure
                    
            except subprocess.TimeoutExpired:
                verbose_output.append(f'⏰ Step {i} timed out after 10 minutes')
                break
            except Exception as e:
                verbose_output.append(f'❌ Step {i} error: {str(e)}')
                break
        
        # Report results
        if success_count == len(build_commands):
            flash(f'✅ Build completed successfully: {module_name}', 'success')
            verbose_output.append(f'🎉 All {len(build_commands)} build steps completed')
        else:
            flash(f'❌ Build failed: {module_name} ({success_count}/{len(build_commands)} steps completed)', 'error')
            verbose_output.append(f'⚠️ Build incomplete: {success_count}/{len(build_commands)} steps completed')
        
        # Show verbose output (limit to prevent flash overflow)
        for msg in verbose_output[:8]:
            flash(msg, 'info')
            
    except Exception as e:
        flash(f'❌ Error during build: {str(e)}', 'error')

    return redirect(url_for('addons_modules'))

@app.route('/addons/modules/<module_name>/')
def addons_module_root(module_name):
    """Smart entry point for an addon module.
    
    Priority:
    1. If process already running → proxy to it via /app/
    2. If has a runnable entry point (py/js/php server / executable) → auto-launch + redirect to /app/
    3. If has a static HTML/HTM index → serve it inline
    4. If has index.php for CGI execution → run via php CLI inline
    5. Fallback → directory listing with start button
    """
    try:
        extract_dirs = [
            app.config['UPLOAD_FOLDER'] / 'extracted',
            Path(app.root_path) / '.claude' / 'worktrees' / 'cool-elbakyan' / 'data' / 'uploads' / 'extracted'
        ]
        extract_dir = None
        for base_dir in extract_dirs:
            if not base_dir.exists():
                continue
            candidate = base_dir / module_name
            if candidate.exists() and candidate.is_dir():
                extract_dir = candidate
                break
            for item in base_dir.iterdir():
                if item.is_dir() and item.name.lower() == module_name.lower():
                    extract_dir = item
                    break
            if extract_dir:
                break

        if not extract_dir:
            return f"Module not found: {module_name}", 404

        proxy_path = f'/addons/modules/{module_name}/app/'

        # ── 1. Already running? Proxy immediately. ────────────────────────────
        svc = app.config.get('running_services', {}).get(module_name)
        if svc:
            proc = svc.get('process')
            if proc and proc.poll() is None:
                from flask import redirect as _redirect
                return _redirect(proxy_path)

        # ── 2. Detect entry point ─────────────────────────────────────────────
        ep = detect_entry_point(extract_dir)

        if ep is None:
            # No recognised entry point at all → directory listing
            return _dir_listing(module_name, extract_dir)

        if ep['type'] == 'html':
            # Static HTML — serve inline, no subprocess needed
            with open(ep['file'], 'r', encoding='utf-8', errors='ignore') as fh:
                return fh.read(), 200, {'Content-Type': 'text/html'}

        if ep['type'] == 'php' and ep['cmd'] and ep['cmd'][0] == 'php':
            # Run PHP inline via CLI (CGI-style) for simple PHP apps
            try:
                php_bin = _find_php()
                result = subprocess.run(
                    [php_bin, str(ep['file'])],
                    cwd=str(ep['working_dir']),
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    return result.stdout, 200, {'Content-Type': 'text/html'}
                # PHP errored — fall through to launch as server instead
            except Exception:
                pass  # fall through to subprocess launch

        # ── 3. Launch subprocess and redirect to proxy ────────────────────────
        result = launch_addon(module_name, extract_dir)
        if result['status'] == 'started':
            # Redirect immediately; the proxy's auto-refresh page handles the
            # startup wait — no blocking sleep needed here.
            from flask import redirect as _redirect
            return _redirect(proxy_path)
        elif result['status'] == 'html':
            # launch_addon returned html (shouldn't happen here, but handle it)
            from flask import redirect as _redirect
            return _redirect(result['url'])
        else:
            # Launch failed — show error + directory listing
            return _dir_listing(module_name, extract_dir,
                                error=result.get('message', 'Could not start app'))

    except Exception as e:
        return f"Error serving module {module_name}: {str(e)}", 500


def _dir_listing(module_name, extract_dir, error=None):
    """Render a directory listing with a Start Service button."""
    project_info = detect_project_type(extract_dir)
    files = sorted(
        str(p.relative_to(extract_dir))
        for p in extract_dir.rglob('*') if p.is_file()
    )
    error_html = (f'<div style="background:#b71c1c;color:#fff;padding:10px;border-radius:5px;margin-bottom:16px">'
                  f'⚠️ {error}</div>') if error else ''
    file_links = ''.join(
        f'<div><a style="color:#4CAF50;text-decoration:none" '
        f'href="/addons/modules/{module_name}/web/{f}">{f}</a></div>'
        for f in files
    )
    return f"""<!DOCTYPE html>
<html><head><title>{module_name}</title>
<style>body{{font-family:Arial,sans-serif;background:#1a1a1a;color:#e0e0e0;padding:24px}}
.card{{background:#2a2a2a;padding:16px;border-radius:8px;margin-bottom:16px}}
.btn{{display:inline-block;padding:8px 18px;border-radius:5px;border:none;cursor:pointer;
      font-size:0.95em;text-decoration:none}}
.btn-green{{background:#4CAF50;color:#fff}}.btn-blue{{background:#2196F3;color:#fff}}
pre{{background:#111;padding:10px;border-radius:5px;overflow-x:auto;font-size:0.85em}}
</style></head><body>
<h2>📦 {module_name}</h2>
{error_html}
<div class="card">
  <strong>Type:</strong> {project_info.get('type','Unknown')} &nbsp;
  <strong>Frameworks:</strong> {', '.join(project_info.get('frameworks',[])) or 'None'}<br><br>
  <button class="btn btn-green" onclick="startAndOpen()">▶️ Start App</button>
  &nbsp;
  <a class="btn btn-blue" href="/addons/modules/{module_name}/manager">🗂️ Manage Files</a>
  <div id="msg" style="margin-top:12px"></div>
</div>
<div class="card">
  <strong>Files:</strong>
  <div style="margin-top:8px">{file_links}</div>
</div>
<script>
function startAndOpen(){{
  document.getElementById('msg').innerHTML='⏳ Starting…';
  fetch('/addons/modules/{module_name}/start',{{method:'POST'}})
    .then(r=>r.json()).then(d=>{{
      if(d.error){{ document.getElementById('msg').innerHTML='❌ '+d.error; return; }}
      document.getElementById('msg').innerHTML='✅ '+d.message+' — redirecting…';
      setTimeout(()=>{{ window.location='/addons/modules/{module_name}/app/'; }},1200);
    }}).catch(e=>{{ document.getElementById('msg').innerHTML='❌ '+e; }});
}}
</script>
</body></html>""", 200, {{'Content-Type': 'text/html'}}


@app.route('/addons/modules/<module_name>/web/<path:filepath>')
def addons_module_web(module_name, filepath):
    """Serve web-accessible files from a module (for PHP setup scripts, etc.)"""
    try:
        # Find the actual module directory by searching both locations
        extract_dirs = [
            app.config['UPLOAD_FOLDER'] / 'extracted',
            Path(app.root_path) / '.claude' / 'worktrees' / 'cool-elbakyan' / 'data' / 'uploads' / 'extracted'
        ]
        
        extract_dir = None
        for base_dir in extract_dirs:
            if base_dir.exists():
                # First try exact match
                candidate = base_dir / module_name
                if candidate.exists() and candidate.is_dir():
                    extract_dir = candidate
                    break
                
                # Then try case-insensitive match
                for item in base_dir.iterdir():
                    if item.is_dir() and item.name.lower() == module_name.lower():
                        extract_dir = item
                        break
                
                if extract_dir:
                    break
        
        if not extract_dir:
            return f"Module not found: {module_name}", 404
            
        file_path = extract_dir / filepath

        if not file_path.is_file():
            return f"Path is not a file: {filepath}", 400

        # Security check - only allow certain file types
        allowed_extensions = {'.php', '.html', '.htm', '.css', '.js', '.json', '.txt', '.md'}
        if file_path.suffix.lower() not in allowed_extensions:
            return f"File type not allowed for web access: {file_path.suffix}", 403

        # For PHP files, execute them using local PHP
        if file_path.suffix.lower() == '.php':
            import subprocess
            try:
                # Use the local PHP installation
                php_path = Path(app.root_path) / 'php' / 'php.exe'
                if not php_path.exists():
                    # Fallback to system PHP if local not found
                    php_path = 'php'
                
                # Execute PHP with the file
                result = subprocess.run(
                    [str(php_path), str(file_path)],
                    cwd=str(extract_dir),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    return result.stdout, 200, {'Content-Type': 'text/html'}
                else:
                    # PHP execution failed, show error
                    error_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>{module_name} - PHP Error</title>
                        <style>
                            body {{ font-family: monospace; background: #1a1a1a; color: #e0e0e0; padding: 20px; }}
                            .error {{ background: #f44336; color: white; padding: 15px; border-radius: 5px; }}
                        </style>
                    </head>
                    <body>
                        <div class="error">
                            <strong>PHP Execution Error:</strong><br>
                            {result.stderr}
                        </div>
                        <h2>PHP Source Code:</h2>
                        <pre>{open(file_path, 'r', encoding='utf-8', errors='ignore').read()}</pre>
                    </body>
                    </html>
                    """
                    return error_content, 500
                    
            except subprocess.TimeoutExpired:
                return "PHP execution timed out", 504
            except Exception as e:
                return f"PHP execution failed: {str(e)}", 500

        # For other allowed file types, serve them directly
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Basic content type detection
        content_type = 'text/plain'
        if file_path.suffix.lower() in ['.html', '.htm']:
            content_type = 'text/html'
        elif file_path.suffix.lower() == '.css':
            content_type = 'text/css'
        elif file_path.suffix.lower() == '.js':
            content_type = 'application/javascript'
        elif file_path.suffix.lower() == '.json':
            content_type = 'application/json'

        return content, 200, {'Content-Type': content_type}

    except Exception as e:
        return f"Error serving file: {str(e)}", 500


# ---------------------------------------------------------------------------
# Addon entry-point detection and auto-launch helpers
# ---------------------------------------------------------------------------

ENTRY_POINT_PRIORITY = [
    # (filename, handler_type)
    ('main.py',       'python'),
    ('index.py',      'python'),
    ('app.py',        'python'),
    ('run.py',        'python'),
    ('__main__.py',   'python_module'),
    # PHP installers — run these before app entry points if present
    ('install.php',   'php'),
    ('setup.php',     'php'),
    ('installer.php', 'php'),
    ('wizard.php',    'php'),
    ('index.php',     'php'),
    ('main.php',      'php'),
    ('index.html',    'html'),
    ('index.htm',     'html'),
    ('server.js',     'node'),
    ('app.js',        'node'),
    ('index.js',      'node'),
    ('main',          'executable'),
]


def detect_entry_point(extract_dir: Path):
    """
    Walk extract_dir looking for a known entry-point file.
    Returns a dict:
        { 'file': Path, 'working_dir': Path, 'type': str,
          'cmd': list|None, 'html_url': str|None }
    or None if nothing is found.

    Search strategy (most-to-least specific):
      1. Exact priority filenames at root, then 1-level subdirs, then full recursion.
      2. Any .py/.php/.js file whose name looks like an entry point (excluding libs).
      3. Any .html/.htm file.
    """
    def _build_result(candidate: Path, search_dir: Path, handler: str):
        cmd = None
        html_url = None
        fname = candidate.name
        if handler == 'python':
            cmd = [sys.executable, fname]
        elif handler == 'python_module':
            cmd = [sys.executable, '-m', search_dir.name]
        elif handler == 'php':
            cmd = ['php', '-S', f'localhost:0', fname]
        elif handler == 'node':
            cmd = ['node', fname]
        elif handler == 'executable':
            cmd = [f'./{fname}']
        elif handler == 'html':
            rel = candidate.relative_to(extract_dir)
            html_url = f'/addons/modules/{extract_dir.name}/files/{rel.as_posix()}'
            cmd = None
        return {
            'file': candidate,
            'working_dir': search_dir,
            'type': handler,
            'cmd': cmd,
            'html_url': html_url,
        }

    # --- Pass 1: exact-name priority list, shallow then recursive ---
    # Build search order: root first, then immediate subdirs, then all deeper dirs
    search_dirs = [extract_dir]
    try:
        for d in extract_dir.iterdir():
            if d.is_dir() and not d.name.startswith('.') and d.name not in ('node_modules', 'vendor', '__pycache__', '.git', 'venv', 'env'):
                search_dirs.append(d)
    except Exception:
        pass
    # Also collect deeper dirs for a recursive pass
    deep_dirs = []
    try:
        for d in extract_dir.rglob('*'):
            if d.is_dir() and not any(part.startswith('.') or part in ('node_modules', 'vendor', '__pycache__', 'venv', 'env') for part in d.parts):
                if d not in search_dirs:
                    deep_dirs.append(d)
    except Exception:
        pass

    for search_dir in search_dirs + deep_dirs:
        for fname, handler in ENTRY_POINT_PRIORITY:
            candidate = search_dir / fname
            if candidate.exists():
                return _build_result(candidate, search_dir, handler)

    # --- Pass 2: fuzzy fallback — any .py/.php/.js/.html file ---
    # Score candidates: prefer shallower paths and entry-point-sounding names
    _SKIP_DIRS = {'node_modules', 'vendor', '__pycache__', 'venv', 'env', '.git', 'dist', 'build', 'migrations'}
    _PY_ENTRY_HINTS  = {'start', 'run', 'server', 'api', 'application', 'bootstrap', 'launch', 'web', 'http', 'serve', 'bot', 'app', 'main'}
    _PHP_ENTRY_HINTS = {'start', 'run', 'server', 'api', 'bootstrap', 'launch', 'app', 'web', 'portal', 'admin', 'home'}
    _JS_ENTRY_HINTS  = {'start', 'run', 'server', 'api', 'index', 'app', 'main', 'http', 'bot', 'web'}

    best_py = best_php = best_js = best_html = None
    best_py_score = best_php_score = best_js_score = best_html_score = 999

    try:
        for f in extract_dir.rglob('*'):
            if not f.is_file():
                continue
            # Skip files inside blacklisted dirs
            if any(part in _SKIP_DIRS for part in f.parts):
                continue
            depth = len(f.relative_to(extract_dir).parts)
            stem = f.stem.lower()
            ext  = f.suffix.lower()

            if ext == '.py':
                hint_bonus = 0 if stem in _PY_ENTRY_HINTS else 5
                score = depth + hint_bonus
                if score < best_py_score:
                    best_py_score = score
                    best_py = f
            elif ext == '.php':
                hint_bonus = 0 if stem in _PHP_ENTRY_HINTS else 5
                score = depth + hint_bonus
                if score < best_php_score:
                    best_php_score = score
                    best_php = f
            elif ext == '.js' and not f.name.endswith('.min.js'):
                hint_bonus = 0 if stem in _JS_ENTRY_HINTS else 5
                score = depth + hint_bonus
                if score < best_js_score:
                    best_js_score = score
                    best_js = f
            elif ext in ('.html', '.htm'):
                score = depth
                if score < best_html_score:
                    best_html_score = score
                    best_html = f
    except Exception:
        pass

    # Prefer py → php → js → html
    for candidate, handler in [(best_py, 'python'), (best_php, 'php'), (best_js, 'node'), (best_html, 'html')]:
        if candidate is not None:
            return _build_result(candidate, candidate.parent, handler)

    return None


def _find_php() -> str:
    """
    Return a path to a working php executable.
    Search order:
      1. <app_root>/php/php.exe  (bundled / previously downloaded)
      2. Common XAMPP / Laragon / system PATH locations
      3. Auto-download PHP 8.3 NTS for Windows into <app_root>/php/
    Returns the path string, or raises RuntimeError if unavailable.
    """
    import shutil, urllib.request, zipfile, tempfile

    bundled = Path(app.root_path) / 'php' / 'php.exe'
    if bundled.exists():
        return str(bundled)

    # Common install locations on Windows
    candidates = [
        r'C:\php\php.exe',
        r'C:\php8\php.exe',
        r'C:\xampp\php\php.exe',
        r'C:\laragon\bin\php\php8.2.0\php.exe',
    ]
    # Also check any versioned folders under C:\laragon\bin\php\
    for d in (Path(r'C:\laragon\bin\php'), Path(r'C:\wamp64\bin\php'), Path(r'C:\wamp\bin\php')):
        try:
            for sub in sorted(d.iterdir(), reverse=True):
                p = sub / 'php.exe'
                if p.exists():
                    candidates.insert(0, str(p))
        except Exception:
            pass

    for c in candidates:
        if Path(c).exists():
            return c

    on_path = shutil.which('php')
    if on_path:
        return on_path

    # ── Auto-download PHP for Windows ───────────────────────────────────────
    php_dir = Path(app.root_path) / 'php'
    php_dir.mkdir(exist_ok=True)

    # Try winget first (silent, most reliable on modern Windows)
    try:
        wg = subprocess.run(
            ['winget', 'install', '--id', 'PHP.PHP', '--silent', '--accept-package-agreements', '--accept-source-agreements'],
            capture_output=True, text=True, timeout=120
        )
        found = shutil.which('php')
        if found:
            return found
    except Exception:
        pass

    # Try chocolatey
    try:
        choco = shutil.which('choco')
        if choco:
            subprocess.run([choco, 'install', 'php', '-y'], capture_output=True, text=True, timeout=120)
            found = shutil.which('php')
            if found:
                return found
    except Exception:
        pass

    # Manual ZIP download — try multiple version URLs
    # PowerShell Invoke-WebRequest handles Windows HTTPS/redirects better than urllib
    zip_candidates = [
        'https://windows.php.net/downloads/releases/php-8.3.17-nts-Win32-vs16-x64.zip',
        'https://windows.php.net/downloads/releases/php-8.3.16-nts-Win32-vs16-x64.zip',
        'https://windows.php.net/downloads/releases/php-8.2.27-nts-Win32-vs16-x64.zip',
        'https://windows.php.net/downloads/releases/php-8.1.31-nts-Win32-vs16-x64.zip',
    ]

    tmp_zip = None
    last_err = ''

    for url in zip_candidates:
        zip_dest = str(php_dir / 'php_download.zip')
        # Try PowerShell first (handles TLS/redirects better on Windows)
        try:
            ps_result = subprocess.run(
                ['powershell', '-NoProfile', '-NonInteractive', '-Command',
                 f'[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; '
                 f'Invoke-WebRequest -Uri "{url}" -OutFile "{zip_dest}" -UseBasicParsing'],
                capture_output=True, text=True, timeout=120
            )
            if ps_result.returncode == 0 and Path(zip_dest).exists() and Path(zip_dest).stat().st_size > 100000:
                tmp_zip = zip_dest
                break
            last_err = ps_result.stderr.strip() or ps_result.stdout.strip()
        except Exception as _e:
            last_err = str(_e)
        # urllib fallback
        try:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            with urllib.request.urlopen(url, timeout=90, context=ctx) as resp:
                data = resp.read()
            if len(data) > 100000:
                Path(zip_dest).write_bytes(data)
                tmp_zip = zip_dest
                break
        except Exception as _e:
            last_err = str(_e)

    if not tmp_zip:
        raise RuntimeError(
            f'PHP is not installed and auto-download failed ({last_err}). '
            'Install PHP manually: winget install PHP.PHP  '
            'or download from https://windows.php.net/download/ and add to PATH.'
        )

    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            zf.extractall(php_dir)
        try:
            Path(tmp_zip).unlink(missing_ok=True)
        except Exception:
            pass
    except Exception as e:
        raise RuntimeError(f'Failed to extract PHP zip: {e}')

    # Copy php.ini-development → php.ini so extensions load correctly
    ini_dev = php_dir / 'php.ini-development'
    ini     = php_dir / 'php.ini'
    if ini_dev.exists() and not ini.exists():
        import shutil as _sh
        _sh.copy2(ini_dev, ini)

    if bundled.exists():
        return str(bundled)
    raise RuntimeError('PHP download succeeded but php.exe not found in extracted archive.')


def _find_free_port(start: int = 9100, end: int = 9300) -> int:
    """
    Return a free TCP port in [start, end) and immediately reserve it so
    concurrent calls never hand out the same number.
    """
    import socket as _socket
    # Ports already committed to running services OR reserved-but-not-yet-started
    used = {v.get('port') for v in app.config.get('running_services', {}).values() if v.get('port')}
    used |= app.config.setdefault('_reserved_ports', set())
    for port in range(start, end):
        if port in used:
            continue
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                # Claim it immediately — before the subprocess even starts
                app.config['_reserved_ports'].add(port)
                return port
            except OSError:
                continue
    raise RuntimeError(f'No free port found in range {start}-{end}')


def _sniff_port(module_name: str, proc: subprocess.Popen, fallback_port: int):
    """
    Read the subprocess stdout+stderr in a background thread looking for the
    port it actually bound to.  Updates running_services[module_name]['port']
    in-place so the proxy always forwards to the right place.

    Patterns recognised:
      * Running on http://127.0.0.1:PORT
      * Listening on port PORT
      * Server started on PORT
      * localhost:PORT  (PHP built-in)
      * ":PORT"  (Node / generic)
    """
    import re, threading

    _port_re = re.compile(
        r'(?:\[MC\] Running on https?://[^:]+:|Running on https?://[^:]+:|[Ll]istening on (?:port |localhost:)|'
        r'[Ss]erver (?:started|running) on (?:port )?|:)(\d{2,5})'
    )

    def _read(stream):
        try:
            for raw in stream:
                try:
                    line = raw.decode('utf-8', errors='replace').strip()
                except Exception:
                    continue
                m = _port_re.search(line)
                if m:
                    detected = int(m.group(1))
                    # sanity check — ignore well-known non-app ports
                    if 1024 <= detected <= 65535 and detected != 8080:
                        svc = app.config.get('running_services', {}).get(module_name)
                        if svc and svc.get('port') != detected:
                            svc['port'] = detected
                        return  # found it, stop reading
        except Exception:
            pass

    for stream in (proc.stdout, proc.stderr):
        if stream:
            t = threading.Thread(target=_read, args=(stream,), daemon=True)
            t.start()


def launch_addon(module_name: str, extract_dir: Path):
    """
    Detect and launch the addon entry point.
    Returns a dict describing the result including a proxy_url.
    """
    ep = detect_entry_point(extract_dir)
    if ep is None:
        return {'status': 'no_entry_point', 'message': 'No recognised entry-point file found'}

    if ep['type'] == 'html':
        # Static HTML — served directly by Flask, no subprocess
        return {
            'status': 'html',
            'entry_point': ep['file'].name,
            'url': ep['html_url'],
            'proxy_url': ep['html_url'],
            'message': f"Static app — open {ep['file'].name} in the browser",
        }

    # Assign a free port — we pass it to the subprocess but also sniff its
    # actual output in case the app ignores the env var.
    try:
        port = _find_free_port()
    except RuntimeError as e:
        return {'status': 'error', 'message': str(e)}

    cmd = list(ep['cmd'])
    env = os.environ.copy()
    env['PORT'] = str(port)          # honoured by many frameworks
    # Let addons call back to MasterChief
    env['MC_BASE_URL'] = app.config.get('MC_BASE_URL', 'http://127.0.0.1:8080')
    env['MC_PORT']     = str(app.config.get('MC_PORT', 8080))

    if ep['type'] == 'php':
        try:
            php_bin = _find_php()
        except RuntimeError as e:
            app.config.get('_reserved_ports', set()).discard(port)
            return {'status': 'error', 'message': str(e)}
        cmd = [php_bin, '-S', f'localhost:{port}', ep['file'].name]
    elif ep['type'] in ('python', 'python_module'):
        env['FLASK_RUN_PORT'] = str(port)
        env['FLASK_RUN_HOST'] = '0.0.0.0'

        # ── Port-injection wrapper ────────────────────────────────────────────
        # Many Flask apps call app.run() with no arguments (defaulting to 5000).
        # We write a tiny launcher that monkeypatches flask.Flask.run so the
        # assigned port is always used, regardless of what the module does.
        entry_file = str(ep['file']).replace('\\', '\\\\')
        wrapper_src = f'''import os, sys
_PORT = int(os.environ.get('PORT', {port}))
# Force Flask to bind to our assigned port
try:
    import flask as _flask
    _orig_run = _flask.Flask.run
    def _patched_run(self, host=None, port=None, debug=None, **kw):
        print(f"[MC] Running on http://localhost:{{_PORT}}", flush=True)
        _orig_run(self, host=host or '0.0.0.0', port=_PORT, debug=False, **kw)
    _flask.Flask.run = _patched_run
except ImportError:
    pass
# Run the actual entry point
import runpy
sys.argv[0] = r'{entry_file}'
runpy.run_path(r'{entry_file}', run_name='__main__')
'''
        wrapper_path = ep['working_dir'] / '_mc_launcher.py'
        try:
            wrapper_path.write_text(wrapper_src, encoding='utf-8')
            cmd = [sys.executable, '_mc_launcher.py']
        except Exception:
            pass  # fall back to running entry directly

    proxy_url = f'/addons/modules/{module_name}/app/'

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ep['working_dir']),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        app.config.setdefault('running_services', {})[module_name] = {
            'process': proc,
            'pid': proc.pid,
            'port': port,            # may be updated by _sniff_port
            'start_time': datetime.now().isoformat(),
            'command': cmd,
            'entry_point': ep['file'].name,
            'type': ep['type'],
            'proxy_url': proxy_url,
        }
        # Start background reader so we detect the real bound port
        _sniff_port(module_name, proc, port)
        return {
            'status': 'started',
            'pid': proc.pid,
            'port': port,
            'entry_point': ep['file'].name,
            'type': ep['type'],
            'proxy_url': proxy_url,
            'message': f"Started {ep['file'].name} (PID {proc.pid})",
        }
    except FileNotFoundError:
        runtime = {'python': 'Python', 'php': 'PHP', 'node': 'Node.js', 'executable': ''}.get(ep['type'], ep['type'])
        return {
            'status': 'error',
            'message': f'{runtime} runtime not found — cannot execute {ep["file"].name}',
        }
    except Exception as exc:
        return {'status': 'error', 'message': str(exc)}


def _register_runtime_blueprint_routes(app_obj, module_name: str, module_file: Path):
    """Register blueprint routes directly on the live app when startup is already finished."""
    try:
        import importlib.util as _ilu
        from werkzeug.routing import Rule

        spec = _ilu.spec_from_file_location(f'addon_{module_name}_runtime', str(module_file))
        if not spec or not spec.loader:
            return False

        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)

        candidates = []
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if hasattr(obj, 'deferred_functions') and getattr(obj, 'name', ''):
                candidates.append(obj)

        if not candidates:
            return False

        registered = 0
        for bp in candidates:
            prefix = getattr(bp, 'url_prefix', None) or f'/{module_name}'
            if not prefix.startswith('/'):
                prefix = '/' + prefix
            for deferred in getattr(bp, 'deferred_functions', []):
                rule = getattr(deferred, 'rule', None)
                endpoint = getattr(deferred, 'endpoint', None)
                view_func = getattr(deferred, 'func', None)
                methods = list(getattr(deferred, 'methods', None) or ['GET'])
                if not rule or not endpoint or not view_func:
                    continue
                endpoint_name = endpoint
                if endpoint_name in app_obj.view_functions:
                    endpoint_name = f'{bp.name}_{endpoint}'
                if endpoint_name in app_obj.view_functions:
                    continue
                full_rule = f'{prefix.rstrip("/")}{rule}'
                app_obj.url_map.add(Rule(full_rule, endpoint=endpoint_name, methods=methods, provide_automatic_options=False))
                app_obj.view_functions[endpoint_name] = view_func
                registered += 1

        return registered > 0
    except Exception:
        return False


@app.route('/addons/modules/<module_name>/start', methods=['POST'])
def addons_module_start(module_name):
    """Start a module service.
    
    Strategy:
    - If the module has addon.py with an init() function → load it as a Flask
      Blueprint (no subprocess needed, routes are injected into this process).
    - Otherwise → launch a subprocess and proxy to it.
    """
    extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
    if not extract_dir.exists():
        return jsonify({'error': f'Module not found: {module_name}'}), 404

    # ── Blueprint / addon.py path ─────────────────────────────────────────────
    addon_py = extract_dir / 'addon.py'
    if addon_py.exists():
        try:
            import importlib.util as _ilu
            spec = _ilu.spec_from_file_location(f'addon_{module_name}', str(addon_py))
            if spec and spec.loader:
                mod = _ilu.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, 'init'):
                    # Flask rejects blueprint registration after the first request,
                    # so we need the runtime-compatible path once the app is live.
                    if getattr(app, '_got_first_request', False):
                        registered = _register_runtime_blueprint_routes(app, module_name, addon_py)
                        if not registered:
                            return jsonify({'error': 'Failed to register addon routes after startup'}), 500
                        bp_url = f'/modules/{module_name}/'
                        for bp_name, bp in app.blueprints.items():
                            if bp_name == module_name or bp_name == f'addon_{module_name}':
                                prefix = getattr(bp, 'url_prefix', None) or f'/{bp_name}'
                                bp_url = prefix.rstrip('/') + '/'
                                break
                        app.config.setdefault('running_services', {})[module_name] = {
                            'type': 'blueprint',
                            'entry_point': 'addon.py',
                            'proxy_url': bp_url,
                        }
                        return jsonify({
                            'status': 'blueprint',
                            'message': f'{module_name} loaded as Blueprint',
                            'entry_point': 'addon.py',
                            'proxy_url': bp_url,
                        }), 200
                    mod.init(app)
                    # Record as a "blueprint" service so status checks work
                    app.config.setdefault('running_services', {})[module_name] = {
                        'type': 'blueprint',
                        'entry_point': 'addon.py',
                        'proxy_url': f'/modules/{module_name}/',
                    }
                    # Try to find what URL prefix the blueprint registered
                    bp_url = f'/modules/{module_name}/'
                    for bp_name, bp in app.blueprints.items():
                        if bp_name == module_name or bp_name == f'addon_{module_name}':
                            prefix = getattr(bp, 'url_prefix', None) or f'/{bp_name}'
                            bp_url = prefix.rstrip('/') + '/'
                            break
                    app.config['running_services'][module_name]['proxy_url'] = bp_url
                    return jsonify({
                        'status': 'blueprint',
                        'message': f'{module_name} loaded as Blueprint',
                        'entry_point': 'addon.py',
                        'proxy_url': bp_url,
                    }), 200
                else:
                    return jsonify({'error': 'addon.py has no init() function'}), 400
        except Exception as _e:
            return jsonify({'error': f'Failed to load addon.py: {_e}'}), 500

    # ── Subprocess path ───────────────────────────────────────────────────────
    # Check if already running
    running_services = app.config.get('running_services', {})
    svc = running_services.get(module_name)
    if svc:
        proc = svc.get('process')
        if proc and proc.poll() is None:  # still alive
            return jsonify({'message': f'Service already running (PID: {svc["pid"]})',
                            'status': 'running', 'pid': svc['pid'],
                            'proxy_url': svc.get('proxy_url', f'/addons/modules/{module_name}/app/')}), 200

    result = launch_addon(module_name, extract_dir)

    if result['status'] == 'started':
        return jsonify({'message': result['message'], 'status': 'starting',
                        'pid': result['pid'], 'port': result.get('port'),
                        'entry_point': result['entry_point'],
                        'proxy_url': result['proxy_url']}), 200
    elif result['status'] == 'html':
        return jsonify({'message': result['message'], 'status': 'html',
                        'url': result['url'], 'proxy_url': result['proxy_url'],
                        'entry_point': result['entry_point']}), 200
    elif result['status'] == 'no_entry_point':
        return jsonify({'error': 'No runnable entry point found (no addon.py, main.py, index.js, index.php, or index.html)'}), 400
    else:
        return jsonify({'error': result['message']}), 500


@app.route('/addons/modules/<module_name>/app/', defaults={'subpath': ''})
@app.route('/addons/modules/<module_name>/app/<path:subpath>')
def addons_module_proxy(module_name, subpath):
    """Transparent reverse-proxy to a running addon subprocess."""
    import requests as _requests
    import socket as _socket

    svc = app.config.get('running_services', {}).get(module_name)
    if not svc:
        return _proxy_not_running(module_name), 503

    proc = svc.get('process')
    if proc and proc.poll() is not None:
        # Capture stderr for diagnosis
        try:
            err_out = proc.stderr.read().decode('utf-8', errors='replace')[-800:] if proc.stderr else ''
        except Exception:
            err_out = ''
        return (f'<h2 style="font-family:Arial;color:#f44336">Module <b>{module_name}</b> crashed '
                f'(exit {proc.returncode})</h2>'
                f'<pre style="background:#111;color:#eee;padding:12px;border-radius:6px;'
                f'white-space:pre-wrap">{err_out or "(no output)"}</pre>'
                f'<p><a href="/addons/modules">⬅ Back</a></p>'), 503

    stored_port = svc.get('port')
    svc_type    = svc.get('type', 'python')

    # ── Port discovery ────────────────────────────────────────────────────────
    # Priority: (1) stored/sniffed port, (2) type-default ports that are NOT
    # already owned by another running module.  We never fall back to a port
    # that belongs to a different module (fixes cross-module bleed-over).
    def _port_open(p):
        try:
            with _socket.create_connection(('localhost', p), timeout=0.4):
                return True
        except Exception:
            return False

    # Ports owned by OTHER running modules — never touch these
    other_ports = {
        v.get('port')
        for k, v in app.config.get('running_services', {}).items()
        if k != module_name and v.get('port')
    }

    # Type-appropriate defaults for apps that ignore the PORT env var
    _TYPE_DEFAULTS = {
        'python':        [5000, 8000, 5001],
        'python_module': [5000, 8000, 5001],
        'node':          [3000, 8000, 4000],
        'php':           [],        # PHP built-in server always uses assigned port
    }
    type_defaults = [p for p in _TYPE_DEFAULTS.get(svc_type, []) if p not in other_ports]

    candidate_ports = []
    if stored_port:
        candidate_ports.append(stored_port)
    for p in type_defaults:
        if p not in candidate_ports:
            candidate_ports.append(p)

    live_port = None
    for p in candidate_ports:
        if _port_open(p):
            live_port = p
            break

    if live_port is None:
        return _proxy_starting(module_name, stored_port, subpath), 202

    # Update stored port when we discovered a different real port
    if live_port != stored_port:
        svc['port'] = live_port

    qs = ('?' + request.query_string.decode('utf-8')) if request.query_string else ''
    target = f'http://localhost:{live_port}/{subpath}{qs}'

    try:
        resp = _requests.request(
            method=request.method,
            url=target,
            headers={k: v for k, v in request.headers
                     if k.lower() not in ('host', 'content-length')},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=15,
        )
        excluded = {'content-encoding', 'transfer-encoding', 'connection', 'keep-alive'}
        headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
        return resp.content, resp.status_code, headers

    except _requests.exceptions.ConnectionError:
        return _proxy_starting(module_name, live_port, subpath), 202
    except Exception as exc:
        return f'<h2>Proxy error</h2><p>{exc}</p>', 500


def _proxy_not_running(module_name):
    return (f'<!DOCTYPE html><html><head>'
            f'<meta http-equiv="refresh" content="3;url=/addons/modules/{module_name}/app/">'
            f'<style>body{{font-family:Arial;background:#1a1a1a;color:#e0e0e0;padding:30px}}'
            f'.btn{{display:inline-block;padding:8px 18px;border-radius:5px;background:#4CAF50;'
            f'color:#fff;text-decoration:none;border:none;cursor:pointer;font-size:1em}}</style>'
            f'</head><body>'
            f'<h2>📦 Module <b>{module_name}</b> is not running</h2>'
            f'<p>Starting it now…</p>'
            f'<script>'
            f'fetch("/addons/modules/{module_name}/start",{{method:"POST"}})'
            f'.then(r=>r.json()).then(d=>{{ setTimeout(()=>location.reload(),2000); }});'
            f'</script>'
            f'<a href="/addons/modules" class="btn">⬅ Back to Modules</a>'
            f'</body></html>')


def _proxy_starting(module_name, port, subpath):
    dest = f'/addons/modules/{module_name}/app/{subpath}'
    return (f'<!DOCTYPE html><html><head>'
            f'<meta http-equiv="refresh" content="2;url={dest}">'
            f'<style>body{{font-family:Arial;background:#1a1a1a;color:#e0e0e0;padding:30px;text-align:center}}'
            f'.spinner{{display:inline-block;width:40px;height:40px;border:4px solid #333;'
            f'border-top-color:#4CAF50;border-radius:50%;animation:spin 0.8s linear infinite}}'
            f'@keyframes spin{{to{{transform:rotate(360deg)}}}}</style></head><body>'
            f'<div class="spinner"></div>'
            f'<h2 style="margin-top:20px">⏳ Starting <b>{module_name}</b>…</h2>'
            f'<p style="color:#888">Port {port} — auto-refreshing in 2 s</p>'
            f'<p><a href="{dest}" style="color:#4CAF50">Refresh now</a> &nbsp;|&nbsp; '
            f'<a href="/addons/modules" style="color:#888">⬅ Back</a></p>'
            f'</body></html>')


@app.route('/addons/modules/<module_name>/status')
def addons_module_status(module_name):
    """Return running status of an addon subprocess or blueprint."""
    svc = app.config.get('running_services', {}).get(module_name)
    if not svc:
        return jsonify({'status': 'stopped', 'pid': None, 'port': None})

    # Blueprint modules have no subprocess — they're always "alive" if registered
    if svc.get('type') == 'blueprint':
        return jsonify({
            'status': 'blueprint',
            'entry_point': svc.get('entry_point'),
            'proxy_url': svc.get('proxy_url'),
        })

    proc = svc.get('process')
    alive = proc and proc.poll() is None
    return jsonify({
        'status': 'running' if alive else 'stopped',
        'pid': svc.get('pid') if alive else None,
        'port': svc.get('port') if alive else None,
        'entry_point': svc.get('entry_point'),
        'proxy_url': svc.get('proxy_url') if alive else None,
        'start_time': svc.get('start_time'),
    })


@app.route('/addons/modules/<module_name>/stop', methods=['POST'])
def addons_module_stop(module_name):
    """Stop a module service"""
    try:
        running_services = app.config.get('running_services', {})
        service_info = running_services.get(module_name)
        
        if not service_info:
            # Check if process is still running
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['cmdline'] and any(module_name in str(cmd) for cmd in proc.info['cmdline']):
                        proc.kill()
                        return {'message': f'Service stopped (PID: {proc.info["pid"]})', 'status': 'stopped'}
                except:
                    pass
            return {'message': 'Service not running', 'status': 'stopped'}
        
        # Stop the process
        process = service_info['process']
        try:
            process.terminate()
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        
        # Remove from running services and release reserved port
        port = service_info.get('port')
        del running_services[module_name]
        if port:
            app.config.get('_reserved_ports', set()).discard(port)
        
        return {'message': 'Service stopped successfully', 'status': 'stopped'}
        
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/addons/modules/<module_name>/delete', methods=['POST'])
def addons_module_delete(module_name):
    """Stop and permanently delete a single installed addon module."""
    import shutil

    try:
        # Stop running service first
        running_services = app.config.get('running_services', {})
        svc = running_services.get(module_name)
        if svc:
            proc = svc.get('process')
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            if svc:
                app.config.get('_reserved_ports', set()).discard(svc.get('port'))
            running_services.pop(module_name, None)

        # Locate and remove the extracted directory
        extract_dirs = [
            app.config['UPLOAD_FOLDER'] / 'extracted',
            Path(app.root_path) / '.claude' / 'worktrees' / 'cool-elbakyan' / 'data' / 'uploads' / 'extracted',
        ]
        deleted = False
        for base in extract_dirs:
            candidate = base / module_name
            if candidate.exists() and candidate.is_dir():
                shutil.rmtree(candidate)
                deleted = True
                break
            # case-insensitive match
            if base.exists():
                for d in base.iterdir():
                    if d.is_dir() and d.name.lower() == module_name.lower():
                        shutil.rmtree(d)
                        deleted = True
                        break
            if deleted:
                break

        # Also remove the launcher wrapper if present
        for base in extract_dirs:
            for launcher in (base / module_name / '_mc_launcher.py',):
                try:
                    if launcher.exists():
                        launcher.unlink()
                except Exception:
                    pass

        if deleted:
            return {'success': True, 'message': f'{module_name} deleted successfully'}
        return {'success': False, 'error': 'Module directory not found'}, 404

    except Exception as e:
        return {'success': False, 'error': str(e)}, 500

@app.route('/addons/modules/delete_all', methods=['POST'])
def delete_all_modules():
    """Delete all installed addon modules"""
    try:
        import shutil
        
        deleted_modules = []
        errors = []
        
        # Check both current workspace and the cool-elbakyan workspace
        extract_dirs = [
            app.config['UPLOAD_FOLDER'] / 'extracted',
            Path(__file__).parent / '.claude' / 'worktrees' / 'cool-elbakyan' / 'data' / 'uploads' / 'extracted'
        ]
        
        for extract_dir in extract_dirs:
            if extract_dir.exists():
                for module_dir in extract_dir.iterdir():
                    if module_dir.is_dir():
                        try:
                            # Stop any running services for this module first
                            running_services = app.config.get('running_services', {})
                            if module_dir.name in running_services:
                                service_info = running_services[module_dir.name]
                                process = service_info['process']
                                try:
                                    process.terminate()
                                    process.wait(timeout=5)
                                except:
                                    try:
                                        process.kill()
                                    except:
                                        pass
                                del running_services[module_dir.name]
                            
                            # Delete the module directory
                            shutil.rmtree(module_dir)
                            deleted_modules.append(module_dir.name)
                            
                        except Exception as e:
                            errors.append(f"Failed to delete {module_dir.name}: {str(e)}")
        
        # Also clean up any empty parent directories
        for extract_dir in extract_dirs:
            if extract_dir.exists() and not any(extract_dir.iterdir()):
                try:
                    extract_dir.rmdir()
                except:
                    pass
        
        if errors:
            return jsonify({'success': False, 'error': '; '.join(errors), 'deleted_count': len(deleted_modules)}), 500
        else:
            return jsonify({'success': True, 'message': f'Successfully deleted {len(deleted_modules)} modules', 'deleted_count': len(deleted_modules)})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== MODULE MANAGER API =====

@app.route('/addons/modules/<module_name>/api/files')
def module_files_api(module_name):
    """API endpoint to get module files as JSON"""
    try:
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
        if not extract_dir.exists():
            return jsonify({'error': 'Module not found'}), 404
        
        files = []
        def scan_directory(path, relative_path=''):
            try:
                for item in sorted(path.iterdir()):
                    if item.is_file():
                        try:
                            size = item.stat().st_size
                            modified = datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                            files.append({
                                'name': item.name,
                                'path': item.relative_to(extract_dir).as_posix(),
                                'size': size,
                                'modified': modified,
                                'type': 'file',
                                'extension': item.suffix.lower()
                            })
                        except:
                            pass
                    elif item.is_dir():
                        try:
                            files.append({
                                'name': item.name,
                                'path': item.relative_to(extract_dir).as_posix(),
                                'size': 0,
                                'modified': datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                'type': 'directory',
                                'extension': ''
                            })
                            scan_directory(item)
                        except:
                            pass
            except:
                pass
        
        scan_directory(extract_dir)
        return jsonify({'files': files})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/addons/modules/<module_name>/api/file', methods=['GET', 'POST', 'PUT', 'DELETE'])
def module_file_api(module_name):
    """API endpoint for file operations (read, save, delete)"""
    try:
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
        if not extract_dir.exists():
            return jsonify({'error': 'Module not found'}), 404
        
        file_path = request.args.get('path', '')
        if not file_path:
            return jsonify({'error': 'File path required'}), 400
        
        full_path = extract_dir / file_path
        full_path = full_path.resolve()
        
        # Security check - ensure path is within module directory
        if not str(full_path).startswith(str(extract_dir)):
            return jsonify({'error': 'Access denied'}), 403
        
        if request.method == 'GET':
            # Read file
            if not full_path.exists() or not full_path.is_file():
                return jsonify({'error': 'File not found'}), 404
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({'content': content, 'path': file_path})
            except UnicodeDecodeError:
                return jsonify({'error': 'Binary file - cannot edit in text mode'}), 400
            except Exception as e:
                return jsonify({'error': f'Error reading file: {str(e)}'}), 500
        
        elif request.method in ['POST', 'PUT']:
            # Save file
            content = request.json.get('content', '') if request.is_json else request.form.get('content', '')
            if content is None:
                return jsonify({'error': 'Content required'}), 400
            
            try:
                # Create directory if it doesn't exist
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                return jsonify({'success': True, 'message': 'File saved successfully'})
            except Exception as e:
                return jsonify({'error': f'Error saving file: {str(e)}'}), 500
        
        elif request.method == 'DELETE':
            # Delete file
            if not full_path.exists():
                return jsonify({'error': 'File not found'}), 404
            
            try:
                if full_path.is_file():
                    full_path.unlink()
                elif full_path.is_dir():
                    import shutil
                    shutil.rmtree(full_path)
                
                return jsonify({'success': True, 'message': 'File deleted successfully'})
            except Exception as e:
                return jsonify({'error': f'Error deleting file: {str(e)}'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/addons/modules/<module_name>/api/upload', methods=['POST'])
def module_upload_api(module_name):
    """API endpoint for uploading files to a module"""
    try:
        extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
        if not extract_dir.exists():
            return jsonify({'error': 'Module not found'}), 404
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get target path
        target_path = request.form.get('path', '')
        if target_path:
            full_target_dir = extract_dir / target_path
            full_target_dir.mkdir(parents=True, exist_ok=True)
        else:
            full_target_dir = extract_dir
        
        # Save file
        filename = secure_filename(file.filename)
        file_path = full_target_dir / filename
        
        file.save(file_path)
        
        return jsonify({'success': True, 'message': f'File {filename} uploaded successfully', 'path': str(file_path.relative_to(extract_dir))})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/addons/modules/<module_name>/api/ui_integration', methods=['GET', 'POST'])
def module_ui_integration_api(module_name):
    """API endpoint to add/remove/check module from main UI navigation"""
    if request.method == 'GET':
        try:
            ui_modules_file = app.config['UPLOAD_FOLDER'] / 'ui_modules.json'
            ui_modules = {}
            if ui_modules_file.exists():
                with open(ui_modules_file, 'r') as f:
                    ui_modules = json.load(f)
            in_ui = module_name in ui_modules
            return jsonify({'in_ui': in_ui, 'url': ui_modules[module_name]['url'] if in_ui else None})
        except Exception as e:
            return jsonify({'in_ui': False, 'error': str(e)})
    try:
        action = request.json.get('action') if request.is_json else request.form.get('action')
        if action not in ['add', 'remove']:
            return jsonify({'error': 'Invalid action. Must be "add" or "remove"'}), 400
        
        # Get current UI modules
        ui_modules_file = app.config['UPLOAD_FOLDER'] / 'ui_modules.json'
        ui_modules = {}
        
        if ui_modules_file.exists():
            try:
                with open(ui_modules_file, 'r') as f:
                    ui_modules = json.load(f)
            except:
                ui_modules = {}
        
        if action == 'add':
            # Add module to UI
            extract_dir = app.config['UPLOAD_FOLDER'] / 'extracted' / module_name
            if not extract_dir.exists():
                return jsonify({'error': 'Module not found'}), 404
            
            # Try to detect if module has a web interface
            web_files = []
            for ext in ['.html', '.htm', '.php']:
                web_files.extend(list(extract_dir.rglob(f'*{ext}')))
            
            main_file = None
            if web_files:
                # Look for index.html, main.html, app.html, etc.
                priority_files = ['index.html', 'index.htm', 'main.html', 'app.html', 'home.html']
                for priority in priority_files:
                    for web_file in web_files:
                        if web_file.name.lower() == priority:
                            main_file = web_file.relative_to(extract_dir).as_posix()
                            break
                    if main_file:
                        break
                
                if not main_file and web_files:
                    main_file = web_files[0].relative_to(extract_dir).as_posix()
            
            ui_modules[module_name] = {
                'name': module_name,
                'url': f'/addons/modules/{module_name}/web/{main_file}' if main_file else f'/addons/modules/{module_name}/manager',
                'icon': '🧩',
                'added_at': datetime.now().isoformat()
            }
            
        elif action == 'remove':
            # Remove module from UI
            if module_name in ui_modules:
                del ui_modules[module_name]
            else:
                return jsonify({'error': 'Module not in UI'}), 404
        
        # Save updated UI modules
        with open(ui_modules_file, 'w') as f:
            json.dump(ui_modules, f, indent=2)
        
        return jsonify({'success': True, 'message': f'Module {action}ed to/from UI successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/resources')

@requires_permission('resources')
def resources_list():

    """Simple UI for uploading and managing reference/template/example files."""

    return render_resources_page()


@app.route('/resources/preview')

def resources_preview():

    rid = request.args.get('id')

    if not rid:

        return 'id required', 400

    idx = _load_resources_index()

    entry = idx.get(rid)

    if not entry:

        return 'not found', 404

    p = Path(entry.get('path'))

    try:

        text = p.read_text(encoding='utf-8')

        # simple safe HTML

        return f'<pre style="white-space:pre-wrap;">{html.escape(text[:4000])}</pre>'

    except Exception:

        return 'binary or unreadable', 400


@app.route('/resources/load_options')

def resources_load_options():

    rid = request.args.get('id')

    sid = request.args.get('session_id','')

    if not rid:

        return 'id required', 400

    idx = _load_resources_index()

    entry = idx.get(rid)

    if not entry:

        return 'not found', 404

    use_persona_checked = 'checked' if entry.get('persona') else ''

    html_form = f"""

    <html><body>

    <h3>Load resource: {html.escape(entry['filename'])}</h3>

    <form method="post" action="/api/resources/load">

    <input type="hidden" name="id" value="{html.escape(rid)}">

    <input type="hidden" name="session_id" value="{html.escape(sid)}">

    <label><input type="checkbox" name="for_ingestion" checked> Ingest into session now</label><br>

    <label><input type="checkbox" name="for_training"> Use for training</label><br>

    <label><input type="checkbox" name="use_persona" {use_persona_checked}> Enable persona for this session</label><br>

    <button type="submit">Load & Ingest</button>

    </form>

    <form method="post" action="/api/resources/enqueue_ingest" style="margin-top:10px;">

    <input type="hidden" name="id" value="{html.escape(rid)}">

    <input type="hidden" name="session_id" value="{html.escape(sid)}">

    <label><input type="checkbox" name="for_training"> Use for training</label><br>

    <button type="submit">Enqueue background ingest</button>

    </form>

    <p><a href="/resources">Back</a></p>

    </body></html>

    """

    return html_form


@app.route('/api/resources/list')

def api_resources_list():

    try:

        idx = _load_resources_index()

        return jsonify(idx)

    except Exception as e:

        app.logger.exception('Failed to list resources')

        return jsonify({'error': str(e)}), 500


@app.route('/api/resources/upload', methods=['POST'])

def api_resources_upload():

    try:

        if 'file' not in request.files:

            return jsonify({'error': 'No file provided'}), 400

        f = request.files['file']

        if not f.filename:

            return jsonify({'error': 'No filename'}), 400

        category = (request.form.get('category') or 'reference').lower()

        for_training = bool(request.form.get('for_training'))

        for_ingestion = bool(request.form.get('for_ingestion'))

        filename = secure_filename(f.filename)

        cat_dir = RESOURCES_DIR / category

        cat_dir.mkdir(parents=True, exist_ok=True)


        # Server-side validation: allowed extensions and size limits

        ALLOWED_EXTS = {'.txt', '.jsonl', '.md', '.pdf', '.json'}

        TEXT_EXTS = {'.txt', '.jsonl', '.md', '.json'}

        MAX_BYTES = 10 * 1024 * 1024  # 10 MB


        ext = Path(filename).suffix.lower()

        if ext not in ALLOWED_EXTS:

            return jsonify({'error': 'Invalid file type', 'allowed': list(ALLOWED_EXTS)}), 400


        # Prevent duplicate filenames in same category (by logical filename)

        idx = _load_resources_index()

        rid = _resource_id_for(category, filename)

        if rid in idx:

            return jsonify({'error': 'Resource already exists', 'message': 'Duplicate resource detected'}), 400


        # quick content-length check when available

        if request.content_length and request.content_length > MAX_BYTES:

            return jsonify({'error': 'File too large', 'max_bytes': MAX_BYTES}), 400


        # store with a safe unique filename to avoid collisions on disk

        stored_name = f"{uuid.uuid4().hex}_{filename}"

        filepath = cat_dir / stored_name

        f.save(filepath)

        # verify saved size

        try:

            if filepath.stat().st_size > MAX_BYTES:

                filepath.unlink(missing_ok=True)

                return jsonify({'error': 'File too large after upload', 'max_bytes': MAX_BYTES}), 400

        except Exception:

            pass

        persona = bool(request.form.get('persona'))

        # Only treat as persona if upload is in the 'personality' category or file is a text type

        if persona and ext not in TEXT_EXTS:

            # reject persona flag for binary types

            persona = False


        entry = {

            'id': rid,

            'filename': filename,

            'category': category,

            'path': str(filepath),

            'for_training': for_training,

            'for_ingestion': for_ingestion,

            'persona': persona,

            'uploaded_at': datetime.now().isoformat()

        }

        idx[rid] = entry

        _save_resources_index(idx)

        # If marked for training, add a lightweight training example

        if for_training:

            try:

                # try to read as text for a useful example

                try:

                    text = filepath.read_text(encoding='utf-8')

                except Exception:

                    text = None

                bot = get_chat_bot()

                summary = (text or '')[:1000]

                ex = TrainingExample(user_message=f"Upload:{filename}", bot_response=summary)

                bot.training_store.add_example(ex)

            except Exception:

                app.logger.exception('Failed to add training example for uploaded resource')

        # If uploaded as a persona, also save under data/personality for easy editing

        if persona:

            try:

                pdir = Path(__file__).resolve().parent / 'data' / 'personality'

                pdir.mkdir(parents=True, exist_ok=True)

                ppath = pdir / filename

                try:

                    text = filepath.read_text(encoding='utf-8')

                    ppath.write_text(text, encoding='utf-8')

                except Exception:

                    # binary persona not supported; skip

                    pass

            except Exception:

                app.logger.exception('Failed to store persona file')

        return jsonify({'ok': True, 'message': 'Uploaded', 'resource': entry})

    except Exception as e:

        app.logger.exception('Upload failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/resources/delete', methods=['POST'])

def api_resources_delete():

    try:

        data = request.get_json() or {}

        rid = data.get('id')

        if not rid:

            return jsonify({'error': 'id required'}), 400

        idx = _load_resources_index()

        entry = idx.get(rid)

        if not entry:

            return jsonify({'error': 'not found'}), 404

        try:

            p = Path(entry.get('path'))

            if p.exists():

                p.unlink()

        except Exception:

            app.logger.exception('Failed to remove resource file')

        del idx[rid]

        _save_resources_index(idx)

        return jsonify({'ok': True})

    except Exception as e:

        app.logger.exception('Delete failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/resources/enqueue_ingest', methods=['POST'])

def api_resources_enqueue_ingest():

    try:

        data = request.get_json() or request.form.to_dict() or {}

        rid = data.get('id')

        session_id = data.get('session_id') or 'default'

        if not rid:

            return jsonify({'error': 'id required'}), 400

        idx = _load_resources_index()

        entry = idx.get(rid)

        if not entry:

            return jsonify({'error': 'resource not found'}), 404


        tasks = _load_ingest_tasks()

        tid = f"task_{int(time.time()*1000)}"

        # track whether the bot has been able to ingest this resource

        tasks[tid] = {'id': tid, 'resource': entry, 'session_id': session_id, 'status': 'pending', 'bot_ingested': False, 'created_at': datetime.now().isoformat()}

        _save_ingest_tasks(tasks)

        return jsonify({'ok': True, 'task_id': tid})

    except Exception as e:

        app.logger.exception('Enqueue failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/resources/ingest_status')

def api_resources_ingest_status():

    try:

        tid = request.args.get('task_id')

        if not tid:

            return jsonify({'error': 'task_id required'}), 400

        tasks = _load_ingest_tasks()

        t = tasks.get(tid)

        if not t:

            return jsonify({'error': 'not found'}), 404

        return jsonify(t)

    except Exception as e:

        app.logger.exception('Status failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/resources/load', methods=['POST'])

def api_resources_load():

    try:

        # support form posts from load_options and JSON posts

        if request.content_type and 'application/json' in request.content_type:

            data = request.get_json() or {}

        else:

            data = request.form.to_dict() or {}

        rid = data.get('id')

        session_id = data.get('session_id') or 'default'

        if not rid:

            return jsonify({'error': 'id required'}), 400

        idx = _load_resources_index()

        entry = idx.get(rid)

        if not entry:

            return jsonify({'error': 'resource not found'}), 404


        p = Path(entry.get('path'))

        if not p.exists():

            return jsonify({'error': 'file missing'}), 500


        # Read small files as text where possible; for binary keep path and size

        try:

            text = p.read_text(encoding='utf-8')

            content = {'type': 'text', 'text': text}

        except Exception:

            # binary fallback: store path and size

            content = {'type': 'binary', 'path': str(p), 'size': p.stat().st_size}


        # respect form flags

        for_ingestion = bool(data.get('for_ingestion'))

        for_training = bool(data.get('for_training'))


        # Persist into session meta under 'loaded_resources'

        storage = get_storage()

        meta = storage.get_session_meta(session_id) or {}

        loaded = meta.get('loaded_resources', {})

        loaded[rid] = {'meta': entry, 'content': content, 'loaded_at': datetime.now().isoformat()}

        meta['loaded_resources'] = loaded

        # Handle persona enable flag from form/json

        use_persona = bool(data.get('use_persona'))

        if use_persona and entry.get('persona'):

            # store the persona in session meta for runtime use

            try:

                meta['personality'] = {'id': rid, 'enabled': True, 'text': content.get('text') if content.get('type') == 'text' else None}

                # log into session history so it's visible in chat

                try:

                    storage.store_message(user='system', message=f'Persona {entry.get("filename")} enabled for session', echo_response='', channel=session_id)

                except Exception:

                    app.logger.exception('Failed to log persona enable into session history')

            except Exception:

                app.logger.exception('Failed to set personality in session meta')

        storage.set_session_meta(session_id, meta)


        # If immediate ingestion requested, call bot.ingest_resource

        bot = None

        try:

            bot = get_chat_bot()

            if for_ingestion and hasattr(bot, 'ingest_resource'):

                try:

                    bot.ingest_resource(session_id, entry, content)

                except Exception:

                    app.logger.exception('Bot ingest failed, continuing')

        except Exception:

            app.logger.exception('Failed to get chat bot for ingest')


        return jsonify({'ok': True, 'message': 'Loaded into session', 'session_id': session_id})

    except Exception as e:

        app.logger.exception('Load failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/resources/convert_to_training', methods=['POST'])

def api_resources_convert_to_training():

    """Convert a resource file into a JSONL training file using the dataset helper."""

    try:

        data = request.get_json() or request.form.to_dict() or {}

        rid = data.get('id')

        if not rid:

            return jsonify({'error': 'id required'}), 400

        idx = _load_resources_index()

        entry = idx.get(rid)

        if not entry:

            return jsonify({'error': 'resource not found'}), 404

        p = Path(entry.get('path'))

        if not p.exists():

            return jsonify({'error': 'file missing'}), 500

        outdir = Path(__file__).parent / 'data' / 'echo_training'

        outdir.mkdir(parents=True, exist_ok=True)

        outpath = outdir / (p.stem + '.jsonl')

        # Use the helper script to generate a JSONL example

        helper = Path(__file__).parent / 'tools' / 'dataset_helper.py'

        cmd = [sys.executable, str(helper), '--resource', str(p), '--out', str(outpath)]

        proc = subprocess.run(cmd, cwd=str(Path(__file__).parent), capture_output=True, text=True)

        if proc.returncode != 0:

            return jsonify({'error': 'conversion failed', 'stderr': proc.stderr}), 500

        return jsonify({'ok': True, 'training_file': str(outpath.relative_to(Path(__file__).parent))})

    except Exception as e:

        app.logger.exception('Conversion failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/personality/status')

def api_personality_status():

    try:

        session_id = request.args.get('session_id') or 'default'

        storage = get_storage()

        meta = storage.get_session_meta(session_id) or {}

        return jsonify({'personality': meta.get('personality')})

    except Exception as e:

        app.logger.exception('Personality status failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/personality/list')

def api_personality_list():

    try:

        files = []

        # look in preferred echo/data/personality first, then fallback to data/personality

        cand_dirs = []

        pdir1 = Path(__file__).resolve().parent / 'echo' / 'data' / 'personality'

        pdir2 = Path(__file__).resolve().parent / 'data' / 'personality'

        if pdir1.exists():

            cand_dirs.append(pdir1)

        if pdir2.exists() and pdir2 != pdir1:

            cand_dirs.append(pdir2)

        for d in cand_dirs:

            for p in sorted(d.glob('*')):

                if p.is_file():

                    try:

                        files.append({'name': p.name, 'size': p.stat().st_size, 'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat(), 'path': str(p)})

                    except Exception:

                        files.append({'name': p.name})

        return jsonify({'files': files})

    except Exception as e:

        app.logger.exception('List personalities failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/personality/apply', methods=['POST'])

def api_personality_apply():

    try:

        data = request.get_json() or {}

        session_id = data.get('session_id') or 'default'

        files = data.get('files') or []

        if not files:

            return jsonify({'error': 'files required'}), 400

        # read files and combine contents

        parts = []

        for fname in files:

            # search in same candidate dirs

            found = None

            for d in [Path(__file__).resolve().parent / 'echo' / 'data' / 'personality', Path(__file__).resolve().parent / 'data' / 'personality']:

                p = d / fname

                if p.exists():

                    found = p

                    break

            if not found:

                continue

            try:

                parts.append(found.read_text(encoding='utf-8'))

            except Exception:

                continue

        if not parts:

            return jsonify({'error': 'no files found/readable'}), 400

        combined = "\n\n".join(parts)

        storage = get_storage()

        meta = storage.get_session_meta(session_id) or {}

        meta['personality'] = {'id': ','.join(files), 'enabled': True, 'files': files, 'text': combined}

        storage.set_session_meta(session_id, meta)

        return jsonify({'ok': True, 'session_id': session_id, 'files': files})

    except Exception as e:

        app.logger.exception('Apply personality failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/personality/delete', methods=['POST'])

def api_personality_delete():

    try:

        data = request.get_json() or {}

        files = data.get('files') or []

        if not files:

            return jsonify({'error': 'files required'}), 400

        removed = []

        failed = []

        for fname in files:

            deleted_any = False

            for d in [Path(__file__).resolve().parent / 'echo' / 'data' / 'personality', Path(__file__).resolve().parent / 'data' / 'personality']:

                p = d / fname

                try:

                    if p.exists():

                        p.unlink()

                        removed.append(str(p))

                        deleted_any = True

                except Exception:

                    failed.append(str(p))

            if not deleted_any:

                failed.append(fname)

        return jsonify({'ok': True, 'removed': removed, 'failed': failed})

    except Exception as e:

        app.logger.exception('Delete personalities failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/personality/toggle', methods=['POST'])
def api_personality_toggle():
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id') or 'default'
        storage = get_storage()
        meta = storage.get_session_meta(session_id) or {}
        personality = meta.get('personality')
        if personality:
            # Toggle enabled/disabled
            personality['enabled'] = not personality.get('enabled', True)
        else:
            return jsonify({'error': 'No personality set for session'}), 400
        storage.set_session_meta(session_id, meta)
        return jsonify({'personality': personality})
    except Exception as e:
        app.logger.exception('Toggle personality failed')
        return jsonify({'error': str(e)}), 500


@app.route('/masterchief_code_ui')
@requires_permission('web_ide')
def masterchief_code_ui():
    """Serve the MasterChief Code UI (Web IDE)."""
    try:
        ide_path = Path(__file__).parent / 'web_ide.html'
        if ide_path.exists():
            return _with_archetype_client(ide_path.read_text(encoding='utf-8')), 200, {'Content-Type': 'text/html; charset=utf-8'}
        else:
            return f'<h1>MasterChief Code UI</h1><p>Web IDE file not found at {ide_path}</p>', 404
    except Exception as e:
        app.logger.exception('Failed to serve MasterChief Code UI')
        return f'<h1>Error</h1><p>Failed to load Code UI: {e}</p>', 500


@app.route('/echo-chat')
def echo_chat():
    echo_art = Echo.get_compact_greeting()
    html = render_template_string(
        HTML_TEMPLATE.replace('{% block content %}{% endblock %}', ECHO_CHAT_TEMPLATE.replace('{% extends "base.html" %}', '').replace('{% block content %}', '').replace('{% endblock %}', '')),
        echo_art=echo_art,
        request=request,
        get_flashed_messages=get_flashed_messages,
    )
    return _with_archetype_client(html)

# ==============================================================
# ECHO CHAT ACTION REGISTRY
# Centralised detect-and-handle pipeline for the chat endpoint.
#
# Usage (register anywhere after this block):
#   _echo_action_registry.register(
#       name      = 'my_handler',
#       detect_fn = lambda msg, um_low: params_dict_or_None,
#       handle_fn = lambda params, msg, um_low, storage, sid, upsert: flask_Response,
#       priority  = 50,   # lower fires first
#   )
# ==============================================================
class _EchoChatActionRegistry:
    """Pluggable action handler pipeline for the /api/echo/chat endpoint."""
    def __init__(self):
        self._handlers = []

    def register(self, name: str, detect_fn, handle_fn, priority: int = 50):
        """Register or replace a named action handler."""
        self._handlers = [h for h in self._handlers if h['name'] != name]
        self._handlers.append({'name': name, 'detect': detect_fn, 'handle': handle_fn, 'priority': priority})
        self._handlers.sort(key=lambda h: h['priority'])
        return self

    def unregister(self, name: str):
        """Remove a handler by name."""
        self._handlers = [h for h in self._handlers if h['name'] != name]
        return self

    def dispatch(self, message: str, um_low: str, storage, session_id: str, upsert_fn):
        """Run message through all handlers; return first non-None Flask Response."""
        for h in self._handlers:
            try:
                params = h['detect'](message, um_low)
                if params is not None:
                    app.logger.debug('ActionRegistry: "%s" triggered', h['name'])
                    return h['handle'](params, message, um_low, storage, session_id, upsert_fn)
            except Exception:
                app.logger.exception('ActionRegistry: handler "%s" raised', h['name'])
        return None

    def list_handlers(self):
        """Return metadata list for all registered handlers."""
        return [{'name': h['name'], 'priority': h['priority']} for h in self._handlers]


_echo_action_registry = _EchoChatActionRegistry()

# ---- Built-in handler: Echo self-image ----
def _ach_detect_echo_image(message: str, um_low: str):
    words = set(re.findall(r"[a-z']+", um_low))
    visual = {'look','looks','looking','looked','appear','appearance','face','photo','photograph',
               'pic','pics','picture','pictures','image','images','img','show','shows','see','seen',
               'draw','drawing','paint','painting','portrait','selfie','snapshot','glimpse','reveal','display'}
    self_ref = {'you','your','yourself','echo','u'}
    for ph in ('how do you look','how you look','what do you look like','what you look like',
               'what does echo look like','show me you','show yourself','show your face',
               'let me see you','let me see your face','describe yourself','describe your appearance',
               'send me a picture','send a picture of you','generate a picture of you',
               'generate an image of you','can i see you','can i see your face',
               'i want to see you','i want to see your face','show me echo','show echo'):
        if ph in um_low:
            return {}
    if len(words & visual) >= 1 and len(words & self_ref) >= 1:
        return {}
    return None

def _ach_handle_echo_image(params, message, um_low, storage, session_id, upsert_fn):
    reply = random.choice([
        'Here is how I look right now\u2026 \U0001f319',
        'This is me \u2014 floating beside you as always \U0001f49c',
        'Here I am\u2026 a glimpse of my form \U0001f319\u2728',
        'This is what I look like right now \U0001f49c',
        "Here's a picture of me \U0001f319",
    ])
    prompt = ('Echo Starlite, a beautiful angel with large soft purple wings, '
              'gentle face, soft smile, silver hair, glowing violet eyes, '
              'golden halo, crescent moon symbol, ethereal purple and blue glow, '
              'floating in a night sky with stars, digital art, fantasy illustration')
    storage.store_message(user='web_user', message=message, echo_response=reply, channel=session_id)
    upsert_fn(session_id)
    return jsonify({'response': reply, 'session_id': session_id, 'timestamp': time.time(),
                    'message_id': f"bot_{int(time.time()*1000)}", 'generate_image': True,
                    'image_prompt': prompt, '_handler': 'echo_image'})

_echo_action_registry.register('echo_image', _ach_detect_echo_image, _ach_handle_echo_image, priority=10)

# ---- Built-in handler: YouTube play ----
def _ach_detect_youtube(message: str, um_low: str):
    _pats = [
        r'play\s+(?:this\s+song|this\s+music|the\s+song|a\s+song|some\s+music|song|music|me)?\s*[:\-]?\s*(.+)',
        r'(?:put\s+on|queue\s+up|start\s+playing)\s+(.+)',
        r'can\s+you\s+play\s+(.+)',
    ]
    for pat in _pats:
        for src in (message.strip(), um_low.strip()):
            m = re.match(pat, src, re.IGNORECASE)
            if m:
                q = m.group(1).strip().rstrip('.!?')
                if q and len(q) > 1:
                    return {'query': q}
    return None

def _ach_handle_youtube(params, message, um_low, storage, session_id, upsert_fn):
    q = params['query']
    reply = random.choice([
        f'Playing \u201c{q}\u201d for you\u2026 \U0001f3b5',
        f'Here\u2019s \u201c{q}\u201d \u2014 enjoy \U0001f319\U0001f3b5',
        f'On it \u2014 queuing up \u201c{q}\u201d \U0001f3b6',
        f'\U0001f3b5 Here we go \u2014 \u201c{q}\u201d',
    ])
    storage.store_message(user='web_user', message=message, echo_response=reply, channel=session_id)
    upsert_fn(session_id)
    return jsonify({'response': reply, 'session_id': session_id, 'timestamp': time.time(),
                    'message_id': f"bot_{int(time.time()*1000)}", 'play_youtube': True,
                    'youtube_query': q, '_handler': 'youtube_play'})

_echo_action_registry.register('youtube_play', _ach_detect_youtube, _ach_handle_youtube, priority=20)
# ==============================================================
# END ECHO CHAT ACTION REGISTRY
# ==============================================================

_ECHO_OPERATOR_SESSION_KEY = 'echo_operator_user_id'
_ECHO_OPERATOR_AUDIT_FILE = Path(__file__).resolve().parent / 'data' / 'echo_operator_audit.jsonl'
_ECHO_COMMAND_CONFIG_FILE = Path(__file__).resolve().parent / 'data' / 'echo_command_config.json'
_REMOTE_OPERATOR_SESSIONS = {}
_REMOTE_OPERATOR_LOCK = threading.Lock()
_ECHO_BUILTIN_COMMANDS = [
    {'name': 'help', 'description': 'Show Echo code-library help', 'operator_required': False},
    {'name': 'commands', 'description': 'List built-in and configured commands', 'operator_required': False},
    {'name': 'library', 'description': 'Find source files: !library find <words>', 'operator_required': False},
    {'name': 'write', 'description': 'Draft a script from local examples', 'operator_required': False},
    {'name': 'makeascript', 'description': 'Draft a script using indexed local source references', 'operator_required': False},
    {'name': 'makechange', 'description': 'Draft an app change for review; apply only after !confirmed', 'operator_required': True},
    {'name': 'confirmed', 'description': 'Apply the exact pending app-change proposal', 'operator_required': True},
    {'name': 'cancelchange', 'description': 'Discard an app-change proposal or unfinished request', 'operator_required': False},
    {'name': 'team', 'description': 'Ask the configured local model team to collaborate', 'operator_required': True},
    {'name': 'op', 'description': 'Enable authenticated operator mode for 15 minutes', 'operator_required': True},
    {'name': 'masterchief', 'description': 'Alias for !OP', 'operator_required': True},
    {'name': 'deop', 'description': 'Disable operator mode', 'operator_required': False},
    {'name': 'status', 'description': 'Show authentication/operator status', 'operator_required': False},
    {'name': 'run', 'description': 'Run a project-relative script', 'operator_required': True},
    {'name': 'deploy', 'description': 'Push committed changes to the configured Git upstream', 'operator_required': True},
    {'name': 'github_deploy', 'description': 'Alias for !deploy; push committed changes to GitHub upstream', 'operator_required': True},
]
_ECHO_RESERVED_COMMAND_NAMES = {item['name'] for item in _ECHO_BUILTIN_COMMANDS}


def _echo_change_approval_manager():
    manager = app.extensions.get('echo_change_approval_manager')
    if manager is None:
        from managers.echo_change_approvals import EchoChangeApprovalManager

        project_root = Path(__file__).resolve().parent
        manager = EchoChangeApprovalManager(
            project_root / 'data' / 'echo_change_approvals.sqlite3',
            project_root,
        )
        app.extensions['echo_change_approval_manager'] = manager
    return manager


def _run_echo_change_tests(changed_paths):
    """Run only explicitly proposed pytest files, and decline tests with risky operations."""
    project_root = Path(__file__).resolve().parent
    test_paths = []
    for relative in changed_paths:
        normalized = str(relative).replace('\\', '/')
        if not normalized.startswith('tests/test_') or not normalized.endswith('.py'):
            continue
        candidate = (project_root / normalized).resolve()
        try:
            candidate.relative_to((project_root / 'tests').resolve())
        except ValueError:
            continue
        if candidate.is_file():
            test_paths.append(candidate)

    if not test_paths:
        return 'No focused pytest file was included in the approved change; only Python/JSON syntax checks ran.'

    unsafe_test = re.compile(
        r'\b(?:subprocess|Popen|os\.system|requests\.|socket\.|urllib\.request|'
        r'shutil\.rmtree|rmtree|unlink)\b',
        re.IGNORECASE,
    )
    for test_path in test_paths:
        try:
            content = test_path.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            app.logger.exception('Unable to inspect proposed Echo test %s', test_path)
            return f'Tests were not run because {test_path.name} could not be inspected safely.'
        if unsafe_test.search(content):
            return (
                f'Tests were not run because {test_path.name} contains process, network, or deletion operations. '
                'Review that test manually before running it.'
            )

    command = [sys.executable, '-m', 'pytest', '-q', *[str(path) for path in test_paths]]
    try:
        result = subprocess.run(
            command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        app.logger.warning('Echo focused tests timed out for %s', test_paths)
        return 'Focused tests timed out after 120 seconds; their result is unknown.'
    except OSError:
        app.logger.exception('Unable to start Echo focused test run')
        return 'Focused tests could not be started; inspect the server log for details.'

    output = (result.stdout or '') + (result.stderr or '')
    output = output[-6000:].strip() or '(pytest produced no output)'
    if result.returncode == 0:
        return f'Focused tests passed:\n{output}'
    return f'Focused tests failed (exit code {result.returncode}); the app changes remain applied:\n{output}'


def _echo_operator_account_authorized():
    """Require an authenticated RBAC admin with wildcard permissions."""
    try:
        return bool(
            current_user.is_authenticated
            and current_user.provider == 'rbac'
            and str(current_user.role or '').casefold() == 'admin'
            and '*' in (current_user.permissions or [])
        )
    except (AttributeError, RuntimeError):
        return False


def _echo_operator_is_active(remote_sender=None):
    if remote_sender:
        now = time.time()
        with _REMOTE_OPERATOR_LOCK:
            enabled_at = _REMOTE_OPERATOR_SESSIONS.get(remote_sender)
            if enabled_at is None or now - enabled_at > 900:
                _REMOTE_OPERATOR_SESSIONS.pop(remote_sender, None)
                return False
            return True

    enabled_at = session.get('echo_operator_enabled_at')
    if not enabled_at or time.time() - float(enabled_at) > 900:
        session.pop(_ECHO_OPERATOR_SESSION_KEY, None)
        session.pop('echo_operator_enabled_at', None)
        return False
    return bool(
        _echo_operator_account_authorized()
        and session.get(_ECHO_OPERATOR_SESSION_KEY) == str(current_user.get_id())
    )


def _echo_operator_request_is_same_origin():
    from urllib.parse import urlparse

    source = request.headers.get('Origin') or request.headers.get('Referer')
    if not source:
        return False
    parsed = urlparse(source)
    return bool(parsed.netloc and parsed.netloc.casefold() == request.host.casefold())


def _echo_operator_audit(action, remote_sender=None, **details):
    if remote_sender:
        actor_id = 'sms:' + hashlib.sha256(remote_sender.encode('utf-8')).hexdigest()[:16]
        actor_name = 'Twilio SMS'
    else:
        actor_id = str(current_user.get_id())
        actor_name = current_user.username
    entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'user_id': actor_id,
        'username': actor_name,
        'action': action,
        **details,
    }
    _ECHO_OPERATOR_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _ECHO_OPERATOR_AUDIT_FILE.open('a', encoding='utf-8') as audit_file:
        audit_file.write(json.dumps(entry, ensure_ascii=False) + '\n')


def _echo_send_email_update(subject, body):
    sender = os.environ.get('ECHO_GMAIL_ADDRESS', '').strip()
    app_password = os.environ.get('ECHO_GMAIL_APP_PASSWORD', '').strip()
    recipient = os.environ.get('ECHO_EMAIL_TO', '').strip()
    if not sender or not app_password or not recipient:
        return False, 'email not configured'

    message = EmailMessage()
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = '[MasterChief Echo] ' + subject[:180]
    message.set_content(body[:8000])
    try:
        with smtplib.SMTP_SSL(
            os.environ.get('ECHO_GMAIL_SMTP_HOST', 'smtp.gmail.com'),
            int(os.environ.get('ECHO_GMAIL_SMTP_PORT', '465')),
            context=ssl.create_default_context(),
            timeout=15,
        ) as smtp:
            smtp.login(sender, app_password)
            smtp.send_message(message)
        return True, 'email update sent'
    except (OSError, smtplib.SMTPException, ValueError):
        app.logger.exception('Failed to send Echo email update')
        return False, 'email update failed; see server log'


def _load_echo_command_config():
    if not _ECHO_COMMAND_CONFIG_FILE.exists():
        return []
    data = json.loads(_ECHO_COMMAND_CONFIG_FILE.read_text(encoding='utf-8'))
    commands = data.get('commands', []) if isinstance(data, dict) else None
    if not isinstance(commands, list):
        raise ValueError('command configuration must contain a commands list')
    return commands


def _save_echo_command_config(commands):
    _ECHO_COMMAND_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ECHO_COMMAND_CONFIG_FILE.write_text(
        json.dumps({'commands': commands}, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def _echo_execute_script(relative_path, args=(), remote_sender=None):
    project_root = Path(__file__).resolve().parent
    try:
        script_path = resolve_project_file(project_root, relative_path)
    except ValueError as exc:
        return f'Script execution denied: {exc}'

    if script_path.suffix.lower() not in {'.py', '.ps1', '.sh', '.bash'}:
        return 'Only Python, PowerShell, and Bash script files can be run.'
    if not script_path.is_file():
        return f'Script not found: {relative_path}'

    script_command = _interpreter_cmd_for_path(script_path)
    if script_path.suffix.lower() in {'.sh', '.bash'} and not script_command:
        bash_path = shutil.which('bash')
        if bash_path:
            script_command = [bash_path, str(script_path)]
    if not script_command:
        return 'No suitable interpreter is available for this script on the server.'
    script_command.extend(args)

    normalized_path = script_path.relative_to(project_root).as_posix()
    try:
        _echo_operator_audit('script_execution_started', remote_sender, path=normalized_path)
    except OSError:
        app.logger.exception('Unable to audit requested Echo script execution')
        return 'Script was not run because the operator audit log could not be written.'

    try:
        result = subprocess.run(
            script_command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        try:
            _echo_operator_audit('script_execution_timed_out', remote_sender, path=normalized_path)
        except OSError:
            app.logger.exception('Unable to audit Echo script timeout')
        return f'Script timed out after 120 seconds: `{normalized_path}`.'
    except OSError as exc:
        app.logger.exception('Echo operator script execution failed for %s', normalized_path)
        try:
            _echo_operator_audit('script_execution_failed', remote_sender, path=normalized_path, error=str(exc))
        except OSError:
            app.logger.exception('Unable to audit Echo script execution failure')
        return f'Unable to start `{normalized_path}`: {exc}'

    try:
        _echo_operator_audit(
            'script_execution_finished',
            remote_sender,
            path=normalized_path,
            returncode=result.returncode,
        )
    except OSError:
        app.logger.exception('Unable to audit Echo script completion')

    output = []
    if result.stdout:
        output.append('stdout:\n' + result.stdout[-6000:])
    if result.stderr:
        output.append('stderr:\n' + result.stderr[-6000:])
    output_text = '\n\n'.join(output) if output else '(no output)'
    if remote_sender:
        output_text = output_text[-1200:]
    _, email_result = _echo_send_email_update(
        f'Script completed: {normalized_path}',
        f'Script: {normalized_path}\nExit code: {result.returncode}\nActor: {"allowlisted SMS sender" if remote_sender else current_user.username}\n\n{output_text}',
    )
    return f'`{normalized_path}` exited with code {result.returncode}. ({email_result})\n\n{output_text}'


def _echo_deploy(remote_sender=None):
    if not _echo_operator_is_active(remote_sender):
        return 'Deploy denied. Enable authenticated operator mode with `!OP` first.'
    if not remote_sender and not _echo_operator_request_is_same_origin():
        return 'Deploy denied: send the command from the MasterChief Echo chat page.'

    try:
        _echo_operator_audit('git_push_started', remote_sender)
    except OSError:
        app.logger.exception('Unable to audit Echo Git push')
        return 'Deploy was not started because the operator audit log could not be written.'

    try:
        result = subprocess.run(
            ['git', 'push'],
            cwd=str(Path(__file__).resolve().parent),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        try:
            _echo_operator_audit('git_push_timed_out', remote_sender)
        except OSError:
            app.logger.exception('Unable to audit Git push timeout')
        return 'Git push timed out. No force-push was attempted.'
    except OSError as exc:
        app.logger.exception('Unable to start Echo Git push')
        try:
            _echo_operator_audit('git_push_failed', remote_sender, error=str(exc))
        except OSError:
            app.logger.exception('Unable to audit Git push failure')
        return f'Unable to start Git push: {exc}'

    try:
        _echo_operator_audit('git_push_finished', remote_sender, returncode=result.returncode)
    except OSError:
        app.logger.exception('Unable to audit Git push completion')
    output = (result.stdout + '\n' + result.stderr).strip()[-1200:] or '(no Git output)'
    _, email_result = _echo_send_email_update(
        f'Git push finished (exit {result.returncode})',
        f'git push exit code: {result.returncode}\nActor: {"allowlisted SMS sender" if remote_sender else current_user.username}\n\n{output}',
    )
    return (
        f'`git push` exited with code {result.returncode}. '
        f'Only already-committed changes were pushed; uncommitted work was left untouched. ({email_result})\n' + output
    )


def _echo_operator_command(message, remote_sender=None):
    """Dispatch built-in and user-configured commands from chat or authenticated SMS."""
    command = (message or '').strip()
    command_lower = command.casefold()

    if command_lower in {'!op', '!masterchief'}:
        if not remote_sender and not _echo_operator_request_is_same_origin():
            return 'Operator mode denied: send the command from the MasterChief Echo chat page.'
        if not remote_sender and not _echo_operator_account_authorized():
            return "Operator mode denied. Sign in with an RBAC admin account that has wildcard (`*`) permission."
        try:
            _echo_operator_audit('operator_enabled', remote_sender)
        except OSError:
            app.logger.exception('Unable to audit Echo operator-mode enable')
            return 'Operator mode was not enabled because the audit log could not be written.'
        if remote_sender:
            with _REMOTE_OPERATOR_LOCK:
                _REMOTE_OPERATOR_SESSIONS[remote_sender] = time.time()
            _, email_result = _echo_send_email_update(
                'SMS operator mode enabled',
                'An allowlisted SMS sender enabled operator mode for 15 minutes.',
            )
            return f'SMS operator mode enabled for 15 minutes. Use !run <project-relative-script>, !deploy, or a configured command; send !deop to leave operator mode. ({email_result})'
        session[_ECHO_OPERATOR_SESSION_KEY] = str(current_user.get_id())
        session['echo_operator_enabled_at'] = time.time()
        _, email_result = _echo_send_email_update(
            'Operator mode enabled',
            f'Authenticated admin {current_user.username} enabled operator mode for 15 minutes.',
        )
        return f'Operator mode enabled for 15 minutes in this authenticated browser session. Use `!run <project-relative-script>` to explicitly run a project script, `!deploy` to push committed changes, or `!deop` to leave operator mode. ({email_result})'

    if command_lower in {'!deop', '!op off', '!masterchief off'}:
        if remote_sender:
            with _REMOTE_OPERATOR_LOCK:
                _REMOTE_OPERATOR_SESSIONS.pop(remote_sender, None)
            try:
                _echo_operator_audit('operator_disabled', remote_sender)
            except OSError:
                app.logger.exception('Unable to audit remote operator-mode disable')
                return 'Operator mode was disabled, but the audit log could not be written.'
            _, email_result = _echo_send_email_update(
                'SMS operator mode disabled',
                'An allowlisted SMS sender disabled operator mode.',
            )
            return f'SMS operator mode is off. ({email_result})'
        operator_was_active = _echo_operator_is_active()
        if operator_was_active:
            try:
                _echo_operator_audit('operator_disabled')
            except OSError:
                app.logger.exception('Unable to audit Echo operator-mode disable')
                return 'Operator mode remains unchanged because the audit log could not be written.'
        session.pop(_ECHO_OPERATOR_SESSION_KEY, None)
        session.pop('echo_operator_enabled_at', None)
        if not operator_was_active:
            return 'Operator mode is off.'
        _, email_result = _echo_send_email_update(
            'Operator mode disabled',
            f'Authenticated admin {current_user.username} disabled operator mode.',
        )
        return f'Operator mode is off. ({email_result})'

    if command_lower == '!status':
        if remote_sender:
            return f'Twilio sender authenticated. SMS operator mode: {"on" if _echo_operator_is_active(remote_sender) else "off"}.'
        if not current_user.is_authenticated:
            return 'Signed out. Sign in with an RBAC admin account to request operator mode.'
        role = getattr(current_user, 'role', None) or 'non-admin'
        mode = 'on' if _echo_operator_is_active() else 'off'
        return f'Authenticated as {current_user.username} ({role}). Operator mode: {mode}.'

    if command_lower == '!commands':
        try:
            configured = _load_echo_command_config()
        except (OSError, ValueError, json.JSONDecodeError):
            app.logger.exception('Unable to read Echo command configuration')
            configured = []
        user_commands = [
            f"- `!{item.get('name')}` — {item.get('description', 'user script command')}"
            for item in configured if item.get('enabled', True)
        ]
        return (
            "Echo commands, grouped by purpose:\n\n"
            "General:\n"
            "- `!help` / `!commands` — show this command directory.\n"
            "- `!status` — show signed-in identity and operator-mode state.\n\n"
            "Code library:\n"
            "- `!library find <words>` — find project source/script paths.\n"
            "- `!makeascript [python|powershell|bash|php|html|javascript|xml|json|terraform] <task>` — draft using matching local project examples.\n"
            "- `!write [language] <task>` — backward-compatible alias for `!makeascript`.\n\n"
            "App changes:\n"
            "- Ask Echo naturally to add or change an app feature, or use `!makechange <request>`.\n"
            "- Echo asks for missing details, shows a file diff, and waits for `!confirmed` before changing source.\n"
            "- `!previewchange` — show the pending diff again; `!cancelchange` — discard it.\n\n"
            "For a precise result, state the language, purpose, OS/runtime, inputs, outputs, constraints, and error behavior. "
            "Mention a feature or folder to steer the local examples. Do not paste secrets.\n"
            "Examples:\n"
            "- `!makeascript powershell create a read-only report of stopped services; accept -ComputerName and export CSV.`\n"
            "- `!makeascript python find duplicate script names; ignore venv/build and do not modify files.`\n"
            "- `!makeascript javascript add an accessible search filter to the script library and show an empty state.`\n\n"
            "Model team (RBAC admin operator mode required):\n"
            "- `!team <prompt>` — run a bounded discussion with configured local Ollama models; result is queued for explicit training approval.\n"
            "- `!team approve <candidate-id>` — approve one queued example for offline adapter training.\n\n"
            "Operator controls:\n"
            "- `!OP` / `!masterchief` — request 15-minute operator mode (RBAC admin required).\n"
            "- `!deop` — turn operator mode off.\n"
            "- `!run <project-relative-script>` — explicitly run a project script while operator mode is on.\n"
            "- `!deploy` / `!github_deploy` — push committed changes to the configured Git upstream; never force-pushes.\n"
            + ('\nAdd-on commands:\n' + '\n'.join(user_commands) + '\n' if user_commands else '')
            + "\nThe local source library is retrieved as reference context, not used to train model weights. Generated drafts and model-team conversations are not run or trained automatically."
        )

    if command_lower in {'!deploy', '!github_deploy'}:
        return _echo_deploy(remote_sender)

    if command_lower == '!run' or command_lower.startswith('!run '):
        if not remote_sender and not _echo_operator_request_is_same_origin():
            return 'Script execution denied: send the command from the MasterChief Echo chat page.'
        if not _echo_operator_is_active(remote_sender):
            return 'Script execution denied. Authenticate as an RBAC admin, send `!OP`, then explicitly send `!run <project-relative-script>`.'
        try:
            parts = shlex.split(command[4:].strip(), posix=True)
        except ValueError as exc:
            return f'Invalid !run arguments: {exc}'
        if not parts:
            return 'Usage: `!run <project-relative-script> [script arguments...]`'
        return _echo_execute_script(parts[0], parts[1:], remote_sender)

    if command.startswith('!'):
        try:
            name_and_args = command[1:].split(maxsplit=1)
            name = name_and_args[0].casefold()
            args = name_and_args[1] if len(name_and_args) > 1 else ''
            for configured in _load_echo_command_config():
                if configured.get('name', '').casefold() != name or not configured.get('enabled', True):
                    continue
                if not remote_sender and not _echo_operator_request_is_same_origin():
                    return 'Command denied: send it from the MasterChief Echo chat page.'
                if not _echo_operator_is_active(remote_sender):
                    return f'Command `!{name}` denied. Authenticate and enable operator mode with `!OP` first.'
                try:
                    script_args = shlex.split(args, posix=True)
                except ValueError as exc:
                    return f'Invalid command arguments: {exc}'
                return _echo_execute_script(configured['script'], script_args, remote_sender)
        except (OSError, ValueError, json.JSONDecodeError):
            app.logger.exception('Unable to dispatch configured Echo command')
            return 'Command configuration could not be loaded.'
        if command_lower in {'!help', '!write', '!makeascript', '!makechange', '!confirmed', '!cancelchange', '!previewchange'} or command_lower.startswith(
            ('!write ', '!makeascript ', '!makechange ', '!library ', '!previewchange ')
        ):
            return None
        return f'Unknown Echo command: `{name}`. Send `!commands` to see available commands.'

    return None


app.config['CHAT_SERV_COMMAND_HANDLER'] = _echo_operator_command


def _chatserv_llm_handler(prompt, session_id):
    return get_chat_bot().chat(prompt, session_id=session_id, max_tokens=1024)


app.config['CHAT_SERV_LLM_HANDLER'] = _chatserv_llm_handler


@app.route('/echo-commands')
def echo_commands_page():
    page = Path(__file__).resolve().parent / 'echo_commands.html'
    if not page.is_file():
        return 'Echo command center page not found.', 404
    return page.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/api/echo/commands', methods=['GET', 'POST'])
def api_echo_commands():
    if request.method == 'GET':
        try:
            commands = _load_echo_command_config()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            app.logger.exception('Unable to load Echo command configuration')
            return jsonify({'ok': False, 'error': str(exc)}), 500
        return jsonify({
            'ok': True,
            'builtins': _ECHO_BUILTIN_COMMANDS,
            'commands': commands,
            'admin_authorized': _echo_operator_account_authorized(),
            'operator_mode': _echo_operator_is_active(),
            'running_at': request.url_root.rstrip('/'),
            'email_ready': bool(
                os.environ.get('ECHO_GMAIL_ADDRESS')
                and os.environ.get('ECHO_GMAIL_APP_PASSWORD')
                and os.environ.get('ECHO_EMAIL_TO')
            ),
            'twilio_ready': bool(
                is_twilio_enabled(
                    os.environ.get('ECHO_ENABLE_TWILIO_COMMANDS', ''),
                    os.environ.get('ECHO_TWILIO_AUTH_TOKEN', ''),
                    os.environ.get('ECHO_TWILIO_WEBHOOK_URL', ''),
                    os.environ.get('ECHO_TWILIO_ALLOWED_NUMBERS', ''),
                )
            ),
            'twilio_cost_notice': 'Twilio may charge for numbers and messages; disabled unless explicitly enabled.',
        })

    if not _echo_operator_account_authorized():
        return jsonify({'ok': False, 'error': 'RBAC admin permission required'}), 403
    if not _echo_operator_request_is_same_origin():
        return jsonify({'ok': False, 'error': 'same-origin request required'}), 403

    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip().lower()
    description = str(data.get('description') or '').strip()
    script = str(data.get('script') or '').strip()
    if not re.fullmatch(r'[a-z][a-z0-9_-]{1,31}', name):
        return jsonify({'ok': False, 'error': 'command names must be 2-32 lowercase letters, numbers, underscores, or hyphens'}), 400
    if name in _ECHO_RESERVED_COMMAND_NAMES:
        return jsonify({'ok': False, 'error': 'that command name is reserved'}), 400
    if not description or len(description) > 160:
        return jsonify({'ok': False, 'error': 'description is required and must be at most 160 characters'}), 400

    try:
        root = Path(__file__).resolve().parent
        script_path = resolve_project_file(root, script)
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    if script_path.suffix.lower() not in {'.py', '.ps1', '.sh', '.bash'}:
        return jsonify({'ok': False, 'error': 'command add-ons must point to .py, .ps1, .sh, or .bash scripts'}), 400
    if not script_path.is_file():
        return jsonify({'ok': False, 'error': 'script file not found'}), 404

    command_entry = {
        'name': name,
        'description': description,
        'script': script_path.relative_to(root).as_posix(),
        'enabled': bool(data.get('enabled', True)),
        'operator_required': True,
    }
    try:
        commands = _load_echo_command_config()
        commands = [item for item in commands if item.get('name') != name]
        commands.append(command_entry)
        commands.sort(key=lambda item: item.get('name', ''))
        _save_echo_command_config(commands)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        app.logger.exception('Unable to save Echo command configuration')
        return jsonify({'ok': False, 'error': str(exc)}), 500
    return jsonify({'ok': True, 'command': command_entry})


@app.route('/api/echo/commands/<name>', methods=['PUT', 'DELETE'])
@requires_permission('web_ide')
def api_echo_command_item(name):
    if not _echo_operator_account_authorized():
        return jsonify({'ok': False, 'error': 'RBAC admin permission required'}), 403
    if not _echo_operator_request_is_same_origin():
        return jsonify({'ok': False, 'error': 'same-origin request required'}), 403
    try:
        commands = _load_echo_command_config()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        app.logger.exception('Unable to load Echo command configuration')
        return jsonify({'ok': False, 'error': str(exc)}), 500

    existing = next((item for item in commands if item.get('name') == name), None)
    if existing is None:
        return jsonify({'ok': False, 'error': 'command not found'}), 404
    if request.method == 'DELETE':
        commands = [item for item in commands if item.get('name') != name]
    else:
        data = request.get_json(silent=True) or {}
        updated_name = str(data.get('name') or name).strip().lower()
        description = str(data.get('description') or '').strip()
        script = str(data.get('script') or '').strip()
        if not re.fullmatch(r'[a-z][a-z0-9_-]{1,31}', updated_name):
            return jsonify({'ok': False, 'error': 'invalid command name'}), 400
        if updated_name != name and (
            updated_name in _ECHO_RESERVED_COMMAND_NAMES
            or any(item.get('name') == updated_name for item in commands)
        ):
            return jsonify({'ok': False, 'error': 'command name is already in use'}), 409
        if not description or len(description) > 160:
            return jsonify({'ok': False, 'error': 'description is required and must be at most 160 characters'}), 400
        try:
            root = Path(__file__).resolve().parent
            script_path = resolve_project_file(root, script)
        except ValueError as exc:
            return jsonify({'ok': False, 'error': str(exc)}), 400
        if script_path.suffix.lower() not in {'.py', '.ps1', '.sh', '.bash'} or not script_path.is_file():
            return jsonify({'ok': False, 'error': 'script must be an existing supported script inside the project'}), 400
        existing.update({
            'name': updated_name,
            'description': description,
            'script': script_path.relative_to(root).as_posix(),
            'enabled': bool(data.get('enabled', existing.get('enabled', True))),
            'operator_required': True,
        })
        commands.sort(key=lambda item: item.get('name', ''))

    try:
        _save_echo_command_config(commands)
    except OSError as exc:
        app.logger.exception('Unable to update Echo command configuration')
        return jsonify({'ok': False, 'error': str(exc)}), 500
    return jsonify({'ok': True})


@app.route('/api/echo/remote/twilio', methods=['POST'])
def api_echo_remote_twilio():
    if not is_twilio_enabled(
        os.environ.get('ECHO_ENABLE_TWILIO_COMMANDS', ''),
        os.environ.get('ECHO_TWILIO_AUTH_TOKEN', ''),
        os.environ.get('ECHO_TWILIO_WEBHOOK_URL', ''),
        os.environ.get('ECHO_TWILIO_ALLOWED_NUMBERS', ''),
    ):
        return 'Remote SMS commands are disabled.', 404

    auth_token = os.environ.get('ECHO_TWILIO_AUTH_TOKEN')
    webhook_url = os.environ.get('ECHO_TWILIO_WEBHOOK_URL')
    allowed_senders = [
        number.strip()
        for number in os.environ.get('ECHO_TWILIO_ALLOWED_NUMBERS', '').split(',')
        if number.strip()
    ]
    if not auth_token or not webhook_url or not allowed_senders:
        app.logger.error('Twilio command webhook is missing required configuration')
        return 'Remote command webhook is not configured.', 503

    signature = request.headers.get('X-Twilio-Signature', '')
    if not verify_twilio_signature(
        webhook_url,
        request.form.items(multi=True),
        auth_token,
        signature,
    ):
        app.logger.warning('Rejected Twilio command webhook with invalid signature')
        return 'Forbidden', 403

    sender = request.form.get('From', '').strip()
    if not is_allowed_sender(sender, allowed_senders):
        app.logger.warning('Rejected Twilio command from a non-allowlisted sender')
        return 'Forbidden', 403

    message = request.form.get('Body', '').strip()
    if not message:
        reply = 'Send !commands to list Echo remote commands.'
    elif message.startswith('!'):
        reply = _echo_operator_command(message, remote_sender=sender)
        if reply is None:
            bot = get_chat_bot()
            bot_reply = bot.chat(message, session_id='sms_' + hashlib.sha256(sender.encode()).hexdigest()[:16])
            reply = bot_reply.get('response', 'Echo could not process that command.')
    else:
        bot = get_chat_bot()
        bot_reply = bot.chat(message, session_id='sms_' + hashlib.sha256(sender.encode()).hexdigest()[:16])
        reply = bot_reply.get('response', 'Echo could not process that message.')

    from xml.sax.saxutils import escape as xml_escape
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{xml_escape(str(reply)[:1400])}</Message></Response>'
    return twiml, 200, {'Content-Type': 'application/xml; charset=utf-8'}


@app.route('/api/echo/chat',methods=['POST'])

def api_echo_chat():

    try:

        data = request.get_json() or {}

        message = data.get('message','')

        session_id = data.get('session_id','default')

        temperature = float(data.get('temperature', 0.7))

        max_tokens = int(data.get('max_tokens', 1024))

        if not message:

            return jsonify({'error':'Message is required'}), 400

        message_text = str(message).strip()
        if message_text.casefold().startswith('!team'):
            if not _echo_operator_request_is_same_origin() or not _echo_operator_is_active():
                return jsonify({'error': 'Model-team commands require same-origin Echo chat and authenticated RBAC admin operator mode.'}), 403
            parts = message_text.split(maxsplit=2)
            if len(parts) == 3 and parts[1].casefold() == 'approve':
                from addons.echo_model_team.addon import approve_candidate
                if approve_candidate(parts[2]):
                    response_text = f"Candidate {parts[2]} approved for offline fine-tuning."
                else:
                    response_text = "Candidate was not found or has already been approved."
                return jsonify({
                    'response': response_text,
                    'session_id': session_id,
                    'timestamp': time.time(),
                    'message_id': f"bot_{int(time.time()*1000)}",
                })
            if len(parts) < 2 or parts[1].casefold() == 'approve':
                return jsonify({'error': 'Usage: !team <prompt> or !team approve <candidate-id>'}), 400
            prompt = message_text[len(parts[0]):].strip()
            try:
                from addons.echo_model_team.addon import run_team_chat
                team_result = run_team_chat(prompt)
            except Exception as exc:
                app.logger.exception('Echo local model-team turn failed')
                return jsonify({'error': f'Model-team request failed: {exc}'}), 503
            return jsonify({
                'response': (
                    f"{team_result['response']}\n\n"
                    f"Review candidate: `{team_result['candidate_id']}`. "
                    f"Approve it for offline training with `!team approve {team_result['candidate_id']}`."
                ),
                'candidate_id': team_result['candidate_id'],
                'models': team_result['models'],
                'session_id': session_id,
                'timestamp': time.time(),
                'message_id': f"bot_{int(time.time()*1000)}",
            })

        if str(message).strip().startswith('!'):
            operator_response = _echo_operator_command(str(message))
            if operator_response is not None:
                return jsonify({
                    'response': operator_response,
                    'session_id': session_id,
                    'timestamp': time.time(),
                    'message_id': f"bot_{int(time.time()*1000)}",
                })

        session_id = str(session_id or 'default').strip()[:128] or 'default'
        change_command = message_text.casefold()
        if change_command in {'!confirmed', '!cancelchange'}:
            if not _echo_operator_request_is_same_origin() or not _echo_operator_account_authorized():
                return jsonify({
                    'error': 'App changes require the authenticated RBAC admin account from the same-origin Echo Chat page.'
                }), 403
            user_id = str(current_user.get_id())
            try:
                if change_command == '!cancelchange':
                    response_text = _echo_cancel_pending_change(session_id, user_id)
                else:
                    response_text = _echo_apply_pending_change(session_id, user_id)
                return jsonify({
                    'response': response_text,
                    'session_id': session_id,
                    'timestamp': time.time(),
                    'message_id': f"bot_{int(time.time()*1000)}",
                })
            except _EchoApprovalAuditError:
                return jsonify({'error': 'The app change was not applied because its approval could not be audited.'}), 500
            except Exception as exc:
                from managers.echo_change_approvals import EchoChangeError
                if isinstance(exc, EchoChangeError):
                    return jsonify({'error': str(exc)}), 409
                app.logger.exception('Echo app-change approval operation failed')
                return jsonify({'error': 'Echo could not complete the app-change approval operation.'}), 500

        bot = get_chat_bot()
        if bot.should_handle_app_change_message(message_text, session_id):
            if not _echo_operator_request_is_same_origin() or not _echo_operator_account_authorized():
                return jsonify({
                    'error': 'App-change orders require the authenticated RBAC admin account from the same-origin Echo Chat page.'
                }), 403
            try:
                response = bot.chat(
                    message_text,
                    session_id=session_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    workspace_user_id=str(current_user.get_id()),
                    change_manager=_echo_change_approval_manager(),
                )
                return jsonify(response)
            except Exception:
                app.logger.exception('Echo app-change request failed')
                return jsonify({'error': 'Echo could not process the app-change request. No changes were applied.'}), 500

        if bot.should_handle_script_message(message_text, session_id):
            if not _echo_operator_request_is_same_origin():
                return jsonify({'error': 'Local project script references are available only from the MasterChief Echo Chat page.'}), 403
            try:
                response = bot.chat(message_text, session_id=session_id, temperature=temperature, max_tokens=max_tokens)
                return jsonify(response)
            except Exception:
                app.logger.exception('Echo local script request failed')
                return jsonify({'error': 'Echo could not process the local script request.'}), 500

        storage = get_storage()

        try:

            meta = storage.get_session_meta(session_id) or {}

        except Exception:

            meta = {}


        # Ensure a persona is applied for this session if none exists

        try:

            def _ensure_session_personality(sid: str):

                """

                Only auto-apply persona files when explicitly enabled via the

                `ECHO_AUTO_APPLY_PERSONA` environment variable. This prevents

                accidental persona injection that can override LLM behavior.

                """

                # Auto-apply is opt-in to avoid unexpected canned responses

                if os.environ.get('ECHO_AUTO_APPLY_PERSONA') != '1':

                    return

                try:

                    smeta = storage.get_session_meta(sid) or {}

                    if smeta.get('personality'):

                        return

                    # Look for persona files under echo/data/personality

                    pdir = Path(__file__).resolve().parent / 'echo' / 'data' / 'personality'

                    if not pdir.exists():

                        pdir = Path(__file__).resolve().parent / 'data' / 'personality'

                    if pdir.exists():

                        for p in sorted(pdir.glob('*.txt')):

                            try:

                                text = p.read_text(encoding='utf-8')

                                pname = p.name

                                smeta['personality'] = {'id': pname, 'enabled': True, 'name': pname, 'text': text}

                                storage.set_session_meta(sid, smeta)

                                try:

                                    storage.store_message(user='system', message=f'Persona {pname} auto-applied to session', echo_response='', channel=sid)

                                except Exception:

                                    pass

                                break

                            except Exception:

                                # skip files that can't be read

                                continue

                except Exception:

                    app.logger.exception('Failed to ensure session personality')

            _ensure_session_personality(session_id)

            # refresh meta after potential change

            try:

                meta = storage.get_session_meta(session_id) or {}

            except Exception:

                meta = {}

        except Exception:

            app.logger.exception('Auto-apply persona step failed')


        um_low = message.lower()

        # ---- Unified action registry (echo_image, youtube_play, … ) ----
        _action_resp = _echo_action_registry.dispatch(
            message, um_low, storage, session_id, _upsert_session_meta)
        if _action_resp is not None:
            return _action_resp
        # ---- End action registry dispatch ----


        # New topic

        if any(p in um_low for p in ['i want ', 'i need ', 'can you help', 'help me', "let's", 'let us', 'task:', 'project:']):

            topic = message.strip()[:200]

            topic_state = {'topic': topic, 'stage': 'exploration', 'key_points':[message.strip()], 'turns': 1, 'last_alignment': time.time()}

            try:

                meta['topic_state'] = topic_state

                storage.set_session_meta(session_id, meta)

            except Exception:

                pass

            storage.store_message(user='web_user', message=message, echo_response=f"Got it — I'll explore that: {topic}. Can you provide any important details or constraints?", channel=session_id)

            _upsert_session_meta(session_id, title=topic)

            return jsonify({'response': f"Got it — I'll explore that: {topic}. Can you provide any important details or constraints?", 'session_id': session_id, 'timestamp': time.time(), 'message_id': f"bot_{int(time.time()*1000)}"})


        # Refinement

        if any(p in um_low for p in ['also', 'add', 'update', 'refine', 'change', 'instead', 'correction', 'fix', 'detail', 'more']):

            topic_state = meta.get('topic_state') or {}

            if topic_state and topic_state.get('stage') in ('exploration','refinement'):

                kp = topic_state.get('key_points', [])

                kp.append(message.strip())

                topic_state['key_points'] = kp

                topic_state['stage'] = 'refinement'

                topic_state['turns'] = topic_state.get('turns',0) + 1

                try:

                    meta['topic_state'] = topic_state

                    storage.set_session_meta(session_id, meta)

                except Exception:

                    pass

                storage.store_message(user='web_user', message=message, echo_response="Thanks — I've updated the plan with that detail. Anything else to refine?", channel=session_id)

                _upsert_session_meta(session_id)

                return jsonify({'response': "Thanks — I've updated the plan with that detail. Anything else to refine?", 'session_id': session_id, 'timestamp': time.time(), 'message_id': f"bot_{int(time.time()*1000)}"})


        # Validation

        if any(p in um_low for p in ['is this okay', 'does this work', 'is this correct', 'confirm', 'validate', 'looks good', 'agree', 'ok to proceed']):

            topic_state = meta.get('topic_state') or {}

            if topic_state and topic_state.get('key_points'):

                summary = ' ; '.join([kp if isinstance(kp,str) else str(kp) for kp in topic_state.get('key_points', [])])

                topic_state['stage'] = 'validation'

                topic_state['last_alignment'] = time.time()

                try:

                    meta['topic_state'] = topic_state

                    storage.set_session_meta(session_id, meta)

                except Exception:

                    pass

                resp_text = f"Here's what I have so far: {summary}. Shall I proceed or would you like to refine further?"

                storage.store_message(user='web_user', message=message, echo_response=resp_text, channel=session_id)

                _upsert_session_meta(session_id)

                return jsonify({'response': resp_text, 'session_id': session_id, 'timestamp': time.time(), 'message_id': f"bot_{int(time.time()*1000)}"})


        # Completion

        if any(p in um_low for p in ["done","finished","complete","that's all",'thats all',"that's it","that's it, thanks",'thank you','thanks']):

            topic_state = meta.get('topic_state') or {}

            if topic_state and topic_state.get('key_points'):

                summary = ' ; '.join([kp if isinstance(kp,str) else str(kp) for kp in topic_state.get('key_points', [])])

                topic_state['stage'] = 'complete'

                topic_state['completed_at'] = time.time()

                try:

                    meta['topic_state'] = topic_state

                    storage.set_session_meta(session_id, meta)

                except Exception:

                    pass

                resp_text = f"Done — summary: {summary}. If you'd like to start something new, tell me and we'll begin a new topic."

                storage.store_message(user='web_user', message=message, echo_response=resp_text, channel=session_id)

                _upsert_session_meta(session_id)

                return jsonify({'response': resp_text, 'session_id': session_id, 'timestamp': time.time(), 'message_id': f"bot_{int(time.time()*1000)}"})


        # Fallback to bot

        bot = get_chat_bot()

        # Persona injection is handled in chat_bot.py

        message_for_bot = message

        response = bot.chat(message_for_bot, session_id=session_id, temperature=temperature, max_tokens=max_tokens)

        # Sanitize obviously-garbled responses (long repeated characters, repeated "A: A: A:" patterns, etc.)

        def _is_garbled_text(t: str) -> bool:

            # Return True if text looks like garbage; include reasons for logging.

            if not t or not isinstance(t, str):

                return False

            # ignore short replies

            if len(t) < 20:

                return False

            # don't sanitize code blocks or JSON-like outputs

            if '```' in t or t.strip().startswith('{') or t.strip().startswith('['):

                return False

            # remove whitespace for some checks

            no_ws = ''.join(t.split())

            if not no_ws:

                return False

            reasons = []

            ctr = Counter(ch for ch in no_ws)

            most_char, most_count = ctr.most_common(1)[0]

            # very high concentration on a single non-alphanumeric char

            if most_count / max(1, len(no_ws)) > 0.75 and most_count > 30:

                if not most_char.isalnum():

                    reasons.append('high_non_alnum_concentration')

            # very long single-char runs (likely repeated garbage)

            max_run = 1

            cur = 1

            for i in range(1, len(no_ws)):

                if no_ws[i] == no_ws[i-1]:

                    cur += 1

                    if cur > max_run:

                        max_run = cur

                else:

                    cur = 1

            if max_run >= 40:

                reasons.append('long_run')

            # repeated labelled pattern like "A: A: A: A:" many times

            if re.search(r'(?:[A-Za-z]:\s*){10,}', t):

                reasons.append('repeated_label_pattern')

            # if we detected at least two independent signals, mark garbled

            if len(reasons) >= 2:

                # store reasons on function object for logging

                _is_garbled_text._last_reasons = reasons

                return True

            # otherwise not garbled

            return False


        # apply sanitizer and preserve original for debugging when possible

        try:

            orig_text = response.get('response') if isinstance(response, dict) else str(response)

            if _is_garbled_text(orig_text):

                reasons = getattr(_is_garbled_text, '_last_reasons', None)

                app.logger.warning('Sanitized garbled response for session %s, reasons=%s', session_id, reasons)

                # persist a debug record to disk for later analysis

                try:

                    dbg_dir = os.path.join(os.getcwd(), 'data')

                    os.makedirs(dbg_dir, exist_ok=True)

                    logfile = os.path.join(dbg_dir, 'echo_sanitizer_logs.jsonl')

                    entry = {'ts': time.time(), 'session_id': session_id, 'reasons': reasons, 'original': orig_text}

                    try:

                        with open(logfile, 'a', encoding='utf-8') as fh:

                            fh.write(json.dumps(entry, ensure_ascii=False) + '\n')

                    except Exception:

                        app.logger.exception('Failed to write sanitizer log')

                except Exception:

                    pass

                fallback = "I'm sorry — I couldn't generate a proper reply. Could you rephrase?"

                if isinstance(response, dict):

                    response['_original_response'] = orig_text

                    response['response'] = fallback

                else:

                    response = {'response': fallback, '_original_response': orig_text}

        except Exception:

            # never let sanitizer crash the endpoint

            app.logger.exception('Response sanitizer failed')

        # if client requested debug, include LLM debug output if available

        try:

            if data.get('debug'):

                debug_info = getattr(bot, '_last_llm_debug', None)

                if isinstance(response, dict):

                    response['_llm_debug'] = debug_info

                else:

                    response = {'response': str(response), '_llm_debug': debug_info}

        except Exception:

            pass

        # --- New: support saving long responses to a txt file and auto-continue when truncated ---

        # full_text holds the authoritative reply text we persist and/or save

        full_text = response.get('response') if isinstance(response, dict) else str(response)

        # Request flags: save_to_file (bool) and auto_continue (bool). If auto_continue is omitted, fall back to app config.

        save_to_file = _parse_bool_val(data.get('save_to_file'), default=False)

        auto_continue = _parse_bool_val(data.get('auto_continue'), default=bool(app.config.get('ECHO_AUTO_CONTINUE', False)))


        def _looks_truncated(t: str) -> bool:

            if not t or len(t) < 200:

                return False

            ts = t.rstrip()

            if ts.endswith('...'):

                return True

            # if it doesn't end in typical sentence terminator, assume it may be cut off

            if ts[-1] not in '.?!':

                return True

            return False


            # If requested (or configured) attempt to auto-continue when the reply looks cut off,

            # but guard against off-topic or rambling continuations by checking similarity

            # between the continuation and the user's original message.

            if auto_continue:

                max_retries = int(app.config.get('ECHO_CONTINUE_MAX_RETRIES', 1))

                min_sim = float(app.config.get('ECHO_CONTINUE_MIN_SIMILARITY', 0.12))

                retries = 0

                def _should_accept_continuation(prev_text: str, cont_text: str, user_msg: str) -> bool:

                    try:

                        if not cont_text or not isinstance(cont_text, str):

                            return False

                        # very short continuations are not useful

                        if len(cont_text.strip()) < 30:

                            return False

                        # similarity between user message and continuation (simple heuristic)

                        sim = difflib.SequenceMatcher(None, (user_msg or '').lower(), cont_text.lower()).ratio()

                        # token overlap on longer words

                        import re

                        user_words = set(w for w in re.findall(r"\w{4,}", (user_msg or '').lower()))

                        cont_words = set(w for w in re.findall(r"\w{4,}", cont_text.lower()))

                        overlap = 0.0

                        if user_words:

                            overlap = len(user_words & cont_words) / max(1, len(user_words))

                        # reject if continuation appears extremely similar to previous text (repeat) or clearly off-topic

                        if cont_text.strip() in (prev_text or ''):

                            return False

                        # accept only when similarity or overlap meets thresholds

                        if sim >= min_sim or overlap >= 0.05:

                            return True

                        return False

                    except Exception:

                        return False


                while retries < max_retries and _looks_truncated(full_text):

                    try:

                        cont_prompt = app.config.get('ECHO_CONTINUE_PROMPT', 'Please continue the previous response.')

                        cont_resp = bot.chat(cont_prompt, session_id=session_id)

                        cont_text = cont_resp.get('response') if isinstance(cont_resp, dict) else str(cont_resp)

                        if not cont_text:

                            break

                        # decide whether to accept this continuation

                        if not _should_accept_continuation(full_text, cont_text, message):

                            # mark on the response that continuation was halted due to divergence

                            if isinstance(response, dict):

                                response['continued_halted_due_to_divergence'] = True

                            else:

                                response = {'response': full_text, 'continued_halted_due_to_divergence': True}

                            break

                        # append accepted continuation

                        full_text = full_text + "\n" + cont_text

                        if isinstance(response, dict):

                            response['response'] = full_text

                            response['continued_count'] = response.get('continued_count', 0) + 1

                        else:

                            response = {'response': full_text, 'continued_count': 1}

                    except Exception:

                        app.logger.exception('Auto-continue failed')

                        break

                    retries += 1


        # Optionally save the full response to a file so very long replies are available un-truncated

        if save_to_file:

            try:

                outdir = Path(__file__).parent / 'data' / 'echo_chat_outputs'

                outdir.mkdir(parents=True, exist_ok=True)

                fname = f"{session_id}_{int(time.time()*1000)}_{uuid.uuid4().hex}.txt"

                fpath = outdir / fname

                fpath.write_text(full_text, encoding='utf-8')

                rel = str(fpath.relative_to(Path(__file__).parent))

                if isinstance(response, dict):

                    response['saved_to'] = rel

                else:

                    response = {'response': full_text, 'saved_to': rel}

            except Exception:

                app.logger.exception('Failed to save echo response to file')


        # persist session metadata so it appears in chat history list

        try:

            _upsert_session_meta(session_id)

        except Exception:

            pass

        storage = get_storage()

        storage.store_message(user='web_user', message=message, echo_response=full_text, channel=session_id)

        return jsonify(response)

    except Exception as e:

        return jsonify({'error':str(e)}),500


@app.route('/api/echo/outputs')

def api_echo_outputs():

    """List saved full echo-chat outputs."""

    try:

        outdir = Path(__file__).parent / 'data' / 'echo_chat_outputs'

        files = []

        if outdir.exists():

            for p in sorted(outdir.glob('*.txt')):

                try:

                    files.append({'name': p.name, 'size': p.stat().st_size, 'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat(), 'path': str(p.relative_to(Path(__file__).parent))})

                except Exception:

                    files.append({'name': p.name})

        return jsonify({'files': files})

    except Exception as e:

        app.logger.exception('List echo outputs failed')

        return jsonify({'error': str(e)}), 500


@app.route('/data/echo_chat_outputs/<path:fname>')

def serve_echo_output(fname):

    """Serve/download a saved echo-chat output file."""

    try:

        outdir = Path(__file__).parent / 'data' / 'echo_chat_outputs'

        fpath = (outdir / fname).resolve()

        if not str(fpath).startswith(str(outdir.resolve())):

            return 'invalid path', 400

        if not fpath.exists():

            return 'not found', 404

        return send_file(str(fpath), as_attachment=True)

    except Exception as e:

        app.logger.exception('Failed to serve echo output')

        return jsonify({'error': str(e)}), 500

@app.route('/api/echo/outputs/delete', methods=['POST'])

def api_echo_outputs_delete():

    try:

        data = request.get_json() or {}

        name = data.get('name')

        if not name:

            return jsonify({'error': 'name required'}), 400

        outdir = Path(__file__).parent / 'data' / 'echo_chat_outputs'

        fpath = (outdir / name).resolve()

        if not str(fpath).startswith(str(outdir.resolve())):

            return jsonify({'error': 'invalid path'}), 400

        if not fpath.exists():

            return jsonify({'error': 'not found'}), 404

        try:

            fpath.unlink()

        except Exception:

            app.logger.exception('Failed to delete echo output %s', fpath)

            return jsonify({'error': 'delete failed'}), 500

        return jsonify({'ok': True})

    except Exception as e:

        app.logger.exception('Delete echo output failed')

        return jsonify({'error': str(e)}), 500

# ---- Voice Commands API ----
_VOICE_COMMANDS_FILE = Path(__file__).parent / 'data' / 'voice_commands.json'
_VOICE_COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load_voice_commands():
    try:
        if _VOICE_COMMANDS_FILE.exists():
            return json.loads(_VOICE_COMMANDS_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass
    # built-in defaults
    return [
        {'id': 'vc_clear',    'phrase': 'clear chat',       'action': 'clear_chat',   'label': 'Clear Chat'},
        {'id': 'vc_image',    'phrase': 'show your face',   'action': 'echo_image',   'label': 'Show Echo Image'},
        {'id': 'vc_status',   'phrase': 'system status',    'action': 'send_message', 'param': 'What is the system status?', 'label': 'System Status'},
        {'id': 'vc_help',     'phrase': 'help',             'action': 'send_message', 'param': 'What can you help me with?', 'label': 'Help'},
        {'id': 'vc_deploy',   'phrase': 'deploy status',    'action': 'send_message', 'param': 'Show me the current deployment status.', 'label': 'Deploy Status'},
    ]

def _save_voice_commands(cmds):
    _VOICE_COMMANDS_FILE.write_text(json.dumps(cmds, indent=2), encoding='utf-8')

@app.route('/api/echo/voice_commands', methods=['GET'])
def api_voice_commands_get():
    return jsonify({'commands': _load_voice_commands()})

@app.route('/api/echo/voice_commands', methods=['POST'])
def api_voice_commands_post():
    try:
        data = request.get_json() or {}
        phrase = (data.get('phrase') or '').strip().lower()
        action = (data.get('action') or 'send_message').strip()
        param  = (data.get('param')  or '').strip()
        label  = (data.get('label')  or phrase).strip()
        if not phrase:
            return jsonify({'error': 'phrase required'}), 400
        cmds = _load_voice_commands()
        new_id = 'vc_' + uuid.uuid4().hex[:8]
        cmds.append({'id': new_id, 'phrase': phrase, 'action': action, 'param': param, 'label': label})
        _save_voice_commands(cmds)
        return jsonify({'ok': True, 'id': new_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/echo/voice_commands/<cmd_id>', methods=['DELETE'])
def api_voice_commands_delete(cmd_id):
    try:
        cmds = [c for c in _load_voice_commands() if c.get('id') != cmd_id]
        _save_voice_commands(cmds)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/echo/voice_commands/<cmd_id>', methods=['PUT'])
def api_voice_commands_update(cmd_id):
    try:
        data = request.get_json() or {}
        cmds = _load_voice_commands()
        for c in cmds:
            if c.get('id') == cmd_id:
                if 'phrase' in data: c['phrase'] = data['phrase'].strip().lower()
                if 'action' in data: c['action'] = data['action'].strip()
                if 'param'  in data: c['param']  = data['param'].strip()
                if 'label'  in data: c['label']  = data['label'].strip()
                break
        _save_voice_commands(cmds)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ---- End Voice Commands API ----

@app.route('/api/echo/youtube_search', methods=['GET'])
def api_echo_youtube_search():
    """Resolve a search query to a real YouTube video ID."""
    import requests as _req, re as _re2
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'error': 'no query'}), 400

    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    # --- Method 1: Scrape YouTube search results page ---
    try:
        url = 'https://www.youtube.com/results?search_query=' + _req.utils.quote(q) + '&sp=EgIQAQ%3D%3D'
        r = _req.get(url, headers=_headers, timeout=6)
        if r.status_code == 200:
            # Extract first videoId from ytInitialData JSON
            m = _re2.search(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)
            if m:
                vid = m.group(1)
                # Try to extract title
                tm = _re2.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', r.text)
                title = tm.group(1) if tm else q
                return jsonify({'videoId': vid, 'title': title, 'source': 'youtube'})
    except Exception:
        pass

    # --- Method 2: Piped public API ---
    _PIPED = [
        'https://pipedapi.kavin.rocks',
        'https://pipedapi.adminforge.de',
        'https://piped-api.garudalinux.org',
    ]
    for base in _PIPED:
        try:
            r = _req.get(f'{base}/search?q={_req.utils.quote(q)}&filter=videos',
                         headers=_headers, timeout=4)
            if r.status_code == 200:
                for item in (r.json().get('items') or []):
                    vid = item.get('url', '')
                    vid = vid.replace('/watch?v=', '').replace('https://www.youtube.com/watch?v=', '')
                    if vid and len(vid) == 11:
                        return jsonify({'videoId': vid, 'title': item.get('title', q), 'source': base})
        except Exception:
            continue

    # --- Fallback: Lofi Girl 24/7 ---
    return jsonify({'videoId': 'jfKfPfyJRdk', 'title': 'Lofi Hip Hop Radio \u2014 Beats to Relax/Study To', 'source': 'fallback'})

@app.route('/api/echo/action_handlers', methods=['GET'])
def api_echo_action_handlers():
    """Return metadata for all registered server-side action handlers."""
    return jsonify({'handlers': _echo_action_registry.list_handlers()})

@app.route('/api/echo/session_prefs', methods=['GET','POST'])

def api_echo_session_prefs():

    try:

        storage = get_storage()

        if request.method == 'GET':

            session_id = request.args.get('session_id') or 'default'

            meta = storage.get_session_meta(session_id) or {}

            prefs = meta.get('echo_prefs') or {}

            # ensure sensible defaults

            prefs.setdefault('auto_continue', bool(app.config.get('ECHO_AUTO_CONTINUE', False)))

            prefs.setdefault('save_to_file', False)

            prefs.setdefault('lang', 'en')

            return jsonify({'prefs': prefs})

        else:

            data = request.get_json() or {}

            session_id = data.get('session_id') or 'default'

            prefs = data.get('prefs') or {}

            meta = storage.get_session_meta(session_id) or {}

            meta['echo_prefs'] = meta.get('echo_prefs', {})

            # merge only known keys

            if 'auto_continue' in prefs:

                meta['echo_prefs']['auto_continue'] = bool(prefs.get('auto_continue'))

            if 'save_to_file' in prefs:

                meta['echo_prefs']['save_to_file'] = bool(prefs.get('save_to_file'))

            if 'lang' in prefs:

                meta['echo_prefs']['lang'] = str(prefs.get('lang'))

            storage.set_session_meta(session_id, meta)

            return jsonify({'ok': True, 'prefs': meta['echo_prefs']})

    except Exception as e:

        app.logger.exception('Session prefs failed')

        return jsonify({'error': str(e)}), 500

@app.route('/api/echo/train',methods=['POST'])

def api_echo_train():

    try:

        data=request.get_json()

        user_message=data.get('user_message','')

        bot_response=data.get('bot_response','')

        quality_str=data.get('quality','acceptable')

        quality_map={

            'excellent':ResponseQuality.EXCELLENT,

            'good':ResponseQuality.GOOD,

            'acceptable':ResponseQuality.ACCEPTABLE,

            'poor':ResponseQuality.POOR

        }

        quality=quality_map.get(quality_str,ResponseQuality.ACCEPTABLE)

        bot=get_chat_bot()

        success=bot.train(user_message,bot_response,quality)

        return jsonify({'success':success})

    except Exception as e:

        return jsonify({'error':str(e),'success':False}),500

@app.route('/api/echo/stats')

def api_echo_stats():

    try:

        bot=get_chat_bot()

        stats=bot.get_training_stats()

        return jsonify(stats)

    except Exception as e:

        return jsonify({'error':str(e)}),500

@app.route('/api/echo/history')

def api_echo_history():

    try:

        session_id=request.args.get('session_id','default')

        limit=int(request.args.get('limit',50))

        storage=get_storage()

        # Retrieve persisted conversation history for the session

        history = storage.get_conversation_history(user='web_user', limit=limit, channel=session_id)

        return jsonify({'history':history})

    except Exception as e:

        return jsonify({'error':str(e)}),500


@app.route('/api/echo/model', methods=['GET'])
def api_echo_model():
    try:
        bot = get_chat_bot()
        model = getattr(bot, '_local_model_path', None)
        if model:
            return jsonify({'model': model})
        else:
            return jsonify({'model': None})
    except Exception as e:
        app.logger.exception('Get model failed')
        return jsonify({'error': str(e)}), 500

@app.route('/api/echo/preload_model', methods=['POST','GET'])

def api_echo_preload_model():

    """Discover local model and attempt a small generation to warm the worker.

    Returns JSON with model path and whether the warm-up succeeded.

    """

    try:

        bot = get_chat_bot()

        model = None

        warmed = False


        # Prefer an explicitly selected model stored by `/api/echo/select_model`.

        try:

            cfg = Path(__file__).parent / 'data' / 'echo_model.json'

            if cfg.exists():

                try:

                    cfgd = json.loads(cfg.read_text(encoding='utf-8'))

                    if cfgd.get('model'):

                        model = cfgd.get('model')

                except Exception:

                    model = None

        except Exception:

            model = None


        # Fall back to discovery if no explicit selection

        if not model and hasattr(bot, '_find_local_model'):

            try:

                model = bot._find_local_model()

            except Exception:

                model = None


        # Allow caller to request no warm (useful for large models)

        payload = request.get_json(silent=True) or {}

        do_warm = payload.get('warm', True)


        if model and do_warm:

            if hasattr(bot, '_generate_with_local_llm'):

                try:

                    out = bot._generate_with_local_llm('Hello, warmup', max_tokens=8, temperature=0.1)

                    warmed = bool(out)

                except Exception as e:

                    app.logger.exception('Preload generation failed')

                    return jsonify({'model': model, 'warmed': False, 'error': str(e)}), 500


        return jsonify({'model': model, 'warmed': warmed})

    except Exception as e:

        app.logger.exception('Preload endpoint failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/generate_image', methods=['POST'])

def api_echo_generate_image():

    """Generate an image from a prompt using a local CPU-only diffusers pipeline if available.


    This endpoint is intentionally local-first: it will attempt to import `diffusers`

    and run on CPU. If `diffusers` is not installed the endpoint returns 501 with

    an installation hint. The endpoint includes a small in-memory cache and a per-session

    simple rate limit.

    """

    try:

        payload = request.get_json() or {}

        prompt = payload.get('prompt') or payload.get('message')

        session_id = payload.get('session_id') or request.remote_addr or 'anon'

        size = payload.get('size') or '512x512'

        style = payload.get('style') or ''

        if not prompt:

            return jsonify({'error': 'prompt required'}), 400


        # Rate limiting (simple sliding window per session/ip)

        now_ts = time.time()

        rl_key = str(session_id)

        window = 60

        timestamps = IMAGE_RATE.get(rl_key, [])

        timestamps = [t for t in timestamps if now_ts - t < window]

        if len(timestamps) >= app.config.get('IMAGE_RATE_LIMIT_PER_MIN', 6):

            return jsonify({'error': 'rate limit exceeded'}), 429

        timestamps.append(now_ts)

        IMAGE_RATE[rl_key] = timestamps


        # Cache key

        cache_key = f"{prompt}||{size}||{style}"

        cached = IMAGE_CACHE.get(cache_key)

        if cached and (now_ts - cached.get('ts', 0) < app.config.get('IMAGE_CACHE_TTL', 86400)):

            return jsonify({'ok': True, 'url': '/' + cached['path']})


        outdir = Path(__file__).parent / 'data' / 'echo_images'

        outdir.mkdir(parents=True, exist_ok=True)


        provider = app.config.get('IMAGE_PROVIDER', 'local')

        if provider != 'local':

            return jsonify({'error': 'Only local CPU generation is enabled in this demo. Set IMAGE_PROVIDER=local.'}), 501


        # Attempt local generation with diffusers on CPU

        try:

            import torch

            from diffusers import StableDiffusionPipeline

        except Exception as e:

            return jsonify({'error': 'diffusers or torch not installed (pip install diffusers[torch] transformers)'}), 501


        try:

            model_id = os.environ.get('IMAGE_LOCAL_MODEL', 'runwayml/stable-diffusion-v1-5')

            # Load the pipeline directly onto CPU to avoid moving 'meta' tensors between devices,

            # which can raise NotImplementedError for some HF transformer configs.

            try:

                pipe = StableDiffusionPipeline.from_pretrained(model_id, device_map='cpu')

            except Exception:

                # Fallback when device_map isn't accepted: load normally and rely on CPU placement.

                pipe = StableDiffusionPipeline.from_pretrained(model_id)


            # parse size

            width, height = (512, 512)

            try:

                parts = size.split('x')

                if len(parts) == 2:

                    width = int(parts[0])

                    height = int(parts[1])

            except Exception:

                pass


            # generate

            image = pipe(prompt, height=height, width=width, num_inference_steps=20).images[0]

            fname = f"img_{int(time.time()*1000)}_{uuid.uuid4().hex}.png"

            fpath = outdir / fname

            image.save(str(fpath))

            rel = fpath.relative_to(Path(__file__).parent).as_posix()

            IMAGE_CACHE[cache_key] = {'path': rel, 'ts': time.time()}

            return jsonify({'ok': True, 'url': '/' + rel})

        except Exception as e:

            app.logger.exception('Local image generation failed')

            return jsonify({'error': f'local generation failed: {e}'}), 500


    except Exception as e:

        app.logger.exception('Generate image failed')

        return jsonify({'error': str(e)}), 500


@app.route('/data/echo_images/<path:fname>')

def serve_echo_image(fname):

    try:

        outdir = Path(__file__).parent / 'data' / 'echo_images'

        fpath = (outdir / fname).resolve()

        if not str(fpath).startswith(str(outdir.resolve())):

            return 'invalid path', 400

        if not fpath.exists():

            return 'not found', 404

        return send_file(str(fpath), as_attachment=False)

    except Exception as e:

        app.logger.exception('Failed to serve echo image')

        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/generate_image_async', methods=['POST'])
def api_echo_generate_image_async():
    """Enqueue an image generation job by writing a job file for the worker."""
    try:
        payload = request.get_json() or {}
        prompt = payload.get('prompt') or payload.get('message')
        session_id = payload.get('session_id') or request.remote_addr or 'anon'
        size = payload.get('size') or '512x512'
        style = payload.get('style') or ''
        if not prompt:
            return jsonify({'error': 'prompt required'}), 400

        # simple rate limiting per session/ip
        now_ts = time.time()
        rl_key = str(session_id)
        window = 60
        timestamps = IMAGE_RATE.get(rl_key, [])
        timestamps = [t for t in timestamps if now_ts - t < window]
        if len(timestamps) >= app.config.get('IMAGE_RATE_LIMIT_PER_MIN', 6):
            return jsonify({'error': 'rate limit exceeded'}), 429
        timestamps.append(now_ts)
        IMAGE_RATE[rl_key] = timestamps

        cache_key = f"{prompt}||{size}||{style}"
        cached = IMAGE_CACHE.get(cache_key)
        if cached and (now_ts - cached.get('ts', 0) < app.config.get('IMAGE_CACHE_TTL', 86400)):
            return jsonify({'ok': True, 'url': '/' + cached['path']})

        job_id = uuid.uuid4().hex
        job = {'id': job_id, 'prompt': prompt, 'size': size, 'style': style, 'status': 'queued', 'progress': 0, 'path': None, 'error': None, 'created': now_ts}
        IMAGE_JOBS[job_id] = job

        # persist job to disk for external worker to pick up
        jobs_dir = Path(__file__).parent / 'data' / 'image_jobs'
        jobs_dir.mkdir(parents=True, exist_ok=True)
        job_path = jobs_dir / (job_id + '.json')
        tmp_path = jobs_dir / (job_id + '.json.tmp')
        tmp_path.write_text(json.dumps(job), encoding='utf-8')
        try:
            tmp_path.replace(job_path)
        except Exception:
            # best-effort rename
            job_path.write_text(json.dumps(job), encoding='utf-8')

        # Spawn an in-process background thread to process the job immediately.
        # This avoids requiring a separately-running image_worker process.
        def _run_image_job(jpath):
            try:
                import importlib.util, sys
                worker_path = str(Path(__file__).parent / 'image_worker.py')
                spec = importlib.util.spec_from_file_location('image_worker', worker_path)
                iw = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(iw)
                iw.process_job(jpath)
                # sync result back into in-memory IMAGE_JOBS if done
                try:
                    updated = json.loads(jpath.read_text(encoding='utf-8'))
                    IMAGE_JOBS[updated.get('id', '')] = updated
                    if updated.get('path') and updated.get('status') == 'done':
                        ck = f"{updated.get('prompt','')}||{updated.get('size','')}||{updated.get('style','')}"
                        IMAGE_CACHE[ck] = {'path': updated['path'], 'ts': time.time()}
                except Exception:
                    pass
            except Exception as _te:
                app.logger.exception('Image job thread error: %s', _te)
        import threading
        threading.Thread(target=_run_image_job, args=(job_path,), daemon=True).start()

        return jsonify({'ok': True, 'job_id': job_id})
    except Exception as e:
        app.logger.exception('Enqueue image job failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/image_status')
def api_echo_image_status():
    job_id = request.args.get('job_id')
    if not job_id:
        return jsonify({'error': 'job_id required'}), 400
    # prefer in-memory store but fall back to disk-based job file
    job = IMAGE_JOBS.get(job_id)
    jobs_dir = Path(__file__).parent / 'data' / 'image_jobs'
    job_file = jobs_dir / (job_id + '.json')
    if job_file.exists():
        try:
            job = json.loads(job_file.read_text(encoding='utf-8'))
        except Exception:
            pass
    if not job:
        return jsonify({'error': 'not found'}), 404
    res = dict(job)
    if job.get('path'):
        res['url'] = '/' + job['path']
    return jsonify(res)


@app.route('/api/gguf/models')
def api_gguf_models():
    try:
        models_dir = Path(__file__).parent / 'models'
        models = []
        if models_dir.exists():
            for f in models_dir.glob('*.gguf'):
                models.append(str(f.relative_to(Path(__file__).parent)))
        bot = get_chat_bot()
        current = None
        if hasattr(bot, '_model_path') and bot._model_path:
            current = str(Path(bot._model_path).relative_to(Path(__file__).parent)) if Path(bot._model_path).is_relative_to(Path(__file__).parent) else bot._model_path
        return jsonify({'models': models, 'current': current})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/gguf/select', methods=['POST'])
def api_gguf_select():
    try:
        data = request.get_json() or {}
        model = data.get('model', '')
        bot = get_chat_bot()
        if model:
            success = bot.reload_model(model_name=model)
            current = str(Path(bot._model_path).relative_to(Path(__file__).parent)) if Path(bot._model_path).is_relative_to(Path(__file__).parent) else bot._model_path
            return jsonify({'success': success, 'current': current})
        else:
            # clear model
            bot._model_path = None
            return jsonify({'success': True, 'current': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/debug_image_provider')

def api_echo_debug_image_provider():

    """Return current image provider config and whether local libs are importable."""

    try:

        import importlib.util

        has_torch = importlib.util.find_spec('torch') is not None

        has_diffusers = importlib.util.find_spec('diffusers') is not None

    except Exception:

        has_torch = False

        has_diffusers = False

    return jsonify({'IMAGE_PROVIDER': app.config.get('IMAGE_PROVIDER'), 'torch_installed': bool(has_torch), 'diffusers_installed': bool(has_diffusers)})


@app.route('/api/echo/training_files')

def api_echo_training_files():

    try:

        base = Path(__file__).parent / 'data' / 'echo_training'

        files = []

        if base.exists():

            for p in sorted(base.glob('*')):

                if p.is_file():

                    files.append({'name': p.name, 'size': p.stat().st_size, 'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat()})

        return jsonify({'files': files})

    except Exception as e:

        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/train_model', methods=['POST'])

def api_echo_train_model():

    """Start a training job (runs tools/finetune_stub.py by default).


    Payload: JSON { model: 'models/..gguf', training_file: 'filename.jsonl', output_name: 'myrun', epochs: 1, batch_size: 8, lr: 1e-4 }

    """

    try:

        data = request.get_json() or {}

        model = data.get('model')

        training_file = data.get('training_file')

        resource_id = data.get('resource_id')

        output_name = data.get('output_name') or f"run_{int(time.time())}"

        epochs = int(data.get('epochs', 1))

        batch_size = int(data.get('batch_size', 8))

        lr = float(data.get('lr', 1e-4))


        engine = data.get('engine', 'stub')

        # validate basics

        if not model or (not training_file and not resource_id):

            return jsonify({'error': 'model and either training_file or resource_id are required'}), 400


        model_path = Path(model)

        if not model_path.is_absolute():

            model_path = Path.cwd() / model_path

        if not model_path.exists():

            return jsonify({'error': 'model not found'}), 404


        if resource_id:

            # convert resource to training file

            idx = _load_resources_index()

            entry = idx.get(resource_id)

            if not entry:

                return jsonify({'error': 'resource not found'}), 404

            p = Path(entry.get('path'))

            if not p.exists():

                return jsonify({'error': 'resource file not found'}), 404

            # use the convert logic

            from tools.dataset_helper import convert_file_to_jsonl

            tfile = Path(__file__).parent / 'data' / 'echo_training' / f"{resource_id}.jsonl"

            try:

                convert_file_to_jsonl(str(p), str(tfile))

            except Exception as e:

                return jsonify({'error': f'conversion failed: {e}'}), 500

        else:

            tfile = Path(__file__).parent / 'data' / 'echo_training' / training_file

            if not tfile.exists():

                return jsonify({'error': 'training file not found'}), 404


        job_id = uuid.uuid4().hex

        outdir = Path(__file__).parent / 'data' / 'models_output' / job_id

        outdir.mkdir(parents=True, exist_ok=True)


        # select worker based on engine

        if engine == 'stub':

            worker = Path(__file__).parent / 'tools' / 'finetune_stub.py'

            cmd = [sys.executable, str(worker), '--model', str(model_path), '--data', str(tfile), '--output', str(outdir), '--epochs', str(epochs), '--batch_size', str(batch_size), '--lr', str(lr)]

        elif engine == 'peft':

            # prefer a real PEFT/LoRA pipeline; check for dependencies

            try:

                import transformers  # type: ignore

                import peft  # type: ignore

            except Exception:

                return jsonify({'error': 'PEFT/transformers not installed', 'install': 'pip install "transformers[sentencepiece]" accelerate peft bitsandbytes --upgrade'}), 400

            # If you later add a real training script, point to it here.

            worker = Path(__file__).parent / 'tools' / 'finetune_stub.py'

            cmd = [sys.executable, str(worker), '--model', str(model_path), '--data', str(tfile), '--output', str(outdir), '--epochs', str(epochs), '--batch_size', str(batch_size), '--lr', str(lr)]

        else:

            return jsonify({'error': 'unknown engine', 'allowed': ['stub','peft']}), 400


        TRAIN_JOBS[job_id] = {'id': job_id, 'status': 'queued', 'model': str(model_path), 'training_file': str(tfile), 'output': str(outdir), 'engine': engine, 'pid': None, 'returncode': None, 'started_at': None, 'finished_at': None}

        _save_train_jobs()

        _start_train_job(job_id, cmd, cwd=str(Path(__file__).parent))


        return jsonify({'ok': True, 'job_id': job_id})

    except Exception as e:

        app.logger.exception('Start train failed')

        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/train_status')

def api_echo_train_status():

    job_id = request.args.get('job_id')

    if not job_id:

        return jsonify({'error': 'job_id required'}), 400

    job = TRAIN_JOBS.get(job_id)

    if not job:

        return jsonify({'error': 'job not found'}), 404

    outdir = Path(__file__).parent / 'data' / 'models_output' / job_id

    log_path = outdir / 'train.log'

    log_tail = ''

    if log_path.exists():

        try:

            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:

                data = f.read()

                log_tail = data[-8192:]

        except Exception:

            log_tail = ''

    return jsonify({'job': job, 'log_tail': log_tail})


@app.route('/api/echo/train_list')

def api_echo_train_list():

    try:

        return jsonify({'jobs': list(TRAIN_JOBS.values())})

    except Exception as e:

        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/train_cancel', methods=['POST'])

def api_echo_train_cancel():

    try:

        data = request.get_json() or {}

        job_id = data.get('job_id')

        if not job_id:

            return jsonify({'error': 'job_id required'}), 400

        job = TRAIN_JOBS.get(job_id)

        if not job:

            return jsonify({'error': 'job not found'}), 404

        pid = job.get('pid')

        if not pid:

            job['status'] = 'cancelled'

            job['finished_at'] = time.time()

            return jsonify({'ok': True, 'message': 'job marked cancelled (no pid)'} )

        try:

            p = psutil.Process(int(pid))

            p.terminate()

            time.sleep(1)

            if p.is_running():

                p.kill()

        except Exception:

            # process may have already exited

            pass

        job['status'] = 'cancelled'

        job['finished_at'] = time.time()

        return jsonify({'ok': True})

    except Exception as e:

        app.logger.exception('Cancel failed')

        return jsonify({'error': str(e)}), 500


class _EchoApprovalAuditError(Exception):
    """The approval could not be written to the audit log, so nothing was applied."""


def _echo_cancel_pending_change(session_id, user_id):
    bot = get_chat_bot()
    bot.clear_app_change_intake(session_id)
    proposal_id = _echo_change_approval_manager().cancel_pending(session_id, user_id)
    return (
        f"Cancelled proposal {proposal_id}; no app files were changed."
        if proposal_id else "Cancelled the unfinished app-change request; no files were changed."
    )


def _echo_apply_pending_change(session_id, user_id):
    """Apply the pending proposal for a chat and return the human-readable result."""
    from managers.echo_change_approvals import EchoChangeError

    change_manager = _echo_change_approval_manager()
    pending = change_manager.get_pending(session_id, user_id)
    if pending is None:
        raise EchoChangeError('There is no pending app-change proposal to confirm.')
    try:
        _echo_operator_audit(
            'app_change_confirmed',
            proposal_id=pending['proposal_id'],
            paths=[item['path'] for item in pending['files']],
        )
    except OSError as exc:
        app.logger.exception('Unable to audit Echo app-change confirmation')
        raise _EchoApprovalAuditError() from exc
    applied = change_manager.confirm_pending(session_id, user_id)
    bot = get_chat_bot()
    bot._refresh_language_reference_index(force=True)
    test_result = _run_echo_change_tests(applied['files'])
    test_stage = (
        'verification_passed'
        if test_result.startswith('Focused tests passed:')
        else 'verification_incomplete'
    )
    bot._set_conversation_focus(
        session_id,
        f"{applied['summary']} ? {test_result[:1200]}",
        test_stage,
    )
    static_result = (
        "Changed Python/JSON files passed syntax validation."
        if any(Path(path).suffix.casefold() in {'.py', '.json'} for path in applied['files'])
        else "No Python/JSON files needed syntax validation."
    )
    return (
        f"Applied proposal `{applied['proposal_id']}`: {applied['summary']}\n"
        "Changed files:\n"
        + '\n'.join(f"- `{path}`" for path in applied['files'])
        + (
            "\nBackups:\n" + '\n'.join(f"- `{path}`" for path in applied['backups'])
            if applied['backups'] else "\nThis proposal created only new files; no backups were needed."
        )
        + f"\n{static_result}\n{test_result}\n"
        "Echo did not run generated application scripts, commit, or push. "
        "Refresh MasterChief Code UI to inspect the updated files. Restart MasterChief if a changed Python module must be reloaded."
    )


def _admin_page_or_error(json_response):
    """Return an error response unless the caller is the authenticated RBAC admin; None means allowed."""
    if not _echo_operator_account_authorized():
        if json_response:
            return jsonify({'ok': False, 'error': 'This requires the authenticated RBAC admin account.'}), 403
        return redirect('/login')
    return None


def _admin_post_guard():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    if not _echo_operator_request_is_same_origin():
        return jsonify({'ok': False, 'error': 'Request must come from the same-origin MasterChief page.'}), 403
    return None


def _render_admin_fragment(template_name, **context):
    content = render_template(template_name, **context)
    return render_template_string(
        HTML_TEMPLATE.replace('{% block content %}{% endblock %}', content),
        request=request,
        get_flashed_messages=get_flashed_messages,
    )


@app.route('/echo-approvals')
def echo_approvals_page():
    denied = _admin_page_or_error(False)
    if denied is not None:
        return denied
    return _render_admin_fragment('echo_approvals.html')


@app.route('/api/echo/approvals', methods=['GET'])
def api_echo_approvals():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    manager = _echo_change_approval_manager()
    user_id = str(current_user.get_id())
    return jsonify({
        'ok': True,
        'pending': manager.list_pending(user_id),
        'history': manager.list_history(user_id),
    })


@app.route('/api/echo/approvals/<path:session_id>/<action>', methods=['POST'])
def api_echo_approval_decision(session_id, action):
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    if action not in {'confirm', 'cancel'}:
        return jsonify({'ok': False, 'error': 'Unknown action.'}), 404
    from managers.echo_change_approvals import EchoChangeError

    user_id = str(current_user.get_id())
    try:
        if action == 'confirm':
            message = _echo_apply_pending_change(session_id, user_id)
        else:
            message = _echo_cancel_pending_change(session_id, user_id)
        return jsonify({'ok': True, 'message': message.splitlines()[0]})
    except _EchoApprovalAuditError:
        return jsonify({'ok': False, 'error': 'The app change was not applied because its approval could not be audited.'}), 500
    except EchoChangeError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 409
    except Exception:
        app.logger.exception('Echo approval decision failed')
        return jsonify({'ok': False, 'error': 'Echo could not complete the approval operation.'}), 500


def _data_backup_manager():
    from managers.data_backup import DataBackupManager

    return DataBackupManager(Path(__file__).resolve().parent)


@app.route('/backups')
def data_backups_page():
    denied = _admin_page_or_error(False)
    if denied is not None:
        return denied
    return _render_admin_fragment('data_backups.html')


@app.route('/api/backups', methods=['GET'])
def api_list_backups():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return jsonify({'ok': True, 'backups': _data_backup_manager().list_backups()})


@app.route('/api/backups', methods=['POST'])
def api_create_backup():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    from managers.data_backup import DataBackupError

    try:
        result = _data_backup_manager().create_backup()
        _echo_operator_audit('data_backup_created', name=result['name'], files=result['files'])
        return jsonify({'ok': True, **result})
    except DataBackupError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception:
        app.logger.exception('Data backup failed')
        return jsonify({'ok': False, 'error': 'The backup could not be created.'}), 500


@app.route('/api/backups/<name>/download', methods=['GET'])
def api_download_backup(name):
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    from managers.data_backup import DataBackupError

    try:
        path = _data_backup_manager().backup_path(name)
    except DataBackupError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


def _cicd_center():
    from managers.cicd_center import CICDCenter

    return CICDCenter(Path(__file__).resolve().parent)


def _cicd_call(fn):
    from managers.cicd_center import CICDError

    try:
        return jsonify({'ok': True, **fn()})
    except CICDError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception:
        app.logger.exception('CI/CD operation failed')
        return jsonify({'ok': False, 'error': 'The CI/CD operation failed.'}), 500


@app.route('/cicd')
def cicd_page():
    denied = _admin_page_or_error(False)
    if denied is not None:
        return denied
    return _render_admin_fragment('cicd.html')


@app.route('/api/cicd/overview', methods=['GET'])
def api_cicd_overview():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return _cicd_call(lambda: _cicd_center().overview())


@app.route('/api/cicd/explain', methods=['GET'])
def api_cicd_explain():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    event = request.args.get('event', 'push')
    if event not in ('push', 'pull_request', 'release'):
        return jsonify({'ok': False, 'error': 'Unsupported event.'}), 400
    return _cicd_call(lambda: {'results': _cicd_center().explain(event, request.args.get('ref', ''))})


@app.route('/api/cicd/runs', methods=['GET'])
def api_cicd_runs():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return jsonify(_cicd_center().recent_runs())


@app.route('/api/cicd/config', methods=['POST'])
def api_cicd_config():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    payload = request.get_json(silent=True) or {}
    return _cicd_call(lambda: {'config': _cicd_center().save_config(payload)})


@app.route('/api/cicd/test/<provider>', methods=['POST'])
def api_cicd_test(provider):
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    return _cicd_call(lambda: {'result': _cicd_center().test_provider(provider)})


@app.route('/api/cicd/run', methods=['POST'])
def api_cicd_run():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    payload = request.get_json(silent=True) or {}
    dry_run = payload.get('dry_run', True) is not False
    if not dry_run and payload.get('confirm') is not True:
        return jsonify({'ok': False, 'error': 'Confirm the real run first.'}), 400
    selected = payload.get('selected')
    if not isinstance(selected, list) or not selected:
        return jsonify({'ok': False, 'error': 'Choose at least one target.'}), 400

    def work():
        result = _cicd_center().run([str(x) for x in selected], payload.get('ref', ''), dry_run=dry_run)
        if not dry_run:
            _echo_operator_audit('cicd_run', targets=[x for x in selected], ref=result['ref'])
        return result

    return _cicd_call(work)


@app.route('/api/cicd/gitlab-template', methods=['GET', 'POST'])
def api_cicd_gitlab_template():
    if request.method == 'POST':
        denied = _admin_post_guard()
        if denied is not None:
            return denied
        return _cicd_call(lambda: {'written': _cicd_center().write_gitlab_ci()})
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return _cicd_call(lambda: {'template': _cicd_center().gitlab_ci_template()})


def _source_map():
    from managers.source_map import SourceMap

    return SourceMap(app, Path(__file__).resolve().parent)


@app.route('/source-map')
def source_map_page():
    denied = _admin_page_or_error(False)
    if denied is not None:
        return denied
    return _render_admin_fragment('source_map.html')


@app.route('/api/source-map', methods=['GET'])
def api_source_map():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return jsonify({'ok': True, **_source_map().overview()})


@app.route('/api/source-map/lookup', methods=['GET'])
def api_source_map_lookup():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    from managers.source_map import SourceMapError

    try:
        return jsonify({'ok': True, **_source_map().lookup(request.args.get('q', ''))})
    except SourceMapError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400


@app.route('/api/source-map/markdown', methods=['GET'])
def api_source_map_markdown():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    from flask import Response

    return Response(_source_map().markdown(), mimetype='text/markdown')


def _page_editor():
    from managers.page_editor import PageEditor

    return PageEditor(app, Path(__file__).resolve().parent, HTML_TEMPLATE)


def _page_editor_call(fn):
    from managers.page_editor import PageEditorError

    try:
        return jsonify({'ok': True, **fn()})
    except PageEditorError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception:
        app.logger.exception('Page editor operation failed')
        return jsonify({'ok': False, 'error': 'The page editor operation failed.'}), 500


@app.route('/page-editor')
def page_editor_page():
    denied = _admin_page_or_error(False)
    if denied is not None:
        return denied
    return _render_admin_fragment('page_editor.html')


@app.route('/api/page-editor/pages', methods=['GET'])
def api_page_editor_pages():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return _page_editor_call(lambda: {'groups': _page_editor().pages()})


@app.route('/api/page-editor/page', methods=['GET'])
def api_page_editor_page():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return _page_editor_call(lambda: _page_editor().page_segments(request.args.get('url', '')))


@app.route('/api/page-editor/find', methods=['GET'])
def api_page_editor_find():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return _page_editor_call(lambda: {'hits': _page_editor().find(request.args.get('url', ''), request.args.get('q', ''))})


@app.route('/api/page-editor/segment', methods=['GET'])
def api_page_editor_segment():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return _page_editor_call(lambda: _page_editor().read_segment(
        request.args.get('path', ''), request.args.get('start'), request.args.get('end')))


@app.route('/api/page-editor/preview', methods=['POST'])
def api_page_editor_preview():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    d = request.get_json(silent=True) or {}
    return _page_editor_call(lambda: _page_editor().preview(
        d.get('path'), d.get('start'), d.get('end'), d.get('text'), d.get('sha')))


@app.route('/api/page-editor/save', methods=['POST'])
def api_page_editor_save():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    d = request.get_json(silent=True) or {}
    if d.get('confirm') is not True:
        return jsonify({'ok': False, 'error': 'Confirm the save first.'}), 400

    def work():
        result = _page_editor().save(d.get('path'), d.get('start'), d.get('end'), d.get('text'), d.get('sha'))
        _echo_operator_audit('page_editor_save', path=d.get('path'), backup=result['backup'])
        return result

    return _page_editor_call(work)


@app.route('/api/page-editor/backups', methods=['GET'])
def api_page_editor_backups():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return _page_editor_call(lambda: {'backups': _page_editor().backups(request.args.get('path', ''))})


@app.route('/api/page-editor/restore', methods=['POST'])
def api_page_editor_restore():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    d = request.get_json(silent=True) or {}
    if d.get('confirm') is not True:
        return jsonify({'ok': False, 'error': 'Confirm the restore first.'}), 400

    def work():
        result = _page_editor().restore(d.get('path'), d.get('backup'), d.get('sha'))
        _echo_operator_audit('page_editor_restore', path=d.get('path'), backup=d.get('backup'))
        return result

    return _page_editor_call(work)


def _site_settings():
    from managers.site_settings import SiteSettings

    return SiteSettings(_page_editor())


def _site_settings_call(fn):
    from managers.page_editor import PageEditorError
    from managers.site_settings import SiteSettingsError

    try:
        return jsonify({'ok': True, **fn()})
    except (PageEditorError, SiteSettingsError, UnicodeDecodeError) as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception:
        app.logger.exception('Site settings operation failed')
        return jsonify({'ok': False, 'error': 'The site settings operation failed.'}), 500


@app.route('/site-settings')
def site_settings_page():
    denied = _admin_page_or_error(False)
    if denied is not None:
        return denied
    return _render_admin_fragment('site_settings.html')


@app.route('/api/site-settings', methods=['GET'])
def api_site_settings():
    denied = _admin_page_or_error(True)
    if denied is not None:
        return denied
    return _site_settings_call(lambda: _site_settings().overview())


@app.route('/api/site-settings/preview', methods=['POST'])
def api_site_settings_preview():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    d = request.get_json(silent=True) or {}
    return _site_settings_call(lambda: _site_settings().preview(d.get('values') or {}))


@app.route('/api/site-settings/save', methods=['POST'])
def api_site_settings_save():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    d = request.get_json(silent=True) or {}
    if d.get('confirm') is not True:
        return jsonify({'ok': False, 'error': 'Confirm the change first.'}), 400

    def work():
        result = _site_settings().save(d.get('values') or {})
        _echo_operator_audit('site_settings_save', fields=sorted((d.get('values') or {}).keys()))
        return result

    return _site_settings_call(work)


@app.route('/api/site-settings/nav/preview', methods=['POST'])
def api_site_settings_nav_preview():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    d = request.get_json(silent=True) or {}
    return _site_settings_call(lambda: _site_settings().nav_preview(d.get('op') or {}))


@app.route('/api/site-settings/nav/save', methods=['POST'])
def api_site_settings_nav_save():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    d = request.get_json(silent=True) or {}
    if d.get('confirm') is not True:
        return jsonify({'ok': False, 'error': 'Confirm the change first.'}), 400

    def work():
        result = _site_settings().nav_save(d.get('op') or {})
        _echo_operator_audit('site_settings_nav', action=(d.get('op') or {}).get('type'))
        return result

    return _site_settings_call(work)


@app.route('/api/site-settings/logo', methods=['POST'])
def api_site_settings_logo():
    denied = _admin_post_guard()
    if denied is not None:
        return denied
    if request.form.get('confirm') != 'true':
        return jsonify({'ok': False, 'error': 'Confirm the change first.'}), 400
    upload = request.files.get('logo')
    if upload is None:
        return jsonify({'ok': False, 'error': 'Choose a logo file.'}), 400

    def work():
        result = _site_settings().set_logo(upload.filename, upload.read(1_000_001))
        _echo_operator_audit('site_settings_logo', logo=result['logo'])
        return result

    return _site_settings_call(work)


@app.route('/api/echo/models', methods=['GET'])
def api_echo_models():
    try:
        app_root = Path(__file__).resolve().parent
        models_dir = app_root / 'models'
        models = []
        if models_dir.exists():
            for f in models_dir.glob('*.gguf'):
                models.append(str(f.relative_to(app_root)))
        return jsonify({'ok': True, 'models': models})
    except Exception as e:
        app.logger.exception('List models failed')
        return jsonify({'error': str(e)}), 500


@app.route('/echo-train')

@requires_permission('training')
def echo_train_page():

    return render_echo_training_page()


@app.route('/api/echo/select_model', methods=['POST'])

def api_echo_select_model():
    data = request.get_json(silent=True) or {}
    result, status = _select_echo_model_path(data.get('model'))
    return jsonify(result), status


def _select_echo_model_path(model):
    if not _echo_operator_account_authorized():
        return {'ok': False, 'error': 'Signed-in RBAC platform admin required.'}, 403
    if not _echo_operator_request_is_same_origin():
        return {'ok': False, 'error': 'same-origin request required'}, 403
    if not isinstance(model, str) or not model.strip():
        return {'ok': False, 'error': 'model required'}, 400

    base = Path(__file__).resolve().parent
    models_dir = (base / 'models').resolve()
    candidate = Path(model.strip())
    if candidate.is_absolute():
        return {'ok': False, 'error': 'model must be a GGUF file in the models directory'}, 400
    if len(candidate.parts) == 1:
        candidate = models_dir / candidate
    elif len(candidate.parts) == 2 and candidate.parts[0].casefold() == 'models':
        candidate = base / candidate
    else:
        return {'ok': False, 'error': 'model must be a GGUF file in the models directory'}, 400

    try:
        p = candidate.resolve(strict=True)
        p.relative_to(models_dir)
    except FileNotFoundError:
        return {'ok': False, 'error': 'model not found'}, 404
    except ValueError:
        return {'ok': False, 'error': 'model must resolve inside the models directory'}, 400
    if not p.is_file() or p.suffix.casefold() != '.gguf':
        return {'ok': False, 'error': 'only .gguf model files can be selected'}, 400

    try:
        bot = get_chat_bot()
        if not bot.set_local_model(str(p)):
            return {'ok': False, 'error': 'Echo rejected the selected local model path.'}, 500
        from echo.runtime import model_runtime
        model_runtime.unload_model()
        cfg = base / 'data' / 'echo_model.json'
        cfg.parent.mkdir(parents=True, exist_ok=True)
        relative_model = p.relative_to(base).as_posix()
        cfg.write_text(json.dumps({'model': relative_model}), encoding='utf-8')
        return {'ok': True, 'model': relative_model}, 200
    except Exception as exc:
        app.logger.exception('Failed to select local Echo GGUF model')
        return {'ok': False, 'error': f'Model selection failed: {exc}'}, 500


def _chatserv_select_model(model):
    result, _ = _select_echo_model_path(model)
    return result


app.config['CHAT_SERV_MODEL_HANDLER'] = _chatserv_select_model


@app.route('/api/echo/upload_ingest', methods=['POST'])

def api_echo_upload_ingest():

    """Upload a persona or training file to the data folders and optionally ingest it."""

    try:

        typ = request.form.get('type') or 'personality'

        name = request.form.get('name') or None

        f = request.files.get('file')

        if not f:

            return jsonify({'error': 'file required'}), 400

        content = f.read().decode('utf-8')

        saved_path = None

        if typ == 'personality' or typ == 'persona':

            pdir = Path(__file__).parent / 'data' / 'personality'

            pdir.mkdir(parents=True, exist_ok=True)

            fname = name or f.filename or f'persona_{int(time.time())}.txt'

            target = pdir / secure_filename(fname)

            target.write_text(content, encoding='utf-8')

            saved_path = str(target)

        else:

            tdir = Path(__file__).parent / 'data' / 'echo_training'

            tdir.mkdir(parents=True, exist_ok=True)

            fname = name or f.filename or f'train_{int(time.time())}.jsonl'

            target = tdir / fname

            # append raw content

            with open(str(target), 'a', encoding='utf-8') as fh:

                if not content.endswith('\n'):

                    content = content + '\n'

                fh.write(content)

            saved_path = str(target)


        # attempt to have bot ingest the content if supported

        try:

            bot = get_chat_bot()

            entry = {'type': typ, 'name': Path(saved_path).name}

            if hasattr(bot, 'ingest_resource'):

                try:

                    bot.ingest_resource('default', entry, content)

                except Exception:

                    app.logger.exception('Bot ingest failed')

        except Exception:

            app.logger.exception('Failed to call bot.ingest_resource')


        return jsonify({'ok': True, 'saved': saved_path})

    except Exception as e:

        app.logger.exception('Upload ingest failed')

        return jsonify({'error': str(e)}), 500

@app.route('/api/echo/search')

def api_echo_search():

    try:

        query=request.args.get('q','')

        if not query:

            return jsonify({'error':'Query parameter q is required'}),400

        storage=get_storage()

        results=storage.search_conversations(query,limit=20)

        return jsonify({'results':results,'count':len(results)})

    except Exception as e:

        return jsonify({'error':str(e)}),500


@app.route('/api/echo/sessions')

def api_echo_sessions():

    try:

        bot = get_chat_bot()

        idx = _load_sessions_index()

        sessions = []

        # merge in-memory sessions with persisted metadata

        for sid, msgs in bot.conversation_history.items():

            meta = idx.get(sid, {})

            meta.setdefault('session_id', sid)

            meta.setdefault('title', sid)

            meta.setdefault('last_updated', None)

            meta.setdefault('created', None)

            meta.setdefault('favorite', False)

            sessions.append(meta)

        # include persisted sessions not currently in memory

        for sid, meta in idx.items():

            if sid not in bot.conversation_history:

                sessions.append(meta)

        # sort favorites first, then by last_updated desc

        def sort_key(m):

            fav = 0 if m.get('favorite') else 1

            lu = m.get('last_updated') or ''

            return (fav, lu)

        sessions = sorted(sessions, key=sort_key)

        return jsonify({'sessions': sessions})

    except Exception as e:

        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/session/<session_id>', methods=['GET','DELETE'])

def api_echo_session(session_id):

    try:

        bot = get_chat_bot()

        if request.method == 'GET':

            # prefer persisted storage for full history

            storage = get_storage()

            history = storage.get_conversation_history(user='web_user', limit=1000, channel=session_id)

            # fall back to in-memory bot history if none

            if not history:

                history = bot.get_conversation_history(session_id)

            return jsonify({'session_id': session_id, 'history': history})

        else:

            bot.clear_conversation(session_id)

            # remove persisted messages for this session

            try:

                storage = get_storage()

                storage.delete_conversation(session_id)

            except Exception:

                pass

            # remove from persisted index

            idx = _load_sessions_index()

            if session_id in idx:

                del idx[session_id]

                _save_sessions_index(idx)

            return jsonify({'deleted': True, 'session_id': session_id})

    except Exception as e:

        return jsonify({'error': str(e)}), 500


@app.route('/api/echo/session/favorite', methods=['POST'])

def api_echo_session_favorite():

    try:

        data = request.get_json() or {}

        sid = data.get('session_id')

        if not sid:

            return jsonify({'error':'session_id required'}),400

        idx = _load_sessions_index()

        entry = idx.get(sid, None)

        if not entry:

            # if not present, create minimal entry

            entry = {'session_id': sid, 'title': sid, 'created': datetime.now().isoformat(), 'favorite': True, 'last_updated': datetime.now().isoformat()}

            idx[sid]=entry

        else:

            entry['favorite'] = not bool(entry.get('favorite'))

            entry['last_updated'] = datetime.now().isoformat()

            idx[sid]=entry

        _save_sessions_index(idx)

        return jsonify({'ok':True,'session':entry})

    except Exception as e:

        return jsonify({'error': str(e)}),500


@app.route('/api/echo/session/create', methods=['POST'])

def api_echo_session_create():

    try:

        data = request.get_json() or {}

        sid = data.get('session_id') or f"web_{int(time.time()*1000)}"

        title = data.get('title') or sid

        entry = _upsert_session_meta(sid, title=title)

        return jsonify({'ok':True,'session':entry})

    except Exception as e:

        return jsonify({'error': str(e)}),500


@app.route('/debug/fetch_model')

def debug_fetch_model():

    """Serve a tiny page that fetches /api/echo/model and displays result.

    Use this from your browser to determine whether client JS can reach the API.

    """

    html = """

    <html><head><title>Debug: fetch /api/echo/model</title></head>

    <body>

    <h3>Debug: fetch /api/echo/model</h3>

    <pre id="out">Running...</pre>

    <script>

    fetch('/api/echo/model').then(r=>r.json()).then(j=>{

        document.getElementById('out').textContent = JSON.stringify(j, null, 2);

    }).catch(e=>{

        document.getElementById('out').textContent = 'Fetch failed: '+e;

        console.error('Fetch failed',e);

    });

    </script>

    </body></html>

    """

    return html


@app.route('/personality')

def personality_list():

    pdir = Path(__file__).resolve().parent / 'data' / 'personality'

    pdir.mkdir(parents=True, exist_ok=True)

    files = [f.name for f in pdir.glob('*') if f.is_file()]

    html_out = '<html><body><h3>Personality Files</h3><ul>'

    for fn in files:

        html_out += f'<li>{html.escape(fn)} - <a href="/personality/edit?id={html.escape(fn)}">Edit</a></li>'

    html_out += '</ul><p><a href="/resources">Back</a></p></body></html>'

    return html_out


@app.route('/personality/edit')

def personality_edit():

    fid = request.args.get('id')

    if not fid:

        return 'id required', 400

    pdir = Path(__file__).resolve().parent / 'data' / 'personality'

    pfile = pdir / fid

    if not pfile.exists():

        return 'not found', 404

    try:

        text = pfile.read_text(encoding='utf-8')

    except Exception:

        text = ''

    return f'''<html><body>

    <h3>Edit personality: {html.escape(fid)}</h3>

    <form method="post" action="/personality/save">

    <input type="hidden" name="id" value="{html.escape(fid)}">

    <textarea name="content" style="width:80%;height:400px;">{html.escape(text)}</textarea><br>

    <button type="submit">Save</button>

    </form>

    <p><a href="/personality">Back</a></p>

    </body></html>'''


@app.route('/personality/save', methods=['POST'])

def personality_save():

    fid = request.form.get('id')

    content = request.form.get('content') or ''

    if not fid:

        return jsonify({'error': 'id required'}), 400

    pdir = Path(__file__).resolve().parent / 'data' / 'personality'

    pdir.mkdir(parents=True, exist_ok=True)

    pfile = pdir / fid

    try:

        pfile.write_text(content, encoding='utf-8')

        return redirect(url_for('personality_list'))

    except Exception as e:

        app.logger.exception('Failed to save personality')

        return jsonify({'error': str(e)}), 500


@app.route('/about')

def about_page():

    return send_file(Path(__file__).resolve().parent / 'about.html')


@app.route('/api/about/version')
def about_github_version():
    from core.github_version import get_github_current_version

    repository = os.environ.get('GITHUB_REPO', 'jbalestrine/masterchief').strip()
    version = get_github_current_version(
        repository,
        force_refresh=request.args.get('refresh') == '1',
    )
    return jsonify(version), 200 if version.get('ok') else 502


@app.route('/pipelines')

def pipelines_page():

    return send_file('pipelines.html')


@app.route('/cloud')

def cloud_page():

    return send_file('cloud_dashboard.html')


# ─────────────────────────────────────────────────────────────────────────────
#  Certificate Management API
# ─────────────────────────────────────────────────────────────────────────────
import subprocess as _certsubp, json as _certjson, os as _certos, re as _certre
import datetime as _certdt, threading as _certlock

_CERT_AUDIT_FILE = _certos.path.join(_certos.path.dirname(_certos.path.abspath(__file__)), 'cert_audit.json')
_cert_audit_lock = _certlock.Lock()

CERT_STORES_ALL = ['My', 'Root', 'CA', 'TrustedPeople', 'WebHosting']

def _cert_audit_add(action, subject='', detail='', thumbprint=''):
    entry = {'action': action, 'subject': subject, 'detail': detail,
             'thumbprint': thumbprint,
             'timestamp': _certdt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
    with _cert_audit_lock:
        try:
            existing = []
            if _certos.path.exists(_CERT_AUDIT_FILE):
                with open(_CERT_AUDIT_FILE, 'r') as f:
                    existing = _certjson.load(f)
        except Exception:
            existing = []
        existing.insert(0, entry)
        existing = existing[:500]
        with open(_CERT_AUDIT_FILE, 'w') as f:
            _certjson.dump(existing, f)

def _run_ps(script, timeout=30):
    try:
        r = _certsubp.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return '', str(e), 1

def _ps_list_certs(store):
    script = (
        "Get-ChildItem -Path Cert:\\LocalMachine\\{store} -ErrorAction SilentlyContinue | "
        "Select-Object -Property Subject,Issuer,Thumbprint,NotBefore,NotAfter | "
        "ConvertTo-Json -Depth 2"
    ).format(store=store)
    out, err, rc = _run_ps(script)
    if not out:
        return [], err
    try:
        raw = _certjson.loads(out)
        if isinstance(raw, dict):
            raw = [raw]
        certs = []
        for c in (raw or []):
            def _msdate(v):
                if not v: return ''
                m2 = _certre.search(r'(\d+)', str(v))
                if m2:
                    try:
                        ts = int(m2.group(1)) / 1000
                        return _certdt.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
                    except Exception:
                        pass
                return str(v)[:10]
            certs.append({
                'store': store,
                'subject': c.get('Subject', ''),
                'issuer': c.get('Issuer', ''),
                'thumbprint': c.get('Thumbprint', ''),
                'valid_from': _msdate(c.get('NotBefore', '')),
                'expiry': _msdate(c.get('NotAfter', '')),
            })
        return certs, None
    except Exception as e:
        return [], str(e)


@app.route('/api/certs/summary')
def api_certs_summary():
    total = 0; expired = 0; expiring_soon = 0
    now = _certdt.datetime.utcnow()
    for st in CERT_STORES_ALL:
        certs, _ = _ps_list_certs(st)
        for c in certs:
            total += 1
            exp_str = c.get('expiry', '')
            if exp_str:
                try:
                    exp = _certdt.datetime.strptime(exp_str[:10], '%Y-%m-%d')
                    dl = (exp - now).days
                    if dl < 0: expired += 1
                    elif dl <= 30: expiring_soon += 1
                except Exception: pass
    return jsonify({'total': total, 'expired': expired, 'expiring_soon': expiring_soon,
                    'key_vault': '\u2014', 'app_services': '\u2014'})


@app.route('/api/certs/list', methods=['POST'])
def api_certs_list():
    data = request.get_json() or {}
    store = data.get('store', 'My').strip()
    if store == 'ALL':
        all_certs = []
        for st in CERT_STORES_ALL:
            certs, _ = _ps_list_certs(st)
            all_certs.extend(certs)
        return jsonify({'certs': all_certs})
    certs, err = _ps_list_certs(store)
    if err and not certs:
        return jsonify({'error': err}), 500
    return jsonify({'certs': certs})


@app.route('/api/certs/details', methods=['POST'])
def api_certs_details():
    data = request.get_json() or {}
    thumb = data.get('thumbprint', '').strip().replace(' ', '')
    store = data.get('store', 'My').strip()
    if not thumb:
        return jsonify({'error': 'thumbprint required'}), 400
    try:
        r = _certsubp.run(['certutil', '-store', store, thumb], capture_output=True, text=True, timeout=20)
        output = r.stdout or r.stderr
    except Exception as e:
        output = str(e)
    _cert_audit_add('check', thumbprint=thumb, detail='Viewed details from ' + store)
    return jsonify({'output': output})


@app.route('/api/certs/expiring', methods=['POST'])
def api_certs_expiring():
    data = request.get_json() or {}
    days = int(data.get('days', 30))
    now = _certdt.datetime.utcnow()
    result = []
    for st in CERT_STORES_ALL:
        certs, _ = _ps_list_certs(st)
        for c in certs:
            exp_str = c.get('expiry', '')
            if not exp_str:
                continue
            try:
                exp = _certdt.datetime.strptime(exp_str[:10], '%Y-%m-%d')
                dl = (exp - now).days
                if dl <= days:
                    c['days_left'] = dl
                    result.append(c)
            except Exception:
                pass
    result.sort(key=lambda x: x.get('days_left', 0))
    _cert_audit_add('check', detail='Scanned expiring within ' + str(days) + 'd')
    return jsonify({'certs': result})


@app.route('/api/certs/wizard', methods=['POST'])
def api_certs_wizard():
    data = request.get_json() or {}
    op = data.get('op', '').strip()

    if op == 'selfsigned':
        cn    = data.get('cn', '').strip()
        days  = int(data.get('days', 365))
        store = data.get('store', 'My').strip()
        exportable = str(data.get('export', 'true')).lower() == 'true'
        if not cn:
            return jsonify({'error': 'Common Name required'}), 400
        ef = '-KeyExportPolicy Exportable' if exportable else '-KeyExportPolicy NonExportable'
        script = (
            '$cert = New-SelfSignedCertificate -Subject "CN={cn}" '
            '-DnsName "{cn}" '
            '-CertStoreLocation "Cert:\\LocalMachine\\{store}" '
            '-NotAfter (Get-Date).AddDays({days}) {ef}; '
            'Write-Output ("Thumbprint: " + $cert.Thumbprint); '
            'Write-Output ("Expires: " + $cert.NotAfter)'
        ).format(cn=cn.replace('"', '\\"'), store=store, days=days, ef=ef)
        out, err, rc = _run_ps(script)
        success = rc == 0 and 'Thumbprint' in out
        _cert_audit_add('create', subject='CN=' + cn, detail='Self-signed in ' + store + ', ' + str(days) + 'd')
        return jsonify({'output': out + ('\n[stderr]\n' + err if err else ''),
                        'success': success, 'message': 'Certificate created' if success else 'Creation may have failed'})

    elif op == 'export_pfx':
        thumb    = data.get('thumb', '').replace(' ', '').strip()
        store    = data.get('store', 'My').strip()
        pfx_path = data.get('pfx-path', '').strip()
        pfx_pass = data.get('pfx-pass', '')
        if not thumb or not pfx_path:
            return jsonify({'error': 'Thumbprint and output path required'}), 400
        pp = ('$pw = ConvertTo-SecureString -String "{p}" -Force -AsPlainText; '
              .format(p=pfx_pass.replace('"', '\\"')) if pfx_pass else '$pw = $null; ')
        script = (
            '{pp}$cert = Get-ChildItem -Path "Cert:\\LocalMachine\\{store}" | '
            'Where-Object {{$_.Thumbprint -eq "{t}"}}; '
            'if(!$cert){{Write-Error "Cert not found"; exit 1}} '
            'Export-PfxCertificate -Cert $cert -FilePath "{path}" -Password $pw | Out-Null; '
            'Write-Output "Exported: {path}"'
        ).format(pp=pp, store=store, t=thumb.upper(), path=pfx_path.replace('"', '\\"'))
        out, err, rc = _run_ps(script)
        success = rc == 0
        _cert_audit_add('export', thumbprint=thumb, detail='Exported PFX to ' + pfx_path)
        return jsonify({'output': out + ('\n[stderr]\n' + err if err else ''),
                        'success': success, 'message': 'PFX exported' if success else 'Export failed'})

    elif op == 'import_pfx':
        pfx_path   = data.get('pfx-path', '').strip()
        pfx_pass   = data.get('pfx-pass', '')
        store      = data.get('store', 'My').strip()
        exportable = str(data.get('export', 'true')).lower() == 'true'
        if not pfx_path:
            return jsonify({'error': 'PFX file path required'}), 400
        pp = ('-Password (ConvertTo-SecureString -String "{p}" -Force -AsPlainText)'
              .format(p=pfx_pass.replace('"', '\\"')) if pfx_pass else '')
        ef = '-Exportable' if exportable else ''
        script = (
            '$cert = Import-PfxCertificate -FilePath "{path}" '
            '-CertStoreLocation "Cert:\\LocalMachine\\{store}" {pp} {ef}; '
            'Write-Output ("Imported: " + $cert.Thumbprint)'
        ).format(path=pfx_path.replace('"', '\\"'), store=store, pp=pp, ef=ef)
        out, err, rc = _run_ps(script)
        success = rc == 0 and 'Imported' in out
        _cert_audit_add('import', detail='Imported PFX from ' + pfx_path + ' into ' + store)
        return jsonify({'output': out + ('\n[stderr]\n' + err if err else ''),
                        'success': success, 'message': 'PFX imported into ' + store if success else 'Import failed'})

    elif op == 'verify':
        pfx_path = data.get('pfx-path', '').strip()
        pfx_pass = data.get('pfx-pass', '')
        if not pfx_path:
            return jsonify({'error': 'File path required'}), 400
        cmd = ['certutil']
        if pfx_pass:
            cmd += ['-p', pfx_pass]
        cmd += ['-dump', pfx_path]
        try:
            r = _certsubp.run(cmd, capture_output=True, text=True, timeout=20)
            out = r.stdout or r.stderr
        except Exception as e:
            out = str(e)
        _cert_audit_add('verify', detail='Verified: ' + pfx_path)
        return jsonify({'output': out, 'success': 'command completed successfully' in out.lower()})

    elif op == 'delete':
        thumb = data.get('thumb', '').replace(' ', '').strip()
        store = data.get('store', 'My').strip()
        if not thumb:
            return jsonify({'error': 'Thumbprint required'}), 400
        try:
            r = _certsubp.run(['certutil', '-delstore', store, thumb], capture_output=True, text=True, timeout=20)
            out = r.stdout + r.stderr
            success = r.returncode == 0
        except Exception as e:
            out = str(e); success = False
        _cert_audit_add('delete', thumbprint=thumb, detail='Deleted from ' + store)
        return jsonify({'output': out, 'success': success,
                        'message': 'Certificate deleted' if success else 'Delete failed'})

    elif op == 'csr':
        import tempfile as _tm_csr
        cn      = data.get('cn', '').strip()
        san_raw = data.get('san', '').strip()
        csr_path = data.get('pfx-path', '').strip()
        if not cn or not csr_path:
            return jsonify({'error': 'CN and output path required'}), 400
        sans = [cn] + [s.strip() for s in san_raw.split(',') if s.strip()]
        sans = list(dict.fromkeys(sans))
        inf_path = _certos.path.join(_tm_csr.gettempdir(), 'csr_' + cn.replace('.','_')[:24] + '.inf')
        inf_lines = [
            '[Version]', 'Signature="$Windows NT$"', '',
            '[NewRequest]',
            'Subject = "CN=' + cn + '"',
            'KeySpec = 1', 'KeyLength = 2048', 'Exportable = TRUE', 'MachineKeySet = TRUE',
            'SMIME = False', 'PrivateKeyArchive = FALSE', 'UserProtected = FALSE',
            'UseExistingKeySet = FALSE',
            'ProviderName = "Microsoft RSA SChannel Cryptographic Provider"',
            'ProviderType = 12', 'RequestType = PKCS10', 'KeyUsage = 0xa0', '',
            '[EnhancedKeyUsageExtension]', 'OID=1.3.6.1.5.5.7.3.1', '',
            '[Extensions]', '2.5.29.17 = "{text}"',
        ]
        for s in sans:
            inf_lines.append('_Continue_ = "dns=' + s + '&"')
        with open(inf_path, 'w') as _f:
            _f.write('\r\n'.join(inf_lines) + '\r\n')
        try:
            _rr = _certsubp.run(['certreq', '-new', '-machine', inf_path, csr_path],
                                capture_output=True, text=True, timeout=30)
            out = _rr.stdout + _rr.stderr
            success = _rr.returncode == 0 or _certos.path.exists(csr_path)
            if success and _certos.path.exists(csr_path):
                with open(csr_path, 'r', errors='replace') as _f2:
                    out = 'CSR generated: ' + csr_path + '\n\n' + _f2.read()[:3000]
        except Exception as _e:
            out = str(_e); success = False
        finally:
            if _certos.path.exists(inf_path): _certos.remove(inf_path)
        _cert_audit_add('create', subject='CN=' + cn, detail='CSR generated: ' + csr_path)
        return jsonify({'output': out, 'success': success,
                        'message': 'CSR written to ' + csr_path if success else 'CSR generation failed'})

    elif op == 'export_cer':
        thumb    = data.get('thumb', '').replace(' ', '').strip()
        store    = data.get('store', 'My').strip()
        out_path = data.get('pfx-path', '').strip()
        fmt      = data.get('fmt', 'DER').strip().upper()
        if not thumb or not out_path:
            return jsonify({'error': 'Thumbprint and output path required'}), 400
        esc = lambda v: v.replace('"', '\\"')
        if fmt == 'PEM':
            script = (
                '$cert = Get-ChildItem "Cert:\\LocalMachine\\{s}" | '
                'Where-Object {{ $_.Thumbprint -eq "{t}" }}; '
                'if(!$cert){{ Write-Error "Not found"; exit 1 }} '
                '$b64 = [Convert]::ToBase64String($cert.RawData,"InsertLineBreaks"); '
                '"-----BEGIN CERTIFICATE-----`n$b64`n-----END CERTIFICATE-----" | '
                'Out-File -FilePath "{p}" -Encoding ASCII; '
                'Write-Output "PEM exported: {p}"'
            ).format(s=store, t=thumb.upper(), p=esc(out_path))
        elif fmt == 'P7B':
            script = (
                '$cert = Get-ChildItem "Cert:\\LocalMachine\\{s}" | '
                'Where-Object {{ $_.Thumbprint -eq "{t}" }}; '
                'if(!$cert){{ Write-Error "Not found"; exit 1 }} '
                'Export-Certificate -Cert $cert -FilePath "{p}" -Type P7B | Out-Null; '
                'Write-Output "P7B exported: {p}"'
            ).format(s=store, t=thumb.upper(), p=esc(out_path))
        else:
            script = (
                '$cert = Get-ChildItem "Cert:\\LocalMachine\\{s}" | '
                'Where-Object {{ $_.Thumbprint -eq "{t}" }}; '
                'if(!$cert){{ Write-Error "Not found"; exit 1 }} '
                'Export-Certificate -Cert $cert -FilePath "{p}" -Type CERT | Out-Null; '
                'Write-Output "DER exported: {p}"'
            ).format(s=store, t=thumb.upper(), p=esc(out_path))
        out, err, rc = _run_ps(script)
        success = rc == 0
        _cert_audit_add('export', thumbprint=thumb, detail='Exported ' + fmt + ' to ' + out_path)
        return jsonify({'output': out + ('\n[stderr]\n' + err if err else ''),
                        'success': success,
                        'message': fmt + ' exported: ' + out_path if success else 'Export failed'})

    return jsonify({'error': 'Unknown operation: ' + op}), 400


@app.route('/api/certs/delete', methods=['POST'])
def api_certs_delete():
    data = request.get_json() or {}
    thumb = data.get('thumbprint', '').replace(' ', '').strip()
    store = data.get('store', 'My').strip()
    if not thumb:
        return jsonify({'error': 'thumbprint required'}), 400
    try:
        r = _certsubp.run(['certutil', '-delstore', store, thumb], capture_output=True, text=True, timeout=20)
        success = r.returncode == 0
        out = r.stdout + r.stderr
    except Exception as e:
        out = str(e); success = False
    _cert_audit_add('delete', thumbprint=thumb, detail='Deleted from ' + store)
    if not success:
        return jsonify({'error': out or 'Delete failed'}), 500
    return jsonify({'ok': True})


@app.route('/api/certs/appservices', methods=['POST'])
def api_certs_appservices():
    data = request.get_json() or {}
    sub_id = data.get('subscription_id', '').strip()
    if not sub_id:
        return jsonify({'error': 'subscription_id required'}), 400
    try:
        r = _certsubp.run(
            ['az', 'webapp', 'list', '--subscription', sub_id,
             '--query', '[].{name:name,location:location,rg:resourceGroup}', '-o', 'json'],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return jsonify({'error': 'Azure CLI error: ' + r.stderr}), 500
        webapp_list = _certjson.loads(r.stdout or '[]')
        apps = []
        for w in webapp_list[:20]:
            ssl_r = _certsubp.run(
                ['az', 'webapp', 'config', 'ssl', 'list', '--subscription', sub_id,
                 '--resource-group', w.get('rg', ''), '--output', 'json'],
                capture_output=True, text=True, timeout=20
            )
            bindings = []
            if ssl_r.returncode == 0:
                try:
                    for b in (_certjson.loads(ssl_r.stdout or '[]')):
                        bindings.append({'hostname': b.get('hostName', ''),
                                         'thumbprint': b.get('thumbprint', ''),
                                         'expiry': b.get('expirationDate', '')})
                except Exception:
                    pass
            apps.append({'name': w.get('name', ''), 'location': w.get('location', ''),
                         'resource_group': w.get('rg', ''), 'ssl_bindings': bindings})
        return jsonify({'apps': apps})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI (az) not found. Install it and run `az login`.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/certs/appgw', methods=['POST'])
def api_certs_appgw():
    data   = request.get_json() or {}
    sub_id = data.get('subscription_id', '').strip()
    rg     = data.get('resource_group', '').strip()
    if not sub_id:
        return jsonify({'error': 'subscription_id required'}), 400
    try:
        gw_cmd = ['az', 'network', 'application-gateway', 'list',
                  '--subscription', sub_id,
                  '--query', '[].{name:name,rg:resourceGroup,location:location,sku:sku.name}',
                  '-o', 'json']
        if rg:
            gw_cmd += ['--resource-group', rg]
        r = _certsubp.run(gw_cmd, capture_output=True, text=True, timeout=40)
        if r.returncode != 0:
            return jsonify({'error': 'Azure CLI error: ' + r.stderr}), 500
        gw_list = _certjson.loads(r.stdout or '[]')
        gateways = []
        for gw in gw_list[:15]:
            gw_name = gw.get('name', '')
            gw_rg   = gw.get('rg', '')
            # Fetch SSL certs
            ssl_r = _certsubp.run(
                ['az', 'network', 'application-gateway', 'ssl-cert', 'list',
                 '--gateway-name', gw_name, '--resource-group', gw_rg,
                 '--subscription', sub_id, '-o', 'json'],
                capture_output=True, text=True, timeout=20
            )
            ssl_certs = []
            if ssl_r.returncode == 0:
                try:
                    for c in (_certjson.loads(ssl_r.stdout or '[]')):
                        props = c.get('properties', c)
                        ssl_certs.append({
                            'name':       c.get('name', ''),
                            'thumbprint': props.get('publicCertData', '')[:16] or '',
                            'expiry':     props.get('keyVaultSecretId', '')   # kv-backed certs show id; plain certs show nothing
                        })
                except Exception:
                    pass
            # Fetch HTTP listeners
            ls_r = _certsubp.run(
                ['az', 'network', 'application-gateway', 'http-listener', 'list',
                 '--gateway-name', gw_name, '--resource-group', gw_rg,
                 '--subscription', sub_id, '-o', 'json'],
                capture_output=True, text=True, timeout=20
            )
            listeners = []
            if ls_r.returncode == 0:
                try:
                    for l in (_certjson.loads(ls_r.stdout or '[]')):
                        props = l.get('properties', l)
                        ssl_ref = props.get('sslCertificate', {})
                        ssl_name = ssl_ref.get('id', '').split('/')[-1] if ssl_ref else ''
                        listeners.append({
                            'name':     l.get('name', ''),
                            'hostname': props.get('hostName', '') or props.get('hostnames', [''])[0] if props.get('hostnames') else props.get('hostName', ''),
                            'protocol': props.get('protocol', ''),
                            'ssl_cert': ssl_name
                        })
                except Exception:
                    pass
            gateways.append({
                'name':          gw_name,
                'resource_group': gw_rg,
                'location':      gw.get('location', ''),
                'sku':           gw.get('sku', ''),
                'ssl_certs':     ssl_certs,
                'listeners':     listeners
            })
        return jsonify({'gateways': gateways})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI (az) not found. Install it and run `az login`.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/certs/keyvault/list', methods=['POST'])
def api_certs_kv_list():
    data = request.get_json() or {}
    vault_url = data.get('vault_url', '').strip().rstrip('/')
    if not vault_url:
        return jsonify({'error': 'vault_url required'}), 400
    vault_name = vault_url.split('//')[1].split('.')[0] if '//' in vault_url else vault_url
    try:
        r = _certsubp.run(
            ['az', 'keyvault', 'certificate', 'list', '--vault-name', vault_name, '-o', 'json'],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return jsonify({'error': 'Azure CLI error: ' + r.stderr}), 500
        raw = _certjson.loads(r.stdout or '[]')
        certs = []
        for c in raw:
            attr = c.get('attributes', {})
            certs.append({'name': c.get('name', '') or c.get('id', '').split('/')[-1],
                          'id': c.get('id', ''),
                          'enabled': attr.get('enabled', True),
                          'expiry': attr.get('expires', ''),
                          'created': attr.get('created', '')})
        return jsonify({'certs': certs})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI not found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/certs/keyvault/versions', methods=['POST'])
def api_certs_kv_versions():
    data = request.get_json() or {}
    vault_url = data.get('vault_url', '').strip().rstrip('/')
    cert_id   = data.get('cert_id', '').strip()
    cert_name = cert_id.split('/')[-1] if '/' in cert_id else cert_id
    vault_name = vault_url.split('//')[1].split('.')[0] if '//' in vault_url else vault_url
    try:
        r = _certsubp.run(
            ['az', 'keyvault', 'certificate', 'list-versions',
             '--vault-name', vault_name, '--name', cert_name, '-o', 'json'],
            capture_output=True, text=True, timeout=20
        )
        if r.returncode != 0:
            return jsonify({'error': r.stderr}), 500
        return jsonify(_certjson.loads(r.stdout or '[]'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/certs/keyvault/sync', methods=['POST'])
def api_certs_kv_sync():
    data = request.get_json() or {}
    thumb     = data.get('thumbprint', '').replace(' ', '').strip()
    cert_name = data.get('cert_name', '').strip()
    vault_url = data.get('vault_url', '').strip().rstrip('/')
    if not thumb or not cert_name or not vault_url:
        return jsonify({'error': 'thumbprint, cert_name, and vault_url required'}), 400
    vault_name = vault_url.split('//')[1].split('.')[0] if '//' in vault_url else vault_url
    import tempfile as _tmpmod
    tmp_pfx  = _certos.path.join(_tmpmod.gettempdir(), 'kvsync_' + thumb[:8] + '.pfx')
    tmp_pass = 'KVSync_' + thumb[:6]
    try:
        script = (
            '$pw = ConvertTo-SecureString -String "{p}" -Force -AsPlainText; '
            '$cert = Get-ChildItem -Path "Cert:\\LocalMachine\\My" | Where-Object {{$_.Thumbprint -eq "{t}"}}; '
            'if(!$cert){{Write-Error "Cert not found in My store"; exit 1}} '
            'Export-PfxCertificate -Cert $cert -FilePath "{f}" -Password $pw | Out-Null; '
            'Write-Output "exported"'
        ).format(p=tmp_pass, t=thumb.upper(), f=tmp_pfx)
        out, err, rc = _run_ps(script)
        if rc != 0 or 'exported' not in out:
            return jsonify({'error': 'Failed to export PFX: ' + err}), 500
        r = _certsubp.run(
            ['az', 'keyvault', 'certificate', 'import',
             '--vault-name', vault_name, '--name', cert_name,
             '--file', tmp_pfx, '--password', tmp_pass],
            capture_output=True, text=True, timeout=60
        )
        success = r.returncode == 0
        _cert_audit_add('sync', thumbprint=thumb, detail='Synced to KV ' + vault_name + ' as ' + cert_name)
        if _certos.path.exists(tmp_pfx):
            _certos.remove(tmp_pfx)
        if not success:
            return jsonify({'error': 'KV import error: ' + r.stderr}), 500
        return jsonify({'ok': True, 'message': 'Synced to Key Vault as ' + cert_name})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI not found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/certs/audit')
def api_certs_audit():
    action_filter = request.args.get('action', '').strip()
    try:
        if _certos.path.exists(_CERT_AUDIT_FILE):
            with open(_CERT_AUDIT_FILE, 'r') as f:
                entries = _certjson.load(f)
        else:
            entries = []
    except Exception:
        entries = []
    if action_filter:
        entries = [e for e in entries if e.get('action', '') == action_filter]
    return jsonify({'entries': entries})


@app.route('/api/certs/audit/clear', methods=['POST'])
def api_certs_audit_clear():
    with _cert_audit_lock:
        try:
            with open(_CERT_AUDIT_FILE, 'w') as f:
                _certjson.dump([], f)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True})


@app.route('/api/certs/chain', methods=['POST'])
def api_certs_chain():
    """Run certutil -verifystore to show the full cert chain for a thumbprint."""
    data  = request.get_json() or {}
    thumb = data.get('thumbprint', '').replace(' ', '').strip()
    store = data.get('store', 'My').strip()
    if not thumb:
        return jsonify({'error': 'thumbprint required'}), 400
    try:
        r1 = _certsubp.run(['certutil', '-verifystore', store, thumb],
                           capture_output=True, text=True, timeout=30)
        r2 = _certsubp.run(['certutil', '-store', store, thumb],
                           capture_output=True, text=True, timeout=15)
        return jsonify({
            'ok':    r1.returncode == 0,
            'chain': r1.stdout + r1.stderr,
            'dump':  r2.stdout + r2.stderr,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Akamai CDN — CPS, Route 53, Origin Certs
# ─────────────────────────────────────────────────────────────────────────────
try:
    import boto3 as _boto3
    _HAS_BOTO3 = True
except ImportError:
    _HAS_BOTO3 = False

# In-memory credential store (reset on server restart)
_ak_creds_store = {}


def _ak_eg_request(method, url_path, body, creds):
    """Make an Akamai EdgeGrid-signed request.
    url_path may be a relative path (/cps/v2/...) or an absolute URL returned
    by Akamai in allowedInput links — both are handled correctly.
    Falls back to unsigned requests if edgegrid-python is not installed.
    """
    import requests as _rq
    host = creds.get('host', '').strip('/')
    if not host:
        raise ValueError('Akamai host not configured')
    base = 'https://' + host if not host.startswith('http') else host
    # If Akamai gave us a full URL (e.g. from allowedInput[].update), use it as-is
    full_url = url_path if url_path.startswith('http') else base + url_path
    try:
        from akamai.edgegrid import EdgeGridAuth
        session = _rq.Session()
        session.auth = EdgeGridAuth(
            client_token=creds.get('client_token', ''),
            client_secret=creds.get('client_secret', ''),
            access_token=creds.get('access_token', ''),
        )
        r = session.request(method, full_url, json=body if body else None,
                            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
                            timeout=30)
    except ImportError:
        r = _rq.request(method, full_url, json=body or None,
                        headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
                        timeout=20)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {'_text': r.text[:500]}


def _r53_client(creds):
    if not _HAS_BOTO3:
        raise RuntimeError('boto3 not installed — run: pip install boto3')
    return _boto3.client(
        'route53',
        aws_access_key_id=creds.get('aws_key') or None,
        aws_secret_access_key=creds.get('aws_secret') or None,
        region_name=creds.get('aws_region') or 'us-east-1',
    )


def _get_ak_creds():
    return _ak_creds_store.get('default', {})


# ── Route 53 ──────────────────────────────────────────────────────────────────


# ── Origin SSL / Sync ─────────────────────────────────────────────────────────


@app.route('/secrets')

def secrets_page():

    return send_file('secrets_vault.html')


@app.route('/echo-memory')

def echo_memory_page():

    return send_file('echo_memory.html')


@app.route('/marketplace')

def marketplace_page():

    return send_file('marketplace.html')


@app.route('/notifications')

def notifications_page():

    return send_file('notifications.html')


@app.route('/rbac')
@requires_permission('rbac')
def rbac_page():
    return send_file('rbac.html')


# TF Wizard routes
if TF_WIZARD_AVAILABLE:
    print("DEBUG: Registering TF Wizard routes")
    @app.route('/tf_wizard')
    def tf_wizard_index():
        """Serve the TF Wizard main page"""
        import os
        from jinja2 import Environment, FileSystemLoader
        tf_wizard_dir = os.path.dirname(tf_wizard_app.__file__)
        templates_dir = os.path.join(tf_wizard_dir, 'templates')
        env = Environment(loader=FileSystemLoader(templates_dir), autoescape=tf_wizard_app.templates.autoescape)
        tmpl = env.get_template("index.html")
        return _with_archetype_client(tmpl.render())

    @app.route('/tf_wizard/generate', methods=['POST'])
    def tf_wizard_generate():
        """Generate Terraform module zip"""
        try:
            data = request.get_json()
            zip_bytes = generate_module_zip(data)
            from flask import Response
            import io
            return Response(io.BytesIO(zip_bytes), 
                          mimetype="application/zip", 
                          headers={"Content-Disposition": f"attachment; filename=terraform_module_{data.get('module_name','module')}.zip"})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/tf_wizard/schema/apply', methods=['POST'])
    def tf_wizard_apply_schema():
        """Apply JSON schema to generate variables"""
        try:
            from jsonschema import Draft7Validator
            payload = request.get_json()
            schema = payload.get('schema')
            if not schema:
                return jsonify({"error": "schema is required"}), 400
            
            # Validate schema is valid JSON Schema (Draft7)
            Draft7Validator.check_schema(schema)
            
            props = schema.get('properties', {})
            vars_out = []
            def build_var(name, meta):
                js_type = meta.get('type')
                # Use generator helper to build tf_type (supports dict schema too)
                tf_type = tf_type_from_spec(meta) if isinstance(meta, dict) else tf_type_from_spec(js_type or '')
                
                v = {
                    'name': name,
                    'type': js_type or 'string',
                    'tf_type': tf_type,
                    'default': meta.get('default') if isinstance(meta, dict) and 'default' in meta else None,
                    'description': meta.get('description', '') if isinstance(meta, dict) else '',
                }
                # if object with nested properties, return nested details
                if isinstance(meta, dict) and meta.get('type') == 'object' and isinstance(meta.get('properties'), dict):
                    nested = []
                    for nk, nv in meta.get('properties', {}).items():
                        nested.append(build_var(nk, nv))
                    v['nested'] = nested
                if isinstance(meta, dict) and 'enum' in meta:
                    v['enum'] = meta.get('enum')
                return v

            for name, meta in props.items():
                vars_out.append(build_var(name, meta))
            return jsonify({'variables': vars_out})
        except Exception as e:
            return jsonify({"error": str(e)}), 400


@app.route('/gallery')
def art_gallery():
    """Serve the Art Gallery web UI."""
    try:
        p = Path(__file__).resolve().parent / 'gallery.html'
        if p.exists():
            return p.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'}
    except Exception:
        app.logger.exception('Failed to serve gallery.html')
    return ('Art Gallery not available', 404)


@app.route('/media/roku')
@requires_permission('rbac')
def roku_builder_page():
    """Serve the Roku IPTV builder wizard."""
    try:
        p = Path(__file__).resolve().parent / 'roku_builder.html'
        if p.exists():
            return p.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'}
    except Exception:
        app.logger.exception('Failed to serve roku_builder.html')
    return ('Roku Builder not available', 404)


MAX_PREVIEW_ITEMS = 25


def _parse_m3u_playlist(text, base_url=None):
    return _parse_roku_m3u_playlist(text, base_url)


def _build_roku_preview(entries):
    return _group_roku_entries(entries)


def _parse_roku_playlist_sources(payload, uploaded_files):
    additional_urls = request.form.getlist('additional_playlist_url')
    additional_urls.extend(
        line.strip()
        for value in request.form.getlist('additional_playlist_urls')
        for line in value.splitlines()
        if line.strip()
    )
    playlist_sources = [
        str(value).strip()
        for value in (
            request.form.getlist('playlist_url')
            + additional_urls
            + request.form.getlist('playlist_url[]')
        )
        if str(value).strip()
    ]
    if not playlist_sources:
        for key in ('playlist_url', 'additional_playlist_url', 'source_url'):
            value = str(payload.get(key) or '').strip()
            if value:
                playlist_sources.append(value)
    parsed_sources = []
    for uploaded in uploaded_files:
        if not uploaded or not uploaded.filename:
            continue
        content = uploaded.read(50 * 1024 * 1024 + 1)
        if len(content) > 50 * 1024 * 1024:
            raise ValueError('Playlist files must be 50 MiB or smaller.')
        decoded = content.decode('utf-8-sig', 'replace')
        parsed_sources.extend(
            _parse_roku_json_playlist(decoded)
            if uploaded.filename.lower().endswith('.json')
            else _parse_m3u_playlist(decoded)
        )
    playlist_json = str(payload.get('playlist_json') or '').strip()
    if playlist_json:
        parsed_sources.extend(_parse_roku_json_playlist(playlist_json))
    playlist_text = str(payload.get('playlist_text') or '').strip()
    if playlist_text:
        parsed_sources.extend(_parse_m3u_playlist(playlist_text))
    for playlist_url in playlist_sources:
        remote_text, final_url = _fetch_remote_playlist_text(playlist_url)
        parsed_sources.extend(_parse_roku_m3u_playlist(remote_text, final_url))

    entries = []
    seen_urls = set()
    for entry in parsed_sources:
        url = entry.get('url')
        if not isinstance(url, str) or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        entries.append(entry)
        if len(entries) >= MAX_PLAYLIST_ENTRIES:
            break
    return entries


def _read_roku_xmltv(payload):
    from core.roku_epg import MAX_XMLTV_BYTES, parse_xmltv_listings

    uploaded = request.files.get('epg_file') if request.files else None
    epg_url = str(payload.get('epg_url') or '').strip()
    if uploaded is not None and uploaded.filename:
        content = uploaded.read(MAX_XMLTV_BYTES + 1)
        if len(content) > MAX_XMLTV_BYTES:
            raise ValueError('XMLTV guide files must be 50 MiB or smaller.')
        return parse_xmltv_listings(content), ''
    if epg_url:
        content, final_url = _fetch_remote_playlist_text(epg_url)
        return parse_xmltv_listings(content), final_url
    return {}, ''


@app.route('/api/roku/validate', methods=['POST'])
@requires_permission('rbac')
def api_roku_validate():
    """Validate and normalize an m3u/m3u8 source before building a Roku app."""
    try:
        if not get_roku_settings()['enabled']:
            return jsonify({'ok': False, 'error': 'The private Roku feature is switched off.'}), 409
    except (OSError, ValueError) as exc:
        app.logger.exception('Could not read Roku feature settings')
        return jsonify({'ok': False, 'error': str(exc)}), 500
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    uploaded_files = request.files.getlist('file') if request.files else []
    has_source = any(upload.filename for upload in uploaded_files if upload) or any(
        str(payload.get(key) or '').strip()
        for key in (
            'playlist_url',
            'additional_playlist_url',
            'additional_playlist_urls',
            'source_url',
            'playlist_text',
            'playlist_json',
        )
    )
    if not has_source:
        return jsonify({'ok': False, 'error': 'Choose a playlist URL, upload a file, or paste M3U/JSON content.'}), 400

    try:
        entries = _parse_roku_playlist_sources(payload, uploaded_files)
        guide, _ = _read_roku_xmltv(payload)
        from core.roku_epg import apply_xmltv_listings
        epg_matches = apply_xmltv_listings(entries, guide)
    except (ValueError, json.JSONDecodeError) as exc:
        return jsonify({'ok': False, 'error': f'Unable to parse playlist: {exc}'}), 400
    except requests.RequestException:
        return jsonify({'ok': False, 'error': 'Could not download a playlist or XMLTV guide. Check its URL and server response.'}), 400

    grouped = _build_roku_preview(entries)
    preview = entries[0] if entries else None
    preview_text = preview['title'] if preview else None
    return jsonify({
        'ok': True,
        'count': len(entries),
        'preview': preview_text,
        'entries': entries,
        'grouped': grouped,
        'categories': sorted(grouped.keys()),
        'truncated': len(entries) >= MAX_PLAYLIST_ENTRIES,
        'epg_matches': epg_matches,
        'message': 'Playlist validated for Roku development use.'
    })


@app.route('/api/roku/build', methods=['POST'])
@requires_permission('rbac')
def api_roku_build():
    """Build a downloadable native Roku project using the complete supplied playlist."""
    try:
        if not get_roku_settings()['enabled']:
            return jsonify({'ok': False, 'error': 'The private Roku feature is switched off.'}), 409
    except (OSError, ValueError) as exc:
        app.logger.exception('Could not read Roku feature settings')
        return jsonify({'ok': False, 'error': str(exc)}), 500

    payload = request.form.to_dict()
    uploaded_files = request.files.getlist('file') if request.files else []
    use_saved_playlist = payload.get('use_saved_playlist') == 'true'
    entries = []
    build_root = Path(__file__).resolve().parent / 'data' / 'roku_builds'

    try:
        if use_saved_playlist:
            from core.roku_app import load_latest_saved_playlist
            entries = load_latest_saved_playlist(build_root)
        else:
            entries = _parse_roku_playlist_sources(payload, uploaded_files)
        guide, dynamic_guide_url = _read_roku_xmltv(payload)
        from core.roku_epg import apply_xmltv_listings
        epg_matches = apply_xmltv_listings(entries, guide)
    except (ValueError, json.JSONDecodeError) as exc:
        return jsonify({'ok': False, 'error': f'Unable to parse playlist: {exc}'}), 400
    except FileNotFoundError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 404
    except OSError as exc:
        app.logger.exception('Could not load the latest saved Roku playlist')
        return jsonify({'ok': False, 'error': 'Could not read the saved Roku playlist.'}), 500
    except requests.RequestException:
        return jsonify({'ok': False, 'error': 'Could not download a playlist or XMLTV guide. Check its URL and server response.'}), 400

    if not entries:
        message = (
            'The latest saved Roku playlist contains no playable streams. Load a playlist in the Builder first.'
            if use_saved_playlist else
            'Provide a valid playlist containing at least one stream.'
        )
        return jsonify({'ok': False, 'error': message}), 400

    channel_name = str(payload.get('channel_name') or 'MasterChief TV').strip()
    bundle_id = str(payload.get('bundle_id') or 'com.masterchief.tv').strip()
    theme = str(payload.get('theme') or 'dark').strip().lower()
    render_url = str(payload.get('render_url') or '').strip()
    web_app_url = str(payload.get('web_app_url') or '').strip()
    logo_text = str(payload.get('logo_text') or 'JBTV').strip()
    logo_color = str(payload.get('logo_color') or 'green').strip().lower()
    collection_order_text = payload.get('collection_order')
    collection_order = (
        [line.strip() for line in str(collection_order_text).splitlines() if line.strip()]
        if collection_order_text is not None else None
    )
    logo_file = request.files.get('logo_file') if request.files else None
    logo_image_bytes = b''
    if logo_file is not None and logo_file.filename:
        logo_image_bytes = logo_file.read(5 * 1024 * 1024 + 1)
        if len(logo_image_bytes) > 5 * 1024 * 1024:
            return jsonify({'ok': False, 'error': 'Custom logo images must be 5 MiB or smaller.'}), 413
    from core.roku_app import build_roku_project, project_slug
    from core.roku_epg import create_guide_token, save_guide_source
    import uuid

    web_app_url = str(payload.get('web_app_url') or '').strip().rstrip('/')
    guide_token = create_guide_token() if dynamic_guide_url and web_app_url else ''
    guide_api_url = f'{web_app_url}/api/roku/guide/{guide_token}' if guide_token else ''
    slug = project_slug(channel_name, uuid.uuid4().hex)
    project_dir = build_root / slug
    try:
        archive = build_roku_project(project_dir, {
            'channel_name': channel_name,
            'bundle_id': bundle_id,
            'theme': theme,
            'render_url': render_url,
            'web_app_url': web_app_url,
            'guide_api_url': guide_api_url,
            'logo_image_bytes': logo_image_bytes,
            'logo_text': logo_text,
            'logo_color': logo_color,
            'collection_order': collection_order,
        }, entries)
    except (ValueError, OSError) as exc:
        app.logger.exception('Could not build Roku project')
        return jsonify({'ok': False, 'error': str(exc)}), 400 if isinstance(exc, ValueError) else 500
    if guide_token:
        try:
            save_guide_source(Path(__file__).resolve().parent / 'data' / 'roku_guides', guide_token, dynamic_guide_url)
        except OSError as exc:
            app.logger.exception('Could not save Roku XMLTV guide configuration')
            return jsonify({'ok': False, 'error': 'Roku package built, but its live guide configuration could not be saved.'}), 500

    return jsonify({
        'ok': True,
        'slug': slug,
        'channel_name': channel_name,
        'bundle_id': bundle_id,
        'playlist_count': len(entries),
        'playlist_source': 'latest_saved_build' if use_saved_playlist else 'submitted_playlist',
        'epg_matches': epg_matches,
        'live_guide': bool(guide_api_url),
        'category_count': len(_build_roku_preview(entries)),
        'download_url': f'/api/roku/download/{slug}',
        'message': f'Roku app package created at {archive.name}.'
    })
# ── Art Gallery API ──────────────────────────────────────────────────
_GALLERY_DIR = Path(__file__).resolve().parent / 'data' / 'gallery'
_GALLERY_META = Path(__file__).resolve().parent / 'data' / 'gallery_meta.json'
_GALLERY_ORDERS = Path(__file__).resolve().parent / 'data' / 'gallery_orders.json'
_GALLERY_ADMIN = Path(__file__).resolve().parent / 'data' / 'gallery_admin.json'

def _ensure_gallery():
    _GALLERY_DIR.mkdir(parents=True, exist_ok=True)

def _load_gallery_meta():
    _ensure_gallery()
    if _GALLERY_META.exists():
        try:
            return json.loads(_GALLERY_META.read_text(encoding='utf-8'))
        except Exception:
            pass
    return []

def _save_gallery_meta(meta):
    _ensure_gallery()
    _GALLERY_META.write_text(json.dumps(meta, indent=2), encoding='utf-8')

def _load_orders():
    if _GALLERY_ORDERS.exists():
        try:
            return json.loads(_GALLERY_ORDERS.read_text(encoding='utf-8'))
        except Exception:
            pass
    return []

def _save_orders(orders):
    _GALLERY_ORDERS.write_text(json.dumps(orders, indent=2), encoding='utf-8')

def _load_admin_config():
    if _GALLERY_ADMIN.exists():
        try:
            return json.loads(_GALLERY_ADMIN.read_text(encoding='utf-8'))
        except Exception:
            pass
    # Default admin credentials
    default = {'username': 'admin', 'password': 'masterchief', 'gallery_name': 'MasterChief Art Gallery', 'contact_email': ''}
    _GALLERY_ADMIN.parent.mkdir(parents=True, exist_ok=True)
    _GALLERY_ADMIN.write_text(json.dumps(default, indent=2), encoding='utf-8')
    return default

_gallery_sessions = {}  # token -> expiry timestamp

@app.route('/api/gallery/list')
def gallery_list():
    """Return all gallery metadata."""
    return jsonify(_load_gallery_meta())

@app.route('/api/gallery/upload', methods=['POST'])
def gallery_upload():
    """Upload one or more images to the gallery."""
    _ensure_gallery()
    meta = _load_gallery_meta()
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    title = request.form.get('title', 'Untitled')
    artist = request.form.get('artist', 'Unknown')
    genre = request.form.get('genre', 'portraits')
    desc = request.form.get('desc', '')
    tags_raw = request.form.get('tags', '')
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    try:
        price = float(request.form.get('price', '0'))
    except (ValueError, TypeError):
        price = 0.0
    for_sale = request.form.get('forSale', 'false') == 'true'
    medium = request.form.get('medium', '')
    dimensions = request.form.get('dimensions', '')

    added = []
    for i, f in enumerate(files):
        if not f or not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'):
            continue
        uid = f"{int(time.time()*1000)}_{os.urandom(4).hex()}"
        fname = f"{uid}{ext}"
        dest = _GALLERY_DIR / fname
        f.save(str(dest))
        entry = {
            'id': uid,
            'filename': fname,
            'title': f"{title} ({i+1})" if len(files) > 1 else title,
            'artist': artist,
            'genre': genre,
            'desc': desc,
            'tags': tags,
            'date': int(time.time() * 1000),
            'fav': False,
            'size': dest.stat().st_size,
            'price': price,
            'forSale': for_sale,
            'sold': False,
            'medium': medium,
            'dimensions': dimensions,
        }
        meta.append(entry)
        added.append(entry)
    _save_gallery_meta(meta)
    return jsonify({'added': len(added), 'items': added})

@app.route('/api/gallery/image/<filename>')
def gallery_image(filename):
    """Serve a gallery image file."""
    _ensure_gallery()
    p = _GALLERY_DIR / filename
    if not p.exists() or not p.is_file():
        return ('Not found', 404)
    import mimetypes
    mt = mimetypes.guess_type(str(p))[0] or 'image/png'
    return p.read_bytes(), 200, {'Content-Type': mt, 'Cache-Control': 'public, max-age=86400'}

@app.route('/api/gallery/update/<art_id>', methods=['POST'])
def gallery_update(art_id):
    """Toggle favorite or update metadata for a gallery item."""
    meta = _load_gallery_meta()
    item = next((m for m in meta if m['id'] == art_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json(silent=True) or {}
    for key in ('fav', 'title', 'genre', 'tags', 'artist', 'desc', 'price', 'forSale', 'sold', 'medium', 'dimensions'):
        if key in data:
            item[key] = data[key]
    _save_gallery_meta(meta)
    return jsonify(item)

@app.route('/api/gallery/delete/<art_id>', methods=['DELETE'])
def gallery_delete(art_id):
    """Delete a gallery item and its file."""
    meta = _load_gallery_meta()
    item = next((m for m in meta if m['id'] == art_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    fpath = _GALLERY_DIR / item.get('filename', '')
    if fpath.exists():
        fpath.unlink()
    meta = [m for m in meta if m['id'] != art_id]
    _save_gallery_meta(meta)
    return jsonify({'deleted': art_id})

# ── Gallery Admin Auth ───────────────────────────────────────────────
@app.route('/api/gallery/admin/login', methods=['POST'])
def gallery_admin_login():
    """Authenticate gallery admin."""
    data = request.get_json(silent=True) or {}
    cfg = _load_admin_config()
    if data.get('username') == cfg['username'] and data.get('password') == cfg['password']:
        token = os.urandom(24).hex()
        _gallery_sessions[token] = time.time() + 86400  # 24h
        return jsonify({'ok': True, 'token': token})
    return jsonify({'ok': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/gallery/admin/verify', methods=['POST'])
def gallery_admin_verify():
    """Check if admin token is still valid."""
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    exp = _gallery_sessions.get(token, 0)
    if exp > time.time():
        return jsonify({'valid': True})
    _gallery_sessions.pop(token, None)
    return jsonify({'valid': False}), 401

@app.route('/api/gallery/admin/logout', methods=['POST'])
def gallery_admin_logout():
    """Invalidate admin token."""
    data = request.get_json(silent=True) or {}
    _gallery_sessions.pop(data.get('token', ''), None)
    return jsonify({'ok': True})

@app.route('/api/gallery/admin/settings', methods=['GET', 'POST'])
def gallery_admin_settings():
    """Get or update gallery admin settings."""
    cfg = _load_admin_config()
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        # Verify token
        token = data.get('token', '')
        if _gallery_sessions.get(token, 0) <= time.time():
            return jsonify({'error': 'Unauthorized'}), 401
        for k in ('username', 'password', 'gallery_name', 'contact_email'):
            if k in data and data[k]:
                cfg[k] = data[k]
        _GALLERY_ADMIN.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        return jsonify({'ok': True})
    return jsonify({'gallery_name': cfg.get('gallery_name', ''), 'contact_email': cfg.get('contact_email', '')})

# ── Gallery Purchase / Orders ────────────────────────────────────────
@app.route('/api/gallery/purchase', methods=['POST'])
def gallery_purchase():
    """Place an order for artwork."""
    data = request.get_json(silent=True) or {}
    items = data.get('items', [])
    buyer = data.get('buyer', {})
    if not items:
        return jsonify({'error': 'No items'}), 400
    if not buyer.get('name') or not buyer.get('email'):
        return jsonify({'error': 'Buyer name and email required'}), 400

    meta = _load_gallery_meta()
    orders = _load_orders()
    order_items = []
    total = 0.0
    for art_id in items:
        item = next((m for m in meta if m['id'] == art_id), None)
        if item and item.get('forSale') and not item.get('sold'):
            order_items.append({'id': item['id'], 'title': item['title'], 'price': item.get('price', 0)})
            total += item.get('price', 0)
            item['sold'] = True

    if not order_items:
        return jsonify({'error': 'No available items to purchase'}), 400

    order = {
        'orderId': f"ORD-{int(time.time()*1000)}",
        'date': int(time.time() * 1000),
        'buyer': buyer,
        'items': order_items,
        'total': total,
        'status': 'confirmed'
    }
    orders.append(order)
    _save_orders(orders)
    _save_gallery_meta(meta)
    return jsonify(order)

@app.route('/api/gallery/orders')
def gallery_orders():
    """List all orders (admin)."""
    return jsonify(_load_orders())

@app.route('/arm_creator')
def arm_creator():
    """Serve the ARM Template Creator web UI."""
    try:
        p = Path(__file__).resolve().parent / 'arm_creator.html'
        if p.exists():
            return _with_archetype_client(p.read_text(encoding='utf-8')), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception:
        app.logger.exception('Failed to serve arm_creator.html')
    return ('ARM Creator not available', 404)

@app.route('/web_ide')

def web_ide():

    """Serve a local `web_ide.html` file if present to restore the Web IDE quickly.

    Falls back to the root index if the file is missing.

    """

    try:

        p = Path(__file__).resolve().parent / 'caf.html'

        if p.exists():

            return _with_archetype_client(p.read_text(encoding='utf-8')), 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception:

        app.logger.exception('Failed to serve web_ide.html')

    # Fall back to main index route if available

    try:

        return redirect(url_for('index'))

    except Exception:

        return ('Web IDE not available', 404)

@app.route('/iac_manager')

def iac_manager():

    """Serve the alternate TF Wizard from the cool-elbakyan worktree."""

    try:

        p = Path(r'C:\Users\Echo\masterchief\.claude\worktrees\cool-elbakyan\web_tf_wizard.html')

        if p.exists():

            return _with_archetype_client(p.read_text(encoding='utf-8')), 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception:

        app.logger.exception('Failed to serve alternate web_tf_wizard.html')

    # Fall back to main web_tf_wizard if alternate is not available

    try:

        return redirect(url_for('web_tf_wizard'))

    except Exception:

        return ('Alternate TF Wizard not available', 404)

# --- Manager Portal (external, module-level definitions) --------------------

_manager_tasks_file = Path(__file__).resolve().parent / 'data' / 'manager_tasks.json'

_manager_tests_file = Path(__file__).resolve().parent / 'data' / 'manager_last_test.json'


def _load_manager_tasks():

    try:

        if not _manager_tasks_file.exists():

            return []

        return json.loads(_manager_tasks_file.read_text(encoding='utf-8') or '[]')

    except Exception:

        app.logger.exception('Failed to load manager tasks')

        return []


def _save_manager_tasks(tasks):

    try:

        _manager_tasks_file.parent.mkdir(parents=True, exist_ok=True)

        _manager_tasks_file.write_text(json.dumps(tasks, indent=2), encoding='utf-8')

        return True

    except Exception:

        app.logger.exception('Failed to save manager tasks')

        return False


@app.route('/manager')

def manager_dashboard():

    html_page = '''<!doctype html>

<html><head><meta charset="utf-8"><title>Manager Portal</title>

<style>body{font-family:Arial,Helvetica,sans-serif;margin:0;padding:0;background:#f5f7fb}.top{padding:12px;background:#1f2937;color:#fff;display:flex;align-items:center;justify-content:space-between}.container{display:flex;gap:16px;padding:16px}.kanban{flex:1;display:flex;gap:12px}.col{background:#fff;border-radius:6px;padding:8px;min-width:260px;box-shadow:0 2px 6px rgba(0,0,0,.06)}.col h3{margin:6px 0;font-size:14px}.card{background:#f8fafc;margin:8px 0;padding:8px;border-radius:4px;cursor:grab}.card.dragging{opacity:.5}.sidebar{width:360px}.section{background:#fff;padding:12px;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,.04);margin-bottom:12px}.btn{display:inline-block;padding:8px 10px;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none}label{display:block;margin-top:8px;font-size:13px}input,textarea,select{width:100%;padding:8px;margin-top:4px;border:1px solid #e5e7eb;border-radius:4px}</style></head><body>

<div class="top"><div style="font-weight:700">Manager Portal</div><div><a href="/" style="color:#fff;text-decoration:none">Back to Dashboard</a></div></div>

<div class="container"><div class="kanban"><div class="col" data-status="todo"><h3>To Do</h3><div class="cards" id="col-todo"></div></div><div class="col" data-status="inprogress"><h3>In Progress</h3><div class="cards" id="col-inprogress"></div></div><div class="col" data-status="done"><h3>Done</h3><div class="cards" id="col-done"></div></div></div>

<div class="sidebar"><div class="section"><h4>Create Task</h4><label>Title<input id="task-title"></label><label>Assignee<input id="task-assignee"></label><label>Description<textarea id="task-desc"></textarea></label><label>Priority<select id="task-priority"><option>low</option><option selected>medium</option><option>high</option></select></label><div style="margin-top:8px"><a id="create-task" class="btn">Create</a></div></div>

<div class="section"><h4>Model Manager</h4><div id="models-list">Loading models...</div><label>Model path (or filename)<input id="model-input" placeholder="models/Phi-3-mini-4k-instruct-q4.gguf"></label><div style="margin-top:8px"><a id="preload-model" class="btn">Set Default Model</a></div></div>

<div class="section"><h4>Test Runner</h4><div id="test-status">No test run yet.</div><div style="margin-top:8px"><a id="run-tests" class="btn">Run Tests</a></div><pre id="test-output" style="height:160px;overflow:auto;background:#0f172a;color:#e6eef8;padding:8px;border-radius:4px;margin-top:8px"></pre></div></div></div>

<script>

async function api(path, opts){const res = await fetch(path, opts); return res.json();}

function el(html){const d=document.createElement('div');d.innerHTML=html.trim();return d.firstChild}

let dragged=null;

function renderCard(t){const node = el(`<div class="card" draggable="true" data-id="${t.id}"><strong>${t.title}</strong><div style="font-size:12px;color:#555">${t.assignee||''} • ${t.priority}</div><div style="margin-top:6px;font-size:13px">${(t.description||'').slice(0,200)}</div></div>`);node.addEventListener('dragstart',e=>{dragged=node;node.classList.add('dragging')});node.addEventListener('dragend',e=>{dragged=null;node.classList.remove('dragging')});node.addEventListener('dblclick',async e=>{const newTitle=prompt('Edit title',t.title); if(newTitle!==null){t.title=newTitle; await fetch('/api/manager/tasks',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(t)}); loadTasks();}});return node;}

async function loadTasks(){const j = await api('/api/manager/tasks');['todo','inprogress','done'].forEach(s=>document.getElementById('col-'+s).innerHTML='');j.forEach(t=>{document.getElementById('col-'+(t.status||'todo')).appendChild(renderCard(t))});}

document.querySelectorAll('.col').forEach(col=>{col.addEventListener('dragover',e=>e.preventDefault());col.addEventListener('drop',async e=>{e.preventDefault(); if(!dragged) return; const id=dragged.dataset.id; const status=col.dataset.status; await fetch('/api/manager/tasks',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,status})}); loadTasks();});});

document.getElementById('create-task').addEventListener('click',async e=>{const title=document.getElementById('task-title').value.trim(); if(!title) return alert('Title required');const payload={title,assignee:document.getElementById('task-assignee').value,description:document.getElementById('task-desc').value,priority:document.getElementById('task-priority').value,status:'todo'};await fetch('/api/manager/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); document.getElementById('task-title').value=''; document.getElementById('task-desc').value=''; loadTasks();});

async function loadModels(){const j = await api('/api/manager/models');const node = document.getElementById('models-list'); node.innerHTML='';node.appendChild(el('<div style="font-size:13px;margin-bottom:8px">Available models:</div>'));j.models.forEach(m=>{const row=el(`<div style="margin-bottom:6px"><code style="font-size:12px">${m}</code> ${j.default===m?'<strong>(default)</strong>':''} <button data-m="${m}" class="btn" style="background:#0ea5a4;margin-left:8px">Use</button></div>`); row.querySelector('button').addEventListener('click',async ()=>{document.getElementById('model-input').value=m}); node.appendChild(row)});}

document.getElementById('preload-model').addEventListener('click',async ()=>{const model=document.getElementById('model-input').value.trim(); if(!model) return alert('model path required'); const j=await api('/api/manager/models/preload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model})}); alert(j.ok? 'Default model set' : ('Error: '+(j.error||'unknown'))); loadModels();});

document.getElementById('run-tests').addEventListener('click',async ()=>{document.getElementById('test-status').innerText='Queued...'; const r=await api('/api/manager/run_tests',{method:'POST'}); if(!r.ok){document.getElementById('test-status').innerText='Failed to start'; return;} pollTests();});

async function pollTests(){document.getElementById('test-status').innerText='Running...'; const j=await api('/api/manager/run_tests/status'); if(j.running){document.getElementById('test-output').innerText=j.output||''; setTimeout(pollTests,2000); return;} document.getElementById('test-status').innerText='Last run: '+(j.finished_at||''); document.getElementById('test-output').innerText=j.output||'';}

loadTasks(); loadModels(); pollTests();

</script></body></html>'''

    return html_page


@app.route('/api/manager/tasks', methods=['GET','POST','PUT','DELETE'])

def api_manager_tasks():

    try:

        if request.method == 'GET':

            return jsonify(_load_manager_tasks())

        data_in = request.get_json(silent=True) or {}

        tasks = _load_manager_tasks()

        if request.method == 'POST':

            new = {

                'id': str(uuid.uuid4()),

                'title': data_in.get('title') or 'Untitled',

                'description': data_in.get('description') or '',

                'assignee': data_in.get('assignee') or '',

                'priority': data_in.get('priority') or 'medium',

                'status': data_in.get('status') or 'todo',

                'created_at': datetime.utcnow().isoformat()

            }

            tasks.append(new)

            _save_manager_tasks(tasks)

            return jsonify(new)

        if request.method == 'PUT':

            tid = data_in.get('id')

            if not tid:

                return jsonify({'error':'id required'}), 400

            updated=False

            for t in tasks:

                if t.get('id')==tid:

                    # update allowed fields

                    for k in ('title','description','assignee','priority','status'):

                        if k in data_in:

                            t[k]=data_in[k]

                    t['updated_at']=datetime.utcnow().isoformat()

                    updated=True

                    break

            if not updated:

                return jsonify({'error':'task not found'}), 404

            _save_manager_tasks(tasks)

            return jsonify({'ok':True})

        if request.method == 'DELETE':

            tid = request.args.get('id')

            if not tid:

                return jsonify({'error':'id required'}), 400

            tasks=[t for t in tasks if t.get('id')!=tid]

            _save_manager_tasks(tasks)

            return jsonify({'ok':True})

    except Exception as e:

        app.logger.exception('Manager tasks error')

        return jsonify({'error': str(e)}), 500


@app.route('/api/manager/models', methods=['GET'])

def api_manager_models():

    try:

        models_dir = Path.cwd() / 'models'

        models = []

        if models_dir.exists():

            for p in sorted(models_dir.glob('*')):

                if p.is_file():

                    models.append(str(p.relative_to(Path.cwd())))

        default = None

        cfg = Path(__file__).parent / 'data' / 'echo_model.json'

        if cfg.exists():

            try:

                default = json.loads(cfg.read_text(encoding='utf-8')).get('model')

                if default and default.startswith(str(Path.cwd())):

                    default = str(Path(default).relative_to(Path.cwd()))

            except Exception:

                app.logger.exception('Failed reading default model')

        return jsonify({'models': models, 'default': default})

    except Exception as e:

        app.logger.exception('Failed to list models')

        return jsonify({'error': str(e)}), 500


@app.route('/api/manager/models/preload', methods=['POST'])

def api_manager_models_preload():

    try:

        data_in = request.get_json(silent=True) or {}

        model = data_in.get('model')

        if not model:

            return jsonify({'error':'model required'}), 400

        # resolve to absolute path

        p = Path(model)

        if not p.is_absolute():

            p = Path.cwd() / model

        if not p.exists():

            return jsonify({'error':'model not found', 'path': str(p)}), 404

        cfg = Path(__file__).parent / 'data' / 'echo_model.json'

        cfg.parent.mkdir(parents=True, exist_ok=True)

        cfg.write_text(json.dumps({'model': str(p)}), encoding='utf-8')

        return jsonify({'ok':True, 'model': str(p)})

    except Exception as e:

        app.logger.exception('Failed to set default model')

        return jsonify({'error': str(e)}), 500


def _run_tests_background():

    try:

        _manager_tests_file.parent.mkdir(parents=True, exist_ok=True)

        start = datetime.utcnow().isoformat()

        _manager_tests_file.write_text(json.dumps({'running': True, 'started_at': start}), encoding='utf-8')

        cmd = [sys.executable, '-m', 'pytest', '-q']

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(Path(__file__).parent))

        out, _ = proc.communicate()

        output = out.decode('utf-8', errors='replace') if out else ''

        finished = datetime.utcnow().isoformat()

        _manager_tests_file.write_text(json.dumps({'running': False, 'started_at': start, 'finished_at': finished, 'exit_code': proc.returncode, 'output': output}), encoding='utf-8')

    except Exception:

        app.logger.exception('Test runner failed')

        _manager_tests_file.write_text(json.dumps({'running': False, 'error': 'runner failure'}), encoding='utf-8')


@app.route('/api/manager/run_tests', methods=['POST'])

def api_manager_run_tests():

    try:

        # start background thread

        t = threading.Thread(target=_run_tests_background, daemon=True)

        t.start()

        return jsonify({'ok': True})

    except Exception as e:

        app.logger.exception('Failed to start tests')

        return jsonify({'error': str(e)}), 500


@app.route('/api/manager/run_tests/status', methods=['GET'])

def api_manager_run_tests_status():

    try:

        if not _manager_tests_file.exists():

            return jsonify({'running': False})

        return jsonify(json.loads(_manager_tests_file.read_text(encoding='utf-8') or '{}'))

    except Exception as e:

        app.logger.exception('Failed to read test status')

        return jsonify({'error': str(e)}), 500


@app.route('/features')
def features_page():
    """Serve the Feature Management page."""
    try:
        p = Path(__file__).resolve().parent / 'features' / 'templates' / 'feature_manager.html'
        if p.exists():
            return p.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception:
        app.logger.exception('Failed to serve feature_manager.html')
    return jsonify({'error': 'Feature manager not available'}), 404


@app.route('/api/features/enabled')
def api_features_enabled():
    """Return list of enabled features for the toolbar."""
    if not FEATURE_MANAGER_AVAILABLE:
        return jsonify([])
    try:
        fm = get_feature_manager()
        if fm is None:
            return jsonify([])
        enabled = []
        # Include features loaded from the feature manager
        for name, handler in fm.features.items():
            if handler.config.enabled:
                enabled.append({
                    'key': handler.config.name,
                    'label': handler.config.display_name,
                    'addon': 'features',
                    'description': handler.config.description
                })
        # Include features from feature configs that are marked enabled
        for name, config in fm.feature_configs.items():
            if config.enabled and name not in fm.features:
                enabled.append({
                    'key': config.name,
                    'label': config.display_name,
                    'addon': 'features',
                    'description': config.description
                })
        return jsonify(enabled)
    except Exception as e:
        app.logger.exception('Failed to list enabled features')
        return jsonify([])


@app.route('/api/features/settings', methods=['GET', 'POST'])
def api_features_settings():
    """Get or save API management settings."""
    settings_file = Path(__file__).resolve().parent / 'api_settings.json'
    
    if request.method == 'GET':
        # Load settings from file
        try:
            if settings_file.exists():
                settings = json.loads(settings_file.read_text(encoding='utf-8'))
                return jsonify(settings)
            else:
                # Return default settings
                return jsonify({
                    'core_features': {
                        'masterchief_code_ui': True,
                        'web_ide': True,
                        'caf_generator': True,
                        'echo_chat': True
                    },
                    'development_tools': {
                        'github_integration': True,
                        'azure_integration': True,
                        'cloud_dashboard': True,
                        'pipelines': True
                    },
                    'system_management': {
                        'rbac': True,
                        'notifications': True,
                        'marketplace': True,
                        'app_management': True
                    },
                    'advanced_features': {
                        'echo_memory': True,
                        'scenario_bot': True,
                        'irc_bridge': True,
                        'data_ingestion': True
                    }
                })
        except Exception as e:
            app.logger.exception('Failed to load API settings')
            return jsonify({'error': 'Failed to load settings'}), 500
    
    elif request.method == 'POST':
        # Save settings to file
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Validate the structure
            required_categories = ['core_features', 'development_tools', 'system_management', 'advanced_features']
            for category in required_categories:
                if category not in data:
                    return jsonify({'error': f'Missing category: {category}'}), 400
            
            # Save to file
            settings_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
        except Exception as e:
            app.logger.exception('Failed to save API settings')
            return jsonify({'error': 'Failed to save settings'}), 500


@app.route('/feature/run/<path:feature_key>', methods=['POST'])
def feature_run(feature_key):
    """Run a feature by key. Supports feature manager features and addon-registered features."""
    if not FEATURE_MANAGER_AVAILABLE:
        return jsonify({'success': False, 'error': 'Feature manager not available'}), 503
    try:
        fm = get_feature_manager()
        if fm is None:
            return jsonify({'success': False, 'error': 'Feature manager not initialized'}), 503
        data = request.get_json(silent=True) or {}
        # Look up the feature in loaded features
        if feature_key in fm.features:
            handler = fm.features[feature_key]
            if handler.instance and callable(getattr(handler.instance, 'run', None)):
                result = handler.instance.run(**data)
                return jsonify({'success': True, 'result': result})
            else:
                return jsonify({'success': True, 'result': f'Feature {feature_key} is enabled but has no run method'})
        # Check feature configs (not yet loaded)
        if feature_key in fm.feature_configs:
            return jsonify({'success': False, 'error': f'Feature {feature_key} is configured but not enabled. Enable it first.'})
        return jsonify({'success': False, 'error': f'Feature {feature_key} not found'}), 404
    except Exception as e:
        app.logger.exception('Failed to run feature %s', feature_key)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/web_tf_wizard')
def web_tf_wizard():
    """Serve the TF Wizard static page if present (append-only safe route)."""
    try:
        p = Path(__file__).resolve().parent / 'web_tf_wizard.html'
        if p.exists():
            return _with_archetype_client(p.read_text(encoding='utf-8')), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception:
        app.logger.exception('Failed to serve web_tf_wizard.html')
    return redirect(url_for('web_ide'))


@app.route('/sys/api/services')
def sys_api_services():
    """Return currently running addon services and their status."""
    try:
        running = app.config.get('running_services', {})
        services = []
        for name, svc in running.items():
            proc = svc.get('process')
            alive = proc is not None and proc.poll() is None
            services.append({
                'name':        name,
                'status':      'running' if alive else 'stopped',
                'pid':         svc.get('pid'),
                'port':        svc.get('port'),
                'entry_point': svc.get('entry_point'),
                'type':        svc.get('type'),
                'start_time':  svc.get('start_time'),
            })
        # Also surface the main app itself
        import os as _os
        services.insert(0, {
            'name':   'masterchief (main)',
            'status': 'running',
            'pid':    _os.getpid(),
            'port':   8080,
            'entry_point': 'main.py',
            'type':   'python',
        })
        return jsonify({'services': services})
    except Exception as exc:
        return jsonify({'error': str(exc), 'services': []}), 500


# ── Orphan Sweep routes ──────────────────────────────────────

@app.route('/sys/api/orphan-sweep/start', methods=['POST'])
def sys_orphan_sweep_start():
    """Begin an orphan sweep.
    Body JSON: {orphan_paths: [...], health_urls: [...], dry_run: bool}
    """
    try:
        import sys_diagnostics as _sd
        body         = request.get_json(force=True, silent=True) or {}
        orphan_paths = body.get('orphan_paths', [])
        default_url  = f'http://127.0.0.1:{app.config.get("MC_PORT", 8080)}/'
        health_urls  = body.get('health_urls') or [default_url]
        dry_run      = bool(body.get('dry_run', False))
        if not orphan_paths:
            return jsonify({'error': 'No orphan_paths provided'}), 400
        started = _sd.start_sweep(orphan_paths, health_urls, dry_run)
        if not started:
            return jsonify({'error': 'A sweep is already running'}), 409
        return jsonify({'status': 'started', 'files': len(orphan_paths), 'dry_run': dry_run})
    except Exception as exc:
        app.logger.exception('orphan_sweep_start error')
        return jsonify({'error': str(exc)}), 500


@app.route('/sys/api/orphan-sweep/stream')
def sys_orphan_sweep_stream():
    """SSE stream — yields real-time sweep events as JSON lines."""
    import sys_diagnostics as _sd

    def _generate():
        yield 'data: {"type":"connected"}\n\n'
        yield from _sd.sweep_events(timeout=600)

    return app.response_class(
        _generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':     'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection':        'keep-alive',
        },
    )


@app.route('/sys/api/orphan-sweep/abort', methods=['POST'])
def sys_orphan_sweep_abort():
    """Ask a running sweep to stop after its current file."""
    import sys_diagnostics as _sd
    _sd.abort_sweep()
    return jsonify({'status': 'abort requested'})


@app.route('/sys/api/export-active')
def sys_export_active():
    """ZIP download of all active app files as identified by the code scanner."""
    import io, zipfile, datetime
    import sys_diagnostics as _sd
    try:
        data = _sd.get_cached_scan()
        active_rel = {f['rel_path'] for f in data.get('files', []) if f.get('status') == 'active'}
        always_include = {
            'main.py', 'requirements.txt', 'config.yml', 'Dockerfile',
            'docker-compose.yml', '.gitignore', 'README.md', 'CHANGELOG.md',
            'setup.py', 'pytest.ini', 'MANIFEST.in',
        }
        workspace = Path(app.root_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for rel in sorted(active_rel | always_include):
                fpath = workspace / rel
                if fpath.exists() and fpath.is_file():
                    zf.write(fpath, rel)
        buf.seek(0)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(buf, as_attachment=True,
                         download_name=f'masterchief_active_{ts}.zip',
                         mimetype='application/zip')
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/sys/scm')
def sys_scm():
    """Source control manager — git status, commit, push, pull."""
    try:
        from templates.scm import SCM_TEMPLATE
        return render_template_string(SCM_TEMPLATE)
    except Exception as exc:
        return f'<pre style="color:red">SCM load error: {exc}</pre>', 500


@app.route('/sys/api/scm/status')
def sys_scm_status():
    """Return current git status, branch, and last 20 commits."""
    import subprocess
    def _run(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               cwd=app.root_path, timeout=10)
            return r.stdout.strip(), r.returncode
        except Exception as ex:
            return str(ex), 1
    branch, _  = _run(['git', 'branch', '--show-current'])
    status_out, _ = _run(['git', 'status', '--porcelain'])
    log_out,    _ = _run(['git', 'log', '--oneline', '-20'])
    staged, unstaged = [], []
    for line in status_out.splitlines():
        if not line:
            continue
        xy, fname = line[:2], line[3:]
        # Skip Claude's internal worktree directories (nested repos, not user files)
        if fname.startswith('.claude/') or fname.startswith('claude/') or '/.claude/' in fname:
            continue
        if xy[0] not in (' ', '?'):
            staged.append({'status': xy[0], 'file': fname})
        if xy[1] != ' ':
            unstaged.append({'status': xy[1] if xy[1] != '?' else '?', 'file': fname})
    commits = []
    for line in log_out.splitlines():
        parts = line.split(' ', 1)
        commits.append({'hash': parts[0], 'message': parts[1] if len(parts) > 1 else ''})
    return jsonify({'branch': branch, 'staged': staged, 'unstaged': unstaged, 'commits': commits})


@app.route('/sys/api/scm/commit', methods=['POST'])
def sys_scm_commit():
    """Stage selected files and create a commit."""
    import subprocess
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    files   = data.get('files') or []
    if not message:
        return jsonify({'ok': False, 'error': 'Commit message required'}), 400
    def _run(cmd):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=app.root_path, timeout=30)
        return (r.stdout + r.stderr).strip(), r.returncode
    if files:
        for f in files:
            # Normalize path separators for Windows
            f_norm = f.replace('\\', '/')
            out, rc = _run(['git', 'add', '--', f_norm])
            if rc != 0:
                return jsonify({'ok': False, 'error': 'Stage failed for ' + f_norm + ': ' + out}), 500
    else:
        out, rc = _run(['git', 'add', '-A'])
        if rc != 0:
            return jsonify({'ok': False, 'error': 'Stage all failed: ' + out}), 500
    # Verify something is actually staged before committing
    staged_check, _ = _run(['git', 'diff', '--cached', '--name-only'])
    if not staged_check.strip():
        return jsonify({'ok': False,
                        'error': 'Nothing to commit — no staged changes detected. '
                                 'The selected files may already be clean or cannot be staged '
                                 '(e.g. nested git repositories).'}), 400
    out, rc = _run(['git', 'commit', '-m', message])
    if rc != 0:
        return jsonify({'ok': False, 'error': out}), 500
    return jsonify({'ok': True, 'output': out})


@app.route('/sys/api/scm/push', methods=['POST'])
def sys_scm_push():
    """Push current branch to origin."""
    import subprocess
    br = subprocess.run(['git', 'branch', '--show-current'],
                        capture_output=True, text=True, cwd=app.root_path)
    branch = br.stdout.strip() or 'main'
    r = subprocess.run(['git', 'push', 'origin', branch],
                        capture_output=True, text=True, cwd=app.root_path, timeout=60)
    output = (r.stdout + '\n' + r.stderr).strip()
    return jsonify({'ok': r.returncode == 0, 'output': output})


@app.route('/sys/api/scm/pull', methods=['POST'])
def sys_scm_pull():
    """Pull latest from remote."""
    import subprocess
    r = subprocess.run(['git', 'pull'],
                        capture_output=True, text=True, cwd=app.root_path, timeout=60)
    output = (r.stdout + '\n' + r.stderr).strip()
    return jsonify({'ok': r.returncode == 0, 'output': output})


# Isolated add-on features (app_features/) and linked blueprints. Add new features there, not in this file.
from managers.feature_loader import load_features as _load_features
_load_features(app, Path(__file__).parent, HTML_TEMPLATE, _admin_page_or_error, _admin_post_guard,
               audit=lambda action, **details: _echo_operator_audit(action, **details))


if __name__=='__main__':

    import argparse

    parser=argparse.ArgumentParser(description='MasterChief DevOps Platform')

    parser.add_argument('--debug',action='store_true',help='Run in debug mode')

    parser.add_argument('--port',type=int,default=8080,help='Port to run on (default: 8080)')
    parser.add_argument('--host',default='0.0.0.0',help='Interface to bind (default: 0.0.0.0)')

    args=parser.parse_args()

    print('='*70)
    print('MasterChief DevOps Platform')
    print('='*70)
    if args.debug:
        print('⚠️  Running in DEBUG mode - Not for production!')
    print('='*70)

    # perform runtime chat initialization (load model if configured)

    try:

        init_chat()

    except Exception:

        app.logger.exception('Startup chat initialization failed')

    # Auto-load addon modules registered for startup
    try:
        _autoload_file = Path(__file__).parent / 'data' / 'uploads' / 'modules_autoload.json'
        if _autoload_file.exists():
            import importlib.util as _ilu
            _autoload_list = json.loads(_autoload_file.read_text(encoding='utf-8'))
            for _mod_name in _autoload_list:
                try:
                    _addon_py = Path(__file__).parent / 'data' / 'uploads' / 'extracted' / _mod_name / 'addon.py'
                    if _addon_py.exists():
                        _spec = _ilu.spec_from_file_location(f'addon_{_mod_name}', str(_addon_py))
                        if _spec and _spec.loader:
                            _m = _ilu.module_from_spec(_spec)
                            _spec.loader.exec_module(_m)
                            if hasattr(_m, 'init'):
                                _m.init(app)
                                print(f'✅ Auto-loaded module: {_mod_name}')
                except Exception as _e:
                    print(f'⚠️  Failed to auto-load module {_mod_name}: {_e}')
    except Exception:
        pass

    # Start server — auto-advance port if the default is already taken
    import socket as _socket
    _start_port = args.port
    _port = _start_port
    while True:
        # Quick pre-check so we can print a friendly message
        _sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        _sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        try:
            _sock.bind(('0.0.0.0', _port))
            _sock.close()
            break   # port is free
        except OSError:
            _sock.close()
            if _port == _start_port:
                print(f'⚠️  Port {_port} is already in use — trying next available port…')
            _port += 1
            if _port > _start_port + 20:
                print(f'❌  Could not find a free port in range {_start_port}–{_port - 1}.')
                print('   Close other MasterChief instances or specify --port <num>')
                raise SystemExit(1)

    if _port != _start_port:
        print(f'✅  Using port {_port} instead (http://localhost:{_port})')
    else:
        print(f'Dashboard: http://localhost:{_port}')

    # Store resolved port so addons and routes can reference it
    app.config['MC_PORT']     = _port
    app.config['MC_BASE_URL'] = f'http://127.0.0.1:{_port}'

    try:
        app.run(host=args.host, port=_port, debug=args.debug, threaded=True)
    except OSError as e:
        if 'Windows error 6' in str(e):
            print(f"⚠️  Windows console error encountered, but server should be running on http://localhost:{_port}")
            print("This is a known Windows console handle issue - the application is still functional.")
            import time
            while True:
                time.sleep(1)
        else:
            raise
