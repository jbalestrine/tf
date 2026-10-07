from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, render_template, render_template_string, request, get_flashed_messages

from templates.base import HTML_TEMPLATE
from managers.idea_basket import IdeaBasketError, IdeaBasketManager
from utils.core_scripts import scan_core_scripts, dry_check_script, run_script
from utils.feature_flags import is_feature_enabled

try:
    from auth_module import requires_permission
except ImportError:
    from functools import wraps

    def requires_permission(_permission):
        def decorator(func):
            @wraps(func)
            def authentication_unavailable(*args, **kwargs):
                abort(503, description='Authentication is unavailable; script access is disabled.')
            return authentication_unavailable
        return decorator


core_scripts_bp = Blueprint('core_scripts', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _core_scripts_enabled() -> bool:
    return is_feature_enabled(_root(), 'core_scripts', logger=current_app.logger)


def _is_catalogued_script(script_path: str) -> bool:
    normalized_path = script_path.replace('\\', '/')
    return any(
        script['path'] == normalized_path
        for script in scan_core_scripts(_root())
    )


def _idea_basket() -> IdeaBasketManager:
    return IdeaBasketManager(_root() / "data" / "chaos_monkey_ideas.sqlite3")


@core_scripts_bp.route('/core-scripts')
@core_scripts_bp.route('/chaos-monkey')
@requires_permission('scripts')
def core_scripts_page():
    if not _core_scripts_enabled():
        return ('<h2>Core Scripts is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)

    scripts = scan_core_scripts(_root())
    categories = sorted({script['category'] for script in scripts})
    ideas = _idea_basket().list_ideas()
    idea_paths = {idea['path'] for idea in ideas}
    content = render_template(
        'core_scripts.html',
        scripts=scripts,
        categories=categories,
        ideas=ideas,
        idea_paths=idea_paths,
    )
    return render_template_string(
        HTML_TEMPLATE.replace('{% block content %}{% endblock %}', content),
        request=request,
        get_flashed_messages=get_flashed_messages,
    )


@core_scripts_bp.route('/api/core-scripts', methods=['GET'])
@requires_permission('scripts')
def api_core_scripts():
    if not _core_scripts_enabled():
        return jsonify({'ok': False, 'error': 'Chaos Monkey Area is disabled by feature flag'}), 503
    try:
        return jsonify({'ok': True, 'scripts': scan_core_scripts(_root())})
    except Exception as exc:
        current_app.logger.exception('Failed to scan core scripts')
        return jsonify({'ok': False, 'error': str(exc)}), 500


@core_scripts_bp.route('/api/core-scripts/ideas', methods=['GET'])
@requires_permission('scripts')
def api_core_script_ideas():
    if not _core_scripts_enabled():
        return jsonify({'ok': False, 'error': 'Chaos Monkey Area is disabled by feature flag'}), 503
    try:
        return jsonify({'ok': True, 'ideas': _idea_basket().list_ideas()})
    except Exception as exc:
        current_app.logger.exception('Failed to load the Chaos Monkey Ideas Basket')
        return jsonify({'ok': False, 'error': str(exc)}), 500


@core_scripts_bp.route('/api/core-scripts/ideas', methods=['POST'])
@requires_permission('scripts')
def api_core_script_idea_add():
    if not _core_scripts_enabled():
        return jsonify({'ok': False, 'error': 'Chaos Monkey Area is disabled by feature flag'}), 503
    data_in = request.get_json(silent=True) or {}
    script_path = str(data_in.get('path') or '').strip()
    note = data_in.get('note', '')
    if not script_path:
        return jsonify({'ok': False, 'error': 'path required'}), 400
    if not isinstance(note, str):
        return jsonify({'ok': False, 'error': 'note must be text'}), 400
    if not _is_catalogued_script(script_path):
        return jsonify({'ok': False, 'error': 'only scripts in the project library can be parked'}), 400
    try:
        idea = _idea_basket().add(script_path, note)
        return jsonify({'ok': True, 'idea': idea}), 201
    except IdeaBasketError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception('Failed to save a script idea')
        return jsonify({'ok': False, 'error': str(exc)}), 500


@core_scripts_bp.route('/api/core-scripts/ideas', methods=['DELETE'])
@requires_permission('scripts')
def api_core_script_idea_remove():
    if not _core_scripts_enabled():
        return jsonify({'ok': False, 'error': 'Chaos Monkey Area is disabled by feature flag'}), 503
    data_in = request.get_json(silent=True) or {}
    script_path = str(data_in.get('path') or '').strip()
    if not script_path:
        return jsonify({'ok': False, 'error': 'path required'}), 400
    try:
        removed = _idea_basket().remove(script_path)
    except IdeaBasketError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    if not removed:
        return jsonify({'ok': False, 'error': 'idea not found'}), 404
    return jsonify({'ok': True, 'path': script_path, 'source_preserved': True})


@core_scripts_bp.route('/api/core-scripts/dry-check', methods=['POST'])
@requires_permission('scripts')
def api_core_scripts_dry_check():
    if not _core_scripts_enabled():
        return jsonify({'ok': False, 'error': 'Chaos Monkey Area is disabled by feature flag'}), 503
    data_in = request.get_json(silent=True) or {}
    script_path = str(data_in.get('path') or '').strip()
    if not script_path:
        return jsonify({'ok': False, 'error': 'path required'}), 400
    if not _is_catalogued_script(script_path):
        return jsonify({'ok': False, 'error': 'script is not in the approved project library'}), 400
    return jsonify(dry_check_script(_root(), script_path))


@core_scripts_bp.route('/api/core-scripts/run', methods=['POST'])
@requires_permission('scripts')
def api_core_scripts_run():
    if not _core_scripts_enabled():
        return jsonify({'ok': False, 'error': 'Chaos Monkey Area is disabled by feature flag'}), 503
    data_in = request.get_json(silent=True) or {}
    script_path = str(data_in.get('path') or '').strip()
    if not script_path:
        return jsonify({'ok': False, 'error': 'path required'}), 400
    if not _is_catalogued_script(script_path):
        return jsonify({'ok': False, 'error': 'script is not in the approved project library'}), 400
    arguments = data_in.get('arguments', [])
    if not isinstance(arguments, list):
        return jsonify({'ok': False, 'error': 'arguments must be a list of text values'}), 400
    result = run_script(_root(), script_path, arguments)
    return jsonify(result), 200 if result.get('ok') else 400
