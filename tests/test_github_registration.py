from flask import Flask

from features.handlers.github_integration import register_routes
from github_integration import GitHubIntegration
from unittest import mock
import subprocess
import pytest


def test_register_routes_is_idempotent():
    app = Flask(__name__)

    register_routes(app)
    register_routes(app)

    assert 'github_integration' in app.blueprints


def test_cloned_repositories_are_discovered_and_not_hard_coded(tmp_path, monkeypatch):
    root = tmp_path / "data" / "github_repos"
    (root / "tf" / ".git").mkdir(parents=True)
    (root / "other" / ".git").mkdir(parents=True)
    (root / "not-a-repo").mkdir()
    monkeypatch.chdir(tmp_path)
    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()
    result = client.get('/api/features/github/cloned-repos')
    assert result.status_code == 200
    assert result.get_json() == {'repos': ['other', 'tf']}
    monkeypatch.chdir(tmp_path.parent)
    assert client.get('/api/features/github/cloned-repos').get_json() == {'repos': []}


def test_remote_repository_failure_is_not_an_empty_success():
    app = Flask(__name__)
    register_routes(app)
    with mock.patch('features.handlers.github_integration.github_integration') as github:
        github.is_configured.return_value = True
        github.get_user_repositories.side_effect = RuntimeError('GitHub unavailable')
        response = app.test_client().get('/api/features/github/repos')
        assert response.status_code == 502
        assert response.get_json()['error'] == 'GitHub unavailable'


def test_integration_surfaces_repository_api_failure():
    integration = GitHubIntegration.__new__(GitHubIntegration)
    integration.github = mock.Mock()
    integration.github.get_user.side_effect = RuntimeError('API failure')
    with pytest.raises(RuntimeError, match="repository listing failed"):
        integration.get_user_repositories()


def test_local_file_paths_use_browser_path_separators(tmp_path):
    directory = tmp_path / "folder" / "nested"
    directory.mkdir(parents=True)
    (directory / "sample.txt").write_text("content", encoding="utf-8")
    integration = GitHubIntegration.__new__(GitHubIntegration)
    files = integration.get_repository_files(str(tmp_path), "folder/nested")
    assert files[0]['path'] == "folder/nested/sample.txt"


def test_cli_browser_fails_closed_and_surfaces_github_errors():
    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()
    assert client.get('/api/features/github/cli/repos').status_code == 503
    app.config['SCM_ADMIN_GET_GUARD'] = lambda: ({'error': 'denied'}, 403)
    assert client.get('/api/features/github/cli/repos').status_code == 403
    app.config['SCM_ADMIN_GET_GUARD'] = lambda: None
    with mock.patch('features.github_cli_browser._api', side_effect=RuntimeError('GitHub unavailable')):
        result = client.get('/api/features/github/cli/repos')
        assert result.status_code == 502
        assert 'GitHub unavailable' in result.get_json()['error']


def test_cli_browser_lists_repositories_and_reads_remote_contents():
    app = Flask(__name__)
    register_routes(app)
    app.config['SCM_ADMIN_GET_GUARD'] = lambda: None
    client = app.test_client()
    with mock.patch('features.github_cli_browser._api') as api:
        api.return_value = [[{'name': 'demo', 'full_name': 'owner/demo', 'description': None,
                              'stargazers_count': 0, 'language': 'Python'}]]
        assert client.get('/api/features/github/cli/repos').get_json()['repos'][0]['full_name'] == 'owner/demo'
        api.assert_called_with('user/repos?per_page=100&sort=updated', paginate=True)
        api.return_value = [{'name': 'file.txt', 'path': 'dir/file.txt', 'type': 'file', 'size': 5}]
        assert client.get('/api/features/github/cli/repos/owner/demo/contents?path=dir').get_json()['contents'][0]['name'] == 'file.txt'
        api.return_value = {'type': 'file', 'encoding': 'base64', 'content': 'aGVsbG8=\n'}
        assert client.get('/api/features/github/cli/repos/owner/demo/file-content?file_path=dir/file.txt').get_json()['content'] == 'hello'
        assert client.get('/api/features/github/cli/repos/owner/demo/file-content?file_path=../secret').status_code == 400


def test_cli_api_is_noninteractive_and_reports_failures():
    from features.github_cli_browser import _api
    with mock.patch('features.github_cli_browser.subprocess.run') as run:
        run.return_value = subprocess.CompletedProcess([], 0, '[]', '')
        assert _api('user/repos', paginate=True) == []
        assert run.call_args.args[0] == ['gh', 'api', '--hostname', 'github.com', 'user/repos', '--paginate', '--slurp']
        assert run.call_args.kwargs['env']['GH_PROMPT_DISABLED'] == '1'
        run.return_value = subprocess.CompletedProcess([], 1, '', 'secret details')
        with pytest.raises(RuntimeError, match='GitHub CLI request failed'):
            _api('user/repos')
