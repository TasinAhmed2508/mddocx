from __future__ import annotations

from dataclasses import asdict, dataclass, field
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

from lxml import etree

from .inspection import inspect_docx_bytes

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
ADEC = "http://schemas.microsoft.com/office/drawing/2017/decorative"
DC = "http://purl.org/dc/elements/1.1/"
NS = {"w": W, "m": M, "wp": WP, "adec": ADEC, "dc": DC}

_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}


@dataclass(slots=True)
class AccessibilityFinding:
    code: str
    severity: str
    message: str
    count: int = 1


@dataclass(slots=True)
class AccessibilityReport:
    findings: list[AccessibilityFinding] = field(default_factory=list)
    images: int = 0
    images_missing_alt: int = 0
    semantic_tables: int = 0
    tables_missing_header: int = 0
    headings: int = 0
    heading_level_jumps: int = 0
    empty_hyperlinks: int = 0
    document_title_present: bool = False

    @property
    def high_findings(self) -> int:
        return sum(f.count for f in self.findings if f.severity == "high")

    @property
    def medium_findings(self) -> int:
        return sum(f.count for f in self.findings if f.severity == "medium")

    @property
    def ok(self) -> bool:
        return self.high_findings == 0

    def passes(self, fail_on: str = "high") -> bool:
        threshold = _SEVERITY_RANK.get(fail_on, 3)
        return not any(_SEVERITY_RANK.get(f.severity, 0) >= threshold for f in self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "images": self.images,
            "images_missing_alt": self.images_missing_alt,
            "semantic_tables": self.semantic_tables,
            "tables_missing_header": self.tables_missing_header,
            "headings": self.headings,
            "heading_level_jumps": self.heading_level_jumps,
            "empty_hyperlinks": self.empty_hyperlinks,
            "document_title_present": self.document_title_present,
            "findings": [asdict(f) for f in self.findings],
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)

    def to_text(self) -> str:
        status = "PASS" if self.ok else "ISSUES"
        lines = [
            f"mddocx accessibility audit: {status}",
            f"Images: {self.images}  Missing alt text: {self.images_missing_alt}",
            f"Semantic tables: {self.semantic_tables}  Missing header rows: {self.tables_missing_header}",
            f"Headings: {self.headings}  Heading-level jumps: {self.heading_level_jumps}",
            f"Empty hyperlinks: {self.empty_hyperlinks}",
            f"Document title metadata: {'yes' if self.document_title_present else 'no'}",
        ]
        if self.findings:
            lines.append("Findings:")
            for finding in self.findings:
                suffix = f" (x{finding.count})" if finding.count != 1 else ""
                lines.append(
                    f"  {finding.severity.upper()} {finding.code}: {finding.message}{suffix}"
                )
        return "\n".join(lines)


def audit_docx_accessibility(path: str | Path) -> AccessibilityReport:
    return audit_docx_accessibility_bytes(Path(path).read_bytes())


def audit_docx_accessibility_bytes(blob: bytes) -> AccessibilityReport:
    report = AccessibilityReport()
    package = inspect_docx_bytes(blob)
    if not package.valid_zip:
        report.findings.append(
            AccessibilityFinding("A11Y001", "high", "The input is not a valid DOCX package.")
        )
        return report
    try:
        with ZipFile(BytesIO(blob), "r") as zf:
            parser = etree.XMLParser(
                resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
            )
            document = etree.fromstring(zf.read("word/document.xml"), parser=parser)
            core = None
            if "docProps/core.xml" in zf.namelist():
                try:
                    core = etree.fromstring(zf.read("docProps/core.xml"), parser=parser)
                except etree.XMLSyntaxError:
                    core = None
    except (BadZipFile, KeyError, OSError, etree.XMLSyntaxError):
        report.findings.append(
            AccessibilityFinding("A11Y001", "high", "The DOCX package cannot be audited safely.")
        )
        return report

    docprs = document.xpath(".//wp:docPr", namespaces=NS)
    report.images = len(docprs)
    missing_alt = document.xpath(
        ".//wp:docPr[(not(@descr) or normalize-space(@descr)='') and not(.//adec:decorative[@val='1'])]",
        namespaces=NS,
    )
    report.images_missing_alt = len(missing_alt)
    if report.images_missing_alt:
        report.findings.append(
            AccessibilityFinding(
                "A11Y101",
                "high",
                "Images or charts are missing alternative text.",
                report.images_missing_alt,
            )
        )

    for table in document.xpath(".//w:tbl", namespaces=NS):
        # Equation-number layout tables are presentation scaffolding, not semantic data tables.
        if (
            table.xpath(".//m:oMath", namespaces=NS)
            and len(table.xpath("./w:tr", namespaces=NS)) <= 1
        ):
            continue
        report.semantic_tables += 1
        first_rows = table.xpath("./w:tr[1]", namespaces=NS)
        has_header = bool(first_rows and first_rows[0].xpath("./w:trPr/w:tblHeader", namespaces=NS))
        if not has_header:
            report.tables_missing_header += 1
    if report.tables_missing_header:
        report.findings.append(
            AccessibilityFinding(
                "A11Y201",
                "medium",
                "Semantic tables should identify their first row as a repeating/header row.",
                report.tables_missing_header,
            )
        )

    levels: list[int] = []
    for p in document.xpath(".//w:p[w:pPr/w:pStyle]", namespaces=NS):
        style_nodes = p.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS)
        if not style_nodes:
            continue
        level = _heading_level(str(style_nodes[0]))
        if level is not None:
            levels.append(level)
    report.headings = len(levels)
    last = None
    for level in levels:
        if last is not None and level > last + 1:
            report.heading_level_jumps += 1
        last = level
    if report.heading_level_jumps:
        report.findings.append(
            AccessibilityFinding(
                "A11Y301",
                "medium",
                "Heading hierarchy skips one or more levels.",
                report.heading_level_jumps,
            )
        )

    empty_links = 0
    for link in document.xpath(".//w:hyperlink", namespaces=NS):
        text = "".join(link.itertext()).strip()
        if not text:
            empty_links += 1
    report.empty_hyperlinks = empty_links
    if empty_links:
        report.findings.append(
            AccessibilityFinding(
                "A11Y401", "high", "Hyperlinks with no readable link text were found.", empty_links
            )
        )

    title = ""
    if core is not None:
        nodes = core.xpath("./dc:title", namespaces=NS)
        if nodes and nodes[0].text:
            title = nodes[0].text.strip()
    report.document_title_present = bool(title)
    if not report.document_title_present:
        report.findings.append(
            AccessibilityFinding(
                "A11Y501",
                "low",
                "Document title metadata is empty. Set RenderConfig.title or YAML front matter title.",
            )
        )

    if not levels:
        report.findings.append(
            AccessibilityFinding("A11Y302", "low", "No semantic Word heading styles were detected.")
        )
    return report


def _heading_level(style: str) -> int | None:
    compact = style.replace(" ", "")
    match = re.search(r"(?:MD)?Heading([1-6])$", compact, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None
