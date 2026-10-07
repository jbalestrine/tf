import json

import pytest

from core.code_archetypes import (
    BUILTIN_ARCHETYPES,
    list_archetypes,
    save_custom_archetype,
)
from utils.code_archetypes import with_archetype_client


def test_builtin_archetypes_have_visual_flow_and_code():
    assert len(BUILTIN_ARCHETYPES) >= 5
    assert all(item["code"].strip() and len(item["nodes"]) >= 2 for item in BUILTIN_ARCHETYPES)


def test_custom_archetype_is_persisted_and_listed(tmp_path):
    storage = tmp_path / "custom.json"
    saved = save_custom_archetype(
        {
            "title": "My Python Service",
            "category": "Application",
            "language": "python",
            "description": "A sample",
            "nodes": ["Request", "Service", "Response"],
            "code": "print('hello')\n",
        },
        storage,
    )

    assert saved["id"] == "custom-my-python-service"
    assert saved in list_archetypes(storage)
    assert json.loads(storage.read_text(encoding="utf-8")) == [saved]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "language": "python", "nodes": ["a", "b"], "code": "print(1)"},
        {"title": "Missing nodes", "language": "python", "nodes": ["only"], "code": "print(1)"},
        {"title": "Missing code", "language": "python", "nodes": ["a", "b"], "code": " "},
        {"title": "Bad language", "language": "Python<js>", "nodes": ["a", "b"], "code": "print(1)"},
    ],
)
def test_custom_archetype_rejects_invalid_payloads(tmp_path, payload):
    with pytest.raises(ValueError):
        save_custom_archetype(payload, tmp_path / "custom.json")


def test_custom_archetype_rejects_duplicate_builtin_name(tmp_path):
    with pytest.raises(ValueError, match="already exists"):
        save_custom_archetype(
            {
                "title": "Python CLI tool",
                "language": "python",
                "nodes": ["Input", "Output"],
                "code": "print(1)",
            },
            tmp_path / "custom.json",
        )


def test_archetype_client_is_inserted_once_before_body_end():
    page = '<html><body><textarea id="code-editor"></textarea></body></html>'

    result = with_archetype_client(page)

    assert result.count('/static/code_archetypes.js') == 1
    assert result.index('/static/code_archetypes.js') < result.index('</body>')
    assert with_archetype_client(result) == result
