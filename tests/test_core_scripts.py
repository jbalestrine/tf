import json
from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin

from blueprints.core_scripts import core_scripts_bp
from utils.core_scripts import dry_check_script, run_script, scan_core_scripts


class StubUser(UserMixin):
    def __init__(self, permissions):
        self.id = "test-user"
        self.permissions = permissions


def _make_app(tmp_path, permissions=None, enabled=True):
    template_folder = Path(__file__).resolve().parents[1] / "templates"
    app = Flask(__name__, root_path=str(tmp_path), template_folder=str(template_folder))
    app.config["SECRET_KEY"] = "test-secret"
    app.add_url_rule("/login", endpoint="login", view_func=lambda: "login")
    login_manager = LoginManager()
    login_manager.init_app(app)
    user = StubUser(permissions or [])
    login_manager.user_loader(lambda _user_id: user)
    app.register_blueprint(core_scripts_bp)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "feature_flags.json").write_text(
        json.dumps({"core_scripts": enabled}),
        encoding="utf-8",
    )
    return app


def _log_in(client):
    with client.session_transaction() as session:
        session["_user_id"] = "test-user"
        session["_fresh"] = True


def test_script_inventory_groups_project_tools_and_skips_generated_outputs(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "build" / "tools").mkdir(parents=True)
    (tmp_path / "data" / "roku_builds" / "previous-build").mkdir(parents=True)
    (tmp_path / "data" / "uploads" / "extracted" / "sample").mkdir(parents=True)
    (tmp_path / "tools" / "orphan_helper.py").write_text("print('ready')\n", encoding="utf-8")
    (tmp_path / "build" / "tools" / "generated.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "data" / "roku_builds" / "previous-build" / "generated.js").write_text(
        "console.log('old')\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "uploads" / "extracted" / "sample" / "copied.py").write_text(
        "pass\n",
        encoding="utf-8",
    )

    scripts = scan_core_scripts(tmp_path)

    assert [(script["path"], script["category"]) for script in scripts] == [
        ("tools/orphan_helper.py", "tools")
    ]


def test_script_inventory_labels_sanity_checks_without_calling_them_unused(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_irc_service.py").write_text(
        "def test_irc_service_contract():\n    assert True\n",
        encoding="utf-8",
    )

    scripts = scan_core_scripts(tmp_path)

    assert scripts[0]["category"] == "Sanity Tests"
    assert scripts[0]["kind"] == "sanity_test"
    result = run_script(tmp_path, "tests/test_irc_service.py")
    assert result["ok"] is True
    assert "1 passed" in result["stdout"]


def test_python_dry_check_validates_without_creating_bytecode(tmp_path):
    script = tmp_path / "helper.py"
    script.write_text("value = 42\n", encoding="utf-8")

    result = dry_check_script(tmp_path, "helper.py")

    assert result == {"ok": True, "stdout": "Python syntax is valid", "stderr": ""}
    assert not (tmp_path / "__pycache__").exists()


def test_dry_check_reports_invalid_syntax_and_rejects_path_escape(tmp_path):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    outside = tmp_path.parent / "outside.py"
    outside.write_text("pass\n", encoding="utf-8")

    assert dry_check_script(tmp_path, "broken.py")["ok"] is False
    assert dry_check_script(tmp_path, "../outside.py") == {
        "ok": False,
        "error": "invalid script path",
    }


def test_run_script_executes_only_supported_files_within_workspace(tmp_path):
    script = tmp_path / "safe_sample.py"
    script.write_text("import sys\nprint('|'.join(sys.argv[1:]))\n", encoding="utf-8")
    outside = tmp_path.parent / "outside.py"
    outside.write_text("print('outside')\n", encoding="utf-8")

    result = run_script(tmp_path, "safe_sample.py", ["value with spaces", "--safe"])
    escaped = run_script(tmp_path, "../outside.py")

    assert result["ok"] is True
    assert result["stdout"].strip() == "value with spaces|--safe"
    assert result["argument_count"] == 2
    assert escaped == {"ok": False, "error": "invalid script path"}


def test_chaos_monkey_routes_require_scripts_permission(tmp_path):
    app = _make_app(tmp_path)
    client = app.test_client()

    assert client.get("/chaos-monkey").status_code == 302
    assert client.get("/api/core-scripts").status_code == 302
    assert client.post("/api/core-scripts/run", json={"path": "helper.py"}).status_code == 302


def test_chaos_monkey_page_and_api_are_available_to_script_operators(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "helper.py").write_text("print('ready')\n", encoding="utf-8")
    app = _make_app(tmp_path, permissions=["scripts"])
    client = app.test_client()
    _log_in(client)

    page = client.get("/chaos-monkey")
    inventory = client.get("/api/core-scripts")
    legacy_page = client.get("/core-scripts")

    assert page.status_code == 200
    assert b"Chaos Monkey Area" in page.data
    assert b"tools/helper.py" in page.data
    assert inventory.status_code == 200
    assert [script["path"] for script in inventory.get_json()["scripts"]] == ["tools/helper.py"]
    assert legacy_page.status_code == 200


def test_chaos_monkey_feature_flag_disables_page_and_api(tmp_path):
    app = _make_app(tmp_path, permissions=["scripts"], enabled=False)
    client = app.test_client()
    _log_in(client)

    assert client.get("/chaos-monkey").status_code == 503
    assert client.get("/api/core-scripts").status_code == 503


def test_execution_api_rejects_files_outside_the_script_catalog(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "helper.py").write_text("print('ready')\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "generated.py").write_text("print('generated')\n", encoding="utf-8")
    app = _make_app(tmp_path, permissions=["scripts"])
    client = app.test_client()
    _log_in(client)

    response = client.post("/api/core-scripts/run", json={"path": "build/generated.py"})

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "script is not in the approved project library",
    }


def test_execution_api_passes_cli_arguments_without_shell_interpolation(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "helper.py").write_text(
        "import sys\nprint('|'.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    app = _make_app(tmp_path, permissions=["scripts"])
    client = app.test_client()
    _log_in(client)

    response = client.post(
        "/api/core-scripts/run",
        json={"path": "tools/helper.py", "arguments": ["hello there", "& echo unsafe"]},
    )

    assert response.status_code == 200
    assert response.get_json()["stdout"].strip() == "hello there|& echo unsafe"
