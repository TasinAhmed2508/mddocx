"""Compare normalized Markdown and a DOCX package without rendering either."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from itertools import zip_longest
from io import BytesIO
import json
from pathlib import PurePosixPath
import posixpath
import re
from typing import Literal
from zipfile import ZipFile

from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml.ns import qn
from lxml import etree

from .ast import block, inline
from .ast.base import Document, Node
from .chart_data import prepare_chart_entry
from .chart_verification import chart_data_issue, workbook_data_issue
from .config import RenderConfig
from .data import load_data_table
from .diagnostics import Diagnostic, DiagnosticReporter
from .inspection import M, NS, R, W
from .layout import LayoutPlanner
from .layout_table import (
    FORM_PHOTO_LABEL,
    parse_layout_table,
    parse_ruled_rows,
    parse_text_form,
    text_layout_kind,
)
from .math.latex import UnsupportedLatexError
from .math.normalize import normalize_equation
from .math.validation import (
    explicit_nary_limits_preserved,
    source_matrices_preserved,
    source_phantoms_preserved,
    source_tokens_preserved,
    validate_omml,
    visible_omml,
)
from .ooxml.bangla import LEGACY_BANGLA_FONT, decode_bijoy
from .ooxml.charts import C, CHART_REL, PACKAGE_REL
from .ooxml.fields import WordField, read_field_content, read_field_instructions
from .ooxml.text import INLINE_MATH_SEPARATOR, clean_xml_text
from .references import ReferenceRegistry
from .table_grid import iter_grid_rows, repeatable_header_rows, table_grid

BODY = "word/document.xml"
_HEADING = re.compile(r"(?:MD)?Heading[ ]?([1-6])", re.I)
_TEX_COMMAND = re.compile(r"\\([A-Za-z]+|.)")
_NATIVE_MATH = {
    "frac": "f",
    "dfrac": "f",
    "tfrac": "f",
    "genfrac": "f",
    "binom": "f",
    "dbinom": "f",
    "tbinom": "f",
    "sqrt": "rad",
}


def _sequence_fields(label: str, number, section_scoped: bool) -> tuple[tuple[str, ...], ...]:
    sequence = ("SEQ", label, r"\*", "ARABIC")
    if section_scoped and isinstance(number, str) and "." in number:
        reset = (r"\r", "1") if number.split(".", 1)[1] == "1" else ()
        return (("SEQ", "Section", r"\c"), sequence + reset + (r"\s", "1"))
    return (sequence,)


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


@dataclass(frozen=True, slots=True)
class _SectionStart:
    offset: int
    orientation: Literal["portrait", "landscape"]
    source: Node | None = None
    restoration: bool = False


def compare_document(
    document: Document, roots: dict[str, etree._Element], config: RenderConfig, package: bytes
) -> VerificationResult:
    expected: list[_Unit] = []
    findings: list[VerificationFinding] = []
    caption_counts: dict[str, int] = {}
    caption_section = 0
    section_initialized = False
    sections = [_SectionStart(0, config.page.orientation)]
    layout = LayoutPlanner(config)
    references = ReferenceRegistry.from_document(
        document,
        _plain_text,
        config.references.equation_number_format,
        config.references.caption_number_format,
        config.references.listing_numbering,
        image_captions_from_title=config.image_captions_from_title,
        mermaid_enabled=config.mermaid.enabled,
    )
    notes: dict[str, int] = {}
    note_kind = config.notes.style
    note_part = f"word/{note_kind}s.xml"
    expected_math: list[tuple[str, Node]] = []
    expected_charts: list[block.ChartBlock] = []

    def incomplete(reason: str, node: Node | None = None) -> None:
        findings.append(_finding("VERIFY304", reason, node))

    def start_section(
        orientation: Literal["portrait", "landscape"], node: Node, *, automatic: bool = False
    ) -> None:
        start = _SectionStart(len(expected), orientation, node)
        prior = sections[-1]
        if prior.offset == start.offset and (
            prior.restoration or (automatic and len(sections) == 1)
        ):
            sections[-1] = start
        else:
            sections.append(start)

    def expected_inlines(nodes, *, in_note: bool = False) -> tuple:
        tokens = []
        for node in nodes:
            if isinstance(node, inline.Text):
                tokens.append(clean_xml_text(node.text))
            elif isinstance(node, inline.InlineCode):
                tokens.append(clean_xml_text(node.code))
            elif isinstance(node, (inline.Strong, inline.Emphasis, inline.Strikethrough)):
                tokens.extend(expected_inlines(node.children, in_note=in_note))
            elif isinstance(node, inline.SoftBreak):
                tokens.append(" ")
            elif isinstance(node, inline.HardBreak):
                tokens.append(("break",))
            elif isinstance(node, inline.InlineMath):
                tokens.append(("math",))
                expected_math.append((node.source_text, node))
            elif isinstance(node, inline.Image):
                tokens.append(("image", clean_xml_text(node.alt)))
            elif isinstance(node, inline.Link):
                href = node.href
                content = _merge_text(
                    ("image", clean_xml_text(item.alt))
                    if isinstance(item, inline.Image)
                    else clean_xml_text(item)
                    for item in inline.link_content(node.children)
                )
                if href.startswith("#"):
                    target = references.get(href[1:])
                    if target is None:
                        incomplete("Unresolved internal hyperlink.", node)
                        tokens.extend(content)
                        continue
                    href = "#" + target.bookmark
                tokens.append(("link", href, content))
            elif isinstance(node, inline.FootnoteReference):
                if node.label in document.footnotes and not in_note:
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
                value = (
                    str(target.number) if target.number is not None else target.title or node.target
                )
                tokens.append(
                    ("ref", target.bookmark, r"\h", _merge_text((clean_xml_text(value),)))
                )
            else:
                incomplete(f"Inline {type(node).__name__} coverage is incomplete.", node)
        return _merge_text(tokens)

    def captioned(units: list[_Unit], label: str, text: str | None, node) -> None:
        if text is None:
            expected.extend(units)
            return
        target = references.get(node.identifier) if node.identifier else None
        fields: tuple[tuple[str, ...], ...] = ()
        initial_counter: tuple[_Unit, ...] = ()
        visible = clean_xml_text(text)
        if label != "Listing" or config.references.listing_numbering:
            count = caption_counts.get(label, 0) + 1
            caption_counts[label] = count
            number: int | str = count
            if config.references.caption_number_format == "section":
                initial_counter = initialize_section_counter(node)
                number = f"{max(1, caption_section)}.{count}"
            fields = _sequence_fields(
                label,
                number,
                config.references.caption_number_format == "section",
            )
            display = getattr(config.references, f"{label.lower()}_label")
            visible = display + " " + str(number) + (" — " + visible if text else "")
        caption = _Unit(
            "caption",
            (_merge_text((visible,)), target.bookmark if target else None, fields),
            node,
        )
        if getattr(config.references, f"{label.lower()}_caption_position") == "above":
            expected.extend((*initial_counter, caption, *units))
        else:
            expected.extend((*units, *initial_counter, caption))

    def initialize_section_counter(node: Node) -> tuple[_Unit, ...]:
        nonlocal section_initialized
        if section_initialized:
            return ()
        section_initialized = True
        return (_Unit("section counters", (("SEQ", "Section", r"\r", "1"),), node),)

    def blocks(nodes, level: int = 0) -> None:
        nonlocal caption_section, section_initialized
        for node in nodes:
            if isinstance(node, block.Heading):
                if node.level == 1:
                    caption_section += 1
                    if config.references.caption_number_format == "section":
                        caption_counts.clear()
                target = references.get(node.identifier) if node.identifier else None
                bookmark = target.bookmark if config.heading_bookmarks and target else None
                expected.append(
                    _Unit("heading", (node.level, bookmark, expected_inlines(node.children)), node)
                )
                if node.level == 1:
                    resets = []
                    if (
                        config.references.enabled
                        and config.references.equation_number_format == "section"
                    ):
                        resets.append("Equation")
                    if config.references.caption_number_format == "section":
                        resets.extend(("Figure", "Table", "Listing"))
                    if resets:
                        section_initialized = True
                        section_field = (
                            ("SEQ", "Section", r"\r", "1")
                            if caption_section == 1
                            else ("SEQ", "Section", r"\*", "ARABIC")
                        )
                        reset_fields = (section_field,) + tuple(
                            ("SEQ", label, r"\r", "0") for label in resets
                        )
                        expected.append(_Unit("section counters", reset_fields, node))
            elif isinstance(node, block.Paragraph):
                expected.append(_Unit("paragraph", expected_inlines(node.children), node))
            elif isinstance(node, (block.BulletList, block.OrderedList)):
                for item in node.items:
                    numbered = False
                    kind = "task" if item.task_checked is not None else "list"
                    marker = item.task_checked if kind == "task" else level
                    if not item.children or not isinstance(item.children[0], block.Paragraph):
                        expected.append(_Unit(kind, (marker, ()), item))
                        numbered = True
                    for child in item.children:
                        if isinstance(child, block.Paragraph) and not numbered:
                            expected.append(
                                _Unit(kind, (marker, expected_inlines(child.children)), child)
                            )
                            numbered = True
                        else:
                            blocks([child], level + 1)
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
                start_section(node.orientation or config.page.orientation, node)
            elif isinstance(node, block.DataTableBlock):
                blocks([load_data_table(node, config)], level)
            elif isinstance(node, block.Table):
                columns, placements = table_grid(node, config.limits.max_table_cells)
                rotate = (
                    sections[-1].orientation == "portrait"
                    and layout.landscape_reason(node, columns) is not None
                )
                if rotate:
                    start_section("landscape", node, automatic=True)
                repeat = repeatable_header_rows(node) if config.table.repeat_header else 0
                expected_rows = tuple(
                    (
                        index < repeat,
                        tuple(
                            (
                                entry.span,
                                entry.merge,
                                expected_inlines(entry.cell.children) if entry.cell else (),
                            )
                            for entry in cells
                        ),
                    )
                    for index, cells in enumerate(iter_grid_rows(columns, placements))
                )
                title = (
                    (node.caption or ("Table" if node.identifier else None))
                    if config.references.captions
                    else None
                )
                captioned(
                    [_Unit("table", (columns, expected_rows), node)] if columns else [],
                    "Table",
                    title,
                    node,
                )
                if rotate and config.table.restore_portrait_after_landscape:
                    sections.append(
                        _SectionStart(len(expected), "portrait", node, restoration=True)
                    )
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
                captioned([_Unit("paragraph", (token,), node)], "Figure", title, node)
            elif isinstance(node, block.ChartBlock) and config.charts.enabled:
                expected_charts.append(node)
                title = (
                    (node.caption or node.title or ("Chart" if node.identifier else None))
                    if config.references.captions
                    else None
                )
                captioned([_Unit("paragraph", (("chart",),), node)], "Figure", title, node)
            elif isinstance(node, block.MathBlock):
                expected_math.append((node.source_text, node))
                if (
                    node.identifier
                    and config.references.enabled
                    and config.references.equation_numbering
                ):
                    target = references.get(node.identifier)
                    if config.references.equation_number_format == "section":
                        expected.extend(initialize_section_counter(node))
                    fields = _sequence_fields(
                        "Equation",
                        target.number if target else None,
                        config.references.equation_number_format == "section",
                    )
                    expected.append(
                        _Unit(
                            "numbered equation", (target.bookmark if target else None, fields), node
                        )
                    )
                else:
                    expected.append(_Unit("paragraph", (("math",),), node))
                if node.caption:
                    text = _merge_text((clean_xml_text(node.caption),))
                    expected.append(_Unit("caption", (text, None, ()), node))
            elif isinstance(node, block.CodeBlock):
                title = (
                    (node.caption or ("Code listing" if node.identifier else None))
                    if config.references.captions
                    else None
                )
                layout_units = _expected_text_layout(node, config.limits.max_table_cells)
                if layout_units is not None:
                    captioned(layout_units, "Listing", title, node)
                    continue
                language = (node.language or "text").strip() or "text"
                if language.lower() == "mermaid" and config.mermaid.enabled:
                    incomplete("Rendered Mermaid diagram coverage is incomplete.", node)
                    continue
                lines = node.code.splitlines() or [""]
                numbers = (
                    config.code.line_numbers if node.line_numbers is None else node.line_numbers
                )
                label = (
                    config.code.show_language_label
                    if node.show_language_label is None
                    else node.show_language_label
                )
                units = []
                if label and language.lower() not in {"text", "plain", "plaintext"}:
                    units.append(_Unit("paragraph", (clean_xml_text(language),), node))
                for index, line in enumerate(lines, 1):
                    line_number = f"{index:>{len(str(len(lines)))}}  " if numbers else ""
                    units.append(
                        _Unit("paragraph", _merge_text((line_number + clean_xml_text(line),)), node)
                    )
                captioned(units, "Listing", title, node)
            elif isinstance(node, block.PageBreak):
                expected.append(_Unit("paragraph", (("page-break",),), node))
            else:
                incomplete(f"Block {type(node).__name__} coverage is incomplete.", node)

    blocks(document.children)
    if sections[-1].restoration and sections[-1].offset == len(expected):
        sections.pop()
    if (
        config.extensions
        or config.plugins.names
        or config.template
        or config.title_page.enabled
        or config.abstract.text
        or config.abstract.keywords
        or config.toc.enabled
    ):
        incomplete(
            "Generated front matter, templates, and extensions have limited verification coverage."
        )
    body_math = expected_math
    expected_notes: dict[str, tuple] = {}
    note_math: dict[str, list[tuple[str, Node]]] = {}
    note_sources: dict[str, Node] = {}
    for label, number in list(notes.items()):
        ident = str(number)
        expected_math = []
        content = document.footnotes[label]
        if content:
            note_sources[ident] = content[0]
        expected_notes[ident] = expected_inlines(content, in_note=True)
        note_math[ident] = expected_math
    actual_notes = {}
    if note_part in roots:
        note_links = _hyperlink_targets(roots, note_part)
        for item in roots[note_part]:
            ident = item.get(f"{{{W}}}id")
            if item.tag == f"{{{W}}}{note_kind}" and ident and not item.get(f"{{{W}}}type"):
                tokens = _read_inlines(item, note_links)
                if tokens and isinstance(tokens[0], str):
                    tokens = _merge_text((tokens[0].removeprefix(" "), *tokens[1:]))
                actual_notes[ident] = tokens
                if ident in note_math:
                    findings.extend(_equation_findings(note_math[ident], item, note_part))
    for ident in sorted(set(expected_notes) | set(actual_notes)):
        if expected_notes.get(ident) != actual_notes.get(ident):
            findings.append(
                _finding(
                    "VERIFY303",
                    f"Changed or missing {note_kind} {ident}.",
                    note_sources.get(ident),
                    part=note_part,
                )
            )
    main = roots[BODY].find("w:body", NS)
    if main is not None:
        findings.extend(_equation_findings(body_math, main, BODY))
    actual, section_ends = _read_body(roots)
    findings.extend(_chart_findings(roots, expected_charts, config, package))
    for part in (BODY, note_part):
        if part in roots:
            findings.extend(_image_findings(roots, part))
    expected_keys = [unit.key for unit in expected]
    actual_keys = [unit.key for unit in actual]
    if expected_keys == actual_keys:
        if not any(finding.code == "VERIFY304" for finding in findings):
            changed = _section_finding(sections, section_ends, len(expected))
            if changed is not None:
                findings.append(changed)
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
                f"Unit {first + 1}. {_replacement_message(wanted, found)}",
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
                    _replacement_message(expected[start:end], actual[actual_start:actual_end]),
                    expected[start].source,
                )
            )
    return VerificationResult(len(expected), tuple(findings))


def _equation_findings(
    expected: list[tuple[str, Node]], container: etree._Element, part: str
) -> Iterator[VerificationFinding]:
    if not expected:
        return
    rendered = container.findall(f".//{{{M}}}oMath")
    if len(rendered) != len(expected):
        # The ordered content check reports missing or added math objects.
        return
    for (latex, node), equation in zip(expected, rendered, strict=True):
        try:
            normalized = normalize_equation(latex).text
            validate_omml(equation)
        except UnsupportedLatexError as exc:
            yield _finding("VERIFY303", str(exc), node, part=part)
        else:
            required = {
                _NATIVE_MATH[command]
                for command in _TEX_COMMAND.findall(normalized)
                if command in _NATIVE_MATH
            }
            if not source_tokens_preserved(normalized, equation):
                yield _finding(
                    "VERIFY303",
                    "Native equation lost a source identifier or numeral.",
                    node,
                    part=part,
                )
            elif not source_matrices_preserved(normalized, equation):
                yield _finding(
                    "VERIFY303",
                    "Native equation lost an alignment array or matrix layout.",
                    node,
                    part=part,
                )
            elif not explicit_nary_limits_preserved(normalized, equation):
                yield _finding(
                    "VERIFY303",
                    "Native equation changed a large operator's explicit limit placement.",
                    node,
                    part=part,
                )
            elif not source_phantoms_preserved(normalized, equation):
                yield _finding(
                    "VERIFY303",
                    "Native equation changed phantom or smash spacing.",
                    node,
                    part=part,
                )
            elif required and not required.issubset(
                etree.QName(element).localname for element in visible_omml(equation)
            ):
                yield _finding(
                    "VERIFY303",
                    "Native equation lost a fraction or radical structure.",
                    node,
                    part=part,
                )


def _finding(
    code: str, message: str, node: Node | None = None, *, part: str = BODY
) -> VerificationFinding:
    source = node.source if node else None
    return VerificationFinding(
        code,
        message,
        part,
        source_file=source.file if source else None,
        line=source.line if source else None,
    )


def _describe(units: list[_Unit]) -> str:
    if not units:
        return "end of document"
    first = units[0]
    extra = f" and {len(units) - 1} more" if len(units) > 1 else ""
    return f"{first.kind} {repr(first.content)[:150]}{extra}"


def _replacement_message(expected: list[_Unit], actual: list[_Unit]) -> str:
    if len(expected) == len(actual) == 1 and expected[0].kind == actual[0].kind:
        kind = expected[0].kind
        field_index = {"caption": 2, "numbered equation": 1}.get(kind)
        if field_index is not None:
            wanted, found = expected[0].content[field_index], actual[0].content[field_index]
        elif kind == "section counters":
            wanted, found = expected[0].content, actual[0].content
        else:
            wanted = found = ()
        for before, after in zip_longest(wanted, found):
            if before != after:
                before_text = " ".join(before)[:150] if before else "no field"
                after_text = " ".join(after)[:150] if after else "no field"
                return (
                    f"Word {kind} instructions changed. Expected {before_text}, found {after_text}."
                )
    if len(expected) == len(actual) == 1 and expected[0].kind == actual[0].kind == "table":
        columns, rows = expected[0].content
        found_columns, found_rows = actual[0].content
        if columns != found_columns:
            return f"Expected {columns} table columns, found {found_columns}."
        if len(rows) != len(found_rows):
            return f"Expected {len(rows)} table rows, found {len(found_rows)}."
        for index, (row, found_row) in enumerate(zip(rows, found_rows, strict=True), 1):
            header, cells = row
            found_header, found_cells = found_row
            if header != found_header:
                return f"Table row {index} repeat-header setting changed."
            if len(cells) != len(found_cells):
                return f"Table row {index} has {len(found_cells)} cells, expected {len(cells)}."
            column = 1
            for cell, found_cell in zip(cells, found_cells, strict=True):
                if cell[:2] != found_cell[:2]:
                    return f"Table row {index}, column {column} span or merge changed."
                if cell[2] != found_cell[2]:
                    wanted_text = repr(cell[2])[:150]
                    found_text = repr(found_cell[2])[:150]
                    return (
                        f"Table row {index}, column {column} content changed. "
                        f"Expected {wanted_text}, found {found_text}."
                    )
                column += cell[0]
    return f"Expected {_describe(expected)}, found {_describe(actual)}."


def _chart_findings(
    roots: dict[str, etree._Element],
    expected: list[block.ChartBlock],
    config: RenderConfig,
    package: bytes,
) -> list[VerificationFinding]:
    charts = roots[BODY].xpath(".//c:chart", namespaces={"c": C})
    chart_targets = {
        relation.get("Id"): relation.get("Target", "")
        for relation in _part_relationships(roots, BODY)
        if relation.get("Type") == CHART_REL
    }
    findings = []
    for index, chart in enumerate(charts):
        rid = chart.get(f"{{{R}}}id")
        target = chart_targets.get(rid, "")
        target = target.lstrip("/") if target.startswith("/") else "word/" + target
        chart_root = roots.get(target)
        if chart_root is None or chart_root.find(f".//{{{C}}}plotArea//{{{C}}}ser") is None:
            findings.append(
                VerificationFinding("VERIFY303", "Missing native ChartML plot or series.", target)
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
                relation.get("Id") == external_id
                and relation.get("Type") == PACKAGE_REL
                and (relation.get("TargetMode") or "").lower() != "external"
                for relation in chart_rels
            )
        ):
            findings.append(
                VerificationFinding("VERIFY303", "Missing chart workbook binding.", target)
            )
            continue
        if index >= len(expected):
            continue
        node = expected[index]
        entry = prepare_chart_entry(node, config, DiagnosticReporter())
        issue = chart_data_issue(chart_root, entry)
        if issue:
            findings.append(_finding("VERIFY303", issue, node, part=target))
        relation = next(relation for relation in chart_rels if relation.get("Id") == external_id)
        workbook_target = relation.get("Target", "")
        workbook_part = posixpath.normpath(
            workbook_target.lstrip("/")
            if workbook_target.startswith("/")
            else str(path.parent / workbook_target)
        )
        with ZipFile(BytesIO(package)) as archive:
            if workbook_part not in archive.namelist():
                findings.append(
                    _finding("VERIFY303", "Chart workbook is missing.", node, part=workbook_part)
                )
                continue
            workbook_blob = archive.read(workbook_part)
        issue = workbook_data_issue(workbook_blob, entry, config.validation)
        if issue:
            findings.append(_finding("VERIFY303", issue, node, part=workbook_part))
    return findings


def _part_relationships(roots: dict[str, etree._Element], part: str) -> Iterator[etree._Element]:
    path = PurePosixPath(part)
    relationships = roots.get(str(path.parent / "_rels" / (path.name + ".rels")))
    if relationships is not None:
        yield from relationships


def _hyperlink_targets(roots: dict[str, etree._Element], part: str) -> dict:
    return {
        rel.get("Id"): rel.get("Target")
        for rel in _part_relationships(roots, part)
        if rel.get("Type") == RELATIONSHIP_TYPE.HYPERLINK
        and (rel.get("TargetMode") or "").lower() == "external"
    }


def _image_findings(roots: dict[str, etree._Element], part: str) -> Iterator[VerificationFinding]:
    embedded_ids = {
        relation.get("Id")
        for relation in _part_relationships(roots, part)
        if relation.get("Id")
        and relation.get("Type") == RELATIONSHIP_TYPE.IMAGE
        and relation.get("Target")
        and (relation.get("TargetMode") or "").lower() != "external"
    }
    for picture in roots[part].iter(qn("pic:pic")):
        blip = picture.find(f"./{qn('pic:blipFill')}/{qn('a:blip')}")
        if blip is None or blip.get(qn("r:embed")) not in embedded_ids:
            yield VerificationFinding(
                "VERIFY303", "Picture is missing an embedded image binding.", part
            )


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


def _layout_cell_tokens(text: str) -> tuple:
    return _merge_text(
        ("break",) if part in {"\n", "\r"} else part
        for part in re.split(r"([\r\n])", clean_xml_text(text))
    )


def _plain_grid_content(rows: list[list[str]]) -> tuple:
    return len(rows[0]), tuple(
        (False, tuple((1, None, _layout_cell_tokens(cell)) for cell in row)) for row in rows
    )


def _expected_text_layout(node: block.CodeBlock, cell_limit: int) -> list[_Unit] | None:
    kind = text_layout_kind(node)
    if kind is None:
        return None
    if kind == "structured":
        rows, weights, placements = parse_layout_table(node, cell_limit)
        columns = len(weights)
        cells = tuple(
            (
                False,
                tuple(
                    (
                        entry.span,
                        entry.merge,
                        _layout_cell_tokens(row[entry.column]) if entry.cell is not None else (),
                    )
                    for entry in grid
                ),
            )
            for row, grid in zip(rows, iter_grid_rows(columns, placements), strict=True)
        )
        return [_Unit("table", (columns, cells), node)]
    if kind == "ruled":
        return [_Unit("table", _plain_grid_content(parse_ruled_rows(node.code)), node)]

    fields, addresses, signatures = parse_text_form(node.code)
    field_tokens: list = []
    for index, field in enumerate(fields):
        if index:
            field_tokens.append(("paragraph-break",))
        field_tokens.extend(_layout_cell_tokens(field))
    photo = ("table", *_plain_grid_content([[FORM_PHOTO_LABEL]]))
    form = (2, ((False, ((1, None, tuple(field_tokens)), (1, None, (photo,)))),))
    units = [_Unit("table", form, node)]
    if addresses:
        units.append(_Unit("table", _plain_grid_content(addresses), node))
    units.extend(
        _Unit("paragraph", _layout_cell_tokens(signature), node) for signature in signatures
    )
    return units


def _plain_text(nodes) -> str:
    return clean_xml_text(
        "".join(
            item.alt if isinstance(item, inline.Image) else item
            for item in inline.link_content(nodes)
        )
    )


def _section_finding(
    expected: list[_SectionStart], actual: list[tuple[int, str, str]], unit_count: int
) -> VerificationFinding | None:
    for index, (section, found) in enumerate(zip_longest(expected, actual)):
        if section is None or found is None:
            return _finding(
                "VERIFY303",
                f"Expected {len(expected)} Word sections, found {len(actual)}.",
                section.source if section else None,
            )
        following = expected[index + 1] if index + 1 < len(expected) else None
        end = following.offset if following else unit_count
        actual_end, orientation, break_type = found
        if actual_end != end:
            detail = f"expected the end after body unit {end}, found it after {actual_end}"
            source = following.source if following else section.source
        elif orientation != section.orientation:
            detail = f"expected {section.orientation} orientation, found {orientation}"
            source = section.source
        elif index and break_type != "nextPage":
            detail = f"expected a next-page break, found {break_type}"
            source = section.source
        else:
            continue
        return _finding("VERIFY303", f"Word section {index + 1}: {detail}.", source)
    return None


def _section_end(offset: int, properties: etree._Element) -> tuple[int, str, str]:
    page = properties.find("w:pgSz", NS)
    section_type = properties.find("w:type", NS)
    break_type = (
        section_type.get(f"{{{W}}}val", "nextPage") if section_type is not None else "nextPage"
    )
    if page is None:
        return offset, "missing page size", break_type
    orientation = page.get(f"{{{W}}}orient", "portrait")
    try:
        width, height = int(page.get(f"{{{W}}}w", "")), int(page.get(f"{{{W}}}h", ""))
    except ValueError:
        return offset, "invalid page dimensions", break_type
    if min(width, height) <= 0 or orientation != ("landscape" if width > height else "portrait"):
        return offset, "orientation inconsistent with page dimensions", break_type
    return offset, orientation, break_type


def _read_body(
    roots: dict[str, etree._Element],
) -> tuple[list[_Unit], list[tuple[int, str, str]]]:
    links = _hyperlink_targets(roots, BODY)
    body = roots[BODY].find(f"{{{W}}}body")
    if body is None:
        return [], []
    starts = {}
    bookmarks = {}
    for marker in body.iter(qn("w:bookmarkStart"), qn("w:bookmarkEnd")):
        ident = marker.get(qn("w:id"))
        if ident is None:
            continue
        if marker.tag == qn("w:bookmarkStart"):
            starts[ident] = marker
        elif (start := starts.pop(ident, None)) is not None:
            bookmarks[start] = start.get(qn("w:name"))
    result: list[_Unit] = []
    section_ends = []
    pending = None
    for child in body:
        if pending is not None:
            section_ends.append(_section_end(len(result), pending))
            pending = None
        if child.tag == f"{{{W}}}sectPr":
            section_ends.append(_section_end(len(result), child))
        if child.tag == f"{{{W}}}tbl":
            fields = tuple(read_field_instructions(child))
            if any(words[:2] == ("SEQ", "Equation") for words in fields):
                mark = child.find(".//w:bookmarkStart", NS)
                name = bookmarks.get(mark)
                equations = child.xpath(".//m:oMath", namespaces=NS)
                result.append(
                    _Unit(
                        "numbered equation",
                        (name, fields) if len(equations) == 1 else (name, fields, len(equations)),
                    )
                )
                continue
            result.append(_Unit("table", _read_table_content(child, links)))
        elif child.tag == f"{{{W}}}p":
            pending = child.find("w:pPr/w:sectPr", NS)
            style = child.find("w:pPr/w:pStyle", NS)
            name = style.get(f"{{{W}}}val", "") if style is not None else ""
            hidden_fields = child.find("w:r/w:rPr/w:vanish", NS) is not None and (
                child.find("w:r/w:instrText", NS) is not None
                or child.find("w:fldSimple", NS) is not None
            )
            instructions: list[tuple[str, ...]] | None = (
                [] if name == "MDCaption" or hidden_fields else None
            )
            tokens = _read_inlines(
                child, links, fields=instructions, include_field_values=name == "MDCaption"
            )
            before, after = child.getprevious(), child.getnext()
            if (
                len(child) == 0
                and before is not None
                and before.tag == f"{{{W}}}tbl"
                and after is not None
                and after.tag == f"{{{W}}}sectPr"
            ):
                # Word adds an empty final paragraph when saving a document ending in a table.
                continue
            if (
                not tokens
                and before is not None
                and after is not None
                and before.tag == after.tag == f"{{{W}}}tbl"
            ):
                spacing = child.find("w:pPr/w:spacing", NS)
                if spacing is not None and spacing.get(f"{{{W}}}line") == "20":
                    continue
            heading = _HEADING.fullmatch(name)
            level = child.find("w:pPr/w:numPr/w:ilvl", NS)
            checkbox = child.find(".//w14:checked", NS)
            if heading:
                marker = child.find(f"{{{W}}}bookmarkStart")
                bookmark = bookmarks.get(marker)
                result.append(_Unit("heading", (int(heading[1]), bookmark, tokens)))
            elif name == "MDCaption":
                mark = child.find("w:bookmarkStart", NS)
                result.append(
                    _Unit("caption", (tokens, bookmarks.get(mark), tuple(instructions or ())))
                )
            elif hidden_fields:
                if instructions and any(words[:1] == ("SEQ",) for words in instructions):
                    result.append(_Unit("section counters", tuple(instructions)))
            elif checkbox is not None:
                if tokens and isinstance(tokens[0], str):
                    tokens = (tokens[0].removeprefix(" "), *tokens[1:])
                result.append(_Unit("task", (checkbox.get(f"{{{NS['w14']}}}val") == "1", tokens)))
            elif level is not None:
                result.append(_Unit("list", (int(level.get(f"{{{W}}}val", "0")), tokens)))
            elif tokens or pending is None:
                result.append(_Unit("paragraph", tokens))
    return result, section_ends


def _word_span(element) -> int:
    if element is None:
        return 1
    try:
        return int(element.get(f"{{{W}}}val", "1"))
    except ValueError:
        return 0


def _read_table_content(table: etree._Element, links: dict) -> tuple:
    rows = []
    for row in table.findall("w:tr", NS):
        cells = []
        for cell in row.findall("w:tc", NS):
            span = cell.find("w:tcPr/w:gridSpan", NS)
            merge = cell.find("w:tcPr/w:vMerge", NS)
            cells.append(
                (
                    _word_span(span),
                    merge.get(f"{{{W}}}val", "continue") if merge is not None else None,
                    _read_cell_content(cell, links),
                )
            )
        header = row.find("w:trPr/w:tblHeader", NS)
        repeated = header is not None and header.get(f"{{{W}}}val", "1") not in {
            "0",
            "false",
            "off",
        }
        rows.append((repeated, tuple(cells)))
    columns = len(table.findall("w:tblGrid/w:gridCol", NS))
    return columns, tuple(rows)


def _read_cell_content(cell: etree._Element, links: dict) -> tuple:
    tokens = []
    previous_paragraph = False
    for child in cell:
        if child.tag == f"{{{W}}}p":
            if previous_paragraph:
                tokens.append(("paragraph-break",))
            tokens.extend(_read_inlines(child, links))
            previous_paragraph = True
        elif child.tag == f"{{{W}}}tbl":
            tokens.append(("table", *_read_table_content(child, links)))
            previous_paragraph = False
    return _merge_text(tokens)


def _read_inlines(
    parent: etree._Element,
    links: dict,
    *,
    fields: list[tuple[str, ...]] | None = None,
    include_field_values: bool = False,
) -> tuple:
    return _merge_text(
        _read_inline_content(read_field_content(parent), links, fields, include_field_values)
    )


def _read_inline_content(items, links, fields=None, include_field_values=False) -> list:
    tokens: list = []
    for node in items:
        if isinstance(node, WordField):
            if fields is not None:
                fields.append(node.words)
                if include_field_values:
                    tokens.extend(_read_inline_content(node.result, links))
            elif node.words[:1] == ("REF",):
                tokens.append(
                    ("ref", *node.words[1:], _merge_text(_read_inline_content(node.result, links)))
                )
            else:
                tokens.extend(_read_inline_content(node.result, links))
        elif node.tag == f"{{{W}}}t":
            run = node.getparent()
            font = run.find("w:rPr/w:rFonts", NS) if run is not None else None
            text = node.text or ""
            if (
                text == INLINE_MATH_SEPARATOR
                and run is not None
                and run.find("w:rPr/w:noProof", NS) is not None
            ):
                before, after = run.getprevious(), run.getnext()
                if (
                    before is not None
                    and after is not None
                    and before.tag == after.tag == f"{{{M}}}oMath"
                ):
                    continue
            if (
                font is not None
                and font.get(f"{{{W}}}ascii", "").casefold() == LEGACY_BANGLA_FONT.casefold()
            ):
                text = decode_bijoy(text)
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
            tokens.append(("link", href, _read_inlines(node, links)))
        elif node.tag == f"{{{W}}}drawing":
            if node.find(f".//{{{C}}}chart") is not None:
                tokens.append(("chart",))
            else:
                prop = node.find(".//wp:docPr", NS)
                tokens.append(("image", prop.get("descr", "") if prop is not None else ""))
        elif node.tag in {f"{{{W}}}footnoteReference", f"{{{W}}}endnoteReference"}:
            kind = etree.QName(node).localname.removesuffix("Reference")
            tokens.append(("note", kind, node.get(f"{{{W}}}id")))
        elif node.tag in {f"{{{W}}}p", f"{{{M}}}oMathPara"}:
            tokens.extend(
                _read_inlines(node, links, fields=fields, include_field_values=include_field_values)
            )
    return tokens
