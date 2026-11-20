import subprocess
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template_string, request

from utils.feature_flags import is_feature_enabled


scm_bp = Blueprint('scm_routes', __name__)

@scm_bp.before_request
def _require_admin():
    guard = current_app.config.get('SCM_ADMIN_POST_GUARD' if request.method != 'GET' else 'SCM_ADMIN_GET_GUARD')
    if guard is None:
        return jsonify({'ok': False, 'error': 'Source Control authorization is not configured.'}), 503
    return guard()


@scm_bp.route('/sys/api/scm/commands', methods=['GET', 'POST'])
def command_center():
    from utils.git_command_center import catalog, execute
    if not _enabled():
        return jsonify({'ok': False, 'error': 'scm disabled by feature flag'}), 503
    if request.method == 'GET':
        return jsonify({'commands': catalog()})
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'ok': False, 'error': 'A JSON request is required.'}), 400
    try:
        result = execute(_root(), data.get('action'), data.get('values'), data.get('confirmation'))
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        current_app.logger.warning('Git command failed to execute: %s', exc)
        return jsonify({'ok': False, 'error': str(exc)}), 500
    return jsonify(result)


@scm_bp.route('/sys/api/scm/activity')
def file_activity():
    from utils.git_file_activity import collect
    if not _enabled():
        return jsonify({'ok': False, 'error': 'scm disabled by feature flag'}), 503
    try:
        return jsonify({'ok': True, **collect(_root())})
    except RuntimeError as exc:
        current_app.logger.warning('Git file activity failed: %s', exc)
        return jsonify({'ok': False, 'error': str(exc)}), 500


@scm_bp.route('/sys/api/scm/activity-file', methods=['GET', 'POST'])
def activity_file():
    from utils.git_activity_editor import EditConflict, load, save
    if not _enabled():
        return jsonify({'ok': False, 'error': 'scm disabled by feature flag'}), 503
    try:
        if request.method == 'GET':
            return jsonify({'ok': True, **load(_root(), request.args.get('path'))})
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'ok': False, 'error': 'A JSON request is required.'}), 400
        return jsonify({'ok': True, **save(_root(), data.get('path'), data.get('content'), data.get('version'))})
    except EditConflict as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 409
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except OSError as exc:
        current_app.logger.warning('Activity file operation failed: %s', exc)
        return jsonify({'ok': False, 'error': f'File operation failed: {exc}'}), 500


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _enabled() -> bool:
    try:
        return is_feature_enabled(_root(), 'scm', logger=current_app.logger)
    except Exception:
        current_app.logger.exception('SCM feature flag check failed')
        return False


def _run_git(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=current_app.root_path, timeout=timeout)
        return (result.stdout or ''), (result.stderr or '').strip(), result.returncode
    except Exception as exc:
        return '', str(exc), 1


@scm_bp.route('/sys/scm')
def sys_scm():
    """Source control manager page."""
    if not _enabled():
        return ('<h2>Source Control is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    try:
        from templates.scm import SCM_TEMPLATE
        return render_template_string(SCM_TEMPLATE)
    except Exception as exc:
        return f'<pre style="color:red">SCM load error: {exc}</pre>', 500


@scm_bp.route('/sys/api/scm/status')
def sys_scm_status():
    """Return current git status, branch, and last 20 commits."""
    if not _enabled():
        return jsonify({'error': 'scm disabled by feature flag'}), 503
    branch_out, branch_error, branch_rc = _run_git(['git', 'branch', '--show-current'])
    status_out, status_error, status_rc = _run_git(['git', 'status', '--porcelain', '-z'])
    log_out, log_error, log_rc = _run_git(['git', 'log', '--oneline', '-20'])
    if branch_rc or status_rc or log_rc:
        return jsonify({'error': branch_error or status_error or log_error or 'Git status failed.'}), 500

    staged = []
    unstaged = []
    entries = iter(status_out.split('\0'))
    for line in entries:
        if not line:
            continue
        xy, fname = line[:2], line[3:]
        if 'R' in xy or 'C' in xy:
            next(entries, None)
        if xy[0] not in (' ', '?'):
            staged.append({'status': xy[0], 'file': fname})
        if xy[1] != ' ':
            unstaged.append({'status': xy[1] if xy[1] != '?' else '?', 'file': fname})

    commits = []
    for line in log_out.splitlines():
        parts = line.split(' ', 1)
        commits.append({'hash': parts[0], 'message': parts[1] if len(parts) > 1 else ''})

    return jsonify({'branch': branch_out.strip(), 'staged': staged, 'unstaged': unstaged, 'commits': commits})


@scm_bp.route('/sys/api/scm/commit', methods=['POST'])
def sys_scm_commit():
    """Stage selected files and create a commit."""
    if not _enabled():
        return jsonify({'ok': False, 'error': 'scm disabled by feature flag'}), 503
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    files = data.get('files') or []
    if not message:
        return jsonify({'ok': False, 'error': 'Commit message required'}), 400

    if files:
        for file_name in files:
            file_norm = file_name.replace('\\', '/')
            _, stderr, rc = _run_git(['git', 'add', '--', file_norm], timeout=30)
            if rc != 0:
                return jsonify({'ok': False, 'error': 'Stage failed for ' + file_norm + ': ' + stderr}), 500
    else:
        return jsonify({'ok': False, 'error': 'Select at least one file explicitly.'}), 400

    staged_out, _, _ = _run_git(['git', 'diff', '--cached', '--name-only'])
    if not staged_out.strip():
        return jsonify({
            'ok': False,
            'error': 'Nothing to commit — no staged changes detected. The selected files may already be clean or cannot be staged (e.g. nested git repositories).',
        }), 400

    stdout, stderr, rc = _run_git(['git', 'commit', '-m', message], timeout=30)
    output = (stdout + '\n' + stderr).strip()
    if rc != 0:
        return jsonify({'ok': False, 'error': output}), 500
    return jsonify({'ok': True, 'output': output})


@scm_bp.route('/sys/api/scm/push', methods=['POST'])
def sys_scm_push():
    """Push current branch to origin."""
    if not _enabled():
        return jsonify({'ok': False, 'error': 'scm disabled by feature flag'}), 503
    branch_out, _, _ = _run_git(['git', 'branch', '--show-current'])
    branch = branch_out.strip()
    if not branch:
        return jsonify({'ok': False, 'error': 'Cannot push from detached HEAD.'}), 400
    stdout, stderr, rc = _run_git(['git', 'push', 'origin', branch], timeout=60)
    output = (stdout + '\n' + stderr).strip()
    return jsonify({'ok': rc == 0, 'output': output})


@scm_bp.route('/sys/api/scm/pull', methods=['POST'])
def sys_scm_pull():
    """Pull latest from remote."""
    if not _enabled():
        return jsonify({'ok': False, 'error': 'scm disabled by feature flag'}), 503
    stdout, stderr, rc = _run_git(['git', 'pull'], timeout=60)
    output = (stdout + '\n' + stderr).strip()
    return jsonify({'ok': rc == 0, 'output': output})
