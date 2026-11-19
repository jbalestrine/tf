import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml
from docx import Document
from reportlab.pdfgen import canvas
from starlette.datastructures import UploadFile

import app
import build_resumes
import profile_store as store


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.resume = root / "resume.yaml"
        self.original = store.RESUME.read_text(encoding="utf-8")
        self.resume.write_text(self.original, encoding="utf-8")
        for key, path in (("RESUME", self.resume), ("PROFILES", root / "profiles"), ("ACTIVE", root / "profiles" / ".active")):
            patch = mock.patch.object(store, key, path)
            patch.start()
            self.addCleanup(patch.stop)

    def test_initial_clone_switch_and_saves(self):
        self.assertEqual(store.list_profiles(), {"active": "default", "profiles": ["default"]})
        self.assertEqual((store.PROFILES / "default.yaml").read_text(encoding="utf-8"), self.original)
        store.create("azure_architect", self.original)
        changed = yaml.safe_load(self.original)
        changed["profile"]["name"] = "Example Person"
        store.save_current(yaml.safe_dump(changed, allow_unicode=True), "default")
        store.switch("azure_architect", "default")
        self.assertEqual(yaml.safe_load(self.resume.read_text(encoding="utf-8"))["profile"]["name"],
                         yaml.safe_load(self.original)["profile"]["name"])
        with self.assertRaisesRegex(ValueError, "changed"):
            store.save_current(self.original, "default")
        store.switch("default", "azure_architect")
        self.assertEqual(yaml.safe_load(self.resume.read_text(encoding="utf-8"))["profile"]["name"], "Example Person")
        with self.assertRaises(FileExistsError):
            store.create("DEFAULT", self.original)
        for bad in ("../escape", "CON", "a.yaml", ""):
            with self.assertRaises(ValueError):
                store.create(bad, self.original)

    def test_structured_import_and_rejected_invalid(self):
        data = yaml.safe_load(self.original)
        for name, content in (("a.yaml", self.original.encode()), ("a.json", json.dumps(data).encode())):
            raw, warnings = store.import_file(name, content)
            self.assertEqual(yaml.safe_load(raw), data)
            self.assertEqual(warnings, [])
        with self.assertRaises(ValueError):
            store.import_file("bad.yaml", b"profile: {}")

    def test_docx_and_pdf_import_and_build(self):
        document = Document()
        for line in ("Jane Example", "jane@example.com", "Summary", "Cloud specialist.",
                     "Skills", "Terraform", "Experience", "Engineer | Acme | 2020-2024", "Built systems."):
            document.add_paragraph(line)
        docx = io.BytesIO()
        document.save(docx)
        pdf = io.BytesIO()
        page = canvas.Canvas(pdf)
        page.drawString(40, 750, "Jane Example")
        page.drawString(40, 730, "Skills")
        page.drawString(40, 710, "Terraform")
        page.save()
        for name, content in (("resume.docx", docx.getvalue()), ("resume.pdf", pdf.getvalue())):
            with self.subTest(name=name), mock.patch.object(store, "local_json_request", return_value=(None, None)):
                raw, warnings = store.import_file(name, content)
                parsed = yaml.safe_load(raw)
                self.assertEqual(parsed["profile"]["name"], "Jane Example")
                self.assertIn("Terraform", parsed["import_source_text"])
                self.assertEqual(parsed["metrics"], [])
                self.assertEqual(parsed["microsoft_block"]["company"], "")
                self.assertTrue(warnings)
                build_resumes.build_docx(parsed, "master", self.resume.parent / "test.docx")
                build_resumes.build_pdf(parsed, Path(__file__).parent / "template_v2.html", self.resume.parent / "test.pdf")
        with self.assertRaisesRegex(ValueError, "No text"):
            blank = io.BytesIO()
            page = canvas.Canvas(blank)
            page.showPage()
            page.save()
            store.import_file("scanned.pdf", blank.getvalue())

    def test_llm_invalid_content_falls_back(self):
        document = Document()
        document.add_paragraph("Jane Example")
        document.add_paragraph("Skills")
        document.add_paragraph("Terraform")
        stream = io.BytesIO()
        document.save(stream)
        with mock.patch.object(store, "local_json_request", return_value=(
            {"name": "Invented", "summary": "", "skills": [], "experience": []}, None)):
            raw, warnings = store.import_file("resume.docx", stream.getvalue())
        self.assertEqual(yaml.safe_load(raw)["profile"]["name"], "Jane Example")
        self.assertTrue(any("not verbatim" in x for x in warnings))

    def test_llm_verbatim_extraction_and_failed_switch_cleanup(self):
        document = Document()
        document.add_paragraph("Jane Example")
        document.add_paragraph("Engineer at Acme")
        stream = io.BytesIO()
        document.save(stream)
        model = {"name": "Jane Example", "summary": "", "skills": [],
                 "experience": [{"role": "Engineer", "company": "Acme", "location": "", "dates": "",
                                 "bullets": ["Engineer at Acme"]}]}
        with mock.patch.object(store, "local_json_request", return_value=(model, None)):
            raw, _ = store.import_file("resume.docx", stream.getvalue())
        self.assertEqual(yaml.safe_load(raw)["experience"][0]["company"], "Acme")
        store.initialize()
        with mock.patch.object(store, "switch", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                store.create("failed", raw, activate=True)
        self.assertFalse((store.PROFILES / "failed.yaml").exists())
        self.assertEqual(store.list_profiles()["active"], "default")

    def test_upload_api_switches_and_rejects_large_files(self):
        store.initialize()
        upload = UploadFile(filename="resume.yaml", file=io.BytesIO(self.original.encode()))
        result = asyncio.run(app.import_profile(upload, "imported", "default"))
        self.assertEqual(result["active"], "imported")
        self.assertEqual(store.list_profiles()["active"], "imported")
        large = UploadFile(filename="resume.yaml", file=io.BytesIO(b"x" * (store.MAX_UPLOAD + 1)))
        with self.assertRaises(app.HTTPException) as error:
            asyncio.run(app.import_profile(large, "large", "imported"))
        self.assertEqual(error.exception.status_code, 413)

    def test_api_save_updates_active_profile(self):
        store.initialize()
        backup = self.resume.parent / "backups"
        backup.mkdir()
        data = yaml.safe_load(self.original)
        data["profile"]["name"] = "Updated Name"
        with mock.patch.object(app, "RESUME_YAML", self.resume), mock.patch.object(app, "BACKUP_DIR", backup):
            app.save_resume(app.ResumePayload(data=data, active_profile="default"))
            self.assertEqual(app.get_resume()["active_profile"], "default")
        self.assertEqual(yaml.safe_load((store.PROFILES / "default.yaml").read_text(encoding="utf-8"))["profile"]["name"], "Updated Name")
        self.assertTrue(list(backup.iterdir()))


if __name__ == "__main__":
    unittest.main()
