from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, render_template_string, request, get_flashed_messages

from templates.base import HTML_TEMPLATE
from utils.core_scripts import scan_core_scripts, dry_check_script, run_script, import_script_to_module
from utils.feature_flags import is_feature_enabled

try:
    from auth_module import requires_permission
except Exception:
    def requires_permission(_permission):
        def decorator(func):
            return func
        return decorator


core_scripts_bp = Blueprint('core_scripts', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _core_scripts_enabled() -> bool:
    return is_feature_enabled(_root(), 'core_scripts', logger=current_app.logger)


@core_scripts_bp.route('/core-scripts')
@requires_permission('dashboard')
def core_scripts_page():
    if not _core_scripts_enabled():
        return ('<h2>Core Scripts is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)

    scripts = scan_core_scripts(_root())
    content = render_template('core_scripts.html', scripts=scripts)
    return render_template_string(
        HTML_TEMPLATE.replace('{% block content %}{% endblock %}', content),
        request=request,
        get_flashed_messages=get_flashed_messages,
    )


@core_scripts_bp.route('/api/core-scripts', methods=['GET'])
def api_core_scripts():
    try:
        return jsonify({'ok': True, 'scripts': scan_core_scripts(_root())})
    except Exception as exc:
        current_app.logger.exception('Failed to scan core scripts')
        return jsonify({'ok': False, 'error': str(exc)}), 500


@core_scripts_bp.route('/api/core-scripts/dry-check', methods=['POST'])
def api_core_scripts_dry_check():
    data_in = request.get_json(silent=True) or {}
    script_path = str(data_in.get('path') or '').strip()
    if not script_path:
        return jsonify({'ok': False, 'error': 'path required'}), 400
    return jsonify(dry_check_script(_root(), script_path))


@core_scripts_bp.route('/api/core-scripts/run', methods=['POST'])
def api_core_scripts_run():
    data_in = request.get_json(silent=True) or {}
    script_path = str(data_in.get('path') or '').strip()
    if not script_path:
        return jsonify({'ok': False, 'error': 'path required'}), 400
    return jsonify(run_script(_root(), script_path))


@core_scripts_bp.route('/api/core-scripts/import-module', methods=['POST'])
def api_core_scripts_import_module():
    data_in = request.get_json(silent=True) or {}
    script_path = str(data_in.get('path') or '').strip()
    module_name = str(data_in.get('module_name') or '').strip()
    if not script_path or not module_name:
        return jsonify({'ok': False, 'error': 'path and module_name required'}), 400

    result = import_script_to_module(_root(), script_path, module_name)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code
