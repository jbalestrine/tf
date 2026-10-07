import json
from pathlib import Path

from flask import Flask
from flask_login import LoginManager, UserMixin

from blueprints.core_scripts import core_scripts_bp
from managers.idea_basket import IdeaBasketError, IdeaBasketManager


class BasketUser(UserMixin):
    id = "idea-user"
    permissions = ["scripts"]


def test_idea_basket_persists_notes_and_removes_only_the_entry(tmp_path):
    source = tmp_path / "old_irc_bot.py"
    source.write_text("print('original stays')\n", encoding="utf-8")
    database = tmp_path / "data" / "ideas.sqlite3"

    manager = IdeaBasketManager(database)
    manager.add("old_irc_bot.py", "Could become the standalone IRC prototype.")

    reopened = IdeaBasketManager(database)
    assert reopened.list_ideas()[0]["path"] == "old_irc_bot.py"
    assert reopened.list_ideas()[0]["note"] == "Could become the standalone IRC prototype."
    assert reopened.remove("old_irc_bot.py") is True
    assert reopened.remove("old_irc_bot.py") is False
    assert source.read_text(encoding="utf-8") == "print('original stays')\n"


def test_idea_basket_normalizes_paths_and_rejects_traversal_or_long_notes(tmp_path):
    manager = IdeaBasketManager(tmp_path / "ideas.sqlite3")

    assert manager.add("tools\\irc_bot.py", "Prototype")["path"] == "tools/irc_bot.py"
    for path in ("../outside.py", "/absolute.py", "tools//empty.py"):
        try:
            manager.add(path)
        except IdeaBasketError:
            pass
        else:
            raise AssertionError(f"Unsafe path was accepted: {path}")
    try:
        manager.add("tools/irc_bot.py", "x" * 501)
    except IdeaBasketError:
        pass
    else:
        raise AssertionError("An overlong idea note was accepted")


def _make_app(tmp_path):
    template_folder = Path(__file__).resolve().parents[1] / "templates"
    app = Flask(__name__, root_path=str(tmp_path), template_folder=str(template_folder))
    app.config["SECRET_KEY"] = "test-secret"
    app.add_url_rule("/login", endpoint="login", view_func=lambda: "login")
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.user_loader(lambda _user_id: BasketUser())
    app.register_blueprint(core_scripts_bp)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "feature_flags.json").write_text(
        json.dumps({"core_scripts": True}),
        encoding="utf-8",
    )
    return app


def _log_in(client):
    with client.session_transaction() as session:
        session["_user_id"] = "idea-user"
        session["_fresh"] = True


def test_idea_basket_api_parks_catalogued_script_without_touching_source(tmp_path):
    script = tmp_path / "legacy_irc.py"
    original = "print('valuable prototype')\n"
    script.write_text(original, encoding="utf-8")
    app = _make_app(tmp_path)
    client = app.test_client()
    _log_in(client)

    added = client.post(
        "/api/core-scripts/ideas",
        json={"path": "legacy_irc.py", "note": "Worth revisiting as an IRC add-on."},
    )
    page = client.get("/chaos-monkey")
    listed = client.get("/api/core-scripts/ideas")
    removed = client.delete("/api/core-scripts/ideas", json={"path": "legacy_irc.py"})

    assert added.status_code == 201
    assert added.get_json()["idea"]["note"] == "Worth revisiting as an IRC add-on."
    assert b"Ideas Basket" in page.data
    assert b"Worth revisiting as an IRC add-on." in page.data
    assert listed.get_json()["ideas"][0]["path"] == "legacy_irc.py"
    assert removed.get_json()["source_preserved"] is True
    assert script.read_text(encoding="utf-8") == original
    assert client.get("/api/core-scripts/ideas").get_json()["ideas"] == []


def test_idea_basket_api_rejects_non_catalogued_paths(tmp_path):
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "generated.py").write_text("pass\n", encoding="utf-8")
    app = _make_app(tmp_path)
    client = app.test_client()
    _log_in(client)

    response = client.post(
        "/api/core-scripts/ideas",
        json={"path": "build/generated.py", "note": "Generated output"},
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False
    assert not (tmp_path / "data" / "chaos_monkey_ideas.sqlite3").exists()
