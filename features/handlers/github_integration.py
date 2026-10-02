"""
GitHub Integration Feature

This feature provides GitHub repository management including:
- Repository browsing
- File operations
- Pull request management
- Issue tracking
- Webhook integration
"""

import sys

from flask import request, jsonify, Blueprint
import os
import json
from datetime import datetime
from pathlib import Path

# Import the GitHub integration
from github_integration import github_integration

# Create blueprint for this feature
github_bp = Blueprint('github_integration', __name__, url_prefix='/api/features/github')

def register_routes(app):
    """Register GitHub integration routes once per app."""
    print("DEBUG: Registering GitHub integration routes", file=sys.stderr)
    if 'github_integration' in app.blueprints:
        return
    app.register_blueprint(github_bp)

    @app.route('/github')
    def github_page():
        """Serve the GitHub Integration page."""
        try:
            p = Path(__file__).resolve().parent.parent / 'templates' / 'github_integration.html'
            print(f"DEBUG: Looking for github_integration.html at {p}", file=sys.stderr)
            if p.exists():
                print("DEBUG: File exists, serving it", file=sys.stderr)
                return p.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}
        except Exception as e:
            print(f"DEBUG: Error serving github_integration.html: {e}", file=sys.stderr)
        print("DEBUG: File not found or error, returning 404", file=sys.stderr)
        return jsonify({'error': 'GitHub integration not available'}), 404

    @app.route('/api/features/github/repos')
    def github_repos():
        """List GitHub repositories"""
        if not github_integration.is_configured():
            return jsonify({'error': 'GitHub integration not configured'}), 503
        
        repos = github_integration.get_user_repositories()
        return jsonify({'repos': repos})

    @app.route('/api/features/github/repos/<owner>/<repo>')
    def github_repo_detail(owner, repo):
        """Get repository details"""
        if not github_integration.is_configured():
            return jsonify({'error': 'GitHub integration not configured'}), 503
        
        repo_info = github_integration.get_repository(owner, repo)
        if not repo_info:
            return jsonify({'error': 'Repository not found'}), 404
        
        return jsonify(repo_info)

    @app.route('/api/features/github/clone', methods=['POST'])
    def github_clone_repo():
        """Clone a GitHub repository"""
        data = request.get_json() or {}
        repo_url = data.get('url', '')
        target_dir = data.get('target_dir', './cloned_repo')
        
        if not repo_url:
            return jsonify({'error': 'Repository URL is required'}), 400
        
        # Use absolute path for target_dir
        target_dir = os.path.join(os.getcwd(), 'data', 'github_repos', os.path.basename(repo_url).replace('.git', ''))
        
        result = github_integration.clone_repository(repo_url, target_dir)
        return jsonify(result)

    @app.route('/api/features/github/files/<path:repo_name>')
    def github_repo_files(repo_name):
        """Get files from a cloned repository"""
        repo_path = os.path.join(os.getcwd(), 'data', 'github_repos', repo_name)
        path = request.args.get('path', '')
        
        files = github_integration.get_repository_files(repo_path, path)
        return jsonify({'files': files, 'current_path': path})

    @app.route('/api/features/github/file-content/<path:repo_name>')
    def github_file_content(repo_name):
        """Get content of a file from cloned repository"""
        repo_path = os.path.join(os.getcwd(), 'data', 'github_repos', repo_name)
        file_path = request.args.get('file_path', '')
        
        if not file_path:
            return jsonify({'error': 'File path is required'}), 400
        
        content = github_integration.read_file_content(repo_path, file_path)
        if content is None:
            return jsonify({'error': 'File not found or cannot be read'}), 404
        
        return jsonify({'content': content, 'file_path': file_path})

    @app.route('/api/features/github/save-file', methods=['POST'])
    def github_save_file():
        """Save file content to scripts directory"""
        data = request.get_json() or {}
        content = data.get('content', '')
        filename = data.get('filename', '')
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
        
        result = github_integration.save_file_to_scripts(content, filename)
        return jsonify(result)

    @app.route('/api/features/github/create-repo', methods=['POST'])
    def github_create_repo():
        """Create a new GitHub repository"""
        if not github_integration.is_configured():
            return jsonify({'error': 'GitHub integration not configured'}), 503
        
        data = request.get_json() or {}
        name = data.get('name', 'new-repo')
        description = data.get('description', '')
        private = data.get('private', False)
        
        result = github_integration.create_repository(name, description, private)
        if result:
            return jsonify({'status': 'created', 'repo': result})
        else:
            return jsonify({'error': 'Failed to create repository'}), 500

    @app.route('/api/features/github/repos/<owner>/<repo>/contents')
    def github_repo_contents(owner, repo):
        """Get repository contents via API"""
        print(f"DEBUG: github_repo_contents called for {owner}/{repo}", file=sys.stderr)
        if not github_integration.is_configured():
            return jsonify({'error': 'GitHub integration not configured'}), 503
        
        if repo.endswith('.git'):
            repo = repo[:-4]
        
        path = request.args.get('path', '')
        contents = github_integration.get_repo_contents(owner, repo, path)
        return jsonify({'contents': contents, 'current_path': path})

    @app.route('/api/features/github/repos/<owner>/<repo>/file-content')
    def github_file_content_api(owner, repo):
        """Get file content via GitHub API"""
        if not github_integration.is_configured():
            return jsonify({'error': 'GitHub integration not configured'}), 503
        
        if repo.endswith('.git'):
            repo = repo[:-4]
        
        file_path = request.args.get('file_path', '')
        if not file_path:
            return jsonify({'error': 'File path is required'}), 400
        
        content = github_integration.get_file_content_via_api(owner, repo, file_path)
        if content is None:
            return jsonify({'error': 'File not found or cannot be read'}), 404
        
        return jsonify({'content': content, 'file_path': file_path})

def register_ui(app):
    """Register UI components for GitHub integration"""
    pass

# Feature metadata
FEATURE_CONFIG = {
    'name': 'github-integration',
    'display_name': 'GitHub Integration',
    'description': 'Connect to GitHub repositories and manage resources',
    'version': '1.0.0',
    'dependencies': ['PyGitHub', 'requests'],
    'routes': [
        {'path': '/api/features/github/repos', 'method': 'GET', 'description': 'List repositories'},
        {'path': '/api/features/github/repos/{owner}/{repo}', 'method': 'GET', 'description': 'Get repo details'},
        {'path': '/api/features/github/clone', 'method': 'POST', 'description': 'Clone repository'},
        {'path': '/api/features/github/create-repo', 'method': 'POST', 'description': 'Create repository'}
    ],
    'ui_components': [
        {
            'type': 'card',
            'title': 'GitHub Repositories',
            'content': 'Browse and manage GitHub repositories',
            'actions': [
                {'label': 'View Repos', 'action': 'navigate', 'url': '/features/github/repos'},
                {'label': 'Clone Repo', 'action': 'modal', 'modal': 'github-clone'}
            ]
        }
    ]
}