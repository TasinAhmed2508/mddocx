from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from mddocx.ast.inline import (
    Emphasis,
    FootnoteReference,
    HardBreak,
    Image,
    InlineCode,
    InlineMath,
    Link,
    SoftBreak,
    Strikethrough,
    Strong,
    Text,
)
from mddocx.ooxml.text import clean_xml_text

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
ENDNOTE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes"
ENDNOTE_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"


def append_endnote_reference(paragraph, endnote_id: int) -> None:
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "FootnoteReference")
    rpr.append(style)
    run.append(rpr)
    ref = OxmlElement("w:endnoteReference")
    ref.set(qn("w:id"), str(endnote_id))
    run.append(ref)
    paragraph._p.append(run)


def inject_endnotes(blob: bytes, notes: dict[int, list], math_converter) -> bytes:
    if not notes:
        return blob
    source = BytesIO(blob)
    output = BytesIO()
    with ZipFile(source, "r") as zin:
        parts = {info.filename: zin.read(info.filename) for info in zin.infolist()}

    parts["word/endnotes.xml"] = _build_endnotes_xml(notes, math_converter)
    parts["[Content_Types].xml"] = _patch_content_types(parts["[Content_Types].xml"])
    parts["word/_rels/document.xml.rels"] = _patch_document_rels(
        parts["word/_rels/document.xml.rels"]
    )

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            zout.writestr(name, data)
    return output.getvalue()


def _build_endnotes_xml(notes: dict[int, list], math_converter) -> bytes:
    root = OxmlElement("w:endnotes")
    root.append(_separator(-1, "separator", "w:separator"))
    root.append(_separator(0, "continuationSeparator", "w:continuationSeparator"))
    for endnote_id, nodes in sorted(notes.items()):
        fn = OxmlElement("w:endnote")
        fn.set(qn("w:id"), str(endnote_id))
        p = OxmlElement("w:p")
        ppr = OxmlElement("w:pPr")
        style = OxmlElement("w:pStyle")
        style.set(qn("w:val"), "EndnoteText")
        ppr.append(style)
        p.append(ppr)

        ref_run = OxmlElement("w:r")
        ref_rpr = OxmlElement("w:rPr")
        ref_style = OxmlElement("w:rStyle")
        ref_style.set(qn("w:val"), "FootnoteReference")
        ref_rpr.append(ref_style)
        ref_run.append(ref_rpr)
        ref = OxmlElement("w:endnoteRef")
        ref_run.append(ref)
        p.append(ref_run)
        _append_run(p, " ")
        _append_inlines(p, nodes, math_converter)
        fn.append(p)
        root.append(fn)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _separator(endnote_id: int, kind: str, element_name: str):
    fn = OxmlElement("w:endnote")
    fn.set(qn("w:type"), kind)
    fn.set(qn("w:id"), str(endnote_id))
    p = OxmlElement("w:p")
    r = OxmlElement("w:r")
    r.append(OxmlElement(element_name))
    p.append(r)
    fn.append(p)
    return fn


def _append_inlines(parent, nodes, math_converter, *, bold=False, italic=False, strike=False):
    for node in nodes:
        if isinstance(node, Text):
            _append_run(parent, node.text, bold=bold, italic=italic, strike=strike)
        elif isinstance(node, Strong):
            _append_inlines(
                parent, node.children, math_converter, bold=True, italic=italic, strike=strike
            )
        elif isinstance(node, Emphasis):
            _append_inlines(
                parent, node.children, math_converter, bold=bold, italic=True, strike=strike
            )
        elif isinstance(node, Strikethrough):
            _append_inlines(
                parent, node.children, math_converter, bold=bold, italic=italic, strike=True
            )
        elif isinstance(node, InlineCode):
            _append_run(parent, node.code, bold=bold, italic=italic, strike=strike, code=True)
        elif isinstance(node, InlineMath):
            try:
                parent.append(math_converter.latex_to_omml(node.source_text, False))
            except Exception:
                _append_run(parent, node.source_text, bold=bold, italic=italic, strike=strike)
        elif isinstance(node, Link):
            # Endnotes are a separate OOXML part and need their own relationship
            # collection. Preserve editable visible text rather than emit a broken link.
            _append_inlines(
                parent, node.children, math_converter, bold=bold, italic=italic, strike=strike
            )
        elif isinstance(node, SoftBreak):
            _append_run(parent, " ")
        elif isinstance(node, HardBreak):
            r = OxmlElement("w:r")
            r.append(OxmlElement("w:br"))
            parent.append(r)
        elif isinstance(node, Image):
            _append_run(parent, node.alt or node.src)
        elif isinstance(node, FootnoteReference):
            _append_run(parent, f"[^{node.label}]")
        elif hasattr(node, "children"):
            _append_inlines(
                parent, node.children, math_converter, bold=bold, italic=italic, strike=strike
            )


def _append_run(parent, text: str, *, bold=False, italic=False, strike=False, code=False):
    text = clean_xml_text(text)
    if not text:
        return
    r = OxmlElement("w:r")
    if bold or italic or strike or code:
        rpr = OxmlElement("w:rPr")
        if bold:
            rpr.append(OxmlElement("w:b"))
        if italic:
            rpr.append(OxmlElement("w:i"))
        if strike:
            rpr.append(OxmlElement("w:strike"))
        if code:
            fonts = OxmlElement("w:rFonts")
            fonts.set(qn("w:ascii"), "Consolas")
            fonts.set(qn("w:hAnsi"), "Consolas")
            rpr.append(fonts)
        r.append(rpr)
    t = OxmlElement("w:t")
    if text[:1].isspace() or text[-1:].isspace() or "  " in text:
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    r.append(t)
    parent.append(r)


def _patch_content_types(data: bytes) -> bytes:
    root = etree.fromstring(data)
    if not any(el.get("PartName") == "/word/endnotes.xml" for el in root):
        override = etree.Element(f"{{{CT_NS}}}Override")
        override.set("PartName", "/word/endnotes.xml")
        override.set("ContentType", ENDNOTE_CT)
        root.append(override)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _patch_document_rels(data: bytes) -> bytes:
    root = etree.fromstring(data)
    for rel in root:
        if rel.get("Type") == ENDNOTE_REL:
            return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    used = []
    for rel in root:
        rid = rel.get("Id", "")
        if rid.startswith("rId") and rid[3:].isdigit():
            used.append(int(rid[3:]))
    rel = etree.Element(f"{{{REL_NS}}}Relationship")
    rel.set("Id", f"rId{max(used, default=0) + 1}")
    rel.set("Type", ENDNOTE_REL)
    rel.set("Target", "endnotes.xml")
    root.append(rel)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
