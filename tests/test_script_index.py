from pathlib import Path

from flask import Flask

from managers.script import ScriptManager, register_script_module


def _flatten(categories):
    return [script for category in categories for script in category['scripts']]


def test_index_scans_nested_scripts_once_and_skips_dependency_trees(tmp_path):
    repo_root = tmp_path
    scripts_root = repo_root / 'scripts'
    (scripts_root / 'nested').mkdir(parents=True)
    (repo_root / 'tools' / 'deploy').mkdir(parents=True)
    (repo_root / '.venv' / 'Scripts').mkdir(parents=True)
    (repo_root / 'node_modules' / 'package').mkdir(parents=True)
    (scripts_root / 'nested' / 'local.py').write_text('print("local")', encoding='utf-8')
    (repo_root / 'tools' / 'deploy' / 'deploy.ps1').write_text('Write-Output ok', encoding='utf-8')
    (repo_root / '.venv' / 'Scripts' / 'ignored.py').write_text('', encoding='utf-8')
    (repo_root / 'node_modules' / 'package' / 'ignored.sh').write_text('', encoding='utf-8')

    scripts = _flatten(ScriptManager(scripts_root, repo_root=repo_root).list_scripts(use_cache=False))

    by_name = {script['name']: script for script in scripts}
    assert set(by_name) == {'local.py', 'deploy.ps1'}
    assert by_name['local.py']['source'] == 'scripts_folder'
    assert by_name['deploy.ps1']['source'] == 'repo'
    assert Path(by_name['local.py']['path']).is_absolute()


def test_index_cache_can_be_bypassed_to_pick_up_new_scripts(tmp_path):
    scripts_root = tmp_path / 'scripts'
    scripts_root.mkdir()
    manager = ScriptManager(scripts_root, repo_root=tmp_path)
    (scripts_root / 'first.py').write_text('pass', encoding='utf-8')

    initial = _flatten(manager.list_scripts())
    (scripts_root / 'second.py').write_text('pass', encoding='utf-8')

    cached = _flatten(manager.list_scripts())
    refreshed = _flatten(manager.list_scripts(use_cache=False))

    assert [script['name'] for script in initial] == ['first.py']
    assert [script['name'] for script in cached] == ['first.py']
    assert {script['name'] for script in refreshed} == {'first.py', 'second.py'}


def test_refresh_index_route_invalidates_both_cache_variants(tmp_path):
    app = Flask(__name__, root_path=str(tmp_path))
    register_script_module(app, scripts_folder='scripts')
    cache_dir = tmp_path / 'data'
    cache_dir.mkdir()
    repo_cache = cache_dir / 'script_index_repo.json'
    local_cache = cache_dir / 'script_index_local.json'
    repo_cache.write_text('[]', encoding='utf-8')
    local_cache.write_text('[]', encoding='utf-8')

    response = app.test_client().post('/scripts/refresh_index')

    assert response.status_code == 200
    assert response.get_json()['ok'] is True
    assert not repo_cache.exists()
    assert not local_cache.exists()
