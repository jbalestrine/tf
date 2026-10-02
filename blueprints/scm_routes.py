import subprocess
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template_string, request

from utils.feature_flags import is_feature_enabled


scm_bp = Blueprint('scm_routes', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _enabled() -> bool:
    try:
        return is_feature_enabled(_root(), 'scm', logger=current_app.logger)
    except Exception:
        current_app.logger.exception('SCM feature flag check failed')
        return True


def _run_git(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=current_app.root_path, timeout=timeout)
        return (result.stdout or '').strip(), (result.stderr or '').strip(), result.returncode
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
    branch_out, _, _ = _run_git(['git', 'branch', '--show-current'])
    status_out, _, _ = _run_git(['git', 'status', '--porcelain'])
    log_out, _, _ = _run_git(['git', 'log', '--oneline', '-20'])

    staged = []
    unstaged = []
    for line in status_out.splitlines():
        if not line:
            continue
        xy, fname = line[:2], line[3:]
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

    return jsonify({'branch': branch_out, 'staged': staged, 'unstaged': unstaged, 'commits': commits})


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
        _, stderr, rc = _run_git(['git', 'add', '-A'], timeout=30)
        if rc != 0:
            return jsonify({'ok': False, 'error': 'Stage all failed: ' + stderr}), 500

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
    branch = branch_out or 'main'
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
