import hashlib

import pytest
from flask import Flask

from managers.page_editor import PageEditor, PageEditorError

LAYOUT = '<details><summary class="dropbtn">Operate</summary><a href="/hello">Hello</a></details>'


def _setup(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "page.py").write_text(
        'PAGE_TEMPLATE = """<h1 id="title">Hello</h1>\n<p>Body</p>"""\n\n\ndef hello():\n    return PAGE_TEMPLATE\n',
        encoding="utf-8", newline="",
    )
    app = Flask(__name__)
    ns = {}
    exec(compile((tmp_path / "page.py").read_text(encoding="utf-8"), str(tmp_path / "page.py"), "exec"), ns)
    app.add_url_rule("/hello", "hello", ns["hello"])
    return PageEditor(app, tmp_path, LAYOUT)


def test_pages_from_nav(tmp_path):
    pe = _setup(tmp_path)
    groups = {g["group"]: g["pages"] for g in pe.pages()}
    assert groups["Operate"][0]["url"] == "/hello"


def test_segments_and_find(tmp_path):
    pe = _setup(tmp_path)
    info = pe.page_segments("/hello")
    labels = {s["label"] for s in info["segments"]}
    assert "PAGE_TEMPLATE" in labels
    hits = pe.find("/hello", 'id="title"')
    assert hits and hits[0]["lines"] == [1]


def test_save_validates_backs_up_and_checks_hash(tmp_path):
    pe = _setup(tmp_path)
    seg = pe.read_segment("page.py", 1, 2)
    bad = pe.preview("page.py", 1, 2, 'PAGE_TEMPLATE = """unterminated', seg["sha"])
    assert bad["problems"]
    with pytest.raises(PageEditorError):
        pe.save("page.py", 1, 2, 'PAGE_TEMPLATE = """unterminated', seg["sha"])
    res = pe.save("page.py", 1, 2, 'PAGE_TEMPLATE = """<h1>Changed</h1>"""', seg["sha"])
    assert "Changed" in (tmp_path / "page.py").read_text(encoding="utf-8")
    assert pe.backups("page.py")[0]["name"] == res["backup"]
    with pytest.raises(PageEditorError):
        pe.save("page.py", 1, 1, "X = 1", seg["sha"])  # stale hash
    new_sha = hashlib.sha256((tmp_path / "page.py").read_bytes()).hexdigest()
    pe.restore("page.py", res["backup"], new_sha)
    assert "Body" in (tmp_path / "page.py").read_text(encoding="utf-8")


def test_blocked_paths(tmp_path):
    pe = _setup(tmp_path)
    (tmp_path / "data" / "rbac.json").write_text("{}", encoding="utf-8")
    for bad in ("data/rbac.json", "../etc/passwd", "page.exe", ".env"):
        with pytest.raises(PageEditorError):
            pe.read_segment(bad, 1, 1)
