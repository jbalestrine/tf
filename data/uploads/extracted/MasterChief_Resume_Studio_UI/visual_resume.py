"""Convert the visual editor's limited rich text to downloadable documents."""
from html import escape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

from docx import Document
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
import reportlab


MAX_HTML = 1_000_000
BLOCKS = {"p", "div", "h1", "h2", "h3", "li"}
FORMATS = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic", "u": "underline"}


class EditorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.block = None
        self.styles = []
        self.ignore = 0

    def flush(self):
        if self.block is not None:
            self.blocks.append(self.block)
            self.block = None

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object", "svg", "math"}:
            self.ignore += 1
            return
        if self.ignore:
            return
        if tag in BLOCKS:
            self.flush()
            self.block = {"kind": tag, "runs": []}
        elif tag == "br":
            self.handle_data("\n")
        elif tag in FORMATS:
            self.styles.append((tag, FORMATS[tag]))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "object", "svg", "math"}:
            self.ignore = max(0, self.ignore - 1)
            return
        if self.ignore:
            return
        if tag in BLOCKS:
            self.flush()
        elif tag in FORMATS:
            for index in range(len(self.styles) - 1, -1, -1):
                if self.styles[index][0] == tag:
                    self.styles.pop(index)
                    break

    def handle_data(self, text):
        if self.ignore or not text:
            return
        if self.block is None:
            self.block = {"kind": "p", "runs": []}
        self.block["runs"].append((text, frozenset(style for _, style in self.styles)))


def parse(html):
    if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_HTML:
        raise ValueError("Editor content exceeds the 1 MB limit.")
    parser = EditorParser()
    parser.feed(html)
    parser.close()
    parser.flush()
    if not any(text.strip() for block in parser.blocks for text, _ in block["runs"]):
        raise ValueError("Add resume content before exporting.")
    if len(parser.blocks) > 5000:
        raise ValueError("Document contains too many paragraphs.")
    return parser.blocks


def docx_bytes(html):
    blocks = parse(html)
    doc = Document()
    for block in blocks:
        kind = block["kind"]
        style = {"h1": "Heading 1", "h2": "Heading 2", "h3": "Heading 3", "li": "List Bullet"}.get(kind)
        paragraph = doc.add_paragraph(style=style)
        for text, formats in block["runs"]:
            run = paragraph.add_run(text)
            run.bold = "bold" in formats
            run.italic = "italic" in formats
            run.underline = "underline" in formats
    result = BytesIO()
    doc.save(result)
    return result.getvalue()


def pdf_bytes(html):
    blocks = parse(html)
    font_dir = Path(reportlab.__file__).resolve().parent / "fonts"
    for name, file in (("ResumeVera", "Vera.ttf"), ("ResumeVera-Bold", "VeraBd.ttf"),
                       ("ResumeVera-Italic", "VeraIt.ttf"), ("ResumeVera-BoldItalic", "VeraBI.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_dir / file)))
    pdfmetrics.registerFontFamily("ResumeVera", normal="ResumeVera", bold="ResumeVera-Bold",
                                 italic="ResumeVera-Italic", boldItalic="ResumeVera-BoldItalic")
    font = pdfmetrics.getFont("ResumeVera")
    for block in blocks:
        for text, _ in block["runs"]:
            missing = {c for c in text if ord(c) not in font.face.charWidths and c not in "\r\n\t"}
            if missing:
                raise ValueError("PDF font cannot render some characters. Export DOCX instead or replace those characters.")
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=(8.5 * inch, 11 * inch),
                                 leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                                 topMargin=0.65 * inch, bottomMargin=0.65 * inch)
    story = []
    for block in blocks:
        kind = block["kind"]
        size = {"h1": 20, "h2": 15, "h3": 12}.get(kind, 10.5)
        style = ParagraphStyle("resume", fontName="ResumeVera", fontSize=size, leading=size * 1.35,
                               alignment=TA_LEFT, textColor=colors.HexColor("#18324f"),
                               leftIndent=14 if kind == "li" else 0)
        fragments = []
        for text, formats in block["runs"]:
            value = escape(text).replace("\n", "<br/>")
            for fmt, tag in (("bold", "b"), ("italic", "i"), ("underline", "u")):
                if fmt in formats:
                    value = f"<{tag}>{value}</{tag}>"
            fragments.append(value)
        content = "".join(fragments) or "&#160;"
        if kind == "li":
            content = "&#8226; " + content
        story.append(Paragraph(content, style))
        story.append(Spacer(1, 5))
    document.build(story)
    return stream.getvalue()
