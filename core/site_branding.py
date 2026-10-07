"""Shared page branding for full-document HTML responses."""


_SITE_BRAND = (
    b'<header id="masterchief-site-brand" role="banner" '
    b'style="display:flex;align-items:center;min-height:76px;padding:8px 20px;'
    b'background:#101827;border-bottom:1px solid #334155;">'
    b'<a href="/" aria-label="MasterChief home" style="display:inline-flex;align-items:center;">'
    b'<img src="/static/masterchief-logo.svg" alt="MasterChief - Echo Starlite DevOps Suite" '
    b'style="display:block;width:min(320px,75vw);height:auto;"></a></header>'
)


def add_global_site_brand(response):
    if response.mimetype != "text/html" or response.status_code == 304:
        return response
    if response.is_streamed:
        response.direct_passthrough = False
    body = response.get_data()
    if b'id="masterchief-site-brand"' in body:
        return response

    body_start = body.lower().find(b"<body")
    if body_start < 0:
        return response
    body_open_end = body.find(b">", body_start)
    if body_open_end < 0:
        return response

    response.set_data(body[:body_open_end + 1] + _SITE_BRAND + body[body_open_end + 1:])
    response.headers.pop("ETag", None)
    return response
