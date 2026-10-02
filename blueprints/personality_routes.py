import html
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, request, url_for

from echo.conversation_storage import get_storage


personality_bp = Blueprint('personality_routes', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _personality_dirs():
    pdir1 = _root() / 'echo' / 'data' / 'personality'
    pdir2 = _root() / 'data' / 'personality'
    out = []
    if pdir1.exists():
        out.append(pdir1)
    if pdir2.exists() and pdir2 != pdir1:
        out.append(pdir2)
    return out


@personality_bp.route('/api/personality/status')
def api_personality_status():
    try:
        session_id = request.args.get('session_id') or 'default'
        storage = get_storage()
        meta = storage.get_session_meta(session_id) or {}
        return jsonify({'personality': meta.get('personality')})
    except Exception as exc:
        current_app.logger.exception('Personality status failed')
        return jsonify({'error': str(exc)}), 500


@personality_bp.route('/api/personality/list')
def api_personality_list():
    try:
        files = []
        for d in _personality_dirs():
            for p in sorted(d.glob('*')):
                if p.is_file():
                    try:
                        files.append({'name': p.name, 'size': p.stat().st_size, 'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat(), 'path': str(p)})
                    except Exception:
                        files.append({'name': p.name})
        return jsonify({'files': files})
    except Exception as exc:
        current_app.logger.exception('List personalities failed')
        return jsonify({'error': str(exc)}), 500


@personality_bp.route('/api/personality/apply', methods=['POST'])
def api_personality_apply():
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id') or 'default'
        files = data.get('files') or []
        if not files:
            return jsonify({'error': 'files required'}), 400

        parts = []
        for fname in files:
            found = None
            for d in _personality_dirs():
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

        combined = '\n\n'.join(parts)
        storage = get_storage()
        meta = storage.get_session_meta(session_id) or {}
        meta['personality'] = {'id': ','.join(files), 'enabled': True, 'files': files, 'text': combined}
        storage.set_session_meta(session_id, meta)
        return jsonify({'ok': True, 'session_id': session_id, 'files': files})
    except Exception as exc:
        current_app.logger.exception('Apply personality failed')
        return jsonify({'error': str(exc)}), 500


@personality_bp.route('/api/personality/delete', methods=['POST'])
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
            for d in _personality_dirs():
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
    except Exception as exc:
        current_app.logger.exception('Delete personalities failed')
        return jsonify({'error': str(exc)}), 500


@personality_bp.route('/api/personality/toggle', methods=['POST'])
def api_personality_toggle():
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id') or 'default'
        storage = get_storage()
        meta = storage.get_session_meta(session_id) or {}
        personality = meta.get('personality')
        if personality:
            personality['enabled'] = not personality.get('enabled', True)
        else:
            return jsonify({'error': 'No personality set for session'}), 400
        storage.set_session_meta(session_id, meta)
        return jsonify({'personality': personality})
    except Exception as exc:
        current_app.logger.exception('Toggle personality failed')
        return jsonify({'error': str(exc)}), 500


@personality_bp.route('/personality')
def personality_list():
    pdir = _root() / 'data' / 'personality'
    pdir.mkdir(parents=True, exist_ok=True)
    files = [f.name for f in pdir.glob('*') if f.is_file()]

    html_out = '<html><body><h3>Personality Files</h3><ul>'
    for fn in files:
        html_out += f'<li>{html.escape(fn)} - <a href="/personality/edit?id={html.escape(fn)}">Edit</a></li>'
    html_out += '</ul><p><a href="/resources">Back</a></p></body></html>'
    return html_out


@personality_bp.route('/personality/edit')
def personality_edit():
    fid = request.args.get('id')
    if not fid:
        return 'id required', 400

    pdir = _root() / 'data' / 'personality'
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


@personality_bp.route('/personality/save', methods=['POST'])
def personality_save():
    fid = request.form.get('id')
    content = request.form.get('content') or ''
    if not fid:
        return jsonify({'error': 'id required'}), 400

    pdir = _root() / 'data' / 'personality'
    pdir.mkdir(parents=True, exist_ok=True)
    pfile = pdir / fid

    try:
        pfile.write_text(content, encoding='utf-8')
        return redirect(url_for('personality_routes.personality_list'))
    except Exception as exc:
        current_app.logger.exception('Failed to save personality')
        return jsonify({'error': str(exc)}), 500
