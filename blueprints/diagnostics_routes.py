from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template_string, request

from utils.feature_flags import is_feature_enabled


diagnostics_bp = Blueprint('diagnostics_routes', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _enabled() -> bool:
    try:
        return is_feature_enabled(_root(), 'diagnostics', logger=current_app.logger)
    except Exception:
        current_app.logger.exception('Diagnostics feature flag check failed')
        return True


@diagnostics_bp.route('/sys/diagnostics')
def sys_diagnostics():
    """MasterChief full-repo system diagnostics page."""
    if not _enabled():
        return ('<h2>System Diagnostics is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    try:
        from templates.diagnostics import DIAGNOSTICS_TEMPLATE
        return render_template_string(DIAGNOSTICS_TEMPLATE)
    except Exception as exc:
        return f'<pre style="color:red">Diagnostics load error: {exc}</pre>', 500


@diagnostics_bp.route('/sys/api/scan')
def sys_api_scan():
    """Run full AST workspace scan and return JSON diagnostics data."""
    if not _enabled():
        return jsonify({'error': 'diagnostics disabled by feature flag'}), 503
    try:
        import concurrent.futures as concurrent_futures
        import sys_diagnostics as diagnostics_module

        force = request.args.get('force', '0') == '1'
        with concurrent_futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(diagnostics_module.get_cached_scan, force)
            data = future.result(timeout=120)
        return jsonify(data)
    except Exception as exc:
        current_app.logger.exception('sys_api_scan error')
        return jsonify({'error': str(exc)}), 500


@diagnostics_bp.route('/sys/api/file')
def sys_api_file():
    """Return source file content for the inspector panel."""
    if not _enabled():
        return jsonify({'error': 'diagnostics disabled by feature flag'}), 503
    rel_path = request.args.get('path', '')
    line = int(request.args.get('line', 0) or 0)
    if not rel_path:
        return jsonify({'error': 'path parameter required'}), 400

    try:
        import sys_diagnostics as diagnostics_module

        data = diagnostics_module.get_file_content(rel_path, line)
        if request.args.get('raw'):
            ctype = {
                '.py': 'text/x-python',
                '.html': 'text/html',
                '.js': 'application/javascript',
                '.css': 'text/css',
                '.json': 'application/json',
                '.md': 'text/markdown',
            }.get('.' + rel_path.rsplit('.', 1)[-1], 'text/plain')
            return data.get('content', ''), 200, {'Content-Type': ctype + '; charset=utf-8'}
        return jsonify(data)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
