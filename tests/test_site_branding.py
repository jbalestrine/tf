from flask import Flask, Response, send_file

from core.site_branding import add_global_site_brand


def test_global_brand_is_injected_into_standalone_html_files(tmp_path):
    page = tmp_path / "standalone.html"
    page.write_text("<!doctype html><html><body><main>Page</main></body></html>", encoding="utf-8")
    app = Flask(__name__)

    @app.after_request
    def brand(response):
        return add_global_site_brand(response)

    @app.get("/standalone")
    def standalone():
        return send_file(page)

    response = app.test_client().get("/standalone")

    assert response.status_code == 200
    assert b'id="masterchief-site-brand"' in response.data
    assert b'/static/masterchief-logo.svg' in response.data
    assert int(response.headers["Content-Length"]) == len(response.data)


def test_global_brand_does_not_duplicate_shared_template_header():
    app = Flask(__name__)

    @app.after_request
    def brand(response):
        return add_global_site_brand(response)

    @app.get("/")
    def page():
        return Response(
            '<html><body><header id="masterchief-site-brand">Logo</header></body></html>',
            mimetype="text/html",
        )

    response = app.test_client().get("/")

    assert response.data.count(b'id="masterchief-site-brand"') == 1
