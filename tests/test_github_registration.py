from flask import Flask

from features.handlers.github_integration import register_routes


def test_register_routes_is_idempotent():
    app = Flask(__name__)

    register_routes(app)
    register_routes(app)

    assert 'github_integration' in app.blueprints
