from flask import Flask

from auth_module import init_auth


def test_roku_route_does_not_create_an_admin_session():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-session-key"
    init_auth(app)

    client = app.test_client()
    response = client.get("/roku")

    assert response.status_code == 302
    assert response.location.startswith("/login")
    assert client.get("/auth/status").get_json() == {"authenticated": False}
