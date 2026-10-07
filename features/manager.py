import os
import sys

print("DEBUG: features/manager.py is being executed", file=sys.stderr)

with open('debug.log', 'a') as f:
    f.write(f"DEBUG: Beginning of features/manager.py, cwd={os.getcwd()}\n")

"""
Dynamic Feature Management System for MasterChief Platform

This module provides a dynamic feature loading and management system that allows
users to add, configure, and toggle features through a web interface.
"""

with open('debug.log', 'a') as f:
    f.write("DEBUG: features.manager module is being imported\n")

import json
import importlib
import inspect
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from flask import Flask, request, jsonify, render_template_string, current_app
from flask_login import current_user
import threading
import time
from datetime import datetime

# Import GitHub integration
from github_integration import github_integration
import subprocess
import requests
import zipfile
import io
import shutil


@dataclass
class FeatureConfig:
    """Configuration for a feature"""
    name: str
    display_name: str
    description: str
    version: str = "1.0.0"
    enabled: bool = False
    dependencies: List[str] = None
    settings: Dict[str, Any] = None
    routes: List[Dict[str, Any]] = None
    scripts: List[str] = None
    ui_components: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.settings is None:
            self.settings = {}
        if self.routes is None:
            self.routes = []
        if self.scripts is None:
            self.scripts = []
        if self.ui_components is None:
            self.ui_components = []


class FeatureManager:
    """Manages dynamic features for the MasterChief platform"""

    def __init__(self, app: Flask, features_dir: str = "."):
        print("FeatureManager.__init__ called", file=sys.stderr)
        print("DEBUG: Right after first print", file=sys.stderr)
        self.app = app
        self.features_dir = Path(__file__).parent / features_dir
        self.features_dir.mkdir(exist_ok=True)
        self.features: Dict[str, 'FeatureHandler'] = {}
        self.feature_configs: Dict[str, FeatureConfig] = {}
        self._lock = threading.Lock()

        # Create subdirectories
        (self.features_dir / "configs").mkdir(exist_ok=True)
        (self.features_dir / "handlers").mkdir(exist_ok=True)
        (self.features_dir / "templates").mkdir(exist_ok=True)
        (self.features_dir / "static").mkdir(exist_ok=True)

        # Load existing features
        print("DEBUG: About to call _load_feature_configs", file=sys.stderr)
        self._load_feature_configs()
        self._load_enabled_features()
        self._register_routes()

    def _load_feature_configs(self):
        """Load feature configurations from disk"""
        print(f"DEBUG: _load_feature_configs called", file=sys.stderr)
        try:
            configs_dir = self.features_dir / "configs"
            print(f"DEBUG: Configs dir: {configs_dir}, exists: {configs_dir.exists()}", file=sys.stderr)

            for config_file in configs_dir.glob("*.json"):
                print(f"DEBUG: Processing config file: {config_file}", file=sys.stderr)
                try:
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                        print(f"DEBUG: Loaded config data: {config_data.get('name')}", file=sys.stderr)
                        config = FeatureConfig(**config_data)
                        self.feature_configs[config.name] = config
                        print(f"DEBUG: Added config: {config.name}, enabled: {config.enabled}", file=sys.stderr)
                except Exception as e:
                    print(f"ERROR loading feature config {config_file}: {e}", file=sys.stderr)

            print(f"DEBUG: Final config count: {len(self.feature_configs)}", file=sys.stderr)
        except Exception as e:
            print(f"ERROR in _load_feature_configs: {e}", file=sys.stderr)

    def _register_routes(self):
        """Register feature management routes"""
        with open('debug.log', 'a') as f:
            f.write("ROUTES: _register_routes method called at " + str(datetime.now()) + "\n")
        print("DEBUG: ENTERING _register_routes method")
        try:
            print("Registering feature routes...")

            # Register routes using add_url_rule
            self.app.add_url_rule('/api/features/test', 'test_route', self._test_route, methods=['GET'])
            self.app.add_url_rule('/api/features', 'api_list_features', self._api_list_features, methods=['GET'])
            self.app.add_url_rule('/api/features/create', 'api_create_feature', self._api_create_feature, methods=['POST'])
            self.app.add_url_rule('/api/features/<feature_name>/toggle', 'api_toggle_feature', self._api_toggle_feature, methods=['POST'])
            self.app.add_url_rule('/api/features/github', 'api_load_from_github', self._api_load_from_github, methods=['POST'])
            self.app.add_url_rule('/api/features/github/load', 'api_load_from_github_url', self._api_load_from_github_url, methods=['POST'])
            self.app.add_url_rule('/api/features/github/user/<username>/repos', 'api_get_user_repos', self._api_get_user_repos, methods=['GET'])
            self.app.add_url_rule('/api/features/github/search', 'api_search_github_repos', self._api_search_github_repos, methods=['GET'])
            self.app.add_url_rule('/api/features/load-github', 'api_load_github_repo', self._api_load_github_repo, methods=['POST'])
            self.app.add_url_rule('/api/features/github/repo-scripts', 'api_load_repo_scripts', self._api_load_repo_scripts, methods=['POST'])
            self.app.add_url_rule('/api/features/script', 'api_load_from_script', self._api_load_from_script, methods=['POST'])

            with open('debug.log', 'a') as f:
                f.write("DEBUG: All routes registered successfully\n")
            print("DEBUG: All routes registered successfully")
        except Exception as e:
            with open('debug.log', 'a') as f:
                f.write(f"ERROR in _register_routes: {e}\n")
            print(f"ERROR in _register_routes: {e}")
            import traceback
            traceback.print_exc()

    def _test_route(self):
        """Test route to verify routing is working"""
        return jsonify({'message': 'TEST ROUTE WORKING - FeatureManager routes are registered!', 'timestamp': str(datetime.now())})

    def _is_admin_request(self):
        try:
            return bool(
                current_user.is_authenticated
                and current_user.provider == 'rbac'
                and str(current_user.role or '').casefold() == 'admin'
                and '*' in (current_user.permissions or [])
            )
        except (AttributeError, RuntimeError):
            return False

    def _is_same_origin_request(self):
        from urllib.parse import urlparse

        source = request.headers.get('Origin') or request.headers.get('Referer')
        if not source:
            return False
        parsed = urlparse(source)
        return bool(parsed.netloc and parsed.netloc.casefold() == request.host.casefold())

    def _api_list_features(self):
        return jsonify({
            'success': True,
            'features': [
                asdict(config)
                for _, config in sorted(self.feature_configs.items())
            ],
        })

    def _api_create_feature(self):
        """Create a new feature from template"""
        if not self._is_admin_request():
            return jsonify({'success': False, 'error': 'RBAC platform admin permission required'}), 403
        if not self._is_same_origin_request():
            return jsonify({'success': False, 'error': 'same-origin request required'}), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'No data provided'}), 400

        try:
            name = str(data.get('name') or '').strip().lower()
            display_name = str(data.get('display_name') or '').strip()
            description = str(data.get('description') or '').strip()
            dependencies = data.get('dependencies', [])
            handler_code = data.get('handler_code', '')
            if not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}', name):
                return jsonify({'success': False, 'error': 'Feature names must be 2-64 lowercase letters, numbers, underscores, or hyphens'}), 400
            if not display_name or len(display_name) > 100 or len(description) > 500:
                return jsonify({'success': False, 'error': 'Display name is required (max 100 characters); description is limited to 500 characters'}), 400
            if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
                return jsonify({'success': False, 'error': 'Dependencies must be a list of package names'}), 400
            if not isinstance(handler_code, str) or len(handler_code.encode('utf-8')) > 128 * 1024:
                return jsonify({'success': False, 'error': 'Handler code must be text and no larger than 128 KiB'}), 400
            try:
                compile(handler_code, f'<feature:{name}>', 'exec')
            except SyntaxError as exc:
                return jsonify({'success': False, 'error': f'Handler code has a syntax error on line {exc.lineno}: {exc.msg}'}), 400

            if name in self.feature_configs:
                return jsonify({'success': False, 'error': 'A feature with that name already exists'}), 409

            # Create feature config
            config = FeatureConfig(
                name=name,
                display_name=display_name,
                description=description,
                dependencies=dependencies
            )

            # Save handler code
            handler_file = self.features_dir / "handlers" / f"{name.replace('-', '_')}.py"
            handler_file.parent.mkdir(parents=True, exist_ok=True)
            if handler_file.exists():
                return jsonify({'success': False, 'error': 'A feature handler with that name already exists'}), 409
            handler_file.write_text(handler_code, encoding='utf-8')

            # Save config
            self._save_feature_config(config)
            self.feature_configs[name] = config

            return jsonify({'success': True, 'feature': asdict(config)}), 201
        except Exception as e:
            current_app.logger.exception('Failed to create feature %s', data.get('name'))
            return jsonify({'error': str(e)}), 500

    def _api_toggle_feature(self, feature_name):
        """Enable or disable a feature; enabling executes its admin-created handler."""
        if not self._is_admin_request():
            return jsonify({'success': False, 'error': 'RBAC platform admin permission required'}), 403
        if not self._is_same_origin_request():
            return jsonify({'success': False, 'error': 'same-origin request required'}), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('enabled'), bool):
            return jsonify({'success': False, 'error': 'enabled must be a boolean'}), 400
        if feature_name not in self.feature_configs:
            return jsonify({'success': False, 'error': 'Feature not found'}), 404
        try:
            if data['enabled']:
                self.enable_feature(feature_name)
            else:
                self.disable_feature(feature_name)
            return jsonify({
                'success': True,
                'feature': asdict(self.feature_configs[feature_name]),
            })
        except Exception as exc:
            current_app.logger.exception('Failed to change feature state for %s', feature_name)
            return jsonify({'success': False, 'error': str(exc)}), 500

    def _api_load_from_github(self):
        """Load feature from GitHub repository"""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        try:
            repo_url = data.get('repo_url')
            branch = data.get('branch', 'main')
            feature_name = data.get('feature_name')

            if not repo_url or not feature_name:
                return jsonify({'error': 'repo_url and feature_name are required'}), 400

            # Download from GitHub
            import requests

            # Get repository contents
            api_url = repo_url.replace('github.com', 'api.github.com/repos')
            if api_url.endswith('.git'):
                api_url = api_url[:-4]
            api_url = f"{api_url}/contents?ref={branch}"

            response = requests.get(api_url)
            if response.status_code != 200:
                return jsonify({'error': 'Failed to fetch repository contents'}), 400

            contents = response.json()

            # Look for feature files
            feature_files = [item for item in contents if item['name'].endswith('.py') or item['name'].endswith('.json')]

            if not feature_files:
                return jsonify({'error': 'No feature files found in repository'}), 400

            # Create feature from repository
            config = FeatureConfig(
                name=feature_name,
                display_name=feature_name.replace('-', ' ').title(),
                description=f"Feature loaded from {repo_url}"
            )

            # Download and save files
            for file_info in feature_files:
                file_url = file_info['download_url']
                file_response = requests.get(file_url)
                if file_response.status_code == 200:
                    file_path = self.features_dir / "handlers" / file_info['name']
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w') as f:
                        f.write(file_response.text)

            self.feature_configs[feature_name] = config
            self._save_feature_config(config)

            return jsonify({'success': True, 'feature': asdict(config)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def _api_load_from_github_url(self):
        """Load feature from GitHub repository URL"""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        try:
            repo_url = data.get('url')
            feature_name = data.get('feature_name', 'github-feature')

            if not repo_url:
                return jsonify({'error': 'repo_url is required'}), 400

            # Download from GitHub using requests
            import requests

            # Get repository contents
            api_url = repo_url.replace('github.com', 'api.github.com/repos')
            if api_url.endswith('.git'):
                api_url = api_url[:-4]
            api_url = f"{api_url}/contents"

            response = requests.get(api_url)
            if response.status_code != 200:
                return jsonify({'error': 'Failed to fetch repository contents'}), 400

            contents = response.json()

            # Look for feature files
            feature_files = [item for item in contents if item['name'].endswith('.py') or item['name'].endswith('.json')]

            if not feature_files:
                return jsonify({'error': 'No feature files found in repository'}), 400

            # Create feature from repository
            config = FeatureConfig(
                name=feature_name,
                display_name=feature_name.replace('-', ' ').title(),
                description=f"Feature loaded from {repo_url}"
            )

            # Download and save files
            for file_info in feature_files:
                file_url = file_info['download_url']
                file_response = requests.get(file_url)
                if file_response.status_code == 200:
                    file_path = self.features_dir / "handlers" / file_info['name']
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w') as f:
                        f.write(file_response.text)

            self.feature_configs[feature_name] = config
            self._save_feature_config(config)

            return jsonify({'success': True, 'feature': asdict(config)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def _api_get_user_repos(self, username):
        """Get repositories for a specific GitHub user/organization"""
        try:
            if not github_integration.is_configured():
                return jsonify({'error': 'GitHub integration not configured'}), 503

            repos = github_integration.get_user_repositories(username)
            return jsonify({'repos': repos})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def _api_search_github_repos(self):
        """Search GitHub repositories"""
        try:
            query = request.args.get('q', '')
            if not query:
                return jsonify({'error': 'Search query is required'}), 400

            if not github_integration.is_configured():
                return jsonify({'error': 'GitHub integration not configured'}), 503

            # Use PyGitHub to search repositories
            from github import Github
            g = Github(github_integration.token)

            # Search for repositories
            repos = g.search_repositories(query, sort='stars', order='desc')

            repo_list = []
            for repo in repos[:20]:  # Limit to 20 results
                repo_list.append({
                    'name': repo.name,
                    'full_name': repo.full_name,
                    'description': repo.description,
                    'html_url': repo.html_url,
                    'clone_url': repo.clone_url,
                    'language': repo.language,
                    'stargazers_count': repo.stargazers_count,
                    'forks_count': repo.forks_count,
                    'owner': {
                        'login': repo.owner.login,
                        'avatar_url': repo.owner.avatar_url
                    }
                })

            return jsonify({'repos': repo_list})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def _api_load_github_repo(self):
        """Load feature from selected GitHub repository"""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        try:
            repo_url = data.get('repo_url')
            feature_name = data.get('feature_name')

            if not repo_url:
                return jsonify({'error': 'repo_url is required'}), 400

            # Generate feature name if not provided
            if not feature_name:
                # Extract repo name from URL
                if repo_url.startswith('https://github.com/'):
                    parts = repo_url.replace('https://github.com/', '').split('/')
                    if len(parts) >= 2:
                        feature_name = f"{parts[1]}-feature"

            if not feature_name:
                feature_name = 'github-feature'

            # Use the same logic as repo-scripts
            import requests

            # Get repository contents
            api_url = repo_url.replace('github.com', 'api.github.com/repos')
            if api_url.endswith('.git'):
                api_url = api_url[:-4]
            api_url = f"{api_url}/contents"

            response = requests.get(api_url)
            if response.status_code != 200:
                return jsonify({'error': 'Failed to fetch repository contents'}), 400

            contents = response.json()

            # Look for feature/script files
            feature_files = [item for item in contents if item['name'].endswith(('.py', '.js', '.ps1', '.sh', '.json'))]

            if not feature_files:
                return jsonify({'error': 'No feature files found in repository'}), 400

            # Create feature from repository
            config = FeatureConfig(
                name=feature_name,
                display_name=feature_name.replace('-', ' ').title(),
                description=f"Feature loaded from {repo_url}"
            )

            # Download and save files
            for file_info in feature_files:
                file_url = file_info['download_url']
                file_response = requests.get(file_url)
                if file_response.status_code == 200:
                    file_path = self.features_dir / "handlers" / file_info['name']
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w') as f:
                        f.write(file_response.text)

            self.feature_configs[feature_name] = config
            self._save_feature_config(config)

            return jsonify({'success': True, 'feature': asdict(config)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def _api_load_repo_scripts(self):
        """Load scripts from a GitHub repository"""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        try:
            repo_url = data.get('repo_url')
            feature_name = data.get('feature_name')

            if not repo_url or not feature_name:
                return jsonify({'error': 'repo_url and feature_name are required'}), 400

            # Download from GitHub using requests
            import requests

            # Get repository contents
            api_url = repo_url.replace('github.com', 'api.github.com/repos')
            if api_url.endswith('.git'):
                api_url = api_url[:-4]
            api_url = f"{api_url}/contents"

            response = requests.get(api_url)
            if response.status_code != 200:
                return jsonify({'error': 'Failed to fetch repository contents'}), 400

            contents = response.json()

            # Look for script files (Python, JS, etc.)
            script_files = [item for item in contents if item['name'].endswith(('.py', '.js', '.ps1', '.sh', '.json'))]

            if not script_files:
                return jsonify({'error': 'No script files found in repository'}), 400

            # Create feature from repository scripts
            config = FeatureConfig(
                name=feature_name,
                display_name=feature_name.replace('-', ' ').title(),
                description=f"Feature created from scripts in {repo_url}"
            )

            # Download and save files
            for file_info in script_files:
                file_url = file_info['download_url']
                file_response = requests.get(file_url)
                if file_response.status_code == 200:
                    file_path = self.features_dir / "handlers" / file_info['name']
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w') as f:
                        f.write(file_response.text)

            self.feature_configs[feature_name] = config
            self._save_feature_config(config)

            return jsonify({'success': True, 'feature': asdict(config)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def _api_load_from_script(self):
        """Load feature from script file upload"""
        try:
            feature_name = request.form.get('feature_name')
            display_name = request.form.get('display_name')
            description = request.form.get('description')
            script_file = request.files.get('script_file')

            if not feature_name or not script_file:
                return jsonify({'error': 'feature_name and script_file are required'}), 400

            # Determine script type from file extension
            filename = script_file.filename
            if filename.endswith('.py'):
                script_type = 'python'
            elif filename.endswith('.js'):
                script_type = 'javascript'
            elif filename.endswith('.ps1'):
                script_type = 'powershell'
            elif filename.endswith('.sh'):
                script_type = 'bash'
            elif filename.endswith('.php'):
                script_type = 'php'
            elif filename.endswith('.json'):
                script_type = 'json'
            else:
                script_type = 'text'

            # Read script content
            script_content = script_file.read().decode('utf-8')

            # Create feature config
            config = FeatureConfig(
                name=feature_name,
                display_name=display_name or feature_name.replace('-', ' ').title(),
                description=description or f"Feature created from {script_type} script"
            )

            # Save script
            if script_type == 'python':
                ext = '.py'
            elif script_type == 'javascript':
                ext = '.js'
            elif script_type == 'powershell':
                ext = '.ps1'
            elif script_type == 'bash':
                ext = '.sh'
            elif script_type == 'php':
                ext = '.php'
            else:
                ext = '.txt'

            script_file_path = self.features_dir / "handlers" / f"{feature_name}{ext}"
            script_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(script_file_path, 'w') as f:
                f.write(script_content)

            self.feature_configs[feature_name] = config
            self._save_feature_config(config)

            return jsonify({'success': True, 'feature': asdict(config)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def _load_enabled_features(self):
        """Load handlers for enabled features"""
        with open('debug.log', 'a') as f:
            f.write(f"DEBUG: _load_enabled_features called with {len(self.feature_configs)} configs\n")
        print(f"DEBUG: Loading enabled features from {len(self.feature_configs)} configs", file=sys.stderr)
        for name, config in self.feature_configs.items():
            with open('debug.log', 'a') as f:
                f.write(f"DEBUG: Checking feature {name}, enabled={config.enabled}\n")
            print(f"DEBUG: Checking feature {name}, enabled={config.enabled}", file=sys.stderr)
            if config.enabled and name not in self.features:
                try:
                    with open('debug.log', 'a') as f:
                        f.write(f"DEBUG: Creating handler for {name}\n")
                    print(f"DEBUG: Creating handler for {name}", file=sys.stderr)
                    handler = FeatureHandler(config, self.features_dir, self.app)
                    self.features[name] = handler
                    with open('debug.log', 'a') as f:
                        f.write(f"DEBUG: Successfully loaded feature: {name}\n")
                    print(f"Loaded enabled feature: {name}", file=sys.stderr)
                except Exception as e:
                    with open('debug.log', 'a') as f:
                        f.write(f"ERROR loading enabled feature {name}: {e}\n")
                    print(f"Error loading enabled feature {name}: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc()

    def enable_feature(self, feature_name: str):
        """Enable a feature"""
        if feature_name not in self.feature_configs:
            raise ValueError(f"Feature {feature_name} not found")

        config = self.feature_configs[feature_name]
        if feature_name not in self.features:
            # Create feature handler
            handler = FeatureHandler(config, self.features_dir, self.app)
            self.features[feature_name] = handler

        config.enabled = True
        self._save_feature_config(config)

    def disable_feature(self, feature_name: str):
        """Disable a feature"""
        if feature_name in self.features:
            # Clean up feature
            del self.features[feature_name]

        if feature_name in self.feature_configs:
            config = self.feature_configs[feature_name]
            config.enabled = False
            self._save_feature_config(config)

    def _save_feature_config(self, config: FeatureConfig):
        """Save feature configuration to disk"""
        configs_dir = self.features_dir / "configs"
        config_file = configs_dir / f"{config.name}.json"
        with open(config_file, 'w') as f:
            json.dump(asdict(config), f, indent=2)


class FeatureHandler:
    """Handles a loaded feature"""

    def __init__(self, config: FeatureConfig, features_dir: Path, app: Flask):
        self.config = config
        self.features_dir = features_dir
        self.app = app
        self.instance = None

        # Load the feature if enabled
        if config.enabled:
            self._load_feature()

    def _load_feature(self):
        """Load the feature implementation"""
        with open('debug.log', 'a') as f:
            f.write(f"DEBUG: FeatureHandler._load_feature called for {self.config.name}\n")
        try:
            # Convert feature name to module name (replace hyphens with underscores)
            module_name = self.config.name.replace('-', '_')
            handler_path = self.features_dir / "handlers" / f"{module_name}.py"
            with open('debug.log', 'a') as f:
                f.write(f"DEBUG: Looking for handler at {handler_path}\n")

            if handler_path.exists():
                with open('debug.log', 'a') as f:
                    f.write(f"DEBUG: Handler file exists, importing {module_name}\n")
                # Import the handler module
                spec = importlib.util.spec_from_file_location(module_name, handler_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Call register_routes if it exists
                    if hasattr(module, 'register_routes'):
                        with open('debug.log', 'a') as f:
                            f.write(f"DEBUG: Calling register_routes for {self.config.name}\n")
                        print(f"DEBUG: Calling register_routes for {self.config.name}", file=sys.stderr)
                        module.register_routes(self.app)
                        with open('debug.log', 'a') as f:
                            f.write(f"DEBUG: register_routes completed for {self.config.name}\n")
                        print(f"Registered routes for feature: {self.config.name}", file=sys.stderr)
                    else:
                        with open('debug.log', 'a') as f:
                            f.write(f"WARNING: No register_routes function in {module_name}\n")
                        print(f"Warning: No register_routes function in {module_name}", file=sys.stderr)
                else:
                    with open('debug.log', 'a') as f:
                        f.write(f"WARNING: Could not load module {module_name}\n")
                    print(f"Warning: Could not load module {module_name}")
            else:
                with open('debug.log', 'a') as f:
                    f.write(f"WARNING: Handler file not found for feature {self.config.name}: {handler_path}\n")
                print(f"Warning: Handler file not found for feature {self.config.name}: {handler_path}")
        except Exception as e:
            with open('debug.log', 'a') as f:
                f.write(f"ERROR loading feature {self.config.name}: {e}\n")
            print(f"Error loading feature {self.config.name}: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Unable to load feature {self.config.name}: {e}") from e


# Global feature manager instance
_feature_manager = None


def init_feature_manager(app: Flask) -> FeatureManager:
    """Initialize the global feature manager"""
    with open('debug.log', 'a') as f:
        f.write("ENTERING init_feature_manager function\n")
    print("DEBUG: ENTERING init_feature_manager")
    print("Initializing feature manager...")
    with open('debug.log', 'a') as f:
        f.write("About to create FeatureManager instance\n")
    global _feature_manager
    try:
        print("DEBUG: About to create FeatureManager instance")
        _feature_manager = FeatureManager(app)
        print("DEBUG: FeatureManager instance created successfully")
        with open('debug.log', 'a') as f:
            f.write("FeatureManager instance created successfully\n")
    except Exception as e:
        print(f"DEBUG: ERROR creating FeatureManager: {e}")
        with open('debug.log', 'a') as f:
            f.write(f"ERROR creating FeatureManager: {e}\n")
        import traceback
        with open('debug.log', 'a') as f:
            f.write(f"Traceback: {traceback.format_exc()}\n")
        raise
    with open('debug.log', 'a') as f:
        f.write("init_feature_manager completed\n")
    print("DEBUG: init_feature_manager completed")
    return _feature_manager


def get_feature_manager() -> Optional[FeatureManager]:
    """Get the global feature manager instance"""
    return _feature_manager