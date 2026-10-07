from pathlib import Path

from sys_diagnostics import _collect_files, _is_ignored_directory


def test_ignored_directory_filter_covers_virtual_environment_variants():
    for name in ("venv", "venv310", ".venv-pypi", ".venv_311", "NODE_MODULES", "data"):
        assert _is_ignored_directory(name)
    assert not _is_ignored_directory("services")


def test_file_collection_skips_environment_trees(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    for directory in ("venv310", ".venv-pypi", "venv"):
        package_dir = tmp_path / directory / "Lib" / "site-packages"
        package_dir.mkdir(parents=True)
        (package_dir / "huge_dependency.py").write_text("pass", encoding="utf-8")

    found = {Path(item["rel_path"]).as_posix() for item in _collect_files(tmp_path)}

    assert "src/app.py" in found
    assert not any("site-packages" in path for path in found)
