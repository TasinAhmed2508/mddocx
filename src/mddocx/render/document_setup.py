"""Document shell: opening the package, core properties, and field updates."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from docx import Document as WordDocument
from docx.opc.constants import CONTENT_TYPE as CT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn

from mddocx.diagnostics import Diagnostic, MddocxError
from mddocx.validation import validate_docx_package

from . import sections

_BOOKMARK_STORIES = {
    CT.WML_DOCUMENT_MAIN,
    CT.WML_HEADER,
    CT.WML_FOOTER,
    CT.WML_FOOTNOTES,
    CT.WML_ENDNOTES,
    CT.WML_COMMENTS,
}

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def open_document(renderer: DocxRenderer):
    if renderer.config.template is None:
        return WordDocument()
    template = Path(renderer.config.template).expanduser().resolve()
    if not template.is_file():
        raise MddocxError(
            Diagnostic("error", "CONFIG301", f"DOCX template not found: {template.name}")
        )
    if template.suffix.lower() != ".docx":
        raise MddocxError(Diagnostic("error", "CONFIG302", "Template must be a .docx file."))
    try:
        validate_docx_package(template.read_bytes(), renderer.config.validation)
        return WordDocument(str(template))
    except MddocxError:
        raise
    except Exception as exc:
        raise MddocxError(
            Diagnostic("error", "DOCX301", f"Unable to open template: {template.name}")
        ) from exc


def configure_document(renderer: DocxRenderer) -> None:
    preserve_page = bool(renderer.config.template and renderer.config.preserve_template_page_setup)
    sections.configure_section(renderer, renderer.document.sections[0], preserve_page=preserve_page)
    props = renderer.document.core_properties
    if renderer.config.title:
        props.title = renderer.config.title
    if renderer.config.author:
        props.author = renderer.config.author
    if renderer.config.subject:
        props.subject = renderer.config.subject
    if renderer.config.keywords:
        props.keywords = renderer.config.keywords
    if renderer.config.comments:
        props.comments = renderer.config.comments
    if renderer.config.created_at:
        props.created = renderer.config.created_at


def reserve_template_bookmarks(renderer: DocxRenderer) -> None:
    for part in renderer.document.part.package.parts:
        if part.content_type not in _BOOKMARK_STORIES:
            continue
        root = getattr(part, "element", None)
        if root is None:
            root = parse_xml(part.blob)
        for node in root.iter(qn("w:bookmarkStart"), qn("w:bookmarkEnd")):
            name = node.get(qn("w:name"))
            if name:
                renderer._bookmark_names.add(name)
            try:
                renderer._bookmark_id = max(
                    renderer._bookmark_id, int(node.get(qn("w:id"), "0")) + 1
                )
            except ValueError:
                continue


def request_field_updates(renderer: DocxRenderer) -> None:
    if not renderer.config.fields.update_on_open:
        return
    settings = renderer.document.settings.element
    node = settings.find(qn("w:updateFields"))
    if node is None:
        node = OxmlElement("w:updateFields")
        settings.append(node)
    node.set(qn("w:val"), "true")
