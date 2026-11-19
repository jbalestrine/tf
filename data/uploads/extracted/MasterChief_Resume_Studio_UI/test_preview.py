import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import unquote, urlsplit

import yaml
from docx import Document

import app
import build_resumes


def get(path):
    parts = urlsplit(path)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": unquote(parts.path),
        "raw_path": parts.path.encode("ascii"),
        "query_string": parts.query.encode("ascii"),
        "headers": [],
        "server": ("localhost", 80),
        "client": ("localhost", 1234),
        "root_path": "",
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(app.app(scope, receive, send))
    start = next(message for message in messages if message["type"] == "http.response.start")
    content = b"".join(
        message.get("body", b"")
        for message in messages if message["type"] == "http.response.body"
    )
    return SimpleNamespace(
        status_code=start["status"],
        headers={key.decode().lower(): value.decode() for key, value in start["headers"]},
        content=content,
        text=content.decode("utf-8", errors="replace"),
    )


class PreviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.resume = self.root / "resume.yaml"
        self.data = yaml.safe_load(app.RESUME_YAML.read_text(encoding="utf-8"))
        self.resume.write_text(yaml.safe_dump(self.data), encoding="utf-8")
        self.patches = [
            mock.patch.object(app, "DIST_DIR", self.dist),
            mock.patch.object(app, "RESUME_YAML", self.resume),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_preview_pdf_and_html_inline(self):
        (self.dist / "sample.pdf").write_bytes(b"%PDF-1.4\n")
        (self.dist / "sample.html").write_text("<p>Example</p>", encoding="utf-8")
        pdf = get("/api/preview/sample.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers["content-type"], "application/pdf")
        self.assertTrue(pdf.headers["content-disposition"].startswith("inline"))
        self.assertEqual(pdf.content, b"%PDF-1.4\n")
        html = get("/api/preview/sample.html")
        self.assertEqual(html.status_code, 200)
        self.assertTrue(html.headers["content-type"].startswith("text/html"))
        self.assertIn("<p>Example</p>", html.text)
        self.assertIn("sandbox", html.headers["content-security-policy"])

    def test_preview_docx(self):
        document = Document()
        document.add_heading("Example Resume", 0)
        document.add_paragraph("Cloud architecture")
        document.save(self.dist / "sample.docx")
        response = get("/api/preview/sample.docx")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/html"))
        self.assertIn("Example Resume", response.text)
        self.assertIn("Cloud architecture", response.text)
        self.assertIn("<main>", response.text)
        self.assertIn("sandbox", response.headers["content-security-policy"])

    def test_generated_standard_docx_has_semantic_preview_styles(self):
        for tier in ("master", "exec", "slideedition"):
            with self.subTest(tier=tier):
                build_resumes.build_docx(self.data, tier, self.dist / f"{tier}.docx")
                response = get(f"/api/preview/{tier}.docx")
                self.assertEqual(response.status_code, 200)
                self.assertIn('<div class="resume-banner">', response.text)
                self.assertIn('class="banner-name"', response.text)
                self.assertIn('class="banner-eyebrow"', response.text)
                self.assertIn('class="banner-title"', response.text)
                self.assertIn('class="banner-contact"', response.text)
                self.assertIn('<table class="resume-kpis">', response.text)
                self.assertIn('<table class="resume-skills">', response.text)
                self.assertIn('class="resume-job"', response.text)
                self.assertNotIn('class="resume-thread"', response.text)
                self.assertNotIn("Thread:", response.text)
                self.assertIn('<div class="resume-timeline">', response.text)
                self.assertEqual(response.text.count('<div class="resume-timeline">'), 1)
                self.assertIn('<table class="resume-microsoft">', response.text)
                self.assertIn("<ul><li>", response.text)
                self.assertIn(self.data["profile"]["name"], response.text)
                for metric in self.data["metrics"]:
                    self.assertIn(metric["value"], response.text)
                    self.assertIn(metric["label"].replace("&", "&amp;"), response.text)
                for job in self.data["experience"]:
                    if tier in job["tiers"]:
                        self.assertIn(job["company"].replace("&", "&amp;"), response.text)

    def test_preview_missing_unsupported_and_invalid_paths(self):
        (self.dist / "example.txt").write_text("text", encoding="utf-8")
        self.assertEqual(get("/api/preview/missing.pdf").status_code, 404)
        self.assertEqual(get("/api/preview/example.txt").status_code, 415)
        self.assertEqual(get("/api/preview/..%5Cresume.yaml").status_code, 400)

    def test_template_uses_saved_yaml_and_escapes_values(self):
        self.data["profile"]["name"] = "Example <script>alert(1)</script>"
        self.resume.write_text(yaml.safe_dump(self.data), encoding="utf-8")
        response = get("/api/preview-template")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Example &lt;script&gt;alert(1)&lt;/script&gt;", response.text)
        self.assertIn("sandbox", response.headers["content-security-policy"])
        self.data["profile"]["name"] = "Updated Name"
        self.resume.write_text(yaml.safe_dump(self.data), encoding="utf-8")
        self.assertIn("Updated Name", get("/api/preview-template").text)

    def test_missing_template_or_invalid_yaml_root(self):
        self.resume.write_text("- item", encoding="utf-8")
        self.assertEqual(get("/api/preview-template").status_code, 422)
        with mock.patch.object(app, "TEMPLATE_HTML", self.root / "missing.html"):
            self.assertEqual(get("/api/preview-template").status_code, 404)


if __name__ == "__main__":
    unittest.main()
