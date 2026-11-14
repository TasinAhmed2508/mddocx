"""Compare normalized Markdown and a DOCX package without rendering either."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import json
from pathlib import PurePosixPath
import re

from lxml import etree

from .ast import block, inline
from .ast.base import Document, Node
from .config import RenderConfig
from .diagnostics import Diagnostic
from .inspection import M, NS, R, W
from .ooxml.bangla import LEGACY_BANGLA_FONT
from .ooxml.charts import C, CHART_REL, PACKAGE_REL
from .ooxml.text import clean_xml_text
from .references import ReferenceRegistry

BODY = "word/document.xml"
_RELS = "word/_rels/document.xml.rels"
_HEADING = re.compile(r"(?:MD)?Heading[ ]?([1-6])", re.I)


@dataclass(frozen=True, slots=True)
class VerificationFinding:
    code: str
    message: str
    part: str = BODY
    source_file: str | None = None
    line: int | None = None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    checked_units: int
    findings: tuple[VerificationFinding, ...]
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_json(self) -> str:
        return json.dumps({**asdict(self), "ok": self.ok}, ensure_ascii=True, indent=2)


@dataclass(frozen=True, slots=True)
class _Unit:
    kind: str
    content: tuple
    source: Node | None = None

    @property
    def key(self) -> tuple:
        return self.kind, self.content


def compare_document(
    document: Document, roots: dict[str, etree._Element], config: RenderConfig
) -> VerificationResult:
    expected: list[_Unit] = []
    findings: list[VerificationFinding] = []
    references = ReferenceRegistry.from_document(
        document,
        _plain_text,
        config.references.equation_number_format,
        config.references.caption_number_format,
    )
    notes: dict[str, int] = {}
    note_kind = config.notes.style
    note_part = f"word/{note_kind}s.xml"

    def incomplete(reason: str, node: Node | None = None) -> None:
        findings.append(_finding("VERIFY304", reason, node))

    def expected_inlines(nodes) -> tuple:
        tokens = []
        for node in nodes:
            if isinstance(node, inline.Text):
                tokens.append(clean_xml_text(node.text))
            elif isinstance(node, inline.InlineCode):
                tokens.append(clean_xml_text(node.code))
            elif isinstance(node, (inline.Strong, inline.Emphasis, inline.Strikethrough)):
                tokens.extend(expected_inlines(node.children))
            elif isinstance(node, inline.SoftBreak):
                tokens.append(" ")
            elif isinstance(node, inline.HardBreak):
                tokens.append(("break",))
            elif isinstance(node, inline.InlineMath):
                tokens.append(("math",))
            elif isinstance(node, inline.Image):
                tokens.append(("image", node.alt))
            elif isinstance(node, inline.Link):
                href = node.href
                if href.startswith("#") and config.references.enabled:
                    target = references.get(href[1:])
                    if target is None:
                        incomplete("Unresolved internal hyperlink.", node)
                        tokens.append(_plain_text(node.children))
                        continue
                    href = "#" + target.bookmark
                tokens.append(("link", href, _plain_text(node.children)))
            elif isinstance(node, inline.FootnoteReference):
                if node.label in document.footnotes:
                    number = notes.setdefault(node.label, len(notes) + 1)
                    tokens.append(("note", note_kind, str(number)))
                else:
                    tokens.append(f"[^{node.label}]")
            elif isinstance(node, inline.CrossReference) and config.references.enabled:
                target = references.get(node.target)
                if not target:
                    tokens.append((node.prefix + " " if node.prefix else "") + "@" + node.target)
                    continue
                prefix = node.prefix
                if (
                    prefix is None
                    and config.references.include_prefix_in_crossrefs
                    and target.kind != "Section"
                ):
                    prefix = getattr(config.references, f"{target.kind.lower()}_label", target.kind)
                if prefix and not (
                    target.kind == "Section"
                    and (target.title or "").lower().startswith(prefix.lower())
                ):
                    tokens.append(prefix + " ")
                tokens.append(("ref", target.bookmark))
            else:
                incomplete(f"Inline {type(node).__name__} coverage is incomplete.", node)
        return _merge_text(tokens)

    def captioned(unit: _Unit, label: str, text: str | None, node) -> None:
        if text is None:
            expected.append(unit)
            return
        target = references.get(node.identifier) if node.identifier else None
        caption = _Unit(
            "caption", (label, clean_xml_text(text), target.bookmark if target else None), node
        )
        if getattr(config.references, f"{label.lower()}_caption_position") == "above":
            expected.extend((caption, unit))
        else:
            expected.extend((unit, caption))

    def blocks(nodes, level: int = 0) -> None:
        for node in nodes:
            if isinstance(node, block.Heading):
                target = references.get(node.identifier) if node.identifier else None
                bookmark = target.bookmark if config.heading_bookmarks and target else None
                expected.append(
                    _Unit("heading", (node.level, bookmark, expected_inlines(node.children)), node)
                )
            elif isinstance(node, block.Paragraph):
                expected.append(_Unit("paragraph", expected_inlines(node.children), node))
            elif isinstance(node, (block.BulletList, block.OrderedList)):
                for item in node.items:
                    numbered = False
                    for child in item.children:
                        if isinstance(child, block.Paragraph) and not numbered:
                            kind = "task" if item.task_checked is not None else "list"
                            marker = item.task_checked if kind == "task" else level
                            expected.append(
                                _Unit(kind, (marker, expected_inlines(child.children)), child)
                            )
                            numbered = True
                        else:
                            blocks([child], level + 1)
                    if not numbered:
                        incomplete("List item without an opening paragraph.", item)
            elif isinstance(node, block.BlockQuote):
                blocks(node.children, level)
            elif isinstance(node, block.Callout):
                first = True
                kind = (node.kind or "note").lower()
                title = clean_xml_text(node.title or config.callouts.labels.get(kind, kind.title()))
                for child in node.children or [block.Paragraph()]:
                    if isinstance(child, block.Paragraph):
                        prefix = (title + (" — " if child.children else ""),) if first else ()
                        expected.append(
                            _Unit(
                                "paragraph",
                                _merge_text((*prefix, *expected_inlines(child.children))),
                                child,
                            )
                        )
                        first = False
                    else:
                        if first and isinstance(child, (block.BulletList, block.OrderedList)):
                            expected.append(_Unit("paragraph", (title,), node))
                            first = False
                        blocks([child], level)
            elif isinstance(node, block.DefinitionList):
                for item in node.items:
                    expected.append(_Unit("paragraph", expected_inlines(item.term), item))
                    expected.append(_Unit("paragraph", expected_inlines(item.definition), item))
            elif isinstance(node, block.HorizontalRule):
                expected.append(_Unit("paragraph", (), node))
            elif isinstance(node, block.SectionBreak):
                incomplete("Section break layout is outside current coverage.", node)
            elif isinstance(node, block.Table):
                rows = tuple(
                    tuple(expected_inlines(cell.children) for cell in row.cells)
                    for row in node.rows
                )
                title = (
                    (node.caption or ("Table" if node.identifier else None))
                    if config.references.captions
                    else None
                )
                captioned(_Unit("table", rows, node), "Table", title, node)
            elif isinstance(node, block.ImageBlock):
                title = (
                    (
                        node.caption
                        or (node.title if config.image_captions_from_title else None)
                        or (node.alt if node.identifier else None)
                    )
                    if config.references.captions
                    else None
                )
                decorative = node.decorative and config.accessibility.mark_decorative_images
                token = ("image", "") if decorative else ("image", clean_xml_text(node.alt))
                captioned(_Unit("paragraph", (token,), node), "Figure", title, node)
            elif isinstance(node, block.ChartBlock) and config.charts.enabled:
                title = (
                    (node.caption or node.title or ("Chart" if node.identifier else None))
                    if config.references.captions
                    else None
                )
                captioned(_Unit("paragraph", (("chart",),), node), "Figure", title, node)
            elif isinstance(node, block.MathBlock):
                if (
                    node.identifier
                    and config.references.enabled
                    and config.references.equation_numbering
                ):
                    target = references.get(node.identifier)
                    expected.append(
                        _Unit("numbered equation", (target.bookmark if target else None,), node)
                    )
                else:
                    expected.append(_Unit("paragraph", (("math",),), node))
                if node.caption:
                    expected.append(
                        _Unit("caption", ("", clean_xml_text(node.caption), None), node)
                    )
            elif isinstance(node, block.PageBreak):
                expected.append(_Unit("paragraph", (("page-break",),), node))
            else:
                incomplete(f"Block {type(node).__name__} coverage is incomplete.", node)

    blocks(document.children)
    if (
        config.extensions
        or config.plugins.names
        or config.template
        or config.title_page.enabled
        or config.abstract.text
        or config.toc.enabled
    ):
        incomplete(
            "Generated front matter, templates, and extensions have limited verification coverage."
        )
    expected_notes = {
        str(number): expected_inlines(document.footnotes[label])
        for label, number in list(notes.items())
    }
    actual_notes = {}
    if note_part in roots:
        for item in roots[note_part]:
            ident = item.get(f"{{{W}}}id")
            if item.tag == f"{{{W}}}{note_kind}" and ident and not item.get(f"{{{W}}}type"):
                tokens = _read_inlines(item, {})
                if tokens and isinstance(tokens[0], str):
                    tokens = _merge_text((tokens[0].removeprefix(" "), *tokens[1:]))
                actual_notes[ident] = tokens
    for ident in sorted(set(expected_notes) | set(actual_notes)):
        if expected_notes.get(ident) != actual_notes.get(ident):
            findings.append(
                VerificationFinding(
                    "VERIFY303", f"Changed or missing {note_kind} {ident}.", note_part
                )
            )
    actual = _read_body(roots)
    findings.extend(_chart_findings(roots))
    expected_keys = [unit.key for unit in expected]
    actual_keys = [unit.key for unit in actual]
    if expected_keys == actual_keys:
        return VerificationResult(len(expected), tuple(findings))
    if max(len(expected), len(actual)) > 4000:
        # shortcut: diagnose the first difference for very long files, until a bounded diff is needed.
        first = next(
            (i for i, pair in enumerate(zip(expected_keys, actual_keys)) if pair[0] != pair[1]),
            min(len(expected), len(actual)),
        )
        wanted, found = expected[first : first + 1], actual[first : first + 1]
        findings.append(
            _finding(
                "VERIFY303",
                f"Unit {first + 1}: expected {_describe(wanted)}, found {_describe(found)}.",
                wanted[0].source if wanted else None,
            )
        )
        return VerificationResult(len(expected), tuple(findings))
    matcher = SequenceMatcher(None, expected_keys, actual_keys, autojunk=False)
    for operation, start, end, actual_start, actual_end in matcher.get_opcodes():
        if operation == "equal":
            continue
        if operation == "insert":
            findings.append(
                _finding("VERIFY302", f"Unexpected {_describe(actual[actual_start:actual_end])}.")
            )
        elif operation == "delete":
            findings.append(
                _finding(
                    "VERIFY301",
                    f"Missing {_describe(expected[start:end])}.",
                    expected[start].source,
                )
            )
        else:
            findings.append(
                _finding(
                    "VERIFY303",
                    f"Expected {_describe(expected[start:end])}, found {_describe(actual[actual_start:actual_end])}.",
                    expected[start].source,
                )
            )
    return VerificationResult(len(expected), tuple(findings))


def _finding(code: str, message: str, node: Node | None = None) -> VerificationFinding:
    source = node.source if node else None
    return VerificationFinding(
        code,
        message,
        source_file=source.file if source else None,
        line=source.line if source else None,
    )


def _describe(units: list[_Unit]) -> str:
    if not units:
        return "end of document"
    first = units[0]
    extra = f" and {len(units) - 1} more" if len(units) > 1 else ""
    return f"{first.kind} {repr(first.content)[:150]}{extra}"


def _chart_findings(roots: dict[str, etree._Element]) -> list[VerificationFinding]:
    charts = roots[BODY].xpath(".//c:chart", namespaces={"c": C})
    relationships = roots.get(_RELS)
    chart_targets = (
        {
            relation.get("Id"): relation.get("Target", "")
            for relation in relationships
            if relation.get("Type") == CHART_REL
        }
        if relationships is not None
        else {}
    )
    findings = []
    for chart in charts:
        rid = chart.get(f"{{{R}}}id")
        target = chart_targets.get(rid, "")
        target = target.lstrip("/") if target.startswith("/") else "word/" + target
        chart_root = roots.get(target)
        if chart_root is None or chart_root.find(f".//{{{C}}}plotArea") is None:
            findings.append(
                VerificationFinding("VERIFY303", "Missing native ChartML plot area.", target)
            )
            continue
        path = PurePosixPath(target)
        chart_rels = roots.get(str(path.parent / "_rels" / (path.name + ".rels")))
        data = chart_root.find(f".//{{{C}}}externalData")
        external_id = data.get(f"{{{R}}}id") if data is not None else None
        if (
            chart_rels is None
            or not external_id
            or not any(
                relation.get("Id") == external_id and relation.get("Type") == PACKAGE_REL
                for relation in chart_rels
            )
        ):
            findings.append(
                VerificationFinding("VERIFY303", "Missing chart workbook binding.", target)
            )
    return findings


def _merge_text(tokens) -> tuple:
    merged: list = []
    text: list[str] = []
    for token in tokens:
        if isinstance(token, str):
            if token:
                text.append(token)
        else:
            if text:
                merged.append("".join(text))
                text.clear()
            merged.append(token)
    if text:
        merged.append("".join(text))
    return tuple(merged)


def _plain_text(nodes) -> str:
    pieces = []
    for node in nodes:
        if isinstance(node, inline.Text):
            pieces.append(node.text)
        elif isinstance(node, inline.InlineCode):
            pieces.append(node.code)
        elif isinstance(node, (inline.HardBreak, inline.SoftBreak)):
            pieces.append(" ")
        elif isinstance(node, inline.InlineMath):
            pieces.append(node.source_text)
        elif isinstance(node, inline.Image):
            pieces.append(node.alt)
        elif hasattr(node, "children"):
            pieces.append(_plain_text(node.children))
    return clean_xml_text("".join(pieces))


def _read_body(roots: dict[str, etree._Element]) -> list[_Unit]:
    relationships = roots.get(_RELS)
    links = (
        {rel.get("Id"): rel.get("Target") for rel in relationships}
        if relationships is not None
        else {}
    )
    body = roots[BODY].find(f"{{{W}}}body")
    if body is None:
        return []
    result = []
    for child in body:
        if child.tag == f"{{{W}}}tbl":
            instructions = child.xpath(".//w:instrText/text()", namespaces=NS)
            if any("SEQ Equation" in instruction for instruction in instructions):
                mark = child.find(".//w:bookmarkStart", NS)
                name = mark.get(f"{{{W}}}name") if mark is not None else None
                equations = child.xpath(".//m:oMath", namespaces=NS)
                result.append(
                    _Unit(
                        "numbered equation",
                        (name,) if len(equations) == 1 else (name, len(equations)),
                    )
                )
                continue
            rows = tuple(
                tuple(_read_inlines(cell, links) for cell in row.findall(f"{{{W}}}tc"))
                for row in child.findall(f"{{{W}}}tr")
            )
            result.append(_Unit("table", rows))
        elif child.tag == f"{{{W}}}p":
            tokens = _read_inlines(child, links)
            style = child.find("w:pPr/w:pStyle", NS)
            name = style.get(f"{{{W}}}val", "") if style is not None else ""
            heading = _HEADING.fullmatch(name)
            level = child.find("w:pPr/w:numPr/w:ilvl", NS)
            checkbox = child.find(".//w14:checked", NS)
            if heading:
                marker = child.find(f"{{{W}}}bookmarkStart")
                bookmark = marker.get(f"{{{W}}}name") if marker is not None else None
                result.append(_Unit("heading", (int(heading[1]), bookmark, tokens)))
            elif name == "MDCaption":
                instructions = child.xpath(".//w:instrText/text()", namespaces=NS)
                labels = [
                    instruction.split()[1]
                    for instruction in instructions
                    if len(instruction.split()) > 1 and instruction.lstrip().startswith("SEQ ")
                ]
                label = labels[-1] if labels else ""
                text = "".join(token for token in tokens if isinstance(token, str))
                mark = child.find("w:bookmarkStart", NS)
                bookmark = mark.get(f"{{{W}}}name") if mark is not None else None
                result.append(
                    _Unit("caption", (label, text.split(" — ", 1)[-1] if label else text, bookmark))
                )
            elif (
                child.xpath(".//w:rPr/w:vanish", namespaces=NS)
                and child.find(".//w:instrText", NS) is not None
            ):
                continue
            elif checkbox is not None:
                if tokens and isinstance(tokens[0], str):
                    tokens = (tokens[0].removeprefix(" "), *tokens[1:])
                result.append(_Unit("task", (checkbox.get(f"{{{NS['w14']}}}val") == "1", tokens)))
            elif level is not None:
                result.append(_Unit("list", (int(level.get(f"{{{W}}}val", "0")), tokens)))
            elif tokens or child.find("w:pPr/w:sectPr", NS) is None:
                result.append(_Unit("paragraph", tokens))
    return result


def _read_inlines(parent: etree._Element, links: dict) -> tuple:
    tokens = []
    ref_field = False
    for node in parent:
        if node.tag == f"{{{W}}}t":
            run = node.getparent()
            font = run.find("w:rPr/w:rFonts", NS) if run is not None else None
            text = node.text or ""
            if (
                font is not None
                and font.get(f"{{{W}}}ascii", "").casefold() == LEGACY_BANGLA_FONT.casefold()
            ):
                from bijoy2unicode.converter import Unicode

                text = Unicode().convertBijoyToUnicode(text.replace("\u00f8", "\u00ad"))
            tokens.append(text)
        elif node.tag == f"{{{W}}}br":
            tokens.append(("page-break",) if node.get(f"{{{W}}}type") == "page" else ("break",))
        elif node.tag == f"{{{W}}}tab":
            tokens.append("\t")
        elif node.tag == f"{{{M}}}oMath":
            tokens.append(("math",))
        elif node.tag == f"{{{W}}}hyperlink":
            anchor = node.get(f"{{{W}}}anchor")
            href = "#" + anchor if anchor else links.get(node.get(f"{{{R}}}id"))
            tokens.append(("link", href, "".join(str(t) for t in _read_inlines(node, links))))
        elif node.tag == f"{{{W}}}drawing":
            if node.find(f".//{{{C}}}chart") is not None:
                tokens.append(("chart",))
            else:
                prop = node.find(".//wp:docPr", NS)
                tokens.append(("image", prop.get("descr", "") if prop is not None else ""))
        elif node.tag in {f"{{{W}}}footnoteReference", f"{{{W}}}endnoteReference"}:
            kind = etree.QName(node).localname.removesuffix("Reference")
            tokens.append(("note", kind, node.get(f"{{{W}}}id")))
        elif node.tag == f"{{{W}}}r":
            instruction = node.findtext(f"{{{W}}}instrText", "")
            match = re.match(r"\s*REF\s+(\S+)", instruction, re.I)
            end = node.find(f"{{{W}}}fldChar")
            if match:
                tokens.append(("ref", match[1]))
                ref_field = True
            elif end is not None and end.get(f"{{{W}}}fldCharType") == "end":
                ref_field = False
            elif not ref_field:
                tokens.extend(_read_inlines(node, links))
        elif node.tag in {f"{{{W}}}p", f"{{{M}}}oMathPara"}:
            tokens.extend(_read_inlines(node, links))
    return _merge_text(tokens)
