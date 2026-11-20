"""Administrator-only, read-only GitHub CLI repository browser."""

import base64
import binascii
import json
import os
import re
import subprocess
from urllib.parse import quote

from flask import current_app, jsonify, request


def _api(endpoint, paginate=False):
    args = ['gh', 'api', '--hostname', 'github.com', endpoint]
    if paginate:
        args.extend(['--paginate', '--slurp'])
    env = os.environ.copy()
    env.update(GH_PROMPT_DISABLED='1', GIT_TERMINAL_PROMPT='0', GH_PAGER='cat')
    try:
        result = subprocess.run(args, capture_output=True, text=True, errors='replace',
                                timeout=90, stdin=subprocess.DEVNULL, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f'GitHub CLI could not complete: {exc}') from exc
    if result.returncode:
        raise RuntimeError('GitHub CLI request failed. Check login, repository access and server logs.')
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise RuntimeError('GitHub returned an invalid response.') from exc


def _repo_path(owner, repo, path):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner):
        raise ValueError('Invalid GitHub owner.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', repo) or repo in ('.', '..'):
        raise ValueError('Invalid GitHub repository name.')
    if path and any(part in ('', '.', '..') for part in path.split('/')):
        raise ValueError('Invalid repository path.')
    return f'repos/{quote(owner, safe="")}/{quote(repo, safe="")}/contents/{quote(path, safe="/")}'


def register_cli_browser(app):
    def authorize():
        guard = current_app.config.get('SCM_ADMIN_GET_GUARD')
        if guard is None:
            return jsonify({'error': 'Source Control authorization is not configured.'}), 503
        return guard()

    @app.route('/api/features/github/cli/repos')
    def github_cli_repos():
        denied = authorize()
        if denied is not None:
            return denied
        try:
            pages = _api('user/repos?per_page=100&sort=updated', paginate=True)
            if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
                raise ValueError('Invalid repository list.')
            repos = [{'name': repo['name'], 'full_name': repo['full_name'],
                      'description': repo['description'], 'stars': repo['stargazers_count'],
                      'language': repo['language']} for page in pages for repo in page]
            return jsonify({'repos': repos})
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            current_app.logger.warning('GitHub CLI repository list failed: %s', exc)
            return jsonify({'error': str(exc)}), 502

    @app.route('/api/features/github/cli/repos/<owner>/<repo>/contents')
    def github_cli_contents(owner, repo):
        denied = authorize()
        if denied is not None:
            return denied
        path = request.args.get('path', '')
        try:
            data = _api(_repo_path(owner, repo, path))
            if not isinstance(data, list):
                raise ValueError('GitHub returned a file instead of a directory.')
            contents = [{'name': item['name'], 'path': item['path'], 'type': item['type'],
                         'size': item['size'], 'last_modified': 'N/A'} for item in data]
            return jsonify({'contents': contents, 'current_path': path})
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        except (RuntimeError, KeyError, TypeError) as exc:
            current_app.logger.warning('GitHub CLI directory request failed: %s', exc)
            return jsonify({'error': 'Unable to load repository files. Check GitHub access and server logs.'}), 502

    @app.route('/api/features/github/cli/repos/<owner>/<repo>/file-content')
    def github_cli_file(owner, repo):
        denied = authorize()
        if denied is not None:
            return denied
        path = request.args.get('file_path', '')
        try:
            if not path:
                raise ValueError('File path is required.')
            data = _api(_repo_path(owner, repo, path))
            if not isinstance(data, dict) or data.get('type') != 'file' or data.get('encoding') != 'base64':
                raise ValueError('GitHub did not return a readable file.')
            content = base64.b64decode(data['content'], validate=False).decode('utf-8')
            return jsonify({'content': content, 'file_path': path})
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            return jsonify({'error': f'Cannot read this text file: {exc}'}), 400
        except (RuntimeError, KeyError, TypeError) as exc:
            current_app.logger.warning('GitHub CLI file request failed: %s', exc)
            return jsonify({'error': 'Unable to load file. Check GitHub access and server logs.'}), 502
