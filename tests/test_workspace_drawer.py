import json

from flask import Flask, Response

from core.workspace_drawer import add_workspace_drawer
from utils.workspace_drawer import catalog


def test_injection_only_for_regular_html():
    response = Response("<html><body>hello</body></html>", mimetype="text/html")
    add_workspace_drawer(response)
    add_workspace_drawer(response)
    assert response.data.count(b'/static/workspace-drawer.js') == 1
    assert response.headers["Cache-Control"] == "no-store"
    assert int(response.headers["Content-Length"]) == len(response.data)
    download = Response("<html><body>download</body></html>", mimetype="text/html",
                        headers={"Content-Disposition": "attachment; filename=test.html"})
    assert b"workspace-drawer.js" not in add_workspace_drawer(download).data
    data = Response('{"ok":true}', mimetype="application/json")
    assert add_workspace_drawer(data).data == b'{"ok":true}'


def test_catalog_uses_real_pages_features_and_installed_addons(tmp_path):
    app = Flask(__name__, root_path=str(tmp_path))
    for path in ["/", "/sys/scm", "/pipelines", "/scripts", "/echo-chat", "/ext/feature/"]:
        app.add_url_rule(path, endpoint=path, view_func=lambda: "ok")
    upload = tmp_path / "uploads"
    (upload / "extracted" / "Pinned").mkdir(parents=True)
    (upload / "extracted" / "Other Addon").mkdir()
    (upload / "ui_modules.json").write_text(json.dumps({
        "Pinned": {"url": "/addons/modules/Pinned/manager"},
        "Missing": {"url": "/addons/modules/Missing/manager"},
    }), encoding="utf-8")
    app.config["UPLOAD_FOLDER"] = upload
    app.config["_feature_nav"] = [
        {"href": "/ext/feature/", "label": "Feature"},
        {"href": "//example.invalid", "label": "External"},
    ]
    items = catalog(app)
    urls = {item["url"] for item in items}
    assert "/sys/scm" in urls and "/static/git-workflow-guide.html#activity-status" in urls
    assert "/static/git-workflow-guide.html#release-journey" in urls
    assert next(item for item in items if item["url"] == "/scripts")["group"] == "Automate & AI"
    assert next(item for item in items if item["url"] == "/echo-chat")["group"] == "Automate & AI"
    assert "/ext/feature/" in urls
    assert "/addons/modules/Pinned/manager" in urls
    assert "/addons/modules/Other%20Addon/manager" in urls
    assert not any("Missing" in url or "example.invalid" in url for url in urls)
    assert "/masterchief_code_ui" not in urls


def test_disabled_feature_is_labeled(tmp_path):
    app = Flask(__name__, root_path=str(tmp_path))
    app.add_url_rule("/pipelines", endpoint="pipelines", view_func=lambda: "ok")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "feature_flags.json").write_text('{"pipelines": false}', encoding="utf-8")
    item = next(item for item in catalog(app) if item["url"] == "/pipelines")
    assert item["disabled"] is True
