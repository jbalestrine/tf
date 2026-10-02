import html
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from renderers import render_resources_page

try:
    from auth_module import requires_permission
except Exception:
    def requires_permission(_permission):
        def decorator(func):
            return func
        return decorator


resources_bp = Blueprint('resources_bp', __name__)


def _resources_dir() -> Path:
    p = Path(current_app.root_path).resolve() / 'data' / 'resources'
    p.mkdir(parents=True, exist_ok=True)
    return p


def _resource_id_for(category: str, filename: str) -> str:
    return f"{category}:{filename}"


def _resources_index_file() -> Path:
    return _resources_dir() / 'index.json'


def _ingest_tasks_file() -> Path:
    return _resources_dir() / 'ingest_tasks.json'


def _load_resources_index():
    try:
        index_file = _resources_index_file()
        if index_file.exists():
            try:
                return json.loads(index_file.read_text(encoding='utf-8'))
            except Exception:
                return {}

        idx = {}
        for cat_dir in _resources_dir().iterdir():
            if not cat_dir.is_dir():
                continue
            for p in cat_dir.iterdir():
                if p.is_file():
                    rid = _resource_id_for(cat_dir.name, p.name)
                    is_persona = (cat_dir.name.lower() == 'personality')
                    idx[rid] = {
                        'id': rid,
                        'filename': p.name,
                        'category': cat_dir.name,
                        'path': str(p),
                        'persona': is_persona,
                        'uploaded_at': datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                    }
        _save_resources_index(idx)
        return idx
    except Exception:
        return {}


def _save_resources_index(idx: dict):
    try:
        index_file = _resources_index_file()
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(idx, indent=2), encoding='utf-8')
    except Exception:
        current_app.logger.exception('Failed to save resources index')


def _load_ingest_tasks():
    try:
        tasks_file = _ingest_tasks_file()
        if tasks_file.exists():
            try:
                return json.loads(tasks_file.read_text(encoding='utf-8'))
            except Exception:
                return {}
        return {}
    except Exception:
        return {}


def _save_ingest_tasks(tasks: dict):
    try:
        tasks_file = _ingest_tasks_file()
        tasks_file.parent.mkdir(parents=True, exist_ok=True)
        tasks_file.write_text(json.dumps(tasks, indent=2), encoding='utf-8')
    except Exception:
        current_app.logger.exception('Failed to save ingest tasks')


@resources_bp.route('/resources')
@requires_permission('resources')
def resources_list():
    return render_resources_page()


@resources_bp.route('/resources/preview')
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
        return f'<pre style="white-space:pre-wrap;">{html.escape(text[:4000])}</pre>'
    except Exception:
        return 'binary or unreadable', 400


@resources_bp.route('/resources/load_options')
def resources_load_options():
    rid = request.args.get('id')
    sid = request.args.get('session_id', '')
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
    <form method=\"post\" action=\"/api/resources/load\">
    <input type=\"hidden\" name=\"id\" value=\"{html.escape(rid)}\">
    <input type=\"hidden\" name=\"session_id\" value=\"{html.escape(sid)}\">
    <label><input type=\"checkbox\" name=\"for_ingestion\" checked> Ingest into session now</label><br>
    <label><input type=\"checkbox\" name=\"for_training\"> Use for training</label><br>
    <label><input type=\"checkbox\" name=\"use_persona\" {use_persona_checked}> Enable persona for this session</label><br>
    <button type=\"submit\">Load & Ingest</button>
    </form>
    <form method=\"post\" action=\"/api/resources/enqueue_ingest\" style=\"margin-top:10px;\">
    <input type=\"hidden\" name=\"id\" value=\"{html.escape(rid)}\">
    <input type=\"hidden\" name=\"session_id\" value=\"{html.escape(sid)}\">
    <label><input type=\"checkbox\" name=\"for_training\"> Use for training</label><br>
    <button type=\"submit\">Enqueue background ingest</button>
    </form>
    <p><a href=\"/resources\">Back</a></p>
    </body></html>
    """
    return html_form


@resources_bp.route('/api/resources/list')
def api_resources_list():
    try:
        idx = _load_resources_index()
        return jsonify(idx)
    except Exception as exc:
        current_app.logger.exception('Failed to list resources')
        return jsonify({'error': str(exc)}), 500


@resources_bp.route('/api/resources/upload', methods=['POST'])
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
        cat_dir = _resources_dir() / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        allowed_exts = {'.txt', '.jsonl', '.md', '.pdf', '.json'}
        text_exts = {'.txt', '.jsonl', '.md', '.json'}
        max_bytes = 10 * 1024 * 1024

        ext = Path(filename).suffix.lower()
        if ext not in allowed_exts:
            return jsonify({'error': 'Invalid file type', 'allowed': list(allowed_exts)}), 400

        idx = _load_resources_index()
        rid = _resource_id_for(category, filename)
        if rid in idx:
            return jsonify({'error': 'Resource already exists', 'message': 'Duplicate resource detected'}), 400

        if request.content_length and request.content_length > max_bytes:
            return jsonify({'error': 'File too large', 'max_bytes': max_bytes}), 400

        stored_name = f"{uuid.uuid4().hex}_{filename}"
        filepath = cat_dir / stored_name
        f.save(filepath)

        try:
            if filepath.stat().st_size > max_bytes:
                filepath.unlink(missing_ok=True)
                return jsonify({'error': 'File too large after upload', 'max_bytes': max_bytes}), 400
        except Exception:
            pass

        persona = bool(request.form.get('persona'))
        if persona and ext not in text_exts:
            persona = False

        entry = {
            'id': rid,
            'filename': filename,
            'category': category,
            'path': str(filepath),
            'for_training': for_training,
            'for_ingestion': for_ingestion,
            'persona': persona,
            'uploaded_at': datetime.now().isoformat(),
        }

        idx[rid] = entry
        _save_resources_index(idx)

        if for_training:
            try:
                try:
                    text = filepath.read_text(encoding='utf-8')
                except Exception:
                    text = None

                from echo.chat_bot import TrainingExample, get_chat_bot

                bot = get_chat_bot()
                summary = (text or '')[:1000]
                ex = TrainingExample(user_message=f"Upload:{filename}", bot_response=summary)
                bot.training_store.add_example(ex)
            except Exception:
                current_app.logger.exception('Failed to add training example for uploaded resource')

        if persona:
            try:
                pdir = Path(current_app.root_path).resolve() / 'data' / 'personality'
                pdir.mkdir(parents=True, exist_ok=True)
                ppath = pdir / filename
                try:
                    text = filepath.read_text(encoding='utf-8')
                    ppath.write_text(text, encoding='utf-8')
                except Exception:
                    pass
            except Exception:
                current_app.logger.exception('Failed to store persona file')

        return jsonify({'ok': True, 'message': 'Uploaded', 'resource': entry})
    except Exception as exc:
        current_app.logger.exception('Upload failed')
        return jsonify({'error': str(exc)}), 500


@resources_bp.route('/api/resources/delete', methods=['POST'])
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
            current_app.logger.exception('Failed to remove resource file')

        del idx[rid]
        _save_resources_index(idx)
        return jsonify({'ok': True})
    except Exception as exc:
        current_app.logger.exception('Delete failed')
        return jsonify({'error': str(exc)}), 500


@resources_bp.route('/api/resources/enqueue_ingest', methods=['POST'])
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
        tid = f"task_{int(time.time() * 1000)}"
        tasks[tid] = {
            'id': tid,
            'resource': entry,
            'session_id': session_id,
            'status': 'pending',
            'bot_ingested': False,
            'created_at': datetime.now().isoformat(),
        }
        _save_ingest_tasks(tasks)
        return jsonify({'ok': True, 'task_id': tid})
    except Exception as exc:
        current_app.logger.exception('Enqueue failed')
        return jsonify({'error': str(exc)}), 500


@resources_bp.route('/api/resources/ingest_status')
def api_resources_ingest_status():
    try:
        tid = request.args.get('task_id')
        if not tid:
            return jsonify({'error': 'task_id required'}), 400

        tasks = _load_ingest_tasks()
        task = tasks.get(tid)
        if not task:
            return jsonify({'error': 'not found'}), 404
        return jsonify(task)
    except Exception as exc:
        current_app.logger.exception('Status failed')
        return jsonify({'error': str(exc)}), 500


@resources_bp.route('/api/resources/load', methods=['POST'])
def api_resources_load():
    try:
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

        try:
            text = p.read_text(encoding='utf-8')
            content = {'type': 'text', 'text': text}
        except Exception:
            content = {'type': 'binary', 'path': str(p), 'size': p.stat().st_size}

        for_ingestion = bool(data.get('for_ingestion'))

        from echo.chat_bot import get_chat_bot
        from echo.conversation_storage import get_storage

        storage = get_storage()
        meta = storage.get_session_meta(session_id) or {}
        loaded = meta.get('loaded_resources', {})
        loaded[rid] = {'meta': entry, 'content': content, 'loaded_at': datetime.now().isoformat()}
        meta['loaded_resources'] = loaded

        use_persona = bool(data.get('use_persona'))
        if use_persona and entry.get('persona'):
            try:
                meta['personality'] = {
                    'id': rid,
                    'enabled': True,
                    'text': content.get('text') if content.get('type') == 'text' else None,
                }
                try:
                    storage.store_message(
                        user='system',
                        message=f'Persona {entry.get("filename")} enabled for session',
                        echo_response='',
                        channel=session_id,
                    )
                except Exception:
                    current_app.logger.exception('Failed to log persona enable into session history')
            except Exception:
                current_app.logger.exception('Failed to set personality in session meta')

        storage.set_session_meta(session_id, meta)

        try:
            bot = get_chat_bot()
            if for_ingestion and hasattr(bot, 'ingest_resource'):
                try:
                    bot.ingest_resource(session_id, entry, content)
                except Exception:
                    current_app.logger.exception('Bot ingest failed, continuing')
        except Exception:
            current_app.logger.exception('Failed to get chat bot for ingest')

        return jsonify({'ok': True, 'message': 'Loaded into session', 'session_id': session_id})
    except Exception as exc:
        current_app.logger.exception('Load failed')
        return jsonify({'error': str(exc)}), 500


@resources_bp.route('/api/resources/convert_to_training', methods=['POST'])
def api_resources_convert_to_training():
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

        outdir = Path(current_app.root_path).resolve() / 'data' / 'echo_training'
        outdir.mkdir(parents=True, exist_ok=True)
        outpath = outdir / (p.stem + '.jsonl')

        helper = Path(current_app.root_path).resolve() / 'tools' / 'dataset_helper.py'
        cmd = [sys.executable, str(helper), '--resource', str(p), '--out', str(outpath)]
        proc = subprocess.run(cmd, cwd=str(Path(current_app.root_path).resolve()), capture_output=True, text=True)
        if proc.returncode != 0:
            return jsonify({'error': 'conversion failed', 'stderr': proc.stderr}), 500

        rel = outpath.relative_to(Path(current_app.root_path).resolve())
        return jsonify({'ok': True, 'training_file': str(rel)})
    except Exception as exc:
        current_app.logger.exception('Conversion failed')
        return jsonify({'error': str(exc)}), 500
