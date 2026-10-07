from flask import Flask
from flask_login import LoginManager

from blueprints.roku_routes import roku_bp


def create_app(with_login_manager=False):
    app = Flask(__name__)
    app.config["TESTING"] = True
    if with_login_manager:
        login_manager = LoginManager()
        login_manager.user_loader(lambda user_id: None)
        login_manager.init_app(app)
    app.register_blueprint(roku_bp)
    return app


def test_roku_admin_route_fails_closed_without_rbac_initialization():
    response = create_app().test_client().get("/api/roku/settings")

    assert response.status_code == 503
    assert response.get_json()["ok"] is False


def test_roku_admin_route_requires_authenticated_session():
    response = create_app(with_login_manager=True).test_client().get("/api/roku/settings")

    assert response.status_code == 401
    assert response.get_json()["ok"] is False
