import runpy
import sys
from pathlib import Path
from types import ModuleType


def test_web_templates_are_installed_next_to_main(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    captured = {}
    setuptools = ModuleType('setuptools')
    setuptools.setup = lambda **kwargs: captured.update(kwargs)
    setuptools.find_packages = lambda **kwargs: []
    monkeypatch.chdir(root)
    monkeypatch.setitem(sys.modules, 'setuptools', setuptools)

    runpy.run_path(str(root / 'setup.py'))

    files = dict(captured['data_files'])
    templates = {Path(path).name for path in files['share/masterchief/templates']}
    assert {'layout.html', 'scripts.html', 'processes.html', 'addons.html'} <= templates
    assert 'main.py' in files['share/masterchief']
    static = {Path(path).name for path in files['share/masterchief/static']}
    assert {'ubuntu-desktop.js', 'ubuntu-desktop.css', 'novnc-LICENSE.txt',
            'novnc-MPL-2.0.txt', 'novnc-pako-LICENSE.txt'} <= static
