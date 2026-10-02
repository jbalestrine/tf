import sys
from flask import Blueprint, jsonify, current_app, request
from pathlib import Path
from datetime import datetime

# Direct routing link to our fixed engine runner
from utils.core_scripts import run_script

ide_bp = Blueprint('ide', __name__)

@ide_bp.route('/api/ide/scripts')
def api_ide_scripts():
    files = []
    try:
        scripts_dir = Path(current_app.config.get('SCRIPTS_FOLDER', 'data/scripts'))
        for p in sorted(scripts_dir.glob('*')):
            if p.is_file():
                files.append({
                    'name': p.name, 
                    'size': p.stat().st_size, 
                    'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat()
                })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({'ok': True, 'files': files})


@ide_bp.route('/api/ide/execute', methods=['POST'])
def api_ide_execute():
    try:
        data_in = request.get_json(silent=True) or {}
        
        # Flexibly handle whatever path parameter key your frontend UI payload passes
        script_name = data_in.get('script_name') or data_in.get('path') or data_in.get('name')
        if not script_name:
            return jsonify({'ok': False, 'error': 'No target script specified'}), 400

        # Point directly to your active configuration path directory
        base_dir = Path(current_app.config.get('SCRIPTS_FOLDER', 'data/scripts')).resolve()

        # Execute using our fixed string-handling engine utility
        result = run_script(base_dir, script_name)
        return jsonify(result)

    except Exception as e:
        current_app.logger.exception("Web IDE application runner encountered an unexpected crash")
        return jsonify({'ok': False, 'error': str(e)}), 500
