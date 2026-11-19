import contextlib
import io
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from docx import Document
from docx.oxml.ns import qn
import yaml

import build_resumes


ROOT = Path(__file__).resolve().parent
DOCX_OUTPUTS = {
    "master": "Joseph_Balestrine_DevOps_Architect_Master.docx",
    "exec": "Joseph_Balestrine_Executive_2Page.docx",
    "slideedition": "Joseph_Balestrine_Slide_Edition.docx",
    "coverletter": "Joseph_Balestrine_Cover_Letter.docx",
    "interviewprep": "Joseph_Balestrine_Interview_WarRoom.docx",
}
PDF_OUTPUT = "Joseph_Balestrine_Architect_Portfolio.pdf"


class BuildTargetsTest(unittest.TestCase):
    def test_standard_documents_have_editable_tier_filtered_layout(self):
        data = yaml.safe_load((ROOT / "resume.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            for tier in ("master", "exec", "slideedition"):
                with self.subTest(tier=tier):
                    path = Path(directory) / f"{tier}.docx"
                    build_resumes.build_docx(data, tier, path)
                    document = Document(path)
                    metrics, domains, microsoft = document.tables
                    self.assertEqual(len(metrics.columns), 4)
                    self.assertEqual(
                        [cell.paragraphs[0].text for row in metrics.rows for cell in row.cells],
                        [metric["value"] for metric in data["metrics"]],
                    )
                    self.assertEqual(
                        [cell.paragraphs[1].text for row in metrics.rows for cell in row.cells],
                        [metric["label"] for metric in data["metrics"]],
                    )
                    self.assertEqual(len(domains.columns), 2)
                    selected = [group for group in data["skills"] if tier in group["tiers"]]
                    self.assertEqual(len(domains.rows), len(selected))
                    for index, (row, group) in enumerate(zip(domains.rows, selected)):
                        self.assertEqual(row.cells[0].text, f'{group["category"]}:')
                        self.assertEqual(row.cells[1].text, " | ".join(group["items"]))
                        for cell in row.cells:
                            shading = cell._tc.tcPr.find(qn("w:shd"))
                            self.assertEqual(shading.get(qn("w:fill")), "F0F6FF" if index % 2 == 0 else "DEECF9")
                    for index, cell in enumerate(metrics.rows[0].cells):
                        border = cell._tc.tcPr.find(qn("w:tcBorders")).find(qn("w:top"))
                        self.assertEqual(border.get(qn("w:color")), "50E6FF")
                        self.assertEqual(border.get(qn("w:sz")), "24")
                    self.assertEqual(document.paragraphs[0].text, build_resumes.EYEBROW)
                    for paragraph in document.paragraphs[1:4]:
                        self.assertEqual(paragraph._p.pPr.find(qn("w:shd")).get(qn("w:fill")), "002050")
                        self.assertEqual(str(paragraph.runs[0].font.color.rgb), "FFFFFF")
                    self.assertEqual(
                        document.paragraphs[3]._p.pPr.find(qn("w:pBdr")).find(qn("w:bottom")).get(qn("w:color")),
                        "50E6FF",
                    )
                    headers = [
                        p for p in document.paragraphs
                        if any(p.text.startswith(f'◈ {job["role"]} — {job["company"]}')
                               for job in data["experience"] if tier in job["tiers"])
                    ]
                    self.assertEqual(len(headers), sum(tier in job["tiers"] for job in data["experience"]))
                    headers.append(microsoft.cell(0, 0).paragraphs[0])
                    for paragraph in headers:
                        props = paragraph._p.pPr
                        self.assertEqual(props.find(qn("w:shd")).get(qn("w:fill")), "F0F6FF")
                        left = props.find(qn("w:pBdr")).find(qn("w:left"))
                        self.assertEqual(left.get(qn("w:color")), "0078D4")
                        self.assertEqual(left.get(qn("w:sz")), "24")
                        for edge in ("top", "bottom", "right"):
                            self.assertEqual(props.find(qn("w:pBdr")).find(qn(f"w:{edge}")).get(qn("w:color")), "B4D6FA")
                    cell_border = microsoft.cell(0, 0)._tc.tcPr.find(qn("w:tcBorders"))
                    self.assertEqual(cell_border.find(qn("w:left")).get(qn("w:color")), "0078D4")
                    self.assertEqual(cell_border.find(qn("w:top")).get(qn("w:color")), "B4D6FA")
                    paragraphs = list(document.paragraphs)
                    for table in document.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                paragraphs.extend(cell.paragraphs)
                    self.assertFalse(any("Thread:" in p.text for p in paragraphs))
                    self.assertFalse(any(p.style.name in ("Resume Tech Thread", "Resume Microsoft Thread")
                                         for p in paragraphs))
                    self.assertTrue(any(p.style.name == "Resume Timeline Bullet" for p in document.paragraphs))
                    self.assertEqual(len(document.inline_shapes), 0)

    def test_standard_metric_strip_does_not_drop_extra_metrics(self):
        data = yaml.safe_load((ROOT / "resume.yaml").read_text(encoding="utf-8"))
        data["metrics"].append({"value": "Extra", "label": "Fifth metric"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.docx"
            build_resumes.build_docx(data, "master", path)
            table = Document(path).tables[0]
            self.assertEqual(len(table.rows), 2)
            self.assertIn("Fifth metric", table.cell(1, 0).text)

    def test_all_targets_generate_expected_files_without_external_processes(self):
        for target in (*DOCX_OUTPUTS, "pdf", "all"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ("build_resumes.py", "resume.yaml", "template_v2.html"):
                    shutil.copy2(ROOT / name, root / name)
                argv = [
                    str(root / "build_resumes.py"), "--target", target,
                    "--company", "Example Company", "--role", "Cloud Architect",
                ]
                with mock.patch.object(sys, "argv", argv), \
                        mock.patch.object(subprocess, "Popen", side_effect=AssertionError("external process")), \
                        contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(root / "build_resumes.py"), run_name="__main__")

                dist = root / "dist"
                expected = DOCX_OUTPUTS if target == "all" else (
                    {target: DOCX_OUTPUTS[target]} if target in DOCX_OUTPUTS else {}
                )
                expected_names = set(expected.values())
                if target in ("all", "pdf"):
                    expected_names.add(PDF_OUTPUT)
                    self.assertTrue((dist / PDF_OUTPUT).read_bytes().startswith(b"%PDF-"))
                self.assertEqual({path.name for path in dist.iterdir()}, expected_names)
                for name in expected.values():
                    self.assertTrue(Document(dist / name).paragraphs)
                if "coverletter" in expected:
                    letter = Document(dist / expected["coverletter"])
                    text = "\n".join(paragraph.text for paragraph in letter.paragraphs)
                    self.assertIn("Example Company", text)
                    self.assertIn("Cloud Architect", text)
                    self.assertNotIn("{company_name}", text)
                    self.assertNotIn("{role_title}", text)

    def test_pdf_includes_selected_content_and_escapes_text(self):
        data = yaml.safe_load((ROOT / "resume.yaml").read_text(encoding="utf-8"))
        data["profile"]["name"] = "Example <Name> & Co"
        data["experience"][0]["bullets"][0]["text"] = "Selected <PDF> bullet"
        data["experience"][0]["bullets"][1]["text"] = "Excluded bullet"
        data["experience"][0]["bullets"][1]["tiers"] = ["master"]
        pdf = mock.Mock()
        pdf.width = 500
        with mock.patch.object(build_resumes, "SimpleDocTemplate", return_value=pdf):
            build_resumes.build_pdf(data, ROOT / "template_v2.html", "unused.pdf")
        story = pdf.build.call_args.args[0]
        text = "\n".join(getattr(item, "text", "") for item in story)
        self.assertNotIn("Thread:", text)
        self.assertIn("Selected &lt;PDF&gt; bullet", text)
        self.assertNotIn("Excluded bullet", text)
        self.assertIn(data["profile"]["summary"], text)
        microsoft_card = next(
            item for item in story
            if hasattr(item, "_cellvalues")
            and any(data["microsoft_block"]["company"] in getattr(cell, "text", "")
                    for row in item._cellvalues for cell in row)
        )
        self.assertTrue(microsoft_card._cellvalues)
        self.assertFalse(any("Thread:" in getattr(cell, "text", "")
                             for row in microsoft_card._cellvalues for cell in row))
        self.assertIn(data["education"][0]["credential"], text)

    def test_missing_logo_is_reported(self):
        data = yaml.safe_load((ROOT / "resume.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "missing.html"
            template.write_text("<html></html>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Brand logo not found"):
                build_resumes.build_pdf(data, template, Path(directory) / "out.pdf")


if __name__ == "__main__":
    unittest.main()
