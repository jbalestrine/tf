import pytest
from flask import Flask

from managers.page_editor import PageEditor
from managers.site_settings import SiteSettings, SiteSettingsError

LAYOUT = '''HTML_TEMPLATE = """<!DOCTYPE html>
<title>Old Title</title>
<header id="masterchief-site-brand">
<a href="/"><img src="/static/masterchief-logo.svg" alt="Old alt" style="width:min(360px,75vw);"></a>
</header>
<nav aria-label="Main navigation">
  <a href="/" class="{{ 'active' if request.path=='/' else '' }}">Dashboard</a>
  <details class="nav-group">
    <summary class="dropbtn">Operate &amp; More</summary>
    <div>
      <a href="/one" class="x">One</a>
      <a href="/two" class="x">Two</a>
    </div>
  </details>
</nav>
"""
'''
ABOUT = '<title>About - Old</title>\n<h1>Head</h1>\n<p class="hero-description">\n   First   line\n   second.\n</p>\n'


def _make(tmp_path, with_base=True):
    (tmp_path / "data").mkdir()
    (tmp_path / "static").mkdir()
    (tmp_path / "templates").mkdir()
    (tmp_path / "masterchief").mkdir()
    (tmp_path / "main.py").write_bytes(LAYOUT.replace("\n", "\r\n").encode())
    if with_base:
        (tmp_path / "templates" / "base.py").write_text(LAYOUT, encoding="utf-8", newline="")
    (tmp_path / "about.html").write_text(ABOUT, encoding="utf-8")
    (tmp_path / "setup.py").write_text('setup(\n    version="1.0.0",\n)\n', encoding="utf-8")
    (tmp_path / "masterchief" / "__init__.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
    (tmp_path / "static" / "masterchief-logo.svg").write_text("<svg></svg>", encoding="utf-8")
    return SiteSettings(PageEditor(Flask(__name__), tmp_path, LAYOUT))


def test_overview_reads_values(tmp_path):
    ss = _make(tmp_path)
    o = ss.overview()
    vals = {f["id"]: f["value"] for g in o["groups"] for f in g["fields"]}
    assert vals["site_title"] == "Old Title" and vals["logo_alt"] == "Old alt" and vals["logo_width"] == "360"
    assert vals["version"] == "1.0.0" and vals["about_description"] == "First line second."
    assert o["nav"]["groups"][1]["label"] == "Operate & More"
    assert o["logo"]["src"] == "/static/masterchief-logo.svg"


def test_save_fields_in_every_file_and_keep_crlf(tmp_path):
    ss = _make(tmp_path)
    ss.save({"site_title": "New <T>", "logo_alt": 'Say "hi"', "version": "2.1.0", "about_description": "Brand new text"})
    main = (tmp_path / "main.py").read_bytes().decode()
    assert "<title>New &lt;T&gt;</title>" in main and 'alt="Say &quot;hi&quot;"' in main and "\r\n" in main
    assert "New &lt;T&gt;" in (tmp_path / "templates" / "base.py").read_text(encoding="utf-8")
    assert 'version="2.1.0"' in (tmp_path / "setup.py").read_text() and '"2.1.0"' in (tmp_path / "masterchief" / "__init__.py").read_text()
    assert "Brand new text" in (tmp_path / "about.html").read_text()
    assert list((tmp_path / "data" / "page_editor_backups").iterdir())


def test_validation(tmp_path):
    ss = _make(tmp_path)
    for values in ({"version": "abc"}, {"site_title": "{{ evil }}"}, {"logo_width": "5"}, {"nope": "x"}):
        with pytest.raises(SiteSettingsError):
            ss.preview(values)


def test_nav_ops(tmp_path):
    ss = _make(tmp_path)
    nav = ss.nav()["groups"]
    group, one = nav[1], nav[1]["links"][0]
    ss.nav_save({"type": "rename_group", "line": group["line"], "label": "Ops & Co"})
    ss.nav_save({"type": "rename_link", "line": one["line"], "label": "Uno", "href": "/uno"})
    nav = ss.nav()["groups"]
    assert nav[1]["label"] == "Ops & Co" and nav[1]["links"][0]["href"] == "/uno"
    last = nav[1]["links"][-1]
    ss.nav_save({"type": "add_link", "line": last["line"], "label": "Three", "href": "/three"})
    assert [l["href"] for l in ss.nav()["groups"][1]["links"]] == ["/uno", "/two", "/three"]
    two = ss.nav()["groups"][1]["links"][1]
    ss.nav_save({"type": "remove_link", "line": two["line"], "href": "/two"})
    assert [l["href"] for l in ss.nav()["groups"][1]["links"]] == ["/uno", "/three"]
    base = (tmp_path / "templates" / "base.py").read_text(encoding="utf-8")
    assert "/three" in base and "/two" not in base and "Ops &amp; Co" in base
    with pytest.raises(SiteSettingsError):
        ss.nav_preview({"type": "add_link", "line": last["line"], "label": "x", "href": "javascript:alert(1)"})


def test_logo_upload_rules_and_switch(tmp_path):
    ss = _make(tmp_path)
    for name, data in (("a.svg", b"<svg><script>x</script></svg>"), ("a.png", b"notpng"), ("a.exe", b"MZ"), ("a.svg", b"")):
        with pytest.raises(SiteSettingsError):
            ss.set_logo(name, data)
    result = ss.set_logo("new.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    assert result["logo"] == "/static/masterchief-logo.png" and (tmp_path / "static" / "masterchief-logo.png").exists()
    assert ss.logo_info()["src"] == "/static/masterchief-logo.png"
    assert (tmp_path / "static" / "masterchief-logo.svg").exists() and result["backup"]
