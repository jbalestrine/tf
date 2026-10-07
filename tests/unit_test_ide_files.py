import pytest

from utils.ide_files import resolve_project_file


def test_resolves_project_paths_and_windows_separators(tmp_path):
    root = tmp_path.resolve()

    assert resolve_project_file(root, 'main.py') == root / 'main.py'
    assert resolve_project_file(root, r'src\feature.py') == root / 'src' / 'feature.py'


@pytest.mark.parametrize('relative_path', ['../outside.py', r'..\outside.py', 'C:/outside.py', '/outside.py'])
def test_rejects_paths_outside_project(tmp_path, relative_path):
    with pytest.raises(ValueError):
        resolve_project_file(tmp_path, relative_path)


def test_rejects_symlink_escape(tmp_path):
    root = tmp_path / 'project'
    outside = tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    try:
        (root / 'linked').symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'symlink creation is unavailable: {exc}')

    with pytest.raises(ValueError):
        resolve_project_file(root, 'linked/secret.py')
