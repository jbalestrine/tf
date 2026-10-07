from unittest.mock import Mock

import requests

from core import github_version


def test_returns_and_caches_latest_release(monkeypatch):
    github_version.clear_github_version_cache()
    response = Mock(status_code=200)
    response.json.return_value = {
        "tag_name": "v2.4.1",
        "html_url": "https://github.com/jbalestrine/tf/releases/tag/v2.4.1",
        "published_at": "2026-10-01T12:00:00Z",
    }
    request = Mock(return_value=response)
    monkeypatch.setattr(github_version.requests, "get", request)

    first = github_version.get_github_current_version("jbalestrine/tf")
    second = github_version.get_github_current_version("jbalestrine/tf")

    assert first["version"] == "v2.4.1"
    assert first["kind"] == "release"
    assert second["cached"] is True
    request.assert_called_once()
    github_version.clear_github_version_cache()


def test_sends_configured_token_for_private_repository(monkeypatch):
    github_version.clear_github_version_cache()
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    response = Mock(status_code=200)
    response.json.return_value = {"tag_name": "v4.0.0"}
    request = Mock(return_value=response)
    monkeypatch.setattr(github_version.requests, "get", request)

    result = github_version.get_github_current_version("jbalestrine/masterchief")

    assert result["version"] == "v4.0.0"
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"
    github_version.clear_github_version_cache()


def test_falls_back_to_default_branch_commit_when_no_release(monkeypatch):
    github_version.clear_github_version_cache()
    responses = [
        Mock(status_code=404, json=Mock(return_value={})),
        Mock(status_code=200, json=Mock(return_value={"default_branch": "main"})),
        Mock(status_code=200, json=Mock(return_value={
            "sha": "1234567890abcdef",
            "html_url": "https://github.com/jbalestrine/tf/commit/1234567890abcdef",
        })),
    ]
    request = Mock(side_effect=responses)
    monkeypatch.setattr(github_version.requests, "get", request)

    result = github_version.get_github_current_version("jbalestrine/tf")

    assert result["version"] == "main@1234567"
    assert result["kind"] == "commit"
    assert request.call_count == 3
    github_version.clear_github_version_cache()


def test_uses_stale_version_if_github_fails_after_a_success(monkeypatch):
    github_version.clear_github_version_cache()
    response = Mock(status_code=200)
    response.json.return_value = {
        "tag_name": "v1.3.0",
        "html_url": "https://github.com/jbalestrine/tf/releases/tag/v1.3.0",
    }
    request = Mock(return_value=response)
    monkeypatch.setattr(github_version.requests, "get", request)
    initial = github_version.get_github_current_version("jbalestrine/tf")

    monkeypatch.setattr(github_version, "_CACHE_TTL_SECONDS", -1)
    monkeypatch.setattr(
        github_version.requests,
        "get",
        Mock(side_effect=requests.ConnectionError("offline")),
    )
    stale = github_version.get_github_current_version("jbalestrine/tf")

    assert initial["version"] == stale["version"] == "v1.3.0"
    assert stale["stale"] is True
    assert "last successful version" in stale["warning"]
    github_version.clear_github_version_cache()


def test_rejects_invalid_repository_identifier():
    assert github_version.get_github_current_version("https://example.com/repo")["ok"] is False
