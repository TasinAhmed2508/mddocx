"""Footnote and endnote package parts.

Word's footnote and endnote parts differ only in their element, part, style, and
relationship names, so one implementation is parameterized by :class:`NotePart`.
The renderer passes ``configure_run`` and ``configure_paragraph`` callbacks so
note text receives the same script fonts and direction policy as body text.
"""

from __future__ import annotations

from dataclasses import dataclass

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

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
from mddocx.ooxml.package import (
    add_content_type_override,
    add_document_relationship,
    read_parts,
    write_parts,
)
from mddocx.ooxml.text import clean_xml_text


@dataclass(frozen=True, slots=True)
class NotePart:
    """Everything that distinguishes a footnote part from an endnote part."""

    part_name: str
    root_tag: str
    item_tag: str
    ref_tag: str
    style_name: str
    content_type: str
    relationship_type: str
    relationship_target: str
    reference_tag: str


FOOTNOTE_PART = NotePart(
    part_name="word/footnotes.xml",
    root_tag="w:footnotes",
    item_tag="w:footnote",
    ref_tag="w:footnoteRef",
    style_name="FootnoteText",
    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
    relationship_type=(
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
    ),
    relationship_target="footnotes.xml",
    reference_tag="w:footnoteReference",
)

ENDNOTE_PART = NotePart(
    part_name="word/endnotes.xml",
    root_tag="w:endnotes",
    item_tag="w:endnote",
    ref_tag="w:endnoteRef",
    style_name="EndnoteText",
    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml",
    relationship_type=(
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes"
    ),
    relationship_target="endnotes.xml",
    reference_tag="w:endnoteReference",
)


def append_footnote_reference(paragraph, footnote_id: int) -> None:
    _append_reference(paragraph, footnote_id, FOOTNOTE_PART)


def append_endnote_reference(paragraph, endnote_id: int) -> None:
    _append_reference(paragraph, endnote_id, ENDNOTE_PART)


def inject_footnotes(
    blob: bytes,
    notes: dict[int, list],
    math_converter,
    configure_run=None,
    configure_paragraph=None,
) -> bytes:
    return inject_notes(
        blob,
        notes,
        math_converter,
        FOOTNOTE_PART,
        configure_run,
        configure_paragraph,
    )


def inject_endnotes(
    blob: bytes,
    notes: dict[int, list],
    math_converter,
    configure_run=None,
    configure_paragraph=None,
) -> bytes:
    return inject_notes(
        blob,
        notes,
        math_converter,
        ENDNOTE_PART,
        configure_run,
        configure_paragraph,
    )


def inject_notes(
    blob: bytes,
    notes: dict[int, list],
    math_converter,
    part: NotePart,
    configure_run=None,
    configure_paragraph=None,
) -> bytes:
    """Add a note part, its relationships, and its content-type override."""
    if not notes:
        return blob
    parts = read_parts(blob)
    parts[part.part_name] = build_notes_xml(
        notes, math_converter, part, configure_run, configure_paragraph
    )
    add_content_type_override(parts, f"/{part.part_name}", part.content_type)
    add_document_relationship(parts, part.relationship_type, part.relationship_target)
    return write_parts(parts)


def build_notes_xml(
    notes: dict[int, list],
    math_converter,
    part: NotePart,
    configure_run=None,
    configure_paragraph=None,
) -> bytes:
    root = OxmlElement(part.root_tag)
    root.append(_separator(-1, "separator", "w:separator", part.item_tag))
    root.append(_separator(0, "continuationSeparator", "w:continuationSeparator", part.item_tag))
    for note_id, nodes in sorted(notes.items()):
        item = OxmlElement(part.item_tag)
        item.set(qn("w:id"), str(note_id))
        paragraph = OxmlElement("w:p")
        properties = OxmlElement("w:pPr")
        style = OxmlElement("w:pStyle")
        style.set(qn("w:val"), part.style_name)
        properties.append(style)
        paragraph.append(properties)

        reference = OxmlElement("w:r")
        reference_properties = OxmlElement("w:rPr")
        reference_style = OxmlElement("w:rStyle")
        reference_style.set(qn("w:val"), "FootnoteReference")
        reference_properties.append(reference_style)
        reference.append(reference_properties)
        reference.append(OxmlElement(part.ref_tag))
        paragraph.append(reference)

        _append_run(paragraph, " ", configure_run=configure_run)
        _append_inlines(paragraph, nodes, math_converter, configure_run=configure_run)
        if configure_paragraph is not None:
            configure_paragraph(
                paragraph, "".join(node.text or "" for node in paragraph.iter(qn("w:t")))
            )
        item.append(paragraph)
        root.append(item)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _append_reference(paragraph, note_id: int, part: NotePart) -> None:
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "FootnoteReference")
    properties.append(style)
    run.append(properties)
    reference = OxmlElement(part.reference_tag)
    reference.set(qn("w:id"), str(note_id))
    run.append(reference)
    paragraph._p.append(run)


def _separator(note_id: int, kind: str, element_name: str, item_tag: str):
    item = OxmlElement(item_tag)
    item.set(qn("w:type"), kind)
    item.set(qn("w:id"), str(note_id))
    paragraph = OxmlElement("w:p")
    run = OxmlElement("w:r")
    run.append(OxmlElement(element_name))
    paragraph.append(run)
    item.append(paragraph)
    return item


def _append_inlines(
    parent, nodes, math_converter, *, bold=False, italic=False, strike=False, configure_run=None
):
    for node in nodes:
        if isinstance(node, Text):
            _append_run(
                parent,
                node.text,
                bold=bold,
                italic=italic,
                strike=strike,
                configure_run=configure_run,
            )
        elif isinstance(node, Strong):
            _append_inlines(
                parent,
                node.children,
                math_converter,
                bold=True,
                italic=italic,
                strike=strike,
                configure_run=configure_run,
            )
        elif isinstance(node, Emphasis):
            _append_inlines(
                parent,
                node.children,
                math_converter,
                bold=bold,
                italic=True,
                strike=strike,
                configure_run=configure_run,
            )
        elif isinstance(node, Strikethrough):
            _append_inlines(
                parent,
                node.children,
                math_converter,
                bold=bold,
                italic=italic,
                strike=True,
                configure_run=configure_run,
            )
        elif isinstance(node, InlineCode):
            _append_run(
                parent,
                node.code,
                bold=bold,
                italic=italic,
                strike=strike,
                code=True,
                configure_run=configure_run,
            )
        elif isinstance(node, InlineMath):
            try:
                parent.append(math_converter.latex_to_omml(node.source_text, False))
            except Exception:
                _append_run(
                    parent,
                    node.source_text,
                    bold=bold,
                    italic=italic,
                    strike=strike,
                    configure_run=configure_run,
                )
        elif isinstance(node, Link):
            # A note part needs its own relationship collection, so preserve the
            # visible text rather than emitting a broken hyperlink.
            _append_inlines(
                parent,
                node.children,
                math_converter,
                bold=bold,
                italic=italic,
                strike=strike,
                configure_run=configure_run,
            )
        elif isinstance(node, SoftBreak):
            _append_run(parent, " ", configure_run=configure_run)
        elif isinstance(node, HardBreak):
            run = OxmlElement("w:r")
            run.append(OxmlElement("w:br"))
            parent.append(run)
        elif isinstance(node, Image):
            _append_run(parent, node.alt or node.src, configure_run=configure_run)
        elif isinstance(node, FootnoteReference):
            _append_run(parent, f"[^{node.label}]", configure_run=configure_run)
        elif hasattr(node, "children"):
            _append_inlines(
                parent,
                node.children,
                math_converter,
                bold=bold,
                italic=italic,
                strike=strike,
                configure_run=configure_run,
            )


def _append_run(
    parent, text: str, *, bold=False, italic=False, strike=False, code=False, configure_run=None
):
    text = clean_xml_text(text)
    if not text:
        return
    run = OxmlElement("w:r")
    if bold or italic or strike or code:
        properties = OxmlElement("w:rPr")
        if bold:
            properties.append(OxmlElement("w:b"))
        if italic:
            properties.append(OxmlElement("w:i"))
        if strike:
            properties.append(OxmlElement("w:strike"))
        if code:
            fonts = OxmlElement("w:rFonts")
            fonts.set(qn("w:ascii"), "Consolas")
            fonts.set(qn("w:hAnsi"), "Consolas")
            properties.append(fonts)
        run.append(properties)
    content = OxmlElement("w:t")
    if text[:1].isspace() or text[-1:].isspace() or "  " in text:
        content.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    content.text = text
    run.append(content)
    parent.append(run)
    if configure_run is not None:
        configure_run(run, text)
