import json

from utils.navigation import visible_pinned_modules


def test_visible_pinned_modules_skips_hidden_orphan_and_unsafe_links(tmp_path):
    uploads = tmp_path / "uploads"
    extracted = uploads / "extracted"
    (extracted / "echo-tools").mkdir(parents=True)
    (extracted / "create_a_new_module_when_i_say_module_cr").mkdir()
    raw = {
        "echo-tools": {"url": "/addons/modules/echo-tools/manager", "icon": "🧩"},
        "create_a_new_module_when_i_say_module_cr": {
            "url": "/addons/modules/create_a_new_module_when_i_say_module_cr/manager"
        },
        "missing-addon": {"url": "/addons/modules/missing-addon/manager"},
        "external-link": {"url": "https://example.com"},
        "traversal": {"url": "/addons/modules/../../admin"},
    }
    (uploads / "ui_modules.json").write_text(json.dumps(raw), encoding="utf-8")

    result = visible_pinned_modules(raw, uploads)

    assert result == {"echo-tools": {"url": "/addons/modules/echo-tools/manager", "icon": "🧩"}}


def test_visible_pinned_modules_ignores_malformed_data_and_path_escape(tmp_path):
    uploads = tmp_path / "uploads"
    extracted = uploads / "extracted"
    extracted.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()

    assert visible_pinned_modules(None, uploads) == {}
    assert visible_pinned_modules(
        {"../outside": {"url": "/addons/modules/outside/manager"}}, uploads
    ) == {}
