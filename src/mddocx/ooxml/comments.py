from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from mddocx.ooxml.text import clean_xml_text

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
COMMENT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
COMMENT_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"


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
    with ZipFile(BytesIO(blob), "r") as zin:
        parts = {info.filename: zin.read(info.filename) for info in zin.infolist()}

    parts["word/comments.xml"] = _build_comments_xml(comments, author, initials)
    parts["[Content_Types].xml"] = _patch_content_types(parts["[Content_Types].xml"])
    parts["word/_rels/document.xml.rels"] = _patch_document_rels(
        parts["word/_rels/document.xml.rels"]
    )

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            zout.writestr(name, data)
    return output.getvalue()


def _build_comments_xml(comments: dict[int, str], author: str, initials: str) -> bytes:
    root = OxmlElement("w:comments")
    now = "2000-01-01T00:00:00Z"
    for comment_id, body in sorted(comments.items()):
        comment = OxmlElement("w:comment")
        comment.set(qn("w:id"), str(comment_id))
        comment.set(qn("w:author"), clean_xml_text(author))
        comment.set(qn("w:initials"), clean_xml_text(initials))
        comment.set(qn("w:date"), now)
        p = OxmlElement("w:p")
        r = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = clean_xml_text(body)
        r.append(t)
        p.append(r)
        comment.append(p)
        root.append(comment)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _patch_content_types(data: bytes) -> bytes:
    root = etree.fromstring(data)
    if not any(el.get("PartName") == "/word/comments.xml" for el in root):
        override = etree.Element(f"{{{CT_NS}}}Override")
        override.set("PartName", "/word/comments.xml")
        override.set("ContentType", COMMENT_CT)
        root.append(override)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _patch_document_rels(data: bytes) -> bytes:
    root = etree.fromstring(data)
    if any(rel.get("Type") == COMMENT_REL for rel in root):
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    used = []
    for rel in root:
        rid = rel.get("Id", "")
        if rid.startswith("rId") and rid[3:].isdigit():
            used.append(int(rid[3:]))
    rel = etree.Element(f"{{{REL_NS}}}Relationship")
    rel.set("Id", f"rId{max(used, default=0) + 1}")
    rel.set("Type", COMMENT_REL)
    rel.set("Target", "comments.xml")
    root.append(rel)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
