import io
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file


orphan_bp = Blueprint('orphan_routes', __name__)


@orphan_bp.route('/sys/api/orphan-sweep/start', methods=['POST'])
def sys_orphan_sweep_start():
    """Begin an orphan sweep."""
    try:
        import sys_diagnostics as diagnostics_module

        body = request.get_json(force=True, silent=True) or {}
        orphan_paths = body.get('orphan_paths', [])
        default_url = f"http://127.0.0.1:{current_app.config.get('MC_PORT', 8080)}/"
        health_urls = body.get('health_urls') or [default_url]
        dry_run = bool(body.get('dry_run', False))

        if not orphan_paths:
            return jsonify({'error': 'No orphan_paths provided'}), 400

        started = diagnostics_module.start_sweep(orphan_paths, health_urls, dry_run)
        if not started:
            return jsonify({'error': 'A sweep is already running'}), 409

        return jsonify({'status': 'started', 'files': len(orphan_paths), 'dry_run': dry_run})
    except Exception as exc:
        current_app.logger.exception('orphan_sweep_start error')
        return jsonify({'error': str(exc)}), 500


@orphan_bp.route('/sys/api/orphan-sweep/stream')
def sys_orphan_sweep_stream():
    """SSE stream for real-time sweep events."""
    import sys_diagnostics as diagnostics_module

    def _generate():
        yield 'data: {"type":"connected"}\n\n'
        yield from diagnostics_module.sweep_events(timeout=600)

    return current_app.response_class(
        _generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@orphan_bp.route('/sys/api/orphan-sweep/abort', methods=['POST'])
def sys_orphan_sweep_abort():
    """Ask a running sweep to stop after current file."""
    import sys_diagnostics as diagnostics_module

    diagnostics_module.abort_sweep()
    return jsonify({'status': 'abort requested'})


@orphan_bp.route('/sys/api/export-active')
def sys_export_active():
    """ZIP download of active app files identified by scanner."""
    import sys_diagnostics as diagnostics_module

    try:
        data = diagnostics_module.get_cached_scan()
        active_rel = {row['rel_path'] for row in data.get('files', []) if row.get('status') == 'active'}
        always_include = {
            'main.py',
            'requirements.txt',
            'config.yml',
            'Dockerfile',
            'docker-compose.yml',
            '.gitignore',
            'README.md',
            'CHANGELOG.md',
            'setup.py',
            'pytest.ini',
            'MANIFEST.in',
        }

        workspace = Path(current_app.root_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for rel in sorted(active_rel | always_include):
                fpath = workspace / rel
                if fpath.exists() and fpath.is_file():
                    zip_file.write(fpath, rel)

        buf.seek(0)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            buf,
            as_attachment=True,
            download_name=f'masterchief_active_{ts}.zip',
            mimetype='application/zip',
        )
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500
