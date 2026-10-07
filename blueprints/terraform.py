from flask import Blueprint, jsonify, request, send_file, current_app
from pathlib import Path
from werkzeug.utils import secure_filename
import uuid
import re
import shutil
from datetime import datetime
import subprocess
import sys

terraform_bp = Blueprint('terraform', __name__)

ENTERPRISE_TF_JOBS = {}  # job_id -> generated project path
EXEC_JOBS = {}  # exec_id -> job info

def _start_job_thread(exec_id, cmd, cwd=None):
    """Start a background thread to run the command."""
    import threading
    def run_job():
        try:
            EXEC_JOBS[exec_id]['status'] = 'running'
            EXEC_JOBS[exec_id]['started_at'] = datetime.now().isoformat()
            proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            EXEC_JOBS[exec_id]['pid'] = proc.pid
            stdout, stderr = proc.communicate()
            EXEC_JOBS[exec_id]['returncode'] = proc.returncode
            EXEC_JOBS[exec_id]['finished_at'] = datetime.now().isoformat()
            EXEC_JOBS[exec_id]['status'] = 'completed' if proc.returncode == 0 else 'failed'
            EXEC_JOBS[exec_id]['stdout'] = stdout
            EXEC_JOBS[exec_id]['stderr'] = stderr
        except Exception as e:
            EXEC_JOBS[exec_id]['status'] = 'failed'
            EXEC_JOBS[exec_id]['error'] = str(e)
    
    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()

@terraform_bp.route('/api/terraform/generate', methods=['POST'])
def api_terraform_generate():
    """Generate a Terraform project on the server from a wizard payload.

    Expects JSON: { name, cloud, backend, provider_settings, variables, resources }

    Returns: { ok: True, path: <relative path> }

    """
    data = request.get_json(silent=True) or {}
    name = data.get('name') or (data.get('config') or {}).get('name') or 'tf_project'
    # sanitize name
    sf = secure_filename(name) or 'tf_project'
    try:
        from tools.terraform_wizard import WizardConfig, create_project
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Import error: {e}'}), 500

    base = Path(current_app.root_path) / 'data' / 'terraform_projects'
    out_dir = base / sf
    try:
        cfg = WizardConfig(
            name=sf,
            cloud=data.get('cloud', 'azure'),
            backend=data.get('backend'),
            provider_settings=data.get('provider_settings'),
            variables=data.get('variables'),
            resources=data.get('resources'),
        )
        create_project(cfg, out_dir)
        return jsonify({'ok': True, 'path': str(out_dir.relative_to(Path(current_app.root_path)))})
    except Exception as e:
        current_app.logger.exception('Failed to generate terraform project')
        return jsonify({'ok': False, 'error': str(e)}), 500


@terraform_bp.route('/api/terraform/validate-design', methods=['POST'])
def api_terraform_validate_design():
    """Validate Azure naming, network topology, and role assignment conflicts."""
    from core.infrastructure_validation import validate_infrastructure_design

    design = request.get_json(silent=True)
    if design is None:
        return jsonify({'ok': False, 'error': 'A JSON design object is required.'}), 400
    issues = validate_infrastructure_design(design)
    return jsonify({
        'ok': not any(issue['severity'] == 'error' for issue in issues),
        'issues': issues,
    }), 200


@terraform_bp.route('/api/terraform/run', methods=['POST'])
def api_terraform_run():
    """Run terraform actions (init|plan|deploy) asynchronously and return exec_id.

    JSON: { action: 'init'|'plan'|'deploy', dir: '<relative path under data/terraform_projects>', auto_approve: bool }

    """
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    rel = data.get('dir')
    if not action or action not in ('init', 'plan', 'deploy'):
        return jsonify({'ok': False, 'error': 'action required (init|plan|deploy)'}), 400

    base = Path(current_app.root_path) / 'data' / 'terraform_projects'
    if not rel:
        return jsonify({'ok': False, 'error': 'dir required'}), 400

    target = (base / rel).resolve()
    try:
        if not str(target).startswith(str(base.resolve())) or not target.exists():
            return jsonify({'ok': False, 'error': 'invalid dir'}), 400
    except Exception:
        return jsonify({'ok': False, 'error': 'invalid dir'}), 400

    # build command
    if action == 'init':
        cmd = ['terraform', 'init', '-input=false']
    elif action == 'plan':
        cmd = ['terraform', 'plan', '-out=tfplan', '-input=false']
    else:
        # deploy
        cmd = ['terraform', 'apply', '-auto-approve']

    exec_id = uuid.uuid4().hex
    EXEC_JOBS[exec_id] = {'id': exec_id, 'status': 'queued', 'cmd': cmd, 'pid': None, 'returncode': None, 'started_at': None, 'finished_at': None, 'cwd': str(target)}
    _start_job_thread(exec_id, cmd, cwd=str(target))
    return jsonify({'ok': True, 'exec_id': exec_id})

@terraform_bp.route('/api/terraform/ci-validate', methods=['POST'])
def api_terraform_ci_validate():
    """Trigger the terraform-validation GitHub Actions workflow for a specific module.

    JSON: { module: 'modules/terraform/azure-aks' }  — module is optional; omit to validate all.
    Requires GITHUB_TOKEN and GITHUB_REPO env vars to be set.
    """
    import os, requests as _requests
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')  # e.g. 'owner/repo'
    if not token or not repo:
        return jsonify({'ok': False, 'error': 'GITHUB_TOKEN and GITHUB_REPO env vars required'}), 500

    data = request.get_json(silent=True) or {}
    module = data.get('module', '')

    resp = _requests.post(
        f'https://api.github.com/repos/{repo}/actions/workflows/terraform-validation.yml/dispatches',
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        },
        json={'ref': 'main', 'inputs': {'module': module}},
        timeout=15,
    )
    if resp.status_code == 204:
        return jsonify({'ok': True, 'message': f'Workflow dispatched for module: {module or "all"}'})
    return jsonify({'ok': False, 'error': resp.text}), resp.status_code

@terraform_bp.route('/api/tf/validate', methods=['POST'])
def api_tf_validate():
    return jsonify({'ok': True, 'output': 'TF validate endpoint working'})

@terraform_bp.route('/api/tf/plan', methods=['POST'])
def api_tf_plan():
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
            
            # Init and plan
            proc = subprocess.run(['terraform', 'init', '-input=false'], cwd=tmpdir, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return jsonify({'ok': False, 'error': proc.stderr}), 500
            
            proc = subprocess.run(['terraform', 'plan', '-input=false'], cwd=tmpdir, capture_output=True, text=True, timeout=120)
            return jsonify({'ok': True, 'output': proc.stdout + proc.stderr}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@terraform_bp.route('/api/tf/apply', methods=['POST'])
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

@terraform_bp.route('/api/tf/destroy', methods=['POST'])
def api_tf_destroy():
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # For destroy, we need the state file, but since this is a demo, we'll assume local state
            # In a real implementation, you'd need to handle state files properly
            return jsonify({'ok': False, 'error': 'destroy not implemented for demo - requires state file'}), 501
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@terraform_bp.route('/api/tf/refresh')
def api_tf_refresh():
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            return jsonify({'ok': False, 'error': 'refresh not implemented for demo - requires state file'}), 501
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@terraform_bp.route('/api/tf/import', methods=['POST'])
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

@terraform_bp.route('/api/tf/state')
def api_tf_state():
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            return jsonify({'ok': False, 'error': 'state show not implemented for demo - requires state file'}), 501
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@terraform_bp.route('/api/tf/backup')
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
