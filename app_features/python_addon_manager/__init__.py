# Module Manager Addon Wizard: installs libraries
# Edit this file for the feature's logic and routes.
# Page markup: templates/index.html.  Name, menu entry and on/off default: feature.json.
from flask import Blueprint, jsonify


def init(app, ctx):
    bp = Blueprint("feature_python_addon_manager", __name__, url_prefix="/ext/python_addon_manager")

    @bp.route("/")
    def index():
        denied = ctx.admin_page(False)
        if denied is not None:
            return denied
        return ctx.render_page("index.html", title='Module Manager Addon Wizard', description='installs libraries')

    @bp.route("/api/ping")
    def ping():
        denied = ctx.admin_page(True)
        if denied is not None:
            return denied
        return jsonify({"ok": True, "feature": "python_addon_manager"})

    return bp
