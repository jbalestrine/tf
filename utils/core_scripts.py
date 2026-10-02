import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ALLOWED_EXTENSIONS = {'.py', '.ps1', '.sh', '.js', '.json', '.tf'}
SKIP_DIRS = {'.git', '__pycache__', 'venv', 'venv310', 'node_modules', '.pytest_cache'}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def scan_core_scripts(base_dir: Path):
    scripts = []
    for path in sorted(base_dir.rglob('*')):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if not _is_within(path, base_dir):
            continue
        rel = path.relative_to(base_dir).as_posix()
        top = rel.split('/', 1)[0] if '/' in rel else 'root'
        scripts.append(
            {
                'name': path.name,
                'path': rel,
                'ext': path.suffix.lower(),
                'size': path.stat().st_size,
                'category': top,
                'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            }
        )
    return scripts


def dry_check_script(base_dir: Path, rel_path: str):
    target = (base_dir / rel_path).resolve()
    if not target.exists() or not target.is_file() or not _is_within(target, base_dir):
        return {'ok': False, 'error': 'invalid script path'}

    ext = target.suffix.lower()
    try:
        if ext == '.py':
            proc = subprocess.run([sys.executable, '-m', 'py_compile', str(target)], capture_output=True, text=True, timeout=30)
            return {'ok': proc.returncode == 0, 'stdout': proc.stdout, 'stderr': proc.stderr}
        if ext == '.json':
            json.loads(target.read_text(encoding='utf-8'))
            return {'ok': True, 'stdout': 'JSON is valid', 'stderr': ''}
        return {'ok': True, 'stdout': f'No static checker configured for {ext}; file accessible.', 'stderr': ''}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def run_script(base_dir: Path, rel_path: str):
    target = (base_dir / rel_path).resolve()
    if not target.exists() or not target.is_file() or not _is_within(target, base_dir):
        return {'ok': False, 'error': 'invalid script path'}

    ext = target.suffix.lower()
    cmd = None
    cwd = str(target.parent)

    if ext == '.py':
        cmd = [sys.executable, str(target)]
    elif ext == '.ps1':
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(target)]
    elif ext == '.sh':
        cmd = ['bash', str(target)]
    elif ext == '.js':
        cmd = ['node', str(target)]
    elif ext == '.tf':
        cmd = ['terraform', 'validate']
    else:
        return {'ok': False, 'error': f'Unsupported runnable type: {ext}'}

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=cwd)
        return {
            'ok': proc.returncode == 0,
            'cmd': cmd,
            'code': proc.returncode,
            'stdout': (proc.stdout or '')[:6000],
            'stderr': (proc.stderr or '')[:6000],
        }
    except FileNotFoundError as exc:
        return {'ok': False, 'error': f'Missing runtime: {exc}'}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def import_script_to_module(base_dir: Path, rel_path: str, module_name: str):
    src = (base_dir / rel_path).resolve()
    if not src.exists() or not src.is_file() or not _is_within(src, base_dir):
        return {'ok': False, 'error': 'invalid script path'}

    safe_module = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in module_name).strip('_')
    if not safe_module:
        return {'ok': False, 'error': 'module_name is required'}

    uploads = base_dir / 'data' / 'uploads'
    extract_dir = uploads / 'extracted' / safe_module
    target_dir = extract_dir / 'imported' / Path(rel_path).parent
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / src.name
    shutil.copy2(src, target)

    readme = extract_dir / 'README_imported.md'
    if not readme.exists():
        readme.write_text(
            f'# Imported Script Module: {safe_module}\n\nThis module was created from core scripts GUI import.\n',
            encoding='utf-8',
        )

    modules_file = uploads / 'modules.json'
    modules = {}
    if modules_file.exists():
        try:
            modules = json.loads(modules_file.read_text(encoding='utf-8') or '{}')
        except Exception:
            modules = {}
    modules[safe_module] = {
        'name': safe_module,
        'extract_dir': str(extract_dir),
        'source_dir': str(extract_dir),
        'installed_at': datetime.utcnow().isoformat(),
        'type': 'script',
        'description': f'Imported from {rel_path}',
        'is_blank_module': True,
    }
    modules_file.parent.mkdir(parents=True, exist_ok=True)
    modules_file.write_text(json.dumps(modules, indent=2), encoding='utf-8')

    ui_file = uploads / 'ui_modules.json'
    ui_modules = {}
    if ui_file.exists():
        try:
            ui_modules = json.loads(ui_file.read_text(encoding='utf-8') or '{}')
        except Exception:
            ui_modules = {}
    ui_modules[safe_module] = {
        'url': f'/addons/modules/{safe_module}/manager',
        'icon': '🧩',
        'enabled': True,
    }
    ui_file.write_text(json.dumps(ui_modules, indent=2), encoding='utf-8')

    return {
        'ok': True,
        'module_name': safe_module,
        'module_path': str(extract_dir.relative_to(base_dir)).replace('\\', '/'),
        'imported_file': str(target.relative_to(base_dir)).replace('\\', '/'),
    }
