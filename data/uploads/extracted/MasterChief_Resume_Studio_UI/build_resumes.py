#!/usr/bin/env python3
"""
Resume-as-Code Build Engine (build_resumes.py)
Reads resume.yaml (Single Source of Truth) and generates:
  1. dist/Joseph_Balestrine_DevOps_Architect_Master.docx
  2. dist/Joseph_Balestrine_Executive_2Page.docx
  3. dist/Joseph_Balestrine_Slide_Edition.docx
  4. dist/Joseph_Balestrine_Cover_Letter.docx
  5. dist/Joseph_Balestrine_Architect_Portfolio.pdf
"""

import argparse
from html import escape
from io import BytesIO
from pathlib import Path
import re

import yaml
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from svglib.svglib import svg2rlg

NAVY = RGBColor(0x00, 0x20, 0x50)
AZURE = RGBColor(0x00, 0x78, 0xD4)
DARK = RGBColor(0x1E, 0x29, 0x3B)
MUTED = RGBColor(0x47, 0x55, 0x69)
EYEBROW = "// ENTERPRISE CLOUD ARCHITECTURE • DEVOPS AUTOMATION • GOVERNANCE"


def set_cell_shading(cell, hex_color):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_bottom_border(paragraph, color_hex="0078D4", size="12"):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), size)
    bottom.set(qn('w:space'), '2')
    bottom.set(qn('w:color'), color_hex)
    pBdr.append(bottom)
    pPr.append(pBdr)


def style_job_header(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), 'F0F6FF')
    pPr.append(shading)
    borders = OxmlElement('w:pBdr')
    for edge in ('top', 'left', 'bottom', 'right'):
        border = OxmlElement(f'w:{edge}')
        for name, value in (
            ('val', 'single'), ('sz', '24' if edge == 'left' else '4'),
            ('space', '6' if edge == 'left' else '2'),
            ('color', '0078D4' if edge == 'left' else 'B4D6FA'),
        ):
            border.set(qn(f'w:{name}'), value)
        borders.append(border)
    pPr.append(borders)


def shade_paragraph(paragraph, color):
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color)
    paragraph._p.get_or_add_pPr().append(shading)


def set_cell_top_border(cell, color):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn('w:tcBorders'))
    if borders is None:
        borders = OxmlElement('w:tcBorders')
        tc_pr.append(borders)
    top = OxmlElement('w:top')
    for name, value in (('val', 'single'), ('sz', '24'), ('color', color)):
        top.set(qn(f'w:{name}'), value)
    borders.append(top)


def add_timeline_border(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)
    left = OxmlElement("w:left")
    for name, value in (("val", "single"), ("sz", "8"), ("space", "6"), ("color", "0078D4")):
        left.set(qn(f"w:{name}"), value)
    borders.append(left)


def style_microsoft_cell(cell):
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        element = OxmlElement(f"w:{edge}")
        for name, value in (("val", "single"), ("sz", "24" if edge == "left" else "4"),
                            ("color", "0078D4" if edge == "left" else "B4D6FA")):
            element.set(qn(f"w:{name}"), value)
        borders.append(element)
    cell._tc.get_or_add_tcPr().append(borders)


def build_docx(data, tier, output_path):
    doc = Document()
    is_exec = (tier == "exec")
    is_standard = tier in ("master", "exec", "slideedition")
    margin = 0.52 if is_exec else 0.58

    for section in doc.sections:
        section.top_margin = Inches(margin)
        section.bottom_margin = Inches(margin)
        section.left_margin = Inches(margin)
        section.right_margin = Inches(margin)

    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(9.5 if is_exec else 10)
    normal.font.color.rgb = DARK
    if is_standard:
        for name in ("Resume Banner Eyebrow", "Resume Banner Name", "Resume Banner Title", "Resume Banner Contact", "Resume Job Header", "Resume Microsoft Header"):
            style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            style.base_style = normal
        bullet_style = doc.styles.add_style("Resume Timeline Bullet", WD_STYLE_TYPE.PARAGRAPH)
        bullet_style.base_style = doc.styles["List Bullet"]
        for name in ("Resume KPI Strip", "Resume Skills Matrix", "Resume Microsoft Block"):
            doc.styles.add_style(name, WD_STYLE_TYPE.TABLE)

    # Header
    p_eyebrow = doc.add_paragraph(style="Resume Banner Eyebrow")
    p_eyebrow.paragraph_format.space_after = Pt(0)
    shade_paragraph(p_eyebrow, "002050")
    eyebrow_run = p_eyebrow.add_run(data['profile'].get('eyebrow', '') if 'import_source_text' in data else EYEBROW)
    eyebrow_run.bold = True
    eyebrow_run.font.size = Pt(7)
    eyebrow_run.font.color.rgb = RGBColor(0x50, 0xE6, 0xFF)
    p_name = doc.add_paragraph(style="Resume Banner Name" if is_standard else None)
    p_name.paragraph_format.space_before = Pt(0)
    p_name.paragraph_format.space_after = Pt(1)
    r_name = p_name.add_run(data['profile']['name'])
    r_name.bold = True
    r_name.font.size = Pt(18 if is_exec else 20)
    r_name.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if is_standard else NAVY
    if is_standard:
        shade_paragraph(p_name, "002050")

    p_title = doc.add_paragraph(style="Resume Banner Title" if is_standard else None)
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(2)
    r_title = p_title.add_run(" | ".join(data['profile']['titles']))
    r_title.bold = True
    r_title.font.size = Pt(10.5)
    r_title.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if is_standard else AZURE
    if is_standard:
        shade_paragraph(p_title, "002050")

    p_contact = doc.add_paragraph(style="Resume Banner Contact" if is_standard else None)
    p_contact.paragraph_format.space_before = Pt(0)
    p_contact.paragraph_format.space_after = Pt(6)
    contact_str = f"{data['profile']['email']}  |  {data['profile']['phone']}  |  {data['profile']['linkedin']}  |  {data['profile']['location']}"
    r_contact = p_contact.add_run(contact_str)
    r_contact.font.size = Pt(9)
    r_contact.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if is_standard else MUTED
    if is_standard:
        shade_paragraph(p_contact, "002050")
    add_bottom_border(p_contact, "50E6FF" if is_standard else "0078D4", "18" if is_standard else "12")

    if is_standard and data['metrics']:
        metrics = data['metrics']
        strip = doc.add_table(rows=(len(metrics) + 3) // 4, cols=4)
        strip.style = "Resume KPI Strip"
        strip.autofit = False
        width = doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin
        for column in strip.columns:
            column.width = width // 4
        for row in strip.rows:
            for index, cell in enumerate(row.cells):
                cell.width = width // 4
                set_cell_shading(cell, "F0F6FF")
                set_cell_margins(cell, top=60, bottom=60, left=75, right=75)
                set_cell_top_border(cell, "50E6FF")
        for index, metric in enumerate(metrics):
            cell = strip.cell(index // 4, index % 4)
            p_value = cell.paragraphs[0]
            p_value.paragraph_format.space_after = Pt(0)
            r_value = p_value.add_run(metric['value'])
            r_value.bold = True
            r_value.font.size = Pt(11)
            r_value.font.color.rgb = AZURE
            p_label = cell.add_paragraph()
            p_label.paragraph_format.space_after = Pt(0)
            r_label = p_label.add_run(metric['label'])
            r_label.font.size = Pt(8)
            r_label.font.color.rgb = DARK

    def add_section_heading(title):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6 if is_exec else 8)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(title.upper())
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = NAVY
        add_bottom_border(p, "CBD5E1", "6")

    # Executive Summary (for Exec tier)
    if is_exec:
        add_section_heading("Executive Summary")
        p_sum = doc.add_paragraph()
        p_sum.paragraph_format.space_before = Pt(1)
        p_sum.paragraph_format.space_after = Pt(4)
        r_sum = p_sum.add_run(data['profile']['summary'])
        r_sum.font.size = Pt(9.5)

    # Skills
    add_section_heading("Core Competencies & Technical Stack")
    groups = [group for group in data['skills'] if tier in group['tiers']]
    if is_standard and groups:
        domains = doc.add_table(rows=len(groups), cols=2)
        domains.style = "Resume Skills Matrix"
        domains.autofit = False
        width = doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin
        domains.columns[0].width = int(width * 0.30)
        domains.columns[1].width = width - domains.columns[0].width
        for index, (row, group) in enumerate(zip(domains.rows, groups)):
            row.cells[0].width = domains.columns[0].width
            row.cells[1].width = domains.columns[1].width
            for cell in row.cells:
                set_cell_shading(cell, "F0F6FF" if index % 2 == 0 else "DEECF9")
                set_cell_margins(cell, top=50, bottom=50, left=90, right=90)
            category = row.cells[0].paragraphs[0]
            category.paragraph_format.space_after = Pt(0)
            r_cat = category.add_run(f"{group['category']}:")
            r_cat.bold = True
            r_cat.font.color.rgb = NAVY
            r_cat.font.size = Pt(9 if is_exec else 9.5)
            items = row.cells[1].paragraphs[0]
            items.paragraph_format.space_after = Pt(0)
            r_items = items.add_run(" | ".join(group['items']))
            r_items.font.size = Pt(9 if is_exec else 9.5)
    elif not is_standard:
        for group in groups:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            r_cat = p.add_run(f"{group['category']}: ")
            r_cat.bold = True
            r_cat.font.color.rgb = NAVY
            r_cat.font.size = Pt(9 if is_exec else 9.5)
            r_items = p.add_run(" | ".join(group['items']))
            r_items.font.size = Pt(9 if is_exec else 9.5)

    # Experience
    add_section_heading("Professional Experience")
    for job in data['experience']:
        if tier not in job['tiers']:
            continue
        p_hdr = doc.add_paragraph(style="Resume Job Header" if is_standard else None)
        p_hdr.paragraph_format.space_before = Pt(5 if is_exec else 6)
        p_hdr.paragraph_format.space_after = Pt(1.5)
        p_hdr.paragraph_format.keep_with_next = True
        p_hdr.paragraph_format.left_indent = Inches(0.22)
        if is_standard:
            style_job_header(p_hdr)

        r_role = p_hdr.add_run(f"◈ {job['role']} — {job['company']}")
        r_role.bold = True
        r_role.font.color.rgb = NAVY
        r_role.font.size = Pt(10 if is_exec else 10.5)

        r_meta = p_hdr.add_run(f"  |  {job['location']}  ({job['dates']})")
        r_meta.bold = True
        r_meta.font.color.rgb = AZURE
        r_meta.font.size = Pt(9 if is_exec else 9.5)

        for b in job['bullets']:
            if tier not in b['tiers']:
                continue
            pb = doc.add_paragraph(style='Resume Timeline Bullet')
            pb.paragraph_format.space_before = Pt(0)
            pb.paragraph_format.space_after = Pt(1.5 if is_exec else 2)
            pb.paragraph_format.left_indent = Inches(0.22)
            add_timeline_border(pb)
            rb_cat = pb.add_run(f"{b['category']}: ")
            rb_cat.bold = True
            rb_cat.font.color.rgb = DARK
            rb_cat.font.size = Pt(9 if is_exec else 9.5)
            rb_txt = pb.add_run(b['text'])
            rb_txt.font.size = Pt(9 if is_exec else 9.5)

    # Enclosed Microsoft Block
    ms = data['microsoft_block']
    tbl = doc.add_table(rows=1, cols=1)
    tbl.style = "Resume Microsoft Block"
    tbl.autofit = False
    tbl.columns[0].width = Inches(8.5 - (margin * 2))
    cell = tbl.cell(0, 0)
    set_cell_shading(cell, "F0F6FF")
    style_microsoft_cell(cell)
    set_cell_margins(cell, top=90, bottom=90, left=130, right=130)

    p_ms_title = cell.paragraphs[0]
    if is_standard:
        p_ms_title.style = "Resume Microsoft Header"
    p_ms_title.paragraph_format.space_before = Pt(0)
    p_ms_title.paragraph_format.space_after = Pt(2)
    if is_standard:
        style_job_header(p_ms_title)
    r_ms1 = p_ms_title.add_run(f"◈ {ms['company']} — {ms['location']}  |  {ms['dates']}")
    r_ms1.bold = True
    r_ms1.font.color.rgb = NAVY
    r_ms1.font.size = Pt(10)

    p_ms_roles = cell.add_paragraph()
    p_ms_roles.paragraph_format.space_before = Pt(0)
    p_ms_roles.paragraph_format.space_after = Pt(4)
    r_msr = p_ms_roles.add_run(" • ".join(ms['roles']))
    r_msr.italic = True
    r_msr.font.color.rgb = AZURE
    r_msr.font.size = Pt(8.5)

    for b in ms['bullets']:
        if tier not in b['tiers']:
            continue
        p_msb = cell.add_paragraph(style='List Bullet')
        p_msb.paragraph_format.space_before = Pt(0)
        p_msb.paragraph_format.space_after = Pt(1.5)
        p_msb.paragraph_format.left_indent = Inches(0.2)
        r_bc = p_msb.add_run(f"{b['category']}: ")
        r_bc.bold = True
        r_bc.font.size = Pt(8.8 if is_exec else 9.2)
        r_bt = p_msb.add_run(b['text'])
        r_bt.font.size = Pt(8.8 if is_exec else 9.2)

    # Earlier Experience
    add_section_heading("Additional & Prior Infrastructure Experience")
    for item in data['earlier_experience']:
        if tier not in item['tiers']:
            continue
        pe = doc.add_paragraph()
        pe.paragraph_format.space_before = Pt(1)
        pe.paragraph_format.space_after = Pt(2)
        re_lbl = pe.add_run(f"{item['company']} ({item['dates']}): ")
        re_lbl.bold = True
        re_lbl.font.size = Pt(8.8 if is_exec else 9.2)
        re_txt = pe.add_run(item['text'])
        re_txt.font.size = Pt(8.8 if is_exec else 9.2)

    # Education
    add_section_heading("Education & Certifications")
    p_ed = doc.add_paragraph()
    p_ed.paragraph_format.space_before = Pt(1)
    p_ed.paragraph_format.space_after = Pt(0)
    ed_parts = []
    for ed in data['education']:
        yr = f" ({ed['year']})" if ed['year'] else ""
        ed_parts.append(f"{ed['credential']} — {ed['institution']}{yr}")
    r_ed = p_ed.add_run("  |  ".join(ed_parts))
    r_ed.bold = True
    r_ed.font.size = Pt(9)

    doc.save(output_path)
    print(f"[OK] Generated {output_path}")


def build_pdf(data, template_path, output_path):
    template = Path(template_path).read_text(encoding="utf-8")
    logo_match = re.search(r'<svg\s+class="brand-logo"[^>]*>.*?</svg>', template, re.DOTALL)
    if not logo_match:
        raise ValueError(f"Brand logo not found in {template_path}")
    logo = svg2rlg(BytesIO(logo_match.group().encode("utf-8")))
    if logo is None:
        raise ValueError(f"Brand logo in {template_path} could not be rendered")

    navy = colors.HexColor("#002050")
    azure = colors.HexColor("#0078D4")
    cyan = colors.HexColor("#50E6FF")
    ice = colors.HexColor("#F0F6FF")
    border = colors.HexColor("#B4D6FA")
    slate = colors.HexColor("#475569")
    white = colors.white
    styles = {
        "name": ParagraphStyle("Name", fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=white),
        "hero": ParagraphStyle("Hero", fontSize=8, leading=11, textColor=white),
        "eyebrow": ParagraphStyle("Eyebrow", fontName="Helvetica-Bold", fontSize=7, leading=10, textColor=cyan),
        "section": ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=navy, spaceBefore=10, spaceAfter=5, keepWithNext=True),
        "body": ParagraphStyle("Body", fontSize=8.5, leading=12, textColor=navy, spaceAfter=4),
        "job": ParagraphStyle("Job", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=navy, spaceBefore=5, keepWithNext=True, backColor=ice, borderColor=border, borderWidth=0.5, borderPadding=5),
        "meta": ParagraphStyle("Meta", fontSize=8, leading=11, textColor=colors.HexColor("#007ACC"), keepWithNext=True),
        "bullet": ParagraphStyle("Bullet", fontSize=8, leading=11, textColor=navy, leftIndent=9, firstLineIndent=-7, spaceAfter=3),
        "metric": ParagraphStyle("Metric", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=azure, alignment=TA_CENTER),
        "metric_label": ParagraphStyle("MetricLabel", fontSize=7, leading=9, textColor=slate, alignment=TA_CENTER),
    }

    class TimelineParagraph(Paragraph):
        def draw(self):
            super().draw()
            self.canv.saveState()
            self.canv.setStrokeColor(azure)
            self.canv.setLineWidth(0.7)
            self.canv.setDash(1, 3)
            self.canv.line(-9, -6, -9, self.height + 6)
            self.canv.restoreState()

    class JobParagraph(TimelineParagraph):
        def draw(self):
            super().draw()
            self.canv.saveState()
            self.canv.setStrokeColor(azure)
            self.canv.setLineWidth(3)
            self.canv.line(-2, -3, -2, self.height + 3)
            self.canv.setFillColor(azure)
            node = self.canv.beginPath()
            y = self.height / 2
            node.moveTo(-9, y + 3)
            node.lineTo(-6, y)
            node.lineTo(-9, y - 3)
            node.lineTo(-12, y)
            node.close()
            self.canv.drawPath(node, fill=1, stroke=0)
            self.canv.restoreState()

    def para(text, style, timeline=False):
        cls = JobParagraph if style == "job" else TimelineParagraph if timeline else Paragraph
        return cls(escape(str(text)), styles[style])

    def heading(text):
        return para(text.upper(), "section")

    def bullet(category, text, timeline=False):
        cls = TimelineParagraph if timeline else Paragraph
        return cls(
            f"&#8226; <b>{escape(str(category))}:</b> {escape(str(text))}",
            styles["bullet"],
        )

    profile = data["profile"]
    title = [
        para(profile.get("eyebrow", "") if "import_source_text" in data else EYEBROW, "eyebrow"),
        para(profile["name"], "name"),
        para(" | ".join(profile["titles"]), "hero"),
        para(f'{profile["email"]}  |  {profile["phone"]}', "hero"),
        para(f'{profile["location"]}  |  {profile["linkedin"]}', "hero"),
    ]
    doc = SimpleDocTemplate(
        str(output_path) if isinstance(output_path, (str, Path)) else output_path, pagesize=letter, leftMargin=0.5 * inch,
        rightMargin=0.5 * inch, topMargin=0.45 * inch, bottomMargin=0.45 * inch,
        title=f'{profile["name"]} - Architect Portfolio',
    )
    hero = Table([[logo, title]], colWidths=[48, doc.width - 48])
    hero.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), navy),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LINEBELOW", (0, 0), (-1, -1), 3, cyan),
    ]))
    story = [hero]
    metrics = [
        [para(metric["value"], "metric"), para(metric["label"], "metric_label")]
        for metric in data["metrics"]
    ]
    if metrics:
        metric_rows = [metrics[i:i + 4] + [""] * (4 - len(metrics[i:i + 4])) for i in range(0, len(metrics), 4)]
        scorecard = Table(metric_rows, colWidths=[doc.width / 4] * 4)
        scorecard.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ice),
            ("LINEABOVE", (0, 0), (-1, -1), 2, cyan),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(scorecard)
    story.extend([heading("Executive Architecture Summary"), para(profile["summary"], "body")])
    story.append(heading("Core Competencies & Technical Stack"))
    for index, group in enumerate(group for group in data["skills"] if "pdf" in group["tiers"]):
        matrix_row = Table([[
            Paragraph(f'<b>{escape(str(group["category"]))}:</b>', styles["body"]),
            para(" | ".join(group["items"]), "body"),
        ]], colWidths=[doc.width * 0.3, doc.width * 0.7])
        matrix_row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ice if index % 2 == 0 else colors.HexColor("#DEECF9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(matrix_row)
    story.append(heading("Professional Experience"))
    for job in data["experience"]:
        if "pdf" not in job["tiers"]:
            continue
        story.append(para(f'{job["role"]} - {job["company"]}', "job"))
        story.append(para(f'{job["location"]} | {job["dates"]}', "meta", timeline=True))
        story.extend(bullet(b["category"], b["text"], timeline=True) for b in job["bullets"] if "pdf" in b["tiers"])

    ms = data["microsoft_block"]
    ms_rows = [[para(ms["company"], "job")],
               [para(f'{ms["location"]} | {ms["dates"]}', "meta", timeline=True)]]
    ms_rows.append([para(" | ".join(ms["roles"]), "body", timeline=True)])
    ms_rows.extend([[bullet(b["category"], b["text"], timeline=True)]
                    for b in ms["bullets"] if "pdf" in b["tiers"]])
    microsoft_card = Table(ms_rows, colWidths=[doc.width], splitInRow=1)
    microsoft_card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ice),
        ("BOX", (0, 0), (-1, -1), 0.5, border),
        ("LINEBEFORE", (0, 0), (0, -1), 3, azure),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(microsoft_card)
    story.append(heading("Additional Experience"))
    story.extend(
        bullet(f'{item["company"]} ({item["dates"]})', item["text"])
        for item in data["earlier_experience"] if "pdf" in item["tiers"]
    )
    story.append(heading("Education & Certifications"))
    for ed in data["education"]:
        year = f' ({ed["year"]})' if ed["year"] else ""
        story.append(para(f'{ed["credential"]} - {ed["institution"]}{year}', "body"))
    def blueprint_page(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#DEECF9"))
        canvas.setLineWidth(0.25)
        for x in range(8, int(document.pagesize[0]), 18):
            canvas.line(x, 8, x, 20)
            canvas.line(x, document.pagesize[1] - 20, x, document.pagesize[1] - 8)
        for y in range(8, int(document.pagesize[1]), 18):
            canvas.line(8, y, 20, y)
            canvas.line(document.pagesize[0] - 20, y, document.pagesize[0] - 8, y)
        canvas.line(8, 8, document.pagesize[0] - 8, 8)
        canvas.line(8, document.pagesize[1] - 8, document.pagesize[0] - 8, document.pagesize[1] - 8)
        canvas.line(8, 20, document.pagesize[0] - 8, 20)
        canvas.line(8, document.pagesize[1] - 20, document.pagesize[0] - 8, document.pagesize[1] - 20)
        canvas.line(8, 8, 8, document.pagesize[1] - 8)
        canvas.line(document.pagesize[0] - 8, 8, document.pagesize[0] - 8, document.pagesize[1] - 8)
        canvas.line(20, 8, 20, document.pagesize[1] - 8)
        canvas.line(document.pagesize[0] - 20, 8, document.pagesize[0] - 20, document.pagesize[1] - 8)
        canvas.restoreState()

    doc.build(story, onFirstPage=blueprint_page, onLaterPages=blueprint_page)
    print(f"[OK] Generated {output_path}")


def build_interview_prep(data, output_path):
    doc = Document()
    for section in doc.sections:
        section.top_margin = section.bottom_margin = Inches(0.45)
        section.left_margin = section.right_margin = Inches(0.55)
    doc.styles["Normal"].font.size = Pt(9)
    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run(f'{data["profile"]["name"]} | INTERVIEW WAR-ROOM')
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = NAVY
    for heading, lines in (
        ("VERIFIED IMPACT", [f'{m["value"]} — {m["label"]}' for m in data["metrics"][:4]]),
        ("ARCHITECTURAL HEADLINES", data["interview_prep"]["headlines"]),
        ("MICROSOFT FABRIC I-G-C-A", data["interview_prep"]["fabric_igca"]),
        ("CLOSING ALIGNMENT QUESTIONS", data["interview_prep"]["questions"]),
    ):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(heading)
        r.bold = True
        r.font.color.rgb = AZURE
        for line in lines:
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(0)
            p.add_run(line)
    doc.save(output_path)
    print(f"[OK] Generated {output_path}")


def build_cover_letter(data, company_name, role_title, output_path):
    doc = Document()
    profile = data["profile"]

    name = doc.add_paragraph()
    name_run = name.add_run(profile["name"])
    name_run.bold = True
    name_run.font.size = Pt(18)
    name_run.font.color.rgb = NAVY

    contact = doc.add_paragraph(
        f"{profile['email']}  |  {profile['phone']}  |  "
        f"{profile['linkedin']}  |  {profile['location']}"
    )
    contact.paragraph_format.space_after = Pt(18)

    subject = doc.add_paragraph()
    subject_run = subject.add_run(f"Re: {role_title} at {company_name}")
    subject_run.bold = True

    doc.add_paragraph(f"Dear {company_name} Hiring Team,")
    replacements = {
        "{company_name}": company_name,
        "{role_title}": role_title,
    }
    for key in ("opening", "body_1", "body_2", "closing"):
        paragraph = data["cover_letter"][key]
        for placeholder, value in replacements.items():
            paragraph = paragraph.replace(placeholder, value)
        doc.add_paragraph(paragraph)

    doc.add_paragraph("Sincerely,")
    doc.add_paragraph(profile["name"])
    doc.save(output_path)
    print(f"[OK] Generated {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build resume and application documents.")
    parser.add_argument(
        "--target",
        choices=("all", "master", "exec", "slideedition", "coverletter", "pdf", "interviewprep"),
        default="all",
    )
    parser.add_argument("--company", default="[Company Name]")
    parser.add_argument(
        "--role",
        default="Senior DevOps Engineer / Enterprise Cloud Architect",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    dist_dir = base_dir / "dist"
    dist_dir.mkdir(exist_ok=True)
    with (base_dir / "resume.yaml").open("r", encoding="utf-8") as f:
        resume_data = yaml.safe_load(f)

    targets = {
        "master": lambda: build_docx(
            resume_data,
            "master",
            dist_dir / "Joseph_Balestrine_DevOps_Architect_Master.docx",
        ),
        "exec": lambda: build_docx(
            resume_data,
            "exec",
            dist_dir / "Joseph_Balestrine_Executive_2Page.docx",
        ),
        "slideedition": lambda: build_docx(
            resume_data,
            "slideedition",
            dist_dir / "Joseph_Balestrine_Slide_Edition.docx",
        ),
        "coverletter": lambda: build_cover_letter(
            resume_data,
            args.company,
            args.role,
            dist_dir / "Joseph_Balestrine_Cover_Letter.docx",
        ),
        "pdf": lambda: build_pdf(
            resume_data,
            base_dir / "template_v2.html",
            dist_dir / "Joseph_Balestrine_Architect_Portfolio.pdf",
        ),
        "interviewprep": lambda: build_interview_prep(
            resume_data, dist_dir / "Joseph_Balestrine_Interview_WarRoom.docx"
        ),
    }
    selected_targets = targets if args.target == "all" else {args.target: targets[args.target]}
    for build_target in selected_targets.values():
        build_target()
