"""Native Word comments part.

Comment anchors stay on python-docx paragraphs; the part itself is injected
through the shared package helpers in :mod:`mddocx.ooxml.package`.
"""

from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from mddocx.ooxml.package import (
    add_content_type_override,
    add_document_relationship,
    read_parts,
    write_parts,
)
from mddocx.ooxml.text import clean_xml_text

COMMENT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
COMMENT_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
COMMENT_PART = "word/comments.xml"


def append_comment_reference(paragraph, comment_id: int) -> None:
    start = OxmlElement("w:commentRangeStart")
    start.set(qn("w:id"), str(comment_id))
    paragraph._p.append(start)

    anchor_run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "\u200b"
    anchor_run.append(text)
    paragraph._p.append(anchor_run)

    end = OxmlElement("w:commentRangeEnd")
    end.set(qn("w:id"), str(comment_id))
    paragraph._p.append(end)

    ref_run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "CommentReference")
    rpr.append(style)
    ref_run.append(rpr)
    ref = OxmlElement("w:commentReference")
    ref.set(qn("w:id"), str(comment_id))
    ref_run.append(ref)
    paragraph._p.append(ref_run)


def inject_comments(
    blob: bytes,
    comments: dict[int, str],
    *,
    author: str = "mddocx",
    initials: str = "MD",
) -> bytes:
    if not comments:
        return blob
    parts = read_parts(blob)
    parts[COMMENT_PART] = _build_comments_xml(comments, author, initials)
    add_content_type_override(parts, f"/{COMMENT_PART}", COMMENT_CT)
    add_document_relationship(parts, COMMENT_REL, "comments.xml")
    return write_parts(parts)


def _build_comments_xml(comments: dict[int, str], author: str, initials: str) -> bytes:
    root = OxmlElement("w:comments")
    now = "2000-01-01T00:00:00Z"
    for comment_id, body in sorted(comments.items()):
        comment = OxmlElement("w:comment")
        comment.set(qn("w:id"), str(comment_id))
        comment.set(qn("w:author"), clean_xml_text(author))
        comment.set(qn("w:initials"), clean_xml_text(initials))
        comment.set(qn("w:date"), now)
        paragraph = OxmlElement("w:p")
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = clean_xml_text(body)
        run.append(text)
        paragraph.append(run)
        comment.append(paragraph)
        root.append(comment)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
