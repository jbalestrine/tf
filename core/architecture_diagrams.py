"""Render editable architecture diagrams for browser and Visio workflows."""

from __future__ import annotations

from html import escape
import io
import re
import zipfile
from xml.etree import ElementTree as ET


MAX_NODES = 40
MAX_EDGES = 80


def normalize_diagram(nodes, edges):
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= MAX_NODES:
        raise ValueError(f"Provide between 2 and {MAX_NODES} diagram components.")
    if not isinstance(edges, list) or len(edges) > MAX_EDGES:
        raise ValueError(f"Provide no more than {MAX_EDGES} diagram connections.")

    clean_nodes = []
    seen_ids = set()
    for index, node in enumerate(nodes):
        if isinstance(node, str):
            node = {"id": f"node-{index + 1}", "label": node, "kind": "service"}
        if not isinstance(node, dict):
            raise ValueError("Each diagram component must be a label or object.")
        node_id = str(node.get("id") or f"node-{index + 1}").strip()
        label = str(node.get("label") or node.get("title") or "").strip()
        kind = str(node.get("kind") or "service").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", node_id):
            raise ValueError("Component IDs may contain only letters, numbers, '_' and '-'.")
        if node_id in seen_ids:
            raise ValueError(f"Duplicate component ID: {node_id}")
        if not label or len(label) > 80 or not kind or len(kind) > 30:
            raise ValueError("Component labels must be 1–80 characters and types 1–30.")
        seen_ids.add(node_id)
        clean_nodes.append({"id": node_id, "label": label, "kind": kind})

    clean_edges = []
    for edge in edges:
        if isinstance(edge, (tuple, list)) and len(edge) >= 2:
            edge = {"from": edge[0], "to": edge[1]}
        if not isinstance(edge, dict):
            raise ValueError("Each connection must specify a source and destination.")
        source = str(edge.get("from") or edge.get("source") or "").strip()
        target = str(edge.get("to") or edge.get("target") or "").strip()
        label = str(edge.get("label") or "").strip()
        if source not in seen_ids or target not in seen_ids:
            raise ValueError("Every connection must point to existing component IDs.")
        if source == target:
            raise ValueError("A component cannot connect to itself.")
        if len(label) > 60:
            raise ValueError("Connection labels must be at most 60 characters.")
        clean_edges.append({"from": source, "to": target, "label": label})
    return clean_nodes, clean_edges


def _layout(nodes):
    columns = min(4, max(2, len(nodes)))
    cell_width = 250
    cell_height = 160
    positions = {}
    for index, node in enumerate(nodes):
        row, column = divmod(index, columns)
        positions[node["id"]] = (
            55 + column * cell_width,
            70 + row * cell_height,
        )
    width = 110 + columns * cell_width
    height = 110 + ((len(nodes) + columns - 1) // columns) * cell_height
    return positions, width, height


def render_svg(title, nodes, edges):
    nodes, edges = normalize_diagram(nodes, edges)
    positions, width, height = _layout(nodes)
    node_by_id = {node["id"]: node for node in nodes}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(title, quote=True)} architecture diagram">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" '
        'orient="auto" markerUnits="strokeWidth"><path d="M0,0 L10,5 L0,10 z" '
        'fill="#70c98a"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#10151d"/>',
        f'<text x="28" y="34" fill="#e5e7eb" font-family="Arial,sans-serif" '
        f'font-size="22" font-weight="700">{escape(title)}</text>',
    ]
    for edge in edges:
        sx, sy = positions[edge["from"]]
        tx, ty = positions[edge["to"]]
        start_x, start_y = sx + 92, sy + 54
        end_x, end_y = tx + 92, ty + 54
        if end_x >= start_x:
            start_x += 92
        else:
            end_x += 92
        parts.append(
            f'<path d="M {start_x} {start_y} L {end_x} {end_y}" '
            'fill="none" stroke="#70c98a" stroke-width="2" marker-end="url(#arrow)"/>'
        )
        if edge["label"]:
            parts.append(
                f'<text x="{(start_x + end_x) / 2:g}" y="{(start_y + end_y) / 2 - 6:g}" '
                'fill="#b9e7c3" font-family="Arial,sans-serif" font-size="12">'
                f'{escape(edge["label"])}</text>'
            )
    for node in nodes:
        x, y = positions[node["id"]]
        parts.extend([
            f'<g data-node-id="{escape(node["id"], quote=True)}">',
            f'<rect x="{x}" y="{y}" width="184" height="108" rx="10" '
            'fill="#1b2430" stroke="#70c98a" stroke-width="2"/>',
            f'<text x="{x + 92}" y="{y + 42}" text-anchor="middle" '
            'fill="#9ca3af" font-family="Arial,sans-serif" font-size="12">'
            f'{escape(node["kind"].upper())}</text>',
            f'<text x="{x + 92}" y="{y + 68}" text-anchor="middle" '
            'fill="#f3f4f6" font-family="Arial,sans-serif" font-size="15" font-weight="700">'
            f'{escape(node["label"])}</text>',
            '</g>',
        ])
    parts.append("</svg>")
    return "\n".join(parts)


def _xml_cell(name, value, formula=None, unit=None):
    attrs = {"N": name, "V": str(value)}
    if formula:
        attrs["F"] = formula
    if unit:
        attrs["U"] = unit
    return ET.Element("{http://schemas.microsoft.com/office/visio/2012/main}Cell", attrs)


def _visio_shape(shape_id, name, x, y, width, height, text="", is_connector=False):
    ns = "{http://schemas.microsoft.com/office/visio/2012/main}"
    shape = ET.Element(ns + "Shape", {
        "ID": str(shape_id),
        "NameU": name,
        "Name": name,
        "Type": "Shape",
    })
    if is_connector:
        shape.extend([
            _xml_cell("BeginX", x, unit="IN"),
            _xml_cell("BeginY", y, unit="IN"),
            _xml_cell("EndX", width, unit="IN"),
            _xml_cell("EndY", height, unit="IN"),
            _xml_cell("LineColor", "RGB(112,201,138)", formula="RGB(112,201,138)"),
            _xml_cell("EndArrow", 4),
        ])
        section = ET.SubElement(shape, ns + "Section", {"N": "Geometry", "IX": "0"})
        ET.SubElement(section, ns + "Cell", {"N": "NoFill", "V": "1"})
        move = ET.SubElement(section, ns + "Row", {"T": "MoveTo", "IX": "1"})
        ET.SubElement(move, ns + "Cell", {"N": "X", "V": "0"})
        ET.SubElement(move, ns + "Cell", {"N": "Y", "V": "0"})
        line = ET.SubElement(section, ns + "Row", {"T": "LineTo", "IX": "2"})
        ET.SubElement(line, ns + "Cell", {"N": "X", "V": "1"})
        ET.SubElement(line, ns + "Cell", {"N": "Y", "V": "1"})
    else:
        shape.extend([
            _xml_cell("PinX", x, unit="IN"),
            _xml_cell("PinY", y, unit="IN"),
            _xml_cell("Width", width, unit="IN"),
            _xml_cell("Height", height, unit="IN"),
            _xml_cell("LocPinX", width / 2, unit="IN"),
            _xml_cell("LocPinY", height / 2, unit="IN"),
            _xml_cell("FillForegnd", "RGB(27,36,48)", formula="RGB(27,36,48)"),
            _xml_cell("LineColor", "RGB(112,201,138)", formula="RGB(112,201,138)"),
        ])
        text_element = ET.SubElement(shape, ns + "Text")
        text_element.text = text
        section = ET.SubElement(shape, ns + "Section", {"N": "Geometry", "IX": "0"})
        for index, (row_type, point_x, point_y) in enumerate([
            ("MoveTo", 0, 0), ("LineTo", width, 0),
            ("LineTo", width, height), ("LineTo", 0, height),
            ("LineTo", 0, 0),
        ], 1):
            row = ET.SubElement(section, ns + "Row", {"T": row_type, "IX": str(index)})
            ET.SubElement(row, ns + "Cell", {"N": "X", "V": str(point_x)})
            ET.SubElement(row, ns + "Cell", {"N": "Y", "V": str(point_y)})
    return shape


def render_vsdx(title, nodes, edges):
    """Build a Visio OPC package with native component and connector shapes."""
    nodes, edges = normalize_diagram(nodes, edges)
    positions, width_px, height_px = _layout(nodes)
    scale = 96
    page_width = width_px / scale
    page_height = height_px / scale
    node_width, node_height = 1.9, 1.1
    ns = "http://schemas.microsoft.com/office/visio/2012/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    root_ns = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"

    page = ET.Element(f"{{{ns}}}PageContents")
    shapes = ET.SubElement(page, f"{{{ns}}}Shapes")
    shape_ids = {node["id"]: index + 1 for index, node in enumerate(nodes)}
    positions_in = {
        node["id"]: (positions[node["id"]][0] / scale, (height_px - positions[node["id"]][1]) / scale)
        for node in nodes
    }
    for node in nodes:
        x, y = positions_in[node["id"]]
        shapes.append(_visio_shape(
            shape_ids[node["id"]],
            node["label"],
            x + node_width / 2,
            y - node_height / 2,
            node_width,
            node_height,
            f'{node["label"]}\n({node["kind"]})',
        ))
    for index, edge in enumerate(edges, len(nodes) + 1):
        sx, sy = positions_in[edge["from"]]
        tx, ty = positions_in[edge["to"]]
        shapes.append(_visio_shape(index, "Dynamic connector", sx + node_width, sy, tx, ty, is_connector=True))
    page_xml = ET.tostring(page, encoding="utf-8", xml_declaration=True)

    page_list = ET.Element(f"{{{ns}}}Pages")
    visio_page = ET.SubElement(page_list, f"{{{ns}}}Page", {
        "ID": "0", "NameU": "Page-1", "Name": "Page-1",
        "IsCustomNameU": "1", "IsCustomName": "1",
        "ViewScale": "1",
    })
    ET.SubElement(visio_page, f"{{{ns}}}Rel", {f"{{{rel_ns}}}id": "rId1"})

    document = ET.Element(f"{{{ns}}}VisioDocument")
    ET.SubElement(document, f"{{{ns}}}DocumentProperties")
    doc_pages = ET.SubElement(document, f"{{{ns}}}Pages")
    page_sheet = ET.SubElement(doc_pages, f"{{{ns}}}Page", {
        "ID": "0", "NameU": "Page-1", "Name": "Page-1",
    })
    page_sheet_values = ET.SubElement(page_sheet, f"{{{ns}}}PageSheet")
    ET.SubElement(page_sheet_values, f"{{{ns}}}Cell", {"N": "PageWidth", "V": str(page_width), "U": "IN"})
    ET.SubElement(page_sheet_values, f"{{{ns}}}Cell", {"N": "PageHeight", "V": str(page_height), "U": "IN"})

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/>
  <Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>
  <Override PartName="/visio/pages/page1.xml" ContentType="application/vnd.ms-visio.page+xml"/>
</Types>"""
    package_rels = ET.Element(f"{{{pkg_rel_ns}}}Relationships")
    ET.SubElement(package_rels, f"{{{pkg_rel_ns}}}Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.microsoft.com/office/visio/2010/relationships/document",
        "Target": "visio/document.xml",
    })
    document_rels = ET.Element(f"{{{pkg_rel_ns}}}Relationships")
    ET.SubElement(document_rels, f"{{{pkg_rel_ns}}}Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.microsoft.com/office/visio/2010/relationships/pages",
        "Target": "pages/pages.xml",
    })
    page_rels = ET.Element(f"{{{pkg_rel_ns}}}Relationships")
    ET.SubElement(page_rels, f"{{{pkg_rel_ns}}}Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.microsoft.com/office/visio/2010/relationships/page",
        "Target": "page1.xml",
    })
    parts = {
        "[Content_Types].xml": content_types.encode("utf-8"),
        "_rels/.rels": ET.tostring(package_rels, encoding="utf-8", xml_declaration=True),
        "visio/document.xml": ET.tostring(document, encoding="utf-8", xml_declaration=True),
        "visio/_rels/document.xml.rels": ET.tostring(document_rels, encoding="utf-8", xml_declaration=True),
        "visio/pages/pages.xml": ET.tostring(page_list, encoding="utf-8", xml_declaration=True),
        "visio/pages/_rels/pages.xml.rels": ET.tostring(page_rels, encoding="utf-8", xml_declaration=True),
        "visio/pages/page1.xml": page_xml,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as package:
        for name, content in parts.items():
            package.writestr(name, content)
    return output.getvalue()
