# Roku Dev: Develops Roku App and deploys to roku devices.
# Edit this file for the feature's logic and routes.
# Page markup: templates/index.html.  Name, menu entry and on/off default: feature.json.
from flask import Blueprint, jsonify


def init(app, ctx):
    bp = Blueprint("feature_roku", __name__, url_prefix="/ext/roku")

    @bp.route("/")
    def index():
        denied = ctx.admin_page(False)
        if denied is not None:
            return denied
        return ctx.render_page("index.html", title='Roku Dev', description='Develops Roku App and deploys to roku devices.')

    @bp.route("/api/ping")
    def ping():
        denied = ctx.admin_page(True)
        if denied is not None:
            return denied
        return jsonify({"ok": True, "feature": "roku"})

    return bp
