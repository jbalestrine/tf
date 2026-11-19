import asyncio
import io
import unittest
from unittest import mock

from docx import Document
from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from reportlab.pdfgen import canvas

import app
import visual_resume


class VisualResumeTests(unittest.TestCase):
    def test_create_and_export_document(self):
        html = "<h1>Ada Example</h1><p>Cloud <strong>architect</strong></p><ul><li>Built platforms</li></ul>"
        response = app.visual_resume_export("docx", app.VisualResumePayload(html=html))
        self.assertEqual(response.status_code, 200)
        document = Document(io.BytesIO(response.body))
        self.assertEqual(document.paragraphs[0].text, "Ada Example")
        self.assertTrue(document.paragraphs[1].runs[-1].bold)
        self.assertEqual(document.paragraphs[2].style.name, "List Bullet")
        response = app.visual_resume_export("pdf", app.VisualResumePayload(html=html))
        self.assertEqual(response.status_code, 200)
        pdf = PdfReader(io.BytesIO(response.body))
        text = "\n".join(page.extract_text() for page in pdf.pages)
        self.assertIn("Ada Example", text)
        self.assertIn("architect", text)
        self.assertIn("Built platforms", text)

    def test_import_docx_and_pdf_text_without_mutating_profile(self):
        doc = Document()
        doc.add_paragraph("Name <script>alert(1)</script>")
        stream = io.BytesIO()
        doc.save(stream)
        pdf_stream = io.BytesIO()
        pdf = canvas.Canvas(pdf_stream)
        pdf.drawString(40, 750, "PDF Example")
        pdf.save()
        with mock.patch.object(app.profile_store, "save_current") as save:
            for name, data, expected in (("source.docx", stream.getvalue(), "&lt;script&gt;"),
                                         ("source.pdf", pdf_stream.getvalue(), "PDF Example")):
                response = asyncio.run(app.visual_resume_import(UploadFile(filename=name, file=io.BytesIO(data))))
                self.assertIn(expected, response["html"])
                self.assertIn("original is unchanged", response["warning"])
            save.assert_not_called()

    def test_rejects_empty_and_unsupported_documents(self):
        with self.assertRaises(HTTPException):
            app.visual_resume_export("docx", app.VisualResumePayload(html=""))
        with self.assertRaises(HTTPException):
            app.visual_resume_export("html", app.VisualResumePayload(html="x"))
        for name in ("bad.txt", "bad.docx"):
            with self.assertRaises(HTTPException):
                asyncio.run(app.visual_resume_import(UploadFile(filename=name, file=io.BytesIO(b"bad"))))

    def test_discards_active_content(self):
        doc = Document(io.BytesIO(visual_resume.docx_bytes("<p>Safe<script>danger</script><b> text</b></p>")))
        self.assertEqual(doc.paragraphs[0].text, "Safe text")


if __name__ == "__main__":
    unittest.main()
