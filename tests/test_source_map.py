from pathlib import Path

from flask import Flask

from managers.source_map import SourceMap, SourceMapError

ROOT = Path(__file__).resolve().parent.parent


def _app():
    app = Flask(__name__)

    @app.route("/hello")
    def hello():
        return "x"

    return app


def test_routes_and_lookup():
    sm = SourceMap(_app(), ROOT)
    found = sm.lookup("/hello")
    assert found["routes"][0]["url"] == "/hello"
    assert found["routes"][0]["file"].endswith("test_source_map.py")


def test_registry_files_exist():
    sm = SourceMap(_app(), ROOT)
    assert sm.health()["missing_files"] == []
    assert any(c["id"] == "logo" for c in sm.components())


def test_rejects_empty_query():
    try:
        SourceMap(_app(), ROOT).lookup("  ")
    except SourceMapError:
        return
    raise AssertionError("expected SourceMapError")
