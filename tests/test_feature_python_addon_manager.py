from pathlib import Path

from flask import Flask

from managers.feature_loader import load_features

ROOT = Path(__file__).resolve().parent.parent


def test_python_addon_manager_loads_and_answers():
    app = Flask(__name__)
    statuses = load_features(app, ROOT, "", lambda json_response: None, lambda: None)
    status = next(s for s in statuses if s["slug"] == "python_addon_manager")
    assert status["state"] == "loaded", status["error"]
    assert app.test_client().get("/ext/python_addon_manager/api/ping").get_json()["ok"] is True
