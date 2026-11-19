import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml
from docx import Document
from fastapi import HTTPException

import app
import build_resumes
import studio_tools
import techlearn_router as learn


def request(method, path, body=None):
    encoded = json.dumps(body).encode() if body is not None else b""
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "http_version": "1.1", "method": method, "scheme": "http", "path": path,
             "raw_path": path.encode(), "query_string": b"", "headers": [(b"content-type", b"application/json")],
             "server": ("localhost", 80), "client": ("localhost", 1), "root_path": ""}
    messages = []
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": encoded, "more_body": False}
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    asyncio.run(app.app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], body


class StudioFeatureTest(unittest.TestCase):
    def test_video_url_validation(self):
        self.assertEqual(learn.video_id("https://youtu.be/abcdefghijk"), "abcdefghijk")
        self.assertEqual(learn.video_id("https://www.youtube.com/watch?v=abcdefghijk"), "abcdefghijk")
        for value in ("https://youtube.com.evil.test/watch?v=abcdefghijk", "file:///etc/passwd",
                      "https://youtube.com/watch?v=bad"):
            with self.assertRaises(ValueError):
                learn.video_id(value)

    def test_study_and_wiki(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(learn, "WIKI", Path(directory)):
            with mock.patch.object(learn, "local_llm", return_value=(None, None)):
                entry = learn.create_study("Test", "Terraform supports configuration. Kubernetes runs workloads.", "youtube")
            self.assertTrue(entry["rules"])
            self.assertTrue(entry["flashcards"])
            self.assertEqual(len(learn.wiki(q="Terraform", tag="Kubernetes")), 1)
            self.assertEqual(learn.delete_wiki(entry["id"])["deleted"], entry["id"])
            with self.assertRaises(HTTPException):
                learn.delete_wiki("../bad")

    def test_offline_model_fallback_and_remote_rejection(self):
        with mock.patch.object(learn, "settings", return_value={"LLM_ENDPOINT_URL": "http://example.com/v1/chat/completions", "LLM_MODEL": "model"}):
            result, warning = learn.local_llm("private text")
            self.assertIsNone(result)
            self.assertIn("loopback", warning)
        with mock.patch.object(learn, "settings", return_value={"LLM_ENDPOINT_URL": "http://127.0.0.1:1/api/generate", "LLM_MODEL": "model"}):
            result, warning = learn.local_llm("private text")
            self.assertIsNone(result)
            self.assertIn("local content", warning)

    def test_video_transcript_and_disabled_captions(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(learn, "WIKI", Path(directory)):
            with mock.patch.object(learn, "local_llm", return_value=(None, None)):
                with mock.patch.object(learn, "YouTubeTranscriptApi") as api:
                    api.return_value.fetch.return_value = [
                        mock.Mock(text="Terraform provisions infrastructure safely."),
                        mock.Mock(text="What is state? State records infrastructure resources."),
                    ]
                    entry = learn.youtube(learn.VideoRequest(url="https://youtu.be/abcdefghijk"))
                    self.assertTrue(entry["takeaways"])
                    self.assertTrue(entry["flashcards"])
                    api.return_value.fetch.side_effect = learn.YouTubeTranscriptApiException("unavailable")
                    with self.assertRaises(HTTPException) as error:
                        learn.youtube(learn.VideoRequest(url="https://youtu.be/abcdefghijk"))
                    self.assertEqual(error.exception.status_code, 502)

    def test_public_only_isolates_private_routes(self):
        with mock.patch.dict(os.environ, {"MASTERCHIEF_PUBLIC_ONLY": "1"}):
            self.assertEqual(request("GET", "/portfolio")[0], 200)
            status, body = request("GET", "/api/portfolio/data")
            self.assertEqual(status, 200)
            self.assertNotIn("email", json.loads(body)["titles"])
            for path in ("/", "/api/resume", "/api/files", "/techlearn", "/docs",
                         "/api/portfolio/download/not-approved.docx"):
                self.assertEqual(request("GET", path)[0], 404, path)
            self.assertEqual(request("POST", "/api/resume", {})[0], 404)

    def test_jd_matching_and_crm(self):
        result = studio_tools.analyze(studio_tools.JDRequest(job_description="Terraform and ArgoCD"))
        self.assertIn("Terraform", result["matched"])
        self.assertIn("ArgoCD", result["missing"])
        self.assertEqual(result["score"], 50)
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(studio_tools, "SUBMISSIONS", Path(directory) / "submissions.json"):
            submission = studio_tools.Submission(company="Example", role_title="Architect",
                                                 date="2026-01-01", status="Submitted")
            saved = studio_tools.add_submission(submission)
            submission.status = "Offer"
            studio_tools.update_submission(saved["id"], submission)
            self.assertEqual(studio_tools.list_submissions()[0]["status"], "Offer")

    def test_interview_content(self):
        data = yaml.safe_load((Path(__file__).parent / "resume.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "interview.docx"
            build_resumes.build_interview_prep(data, path)
            text = "\n".join(p.text for p in Document(path).paragraphs)
            for phrase in ("Isolate Capacities", "Git + Service Principal", "Compliance Guardrails", "Automated Blueprints"):
                self.assertIn(phrase, text)
            self.assertIn(data["metrics"][0]["value"], text)


if __name__ == "__main__":
    unittest.main()
