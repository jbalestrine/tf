import json
import time
import os
import shutil
import stat
import tempfile
import threading
from pathlib import Path
from datetime import datetime
import subprocess
import sys
from werkzeug.utils import secure_filename
from flask import request, jsonify, render_template_string, flash
import base64


def _interpreter_cmd_for_path(p: Path, requested_shell=None):
    try:
        if requested_shell:
            rs = str(requested_shell).lower()
            if rs in ('python','py','python3'):
                return [sys.executable, str(p)]
            if rs in ('powershell','ps1','pwsh'):
                return ['powershell','-ExecutionPolicy','Bypass','-File', str(p)]
            if rs in ('bash','sh'):
                # honor explicit request for bash/sh only if available on PATH
                if shutil.which('bash'):
                    return ['bash', str(p)]
                if shutil.which('wsl'):
                    return ['wsl', str(p)]
                return None
        # common suffixes
        if p.suffix == '.py':
            return [sys.executable, str(p)]
        if p.suffix == '.ps1':
            return ['powershell','-ExecutionPolicy','Bypass','-File', str(p)]
        # On Windows, avoid implicitly selecting WSL/bash for unknown types.
        # Prefer explicit shells (python/powershell) to prevent invoking missing WSL binaries.
        if sys.platform.startswith('win'):
            return None
        # on unix-like platforms run the file directly
        return [str(p)]
    except Exception:
        return None


class ScriptManager:
    _SCRIPT_EXTENSIONS = {'.sh', '.ps1', '.py', '.bash'}
    _SKIP_DIRECTORY_NAMES = {
        '.git', '.hg', '.svn', '.venv', 'venv', 'virtualenv', 'env',
        '__pycache__', 'node_modules', 'site-packages', '.tox',
        '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache',
        'dist', 'build', 'target',
    }

    def __init__(self, scripts_folder, repo_root=None):
        self.scripts_folder = Path(scripts_folder)
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[1]
        self._index_lock = threading.Lock()

    def list_scripts(self, include_repo_paths: bool = True, use_cache: bool = True):
        """Index supported scripts under the app tree without walking dependencies."""
        repo_root = self.repo_root.resolve()
        cache_file = repo_root / 'data' / (
            'script_index_repo.json' if include_repo_paths else 'script_index_local.json'
        )
        cache_ttl = 300

        def read_fresh_cache():
            try:
                age = time.time() - cache_file.stat().st_mtime
                if 0 <= age < cache_ttl:
                    with cache_file.open('r', encoding='utf-8') as cache:
                        cached = json.load(cache)
                    if isinstance(cached, list):
                        return cached
            except (OSError, json.JSONDecodeError):
                return None
            return None

        if use_cache:
            cached = read_fresh_cache()
            if cached is not None:
                return cached

        with self._index_lock:
            if use_cache:
                cached = read_fresh_cache()
                if cached is not None:
                    return cached

            scripts = []
            searched = set()
            scripts_root = self.scripts_folder.resolve()

            def scan_tree(scan_root: Path, source: str, skip_scripts_root: bool = False):
                if not scan_root.is_dir():
                    return
                for current, directories, filenames in os.walk(scan_root, topdown=True, followlinks=False):
                    current_path = Path(current)
                    kept_directories = []
                    for directory in directories:
                        if directory.casefold() in self._SKIP_DIRECTORY_NAMES:
                            continue
                        if directory.casefold().startswith('_extracted_disabled'):
                            continue
                        candidate = current_path / directory
                        try:
                            resolved_candidate = candidate.resolve()
                            if resolved_candidate == cache_file.resolve():
                                continue
                            if skip_scripts_root and resolved_candidate == scripts_root:
                                continue
                            if skip_scripts_root:
                                resolved_candidate.relative_to(scripts_root)
                                continue
                        except ValueError:
                            pass
                        except OSError:
                            continue
                        if candidate.is_symlink():
                            continue
                        kept_directories.append(directory)
                    directories[:] = kept_directories

                    for filename in filenames:
                        script_file = current_path / filename
                        if script_file.suffix.casefold() not in self._SCRIPT_EXTENSIONS:
                            continue
                        try:
                            metadata = script_file.lstat()
                        except OSError:
                            continue
                        if not stat.S_ISREG(metadata.st_mode):
                            continue
                        absolute_path = os.path.abspath(script_file)
                        key = os.path.normcase(absolute_path)
                        if key in searched:
                            continue
                        searched.add(key)
                        scripts.append({
                            'name': script_file.name,
                            'path': absolute_path,
                            'size': metadata.st_size,
                            'modified': datetime.fromtimestamp(metadata.st_mtime).isoformat(),
                            'type': script_file.suffix[1:],
                            'source': source,
                        })

            scan_tree(scripts_root, 'scripts_folder')
            if include_repo_paths and repo_root != scripts_root:
                scan_tree(repo_root, 'repo', skip_scripts_root=True)

        categories_map = {}
        def add_to_category(cat, item):
            if cat not in categories_map:
                categories_map[cat]=[]
            categories_map[cat].append(item)

        keywords = {
            'deploy':['deploy','deploy.sh','deploy.py','k8s','kubernetes','helm','ansible'],
            'backup':['backup','restore','snapshot'],
            'build':['build','compile','make','pack'],
            'test':['test','pytest','unittest','ci','integration'],
            'install':['install','setup','bootstrap','install.ps1'],
            'db':['db','migrate','schema','dump','restore'],
            'tools':['tool','script','util','utility'],
            'images':['image','docker','container'],
        }

        for s in scripts:
            p = Path(s['path'])
            name = p.name.lower()
            placed = False
            try:
                parts = [part.casefold() for part in p.relative_to(repo_root).parts]
            except ValueError:
                parts = [part.casefold() for part in p.relative_to(scripts_root).parts]
            for cat, kws in keywords.items():
                if any(k in name for k in kws) or any(k in part for part in parts for k in kws):
                    add_to_category(cat, s)
                    placed = True
                    break
            if not placed:
                # fallback by top-level folder
                top = parts[0] if parts else ''
                add_to_category(top or 'other', s)

        # Build result list sorted by category name, with scripts sorted
        result = []
        for cat in sorted(categories_map.keys()):
            items = sorted(categories_map[cat], key=lambda x: x['name'])
            result.append({'category':cat,'scripts':items})

        # Replace the cache atomically so readers never observe partial JSON.
        try:
            cache_file.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=cache_file.parent,
                prefix=cache_file.name + '.', suffix='.tmp', delete=False
            ) as cache:
                json.dump(result, cache)
                temporary_cache = Path(cache.name)
            temporary_cache.replace(cache_file)
        except OSError:
            try:
                temporary_cache.unlink(missing_ok=True)
            except (NameError, OSError):
                pass

        return result

    def add_script(self,filename,content):
        # Allow subdirectories but prevent path traversal
        try:
            # normalize and join
            target = Path(self.scripts_folder) / Path(filename)
            resolved = target.resolve()
            base = Path(self.scripts_folder).resolve()
            if not str(resolved).startswith(str(base)):
                return False
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved, 'w', encoding='utf-8') as f:
                f.write(content)
            # make executable where appropriate
            try:
                os.chmod(resolved, 0o755)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def delete_script(self,filename):
        try:
            target = Path(self.scripts_folder) / Path(filename)
            resolved = target.resolve()
            base = Path(self.scripts_folder).resolve()
            if not str(resolved).startswith(str(base)):
                return False
            if resolved.exists():
                resolved.unlink()
                # cleanup empty parents
                try:
                    p = resolved.parent
                    while p != base and not any(p.iterdir()):
                        p.rmdir()
                        p = p.parent
                except Exception:
                    pass
                return True
            return False
        except Exception:
            return False

    def execute_script(self,filename,args=''):
        script_path=self.scripts_folder/secure_filename(filename)
        if not script_path.exists():
            return {'success':False,'error':'Script not found'}
        try:
            # Choose an interpreter-aware command where possible
            cmd = _interpreter_cmd_for_path(script_path)
            if not cmd:
                # Fall back to attempting to execute directly; if this fails on Windows
                # the caller will receive a helpful error
                cmd = [str(script_path)]
            if args:
                cmd.extend(args.split())
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
            return {'success':result.returncode==0,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
        except subprocess.TimeoutExpired:
            return {'success':False,'error':'Script execution timed out'}
        except Exception as e:
            return {'success':False,'error':str(e)}

    def get_script_content(self,filename):
        try:
            target = Path(self.scripts_folder) / Path(filename)
            resolved = target.resolve()
            base = Path(self.scripts_folder).resolve()
            if not str(resolved).startswith(str(base)):
                return None
            if resolved.exists():
                with open(resolved,'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception:
            return None


def register_script_module(app, scripts_folder='scripts'):
    scripts_root = Path(scripts_folder)
    if not scripts_root.is_absolute():
        scripts_root = Path(app.root_path) / scripts_root
    script_mgr = ScriptManager(scripts_root, repo_root=app.root_path)
    
    @app.route('/scripts')
    def scripts_list():
        res = script_mgr.list_scripts(include_repo_paths=True)
        
        # Backwards-compatible: if list_scripts returns categories, flatten for templates that expect a flat list
        if res and isinstance(res, list) and isinstance(res[0], dict) and 'category' in res[0]:
            categories = res
            flat = []
            for c in categories:
                flat.extend(c.get('scripts',[]))
            scripts = flat
        else:
            categories = [{'category':'all','scripts':res}]
            scripts = res
        
        from templates.pages import SCRIPTS_TEMPLATE
        from templates.base import HTML_TEMPLATE
        from flask import request, get_flashed_messages
        return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}',SCRIPTS_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')),scripts=scripts,categories=categories,request=request,get_flashed_messages=get_flashed_messages)
    @app.route('/scripts/refresh_index', methods=['POST'])
    def refresh_index():
        # Admin token protection disabled for local development.
        # This endpoint is intentionally left open in dev to simplify testing.
        cache_files = [
            script_mgr.repo_root / 'data' / 'script_index_repo.json',
            script_mgr.repo_root / 'data' / 'script_index_local.json',
            script_mgr.repo_root / 'data' / 'script_index.json',
        ]
        try:
            for cache_file in cache_files:
                if cache_file.exists():
                    cache_file.unlink()
            return jsonify({'ok':True,'message':'index invalidated'})
        except OSError as e:
            return jsonify({'ok':False,'error':str(e)}),500
    
    @app.route('/scripts/add',methods=['POST'])
    def scripts_add():
        filename=request.form.get('filename')
        content=request.form.get('content')
        if script_mgr.add_script(filename,content):
            flash('Script added successfully!','success')
        else:
            flash('Failed to add script','error')
        from flask import redirect, url_for
        return redirect(url_for('scripts_list'))
    
    @app.route('/api/ide/scripts')
    def api_ide_scripts():
        files = []
        try:
            scripts_dir = script_mgr.scripts_folder
            for p in sorted(scripts_dir.glob('*')):
                if p.is_file():
                    files.append({'name': p.name, 'size': p.stat().st_size, 'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat()})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500
        
        return jsonify({'ok': True, 'files': files})
    
    @app.route('/scripts/execute/<filename>')
    def scripts_execute(filename):
        from templates.pages import SCRIPT_EXECUTE_TEMPLATE
        from templates.base import HTML_TEMPLATE
        from flask import request, get_flashed_messages
        return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}',SCRIPT_EXECUTE_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')),filename=filename,result=None,request=request,get_flashed_messages=get_flashed_messages)
    
    @app.route('/scripts/run/<filename>',methods=['POST'])
    def scripts_run(filename):
        args=request.form.get('args','')
        result=script_mgr.execute_script(filename,args)
        from templates.pages import SCRIPT_EXECUTE_TEMPLATE
        from templates.base import HTML_TEMPLATE
        from flask import request, get_flashed_messages
        return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}',SCRIPT_EXECUTE_TEMPLATE.replace('{% extends "base.html" %}','').replace('{% block content %}','').replace('{% endblock %}','')),filename=filename,result=result,request=request,get_flashed_messages=get_flashed_messages)
    
    return script_mgr