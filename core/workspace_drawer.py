"""Inject the independent workspace drawer into full HTML documents."""

_ASSETS = (b'<link rel="stylesheet" href="/static/workspace-drawer.css">'
           b'<script defer src="/static/workspace-drawer.js"></script>')


def add_workspace_drawer(response):
    if (response.mimetype != "text/html" or response.status_code != 200
            or response.headers.get("Content-Disposition", "").lower().startswith("attachment")
            or response.headers.get("Content-Encoding")):
        return response
    if response.is_streamed:
        response.direct_passthrough = False
    body = response.get_data()
    if b'/static/workspace-drawer.js' in body:
        return response
    body_start = body.lower().find(b"<body")
    if body_start < 0:
        return response
    end = body.find(b">", body_start)
    if end < 0:
        return response
    response.set_data(body[:end + 1] + _ASSETS + body[end + 1:])
    response.headers.pop("ETag", None)
    response.headers["Cache-Control"] = "no-store"
    return response
