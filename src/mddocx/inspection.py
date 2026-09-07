from __future__ import annotations

from dataclasses import asdict, dataclass, field
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import posixpath
from typing import Iterable
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
ADEC = "http://schemas.microsoft.com/office/drawing/2017/decorative"
NS = {"w": W, "m": M, "r": R, "w14": W14, "wp": WP, "adec": ADEC, "pr": PR}

_SUSPICIOUS_PLACEHOLDERS = ("□", "▯", "�")


@dataclass(slots=True)
class DocxInspection:
    valid_zip: bool = False
    package_parts: int = 0
    duplicate_parts: list[str] = field(default_factory=list)
    missing_required_parts: list[str] = field(default_factory=list)
    invalid_xml_parts: list[str] = field(default_factory=list)
    broken_relationships: list[str] = field(default_factory=list)
    duplicate_relationship_ids: int = 0
    duplicate_drawing_ids: int = 0
    duplicate_note_ids: int = 0
    chart_relationship_issues: int = 0
    paragraphs: int = 0
    headings: int = 0
    tables: int = 0
    table_overflow_candidates: int = 0
    equations: int = 0
    nary_operators: int = 0
    empty_nary_operands: int = 0
    radicals: int = 0
    radicals_missing_degree: int = 0
    matrices: int = 0
    native_list_paragraphs: int = 0
    task_checkboxes: int = 0
    footnote_references: int = 0
    footnote_definitions: int = 0
    endnote_references: int = 0
    endnote_definitions: int = 0
    drawings: int = 0
    media_parts: int = 0
    native_charts: int = 0
    embedded_workbooks: int = 0
    hyperlinks: int = 0
    bookmarks: int = 0
    fields: int = 0
    seq_fields: int = 0
    ref_fields: int = 0
    internal_hyperlinks: int = 0
    dangling_internal_hyperlinks: int = 0
    dangling_ref_fields: int = 0
    duplicate_bookmark_names: int = 0
    comment_references: int = 0
    comment_definitions: int = 0
    images_missing_alt: int = 0
    sections: int = 0
    landscape_sections: int = 0
    suspicious_placeholder_chars: dict[str, int] = field(default_factory=dict)

    @property
    def structural_issues(self) -> int:
        return (
            len(self.duplicate_parts)
            + len(self.missing_required_parts)
            + len(self.invalid_xml_parts)
            + len(self.broken_relationships)
            + self.duplicate_relationship_ids
            + self.duplicate_drawing_ids
            + self.duplicate_note_ids
            + self.chart_relationship_issues
            + self.empty_nary_operands
            + self.radicals_missing_degree
            + self.dangling_internal_hyperlinks
            + self.dangling_ref_fields
            + self.duplicate_bookmark_names
            + abs(self.comment_references - self.comment_definitions)
        )

    @property
    def quality_warnings(self) -> int:
        return self.table_overflow_candidates + sum(self.suspicious_placeholder_chars.values())

    @property
    def ok(self) -> bool:
        return self.valid_zip and self.structural_issues == 0

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["structural_issues"] = self.structural_issues
        payload["quality_warnings"] = self.quality_warnings
        payload["ok"] = self.ok
        return payload

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)

    def to_text(self) -> str:
        status = "PASS" if self.ok and not self.quality_warnings else ("PASS WITH WARNINGS" if self.ok else "ISSUES")
        lines = [
            f"mddocx inspection: {status}",
            f"Package parts: {self.package_parts}",
            f"Paragraphs: {self.paragraphs}  Headings: {self.headings}",
            f"Tables: {self.tables}  Overflow candidates: {self.table_overflow_candidates}",
            f"Equations: {self.equations}  N-ary: {self.nary_operators}  Empty n-ary operands: {self.empty_nary_operands}",
            f"Radicals: {self.radicals}  Missing radical degree nodes: {self.radicals_missing_degree}",
            f"Matrices: {self.matrices}",
            f"Native list paragraphs: {self.native_list_paragraphs}  Task checkboxes: {self.task_checkboxes}",
            f"Footnote refs/definitions: {self.footnote_references}/{self.footnote_definitions}  Endnotes: {self.endnote_references}/{self.endnote_definitions}",
            f"Drawings/media: {self.drawings}/{self.media_parts}  Native charts/workbooks: {self.native_charts}/{self.embedded_workbooks}",
            f"Hyperlinks: {self.hyperlinks}  Internal: {self.internal_hyperlinks}  Dangling internal: {self.dangling_internal_hyperlinks}  Bookmarks: {self.bookmarks}",
            f"REF targets dangling: {self.dangling_ref_fields}  Duplicate bookmark names: {self.duplicate_bookmark_names}",
            f"Comments refs/definitions: {self.comment_references}/{self.comment_definitions}",
            f"Fields: {self.fields}  SEQ: {self.seq_fields}  REF: {self.ref_fields}  Images missing alt: {self.images_missing_alt}",
            f"Sections: {self.sections}  Landscape: {self.landscape_sections}",
            f"Broken relationships: {len(self.broken_relationships)}  Duplicate relationship IDs: {self.duplicate_relationship_ids}",
            f"Duplicate drawing IDs: {self.duplicate_drawing_ids}  Duplicate note IDs: {self.duplicate_note_ids}",
            f"Chart/workbook relationship issues: {self.chart_relationship_issues}",
            f"Suspicious placeholder characters: {sum(self.suspicious_placeholder_chars.values())}",
        ]
        if self.missing_required_parts:
            lines.append("Missing required parts: " + ", ".join(self.missing_required_parts))
        if self.duplicate_parts:
            lines.append("Duplicate parts: " + ", ".join(self.duplicate_parts))
        if self.invalid_xml_parts:
            lines.append("Invalid XML parts: " + ", ".join(self.invalid_xml_parts))
        if self.broken_relationships:
            lines.append("Broken relationship targets:")
            lines.extend(f"  - {value}" for value in self.broken_relationships[:20])
        if self.suspicious_placeholder_chars:
            details = ", ".join(f"{repr(k)}×{v}" for k, v in self.suspicious_placeholder_chars.items())
            lines.append("Placeholder details: " + details)
        return "\n".join(lines)


def inspect_docx(path: str | Path) -> DocxInspection:
    return inspect_docx_bytes(Path(path).read_bytes())


def inspect_docx_bytes(blob: bytes) -> DocxInspection:
    report = DocxInspection()
    try:
        archive = ZipFile(BytesIO(blob), "r")
    except (BadZipFile, OSError, ValueError):
        return report

    with archive:
        report.valid_zip = True
        infos = archive.infolist()
        names = [info.filename for info in infos]
        report.package_parts = len(names)
        seen: set[str] = set()
        dupes: set[str] = set()
        for name in names:
            if name in seen:
                dupes.add(name)
            seen.add(name)
        report.duplicate_parts = sorted(dupes)
        required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
        report.missing_required_parts = sorted(required.difference(seen))

        roots: dict[str, etree._Element] = {}
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
        for name in names:
            if not (name.endswith(".xml") or name.endswith(".rels")):
                continue
            try:
                roots[name] = etree.fromstring(archive.read(name), parser=parser)
            except (etree.XMLSyntaxError, ValueError, KeyError):
                report.invalid_xml_parts.append(name)

        report.invalid_xml_parts.sort()
        report.broken_relationships = _broken_relationships(roots, seen)
        report.duplicate_relationship_ids = _count_duplicate_relationship_ids(roots)
        report.chart_relationship_issues = _count_chart_relationship_issues(roots, seen)

        document = roots.get("word/document.xml")
        if document is None:
            return report

        report.duplicate_drawing_ids = _count_duplicate_drawing_ids(document)
        report.paragraphs = len(document.xpath(".//w:p", namespaces=NS))
        report.headings = len(
            document.xpath(
                './/w:p[w:pPr/w:pStyle[starts-with(@w:val,"Heading") or starts-with(@w:val,"MD Heading") or starts-with(@w:val,"MDHeading")]]',
                namespaces=NS,
            )
        )
        report.tables = len(document.xpath(".//w:tbl", namespaces=NS))
        content_roots = [
            root for name, root in roots.items()
            if name == "word/document.xml"
            or name in {"word/footnotes.xml", "word/endnotes.xml"}
            or name.startswith("word/header")
            or name.startswith("word/footer")
        ]
        report.equations = sum(len(root.xpath(".//m:oMath", namespaces=NS)) for root in content_roots)
        report.nary_operators = sum(len(root.xpath(".//m:nary", namespaces=NS)) for root in content_roots)
        report.empty_nary_operands = sum(_count_empty_nary_operands(root) for root in content_roots)
        report.radicals = sum(len(root.xpath(".//m:rad", namespaces=NS)) for root in content_roots)
        report.radicals_missing_degree = sum(len(root.xpath(".//m:rad[not(m:deg)]", namespaces=NS)) for root in content_roots)
        report.matrices = sum(len(root.xpath(".//m:m", namespaces=NS)) for root in content_roots)
        report.native_list_paragraphs = len(document.xpath(".//w:p[w:pPr/w:numPr]", namespaces=NS))
        report.task_checkboxes = len(document.xpath(".//w14:checkbox", namespaces=NS))
        report.footnote_references = len(document.xpath(".//w:footnoteReference", namespaces=NS))
        report.endnote_references = len(document.xpath(".//w:endnoteReference", namespaces=NS))
        report.drawings = sum(len(root.xpath(".//w:drawing", namespaces=NS)) for root in content_roots)
        report.hyperlinks = sum(len(root.xpath(".//w:hyperlink", namespaces=NS)) for root in content_roots)
        report.internal_hyperlinks = len(document.xpath(".//w:hyperlink[@w:anchor]", namespaces=NS))
        bookmark_nodes = document.xpath(".//w:bookmarkStart", namespaces=NS)
        report.bookmarks = len(bookmark_nodes)
        bookmark_names = [n.get(f"{{{W}}}name") for n in bookmark_nodes if n.get(f"{{{W}}}name")]
        report.duplicate_bookmark_names = len(bookmark_names) - len(set(bookmark_names))
        anchors = [n.get(f"{{{W}}}anchor") for n in document.xpath(".//w:hyperlink[@w:anchor]", namespaces=NS)]
        report.dangling_internal_hyperlinks = sum(1 for a in anchors if a and a not in set(bookmark_names))
        report.comment_references = len(document.xpath(".//w:commentReference", namespaces=NS))
        field_nodes = [n for root in content_roots for n in root.xpath(".//w:instrText", namespaces=NS)]
        report.fields = len(field_nodes)
        report.seq_fields = sum(1 for n in field_nodes if (n.text or "").strip().startswith("SEQ "))
        report.ref_fields = sum(1 for n in field_nodes if (n.text or "").strip().startswith("REF "))
        ref_targets = []
        for n in field_nodes:
            text = (n.text or "").strip()
            if text.startswith("REF "):
                parts = text.split()
                if len(parts) >= 2:
                    ref_targets.append(parts[1])
        report.dangling_ref_fields = sum(1 for name in ref_targets if name not in set(bookmark_names))
        report.images_missing_alt = len(document.xpath(".//wp:docPr[(not(@descr) or normalize-space(@descr)='') and not(.//adec:decorative[@val='1'])]", namespaces=NS))
        report.sections = len(document.xpath(".//w:sectPr", namespaces=NS))
        report.landscape_sections = _count_landscape_sections(document)
        report.table_overflow_candidates = _count_table_overflow_candidates(document)

        footnotes = roots.get("word/footnotes.xml")
        if footnotes is not None:
            ids = []
            for node in footnotes.xpath("./w:footnote", namespaces=NS):
                raw = node.get(f"{{{W}}}id")
                try:
                    value = int(raw) if raw is not None else -999
                except ValueError:
                    continue
                if value > 0:
                    ids.append(value)
            report.footnote_definitions = len(ids)
            report.duplicate_note_ids += len(ids) - len(set(ids))

        endnotes = roots.get("word/endnotes.xml")
        if endnotes is not None:
            ids = []
            for node in endnotes.xpath("./w:endnote", namespaces=NS):
                raw = node.get(f"{{{W}}}id")
                try:
                    value = int(raw) if raw is not None else -999
                except ValueError:
                    continue
                if value > 0:
                    ids.append(value)
            report.endnote_definitions = len(ids)
            report.duplicate_note_ids += len(ids) - len(set(ids))

        comments = roots.get("word/comments.xml")
        if comments is not None:
            report.comment_definitions = len(comments.xpath("./w:comment", namespaces=NS))

        report.media_parts = sum(1 for name in names if name.startswith("word/media/") and not name.endswith("/"))
        report.native_charts = sum(1 for name in names if name.startswith("word/charts/chart") and name.endswith(".xml"))
        report.embedded_workbooks = sum(1 for name in names if name.startswith("word/embeddings/") and name.lower().endswith(".xlsx"))
        report.suspicious_placeholder_chars = _placeholder_counts(roots.values())
    return report


def _count_empty_nary_operands(root: etree._Element) -> int:
    count = 0
    for node in root.xpath(".//m:nary", namespaces=NS):
        operands = node.xpath("./m:e", namespaces=NS)
        if not operands:
            count += 1
            continue
        operand = operands[0]
        text = "".join(operand.itertext()).strip()
        # A legitimate operand can contain only structured math without text in an
        # intermediate node, so also consider descendant math runs/elements.
        meaningful = bool(text) or bool(operand.xpath(".//m:r|.//m:f|.//m:rad|.//m:m|.//m:sSup|.//m:sSub|.//m:d", namespaces=NS))
        if not meaningful:
            count += 1
    return count


def _count_landscape_sections(root: etree._Element) -> int:
    total = 0
    for sect in root.xpath(".//w:sectPr", namespaces=NS):
        pg = sect.find(f"{{{W}}}pgSz")
        if pg is None:
            continue
        orient = pg.get(f"{{{W}}}orient")
        try:
            width = int(pg.get(f"{{{W}}}w") or "0")
            height = int(pg.get(f"{{{W}}}h") or "0")
        except ValueError:
            width = height = 0
        if orient == "landscape" or (width and height and width > height):
            total += 1
    return total


def _section_available_widths(root: etree._Element) -> list[int]:
    values: list[int] = []
    for sect in root.xpath(".//w:sectPr", namespaces=NS):
        pg = sect.find(f"{{{W}}}pgSz")
        mar = sect.find(f"{{{W}}}pgMar")
        try:
            width = int((pg.get(f"{{{W}}}w") if pg is not None else None) or "12240")
            left = int((mar.get(f"{{{W}}}left") if mar is not None else None) or "1440")
            right = int((mar.get(f"{{{W}}}right") if mar is not None else None) or "1440")
        except ValueError:
            continue
        values.append(max(1, width - left - right))
    return values or [9360]


def _count_table_overflow_candidates(root: etree._Element) -> int:
    # Conservative structural signal: only flag a table if its explicit grid is
    # wider than *every* section's usable width. This avoids false positives for
    # tables intentionally placed in a landscape section.
    max_available = max(_section_available_widths(root))
    count = 0
    for table in root.xpath(".//w:tbl", namespaces=NS):
        total = 0
        for col in table.xpath("./w:tblGrid/w:gridCol", namespaces=NS):
            try:
                total += int(col.get(f"{{{W}}}w") or "0")
            except ValueError:
                pass
        if total > max_available * 1.03:
            count += 1
    return count


def _placeholder_counts(roots: Iterable[etree._Element]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for root in roots:
        if root.tag.endswith("Relationships"):
            continue
        text = "".join(root.itertext())
        for char in _SUSPICIOUS_PLACEHOLDERS:
            n = text.count(char)
            if n:
                counts[char] = counts.get(char, 0) + n
    return counts


def _broken_relationships(roots: dict[str, etree._Element], names: set[str]) -> list[str]:
    broken: list[str] = []
    for rels_name, root in roots.items():
        if not rels_name.endswith(".rels"):
            continue
        source_dir = _relationship_source_dir(rels_name)
        for rel in root.xpath("./pr:Relationship", namespaces=NS):
            if (rel.get("TargetMode") or "").lower() == "external":
                continue
            target = unquote(rel.get("Target") or "")
            if not target or target.startswith("#"):
                continue
            normalized = _resolve_relationship_target(source_dir, target)
            if normalized not in names:
                rid = rel.get("Id") or "?"
                broken.append(f"{rels_name}:{rid} -> {normalized}")
    return sorted(broken)


def _count_duplicate_relationship_ids(roots: dict[str, etree._Element]) -> int:
    duplicates = 0
    for name, root in roots.items():
        if not name.endswith(".rels"):
            continue
        ids = [value for value in root.xpath("./pr:Relationship/@Id", namespaces=NS) if value]
        duplicates += len(ids) - len(set(ids))
    return duplicates


def _count_duplicate_drawing_ids(document: etree._Element) -> int:
    ids = [value for value in document.xpath(".//wp:docPr/@id", namespaces=NS) if value]
    return len(ids) - len(set(ids))


def _count_chart_relationship_issues(roots: dict[str, etree._Element], names: set[str]) -> int:
    issues = 0
    for name in sorted(names):
        if not (name.startswith("word/charts/chart") and name.endswith(".xml")):
            continue
        chart_name = PurePosixPath(name).name
        rels_name = f"word/charts/_rels/{chart_name}.rels"
        rels = roots.get(rels_name)
        if rels is None:
            issues += 1
            continue
        package_rels = [
            rel for rel in rels.xpath("./pr:Relationship", namespaces=NS)
            if (rel.get("Type") or "").endswith("/package")
        ]
        if len(package_rels) != 1:
            issues += 1
            continue
        target = package_rels[0].get("Target") or ""
        resolved = _resolve_relationship_target("word/charts", target)
        if resolved not in names or not resolved.lower().endswith(".xlsx"):
            issues += 1
    return issues


def _relationship_source_dir(rels_name: str) -> str:
    path = PurePosixPath(rels_name)
    if rels_name == "_rels/.rels":
        return ""
    parts = path.parts
    try:
        idx = parts.index("_rels")
    except ValueError:
        return str(path.parent)
    prefix = parts[:idx]
    rel_file = parts[idx + 1] if idx + 1 < len(parts) else ""
    source_name = rel_file[:-5] if rel_file.endswith(".rels") else rel_file
    source_part = PurePosixPath(*prefix, source_name)
    return str(source_part.parent) if str(source_part.parent) != "." else ""


def _resolve_relationship_target(source_dir: str, target: str) -> str:
    target = target.replace("\\", "/")
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(source_dir, target)).lstrip("./")
