import json

import pytest

from addons.echo_model_team import addon
from addons.echo_model_team.train import load_approved_examples


def test_team_uses_echo_default_and_allows_many_future_models(monkeypatch):
    monkeypatch.setenv("ECHO_TEAM_MAX_MODELS", "12")
    monkeypatch.setenv("ECHO_TEAM_MODELS", ",".join(f"local-{index}" for index in range(10)))

    assert addon.configured_models() == ["echo-default"] + [f"local-{index}" for index in range(10)]


def test_team_uses_only_the_existing_default_model_when_no_additions_are_configured(monkeypatch):
    monkeypatch.delenv("ECHO_TEAM_MODELS", raising=False)

    assert addon.configured_models() == ["echo-default"]


def test_team_turn_sends_prior_responses_and_queues_pending_candidate(tmp_path, monkeypatch):
    prompts = []

    def fake_call(model, prompt, timeout):
        prompts.append((model, prompt))
        return f"reply from {model}"

    monkeypatch.setattr(addon, "_call_model", fake_call)
    result = addon.run_team_chat(
        "Explain a safe change",
        models=["first", "second"],
        pending_file=tmp_path / "pending.jsonl",
    )

    assert result["response"] == "reply from second"
    assert "reply from first" in prompts[1][1]
    queued = json.loads((tmp_path / "pending.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert queued["id"] == result["candidate_id"]


def test_candidate_requires_explicit_approval_before_training(tmp_path):
    pending = tmp_path / "pending.jsonl"
    approved = tmp_path / "approved.jsonl"
    pending.write_text(
        json.dumps({"id": "a" * 32, "prompt": "question", "response": "answer"}) + "\n",
        encoding="utf-8",
    )

    assert addon.approve_candidate("a" * 32, pending_file=pending, approved_file=approved)
    assert not addon.approve_candidate("a" * 32, pending_file=pending, approved_file=approved)
    assert load_approved_examples(approved) == [{"prompt": "question", "response": "answer"}]


def test_invalid_approved_training_json_is_reported(tmp_path):
    approved = tmp_path / "approved.jsonl"
    approved.write_text("{bad json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        load_approved_examples(approved)
