"""Shared OOXML package surgery for parts added after python-docx saves.

python-docx only writes the parts it models. Footnotes, endnotes, and comments
are injected by reading the saved package, adding the part, and updating the
content-type and relationship registries. Those mechanics live here so each
part module only declares what is specific to it.
"""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
CONTENT_TYPES_PART = "[Content_Types].xml"
DOCUMENT_RELS_PART = "word/_rels/document.xml.rels"


def read_parts(blob: bytes) -> dict[str, bytes]:
    """Return every package part keyed by its archive name, preserving order."""
    with ZipFile(BytesIO(blob), "r") as package:
        return {info.filename: package.read(info.filename) for info in package.infolist()}


def write_parts(parts: dict[str, bytes]) -> bytes:
    """Serialize a part mapping back into a DOCX package."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as package:
        for name, data in parts.items():
            package.writestr(name, data)
    return output.getvalue()


def add_content_type_override(parts: dict[str, bytes], part_name: str, content_type: str) -> None:
    """Declare ``/word/<name>`` in the package content types if it is missing."""
    if not part_name.startswith("/"):
        part_name = f"/{part_name}"
    root = etree.fromstring(parts[CONTENT_TYPES_PART])
    if any(element.get("PartName") == part_name for element in root):
        return
    override = etree.Element(f"{{{CT_NS}}}Override")
    override.set("PartName", part_name)
    override.set("ContentType", content_type)
    root.append(override)
    parts[CONTENT_TYPES_PART] = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True
    )


def add_document_relationship(parts: dict[str, bytes], relationship_type: str, target: str) -> None:
    """Register a document relationship with the next free ``rId`` if absent."""
    root = etree.fromstring(parts[DOCUMENT_RELS_PART])
    if any(rel.get("Type") == relationship_type for rel in root):
        return
    used = [
        int(rid[3:])
        for rid in (rel.get("Id", "") for rel in root)
        if rid.startswith("rId") and rid[3:].isdigit()
    ]
    rel = etree.Element(f"{{{REL_NS}}}Relationship")
    rel.set("Id", f"rId{max(used, default=0) + 1}")
    rel.set("Type", relationship_type)
    rel.set("Target", target)
    root.append(rel)
    parts[DOCUMENT_RELS_PART] = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True
    )
