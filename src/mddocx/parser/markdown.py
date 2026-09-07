from __future__ import annotations

from pathlib import Path
import re
from markdown_it import MarkdownIt
from markdown_it.token import Token

from mddocx.ast.base import Document, SourcePosition
from mddocx.ast.block import (
    BlockQuote, BulletList, CodeBlock, Heading, HorizontalRule, ImageBlock, ListItem,
    MathBlock, OrderedList, PageBreak, Paragraph, SectionBreak, Table, TableCell, TableRow, ChartBlock, DataTableBlock, BibliographyBlock, DefinitionList, DefinitionItem, Callout,
)
from mddocx.ast.inline import (
    Emphasis, HardBreak, Image, InlineCode, InlineMath, Link, SoftBreak, Strikethrough,
    Strong, Text, FootnoteReference, CrossReference, Citation, Comment,
)
from .compatibility import (
    extract_footnote_definitions,
    normalize_math_syntax, normalize_bibliography_directives, normalize_definition_lists, normalize_callout_containers,
    normalize_simple_tables,
    protect_escaped_footnote_references,
    split_footnote_references,
    split_text_math, split_comment_markup,
)
from .frontmatter import split_front_matter
from mddocx.attributes import parse_attribute_list, parse_line_spec
from mddocx.extensions.base import call_configure_markdown, parse_custom_block, parse_custom_inline
from mddocx.diagnostics import Diagnostic, MddocxError
from mddocx.config import MetadataConfig
from mddocx.metadata import MetadataSanitizationReport, sanitize_markdown_metadata


class MarkdownParser:
    def __init__(self, extensions: tuple[object, ...] = (), metadata_config: MetadataConfig | None = None) -> None:
        self.extensions = extensions
        self.metadata_config = metadata_config or MetadataConfig()
        self.last_metadata_report = MetadataSanitizationReport(policy=self.metadata_config.ai_export)
        self.md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
        call_configure_markdown(self.extensions, self.md)
        self.source_file: str | None = None

    def parse_file(self, path: str | Path) -> Document:
        path = Path(path)
        return self.parse(path.read_text(encoding="utf-8"), source_file=str(path))

    def parse(self, markdown: str, source_file: str | None = None, *, base_line_offset: int = 0, sanitize_metadata: bool = True) -> Document:
        self.source_file = source_file
        if sanitize_metadata:
            sanitized = sanitize_markdown_metadata(markdown, self.metadata_config)
            markdown = sanitized.markdown
            self.last_metadata_report = sanitized.report
        else:
            self.last_metadata_report = MetadataSanitizationReport(policy=self.metadata_config.ai_export)
        metadata, body, line_offset = split_front_matter(markdown)
        body, footnote_sources = extract_footnote_definitions(body)
        body = protect_escaped_footnote_references(body)
        normalized = normalize_math_syntax(normalize_simple_tables(normalize_bibliography_directives(normalize_definition_lists(normalize_callout_containers(body)))))
        tokens = self.md.parse(normalized)
        self._line_offset = line_offset + base_line_offset
        children, _ = self._parse_blocks(tokens, 0, None)
        children = self._postprocess_blocks(children)
        footnotes: dict[str, list] = {}
        for label, note_source in footnote_sources.items():
            inline_tokens = self.md.parseInline(protect_escaped_footnote_references(note_source))
            inline = inline_tokens[0] if inline_tokens else None
            footnotes[label] = self._inline(inline.children or []) if inline is not None else []
        return Document(
            children=children,
            metadata=metadata,
            footnotes=footnotes,
            source=SourcePosition(file=source_file, line=1, column=1),
        )

    def _pos(self, token: Token) -> SourcePosition:
        line = token.map[0] + 1 + getattr(self, "_line_offset", 0) if token.map else None
        return SourcePosition(file=self.source_file, line=line, column=1 if line else None)

    def _parse_blocks(self, tokens: list[Token], i: int, stop: str | None) -> tuple[list, int]:
        nodes = []
        while i < len(tokens):
            t = tokens[i]
            if stop and t.type == stop:
                return nodes, i + 1
            custom = parse_custom_block(self.extensions, self, tokens, i)
            if custom is not None:
                custom_node, i = custom
                if custom_node is not None:
                    if isinstance(custom_node, list):
                        nodes.extend(custom_node)
                    else:
                        nodes.append(custom_node)
                continue
            if t.type == "heading_open":
                level = int(t.tag[1])
                inline = tokens[i + 1]
                heading_children = self._inline(inline.children or [])
                identifier, _attrs = self._extract_trailing_attrs(heading_children)
                nodes.append(Heading(level=level, children=heading_children, identifier=identifier, source=self._pos(t)))
                i += 3
            elif t.type == "paragraph_open":
                inline = tokens[i + 1]
                content = self._inline(inline.children or [])
                # Promote a standalone image (optionally followed by an attribute list) to a block node.
                if content and isinstance(content[0], Image) and all(isinstance(x, (Image, Text)) for x in content):
                    im = content[0]
                    identifier, attrs = self._extract_trailing_attrs(content[1:])
                    leftover = "".join(x.text for x in content[1:] if isinstance(x, Text)).strip()
                    if not leftover:
                        width = attrs.get("width")
                        width_percent = float(width[:-1]) if width and width.endswith("%") and width[:-1].replace(".", "", 1).isdigit() else None
                        nodes.append(ImageBlock(src=im.src, alt=im.alt, title=im.title, identifier=identifier, caption=attrs.get("caption"), width_percent=width_percent, align=attrs.get("align"), decorative=attrs.get("decorative", "false").lower() in {"1","true","yes"}, source=self._pos(t)))
                    else:
                        nodes.append(Paragraph(children=content, source=self._pos(t)))
                else:
                    nodes.append(Paragraph(children=content, source=self._pos(t)))
                i += 3
            elif t.type in {"fence", "code_block"}:
                info = (t.info or "").strip()
                if info == "mddocx-math":
                    nodes.append(MathBlock(source_text=t.content.strip(), source=self._pos(t)))
                elif info == "mddocx-bibliography":
                    nodes.append(BibliographyBlock(source=self._pos(t)))
                elif info == "mddocx-definition":
                    items = []
                    for line in t.content.splitlines():
                        if "\t" not in line:
                            continue
                        term, definition = line.split("\t", 1)
                        term_tokens = self.md.parseInline(term)
                        def_tokens = self.md.parseInline(definition)
                        term_nodes = self._inline(term_tokens[0].children or []) if term_tokens else [Text(text=term)]
                        def_nodes = self._inline(def_tokens[0].children or []) if def_tokens else [Text(text=definition)]
                        items.append(DefinitionItem(term=term_nodes, definition=def_nodes, source=self._pos(t)))
                    nodes.append(DefinitionList(items=items, source=self._pos(t)))
                else:
                    language, identifier, attrs = self._parse_fence_info(info)
                    if (language or "").lower() in {"chart", "mddocx-chart"}:
                        spec = self._parse_yaml_mapping(t.content, "chart", t)
                        series = spec.get("series") or []
                        if isinstance(series, dict):
                            series = [{"name": str(k), "values": v} for k, v in series.items()]
                        if not isinstance(series, list):
                            raise MddocxError(Diagnostic("error", "PARSE351", "Chart 'series' must be a list or mapping.", self.source_file, getattr(self._pos(t), "line", None)))
                        raw_fields = spec.get("series_fields") or spec.get("values") or []
                        if isinstance(raw_fields, str):
                            raw_fields = [raw_fields]
                        categories = spec.get("categories") or []
                        if not isinstance(categories, list):
                            categories = []
                        x_axis = spec.get("x_axis") if isinstance(spec.get("x_axis"), dict) else {}
                        y_axis = spec.get("y_axis") if isinstance(spec.get("y_axis"), dict) else {}
                        secondary_axis = spec.get("secondary_axis") if isinstance(spec.get("secondary_axis"), dict) else {}
                        raw_secondary = spec.get("secondary_series") or []
                        if isinstance(raw_secondary, str):
                            raw_secondary = [raw_secondary]
                        legend = spec.get("legend", "right")
                        if isinstance(legend, bool):
                            legend = "right" if legend else "none"
                        nodes.append(ChartBlock(
                            chart_type=str(spec.get("type") or "column"),
                            title=str(spec.get("title") or ""),
                            categories=list(categories),
                            series=list(series),
                            source_path=str(spec.get("source")) if spec.get("source") else None,
                            category_field=str(spec.get("category") or spec.get("x")) if (spec.get("category") or spec.get("x")) else None,
                            series_fields=tuple(str(v) for v in raw_fields),
                            identifier=identifier or (str(spec.get("id")) if spec.get("id") else None),
                            caption=attrs.get("caption") or (str(spec.get("caption")) if spec.get("caption") else None),
                            width_mm=float(spec["width_mm"]) if spec.get("width_mm") is not None else None,
                            height_mm=float(spec["height_mm"]) if spec.get("height_mm") is not None else None,
                            x_axis_title=str(x_axis.get("title")) if x_axis.get("title") is not None else None,
                            y_axis_title=str(y_axis.get("title")) if y_axis.get("title") is not None else None,
                            x_min=float(x_axis["min"]) if x_axis.get("min") is not None else None,
                            x_max=float(x_axis["max"]) if x_axis.get("max") is not None else None,
                            y_min=float(y_axis["min"]) if y_axis.get("min") is not None else None,
                            y_max=float(y_axis["max"]) if y_axis.get("max") is not None else None,
                            x_number_format=str(x_axis.get("number_format")) if x_axis.get("number_format") is not None else None,
                            y_number_format=str(y_axis.get("number_format")) if y_axis.get("number_format") is not None else None,
                            legend_position=str(legend).lower(),
                            data_labels=bool(spec.get("data_labels", False)),
                            show_gridlines=bool(spec.get("gridlines", True)),
                            secondary_series=tuple(str(v) for v in raw_secondary),
                            secondary_axis_title=str(secondary_axis.get("title")) if secondary_axis.get("title") is not None else None,
                            secondary_min=float(secondary_axis["min"]) if secondary_axis.get("min") is not None else None,
                            secondary_max=float(secondary_axis["max"]) if secondary_axis.get("max") is not None else None,
                            secondary_number_format=str(secondary_axis.get("number_format")) if secondary_axis.get("number_format") is not None else None,
                            style=int(spec["style"]) if spec.get("style") is not None else None,
                            source=self._pos(t),
                        ))
                    elif (language or "").lower() in {"data-table", "datatable", "mddocx-data-table"}:
                        spec = self._parse_yaml_mapping(t.content, "data table", t)
                        raw_columns = spec.get("columns") or []
                        if isinstance(raw_columns, str):
                            raw_columns = [raw_columns]
                        if not spec.get("source"):
                            raise MddocxError(Diagnostic("error", "PARSE352", "Data table requires a source path.", self.source_file, getattr(self._pos(t), "line", None)))
                        nodes.append(DataTableBlock(
                            source_path=str(spec["source"]),
                            columns=tuple(str(v) for v in raw_columns),
                            identifier=identifier or (str(spec.get("id")) if spec.get("id") else None),
                            caption=attrs.get("caption") or (str(spec.get("caption")) if spec.get("caption") else None),
                            source=self._pos(t),
                        ))
                    else:
                        nodes.append(CodeBlock(
                        code=t.content.rstrip("\n"), language=language, identifier=identifier,
                        caption=attrs.get("caption"),
                        line_numbers=(attrs.get("linenos", attrs.get("line_numbers", "")).lower() in {"1","true","yes","on"}) if ("linenos" in attrs or "line_numbers" in attrs) else None,
                        highlight_lines=parse_line_spec(attrs.get("highlight") or attrs.get("hl_lines")),
                        show_language_label=(attrs.get("label", "").lower() in {"1","true","yes","on"}) if "label" in attrs else None,
                        source=self._pos(t),
                    ))
                i += 1
            elif t.type == "blockquote_open":
                inner, i = self._parse_blocks(tokens, i + 1, "blockquote_close")
                callout = self._callout_from_quote(inner, self._pos(t))
                nodes.append(callout if callout is not None else BlockQuote(children=inner, source=self._pos(t)))
            elif t.type in {"bullet_list_open", "ordered_list_open"}:
                node, i = self._parse_list(tokens, i)
                nodes.append(node)
            elif t.type == "table_open":
                node, i = self._parse_table(tokens, i)
                nodes.append(node)
            elif t.type == "hr":
                nodes.append(HorizontalRule(source=self._pos(t)))
                i += 1
            elif t.type in {"html_block", "html_inline"}:
                directive = t.content.strip().lower()
                if directive == "<!-- pagebreak -->":
                    nodes.append(PageBreak(source=self._pos(t)))
                elif directive == "<!-- sectionbreak -->":
                    nodes.append(SectionBreak(source=self._pos(t)))
                i += 1
            else:
                i += 1
        return nodes, i

    def _parse_yaml_mapping(self, text: str, label: str, token: Token) -> dict:
        try:
            import yaml  # type: ignore
            value = yaml.safe_load(text) if text.strip() else {}
        except Exception as exc:
            raise MddocxError(Diagnostic("error", "PARSE350", f"Unable to parse {label} YAML: {type(exc).__name__}", self.source_file, getattr(self._pos(token), "line", None))) from exc
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise MddocxError(Diagnostic("error", "PARSE350", f"{label.title()} block must contain a YAML mapping.", self.source_file, getattr(self._pos(token), "line", None)))
        return value

    @staticmethod
    def _callout_from_quote(children: list, source) -> Callout | None:
        if not children or not isinstance(children[0], Paragraph):
            return None
        paragraph = children[0]
        if not paragraph.children or not isinstance(paragraph.children[0], Text):
            return None
        first = paragraph.children[0]
        match = re.match(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|EXAMPLE)\](?:[ \t]+(.*))?$", first.text.strip(), re.I)
        if not match:
            return None
        kind = match.group(1).lower()
        title = (match.group(2) or "").strip() or None
        paragraph.children.pop(0)
        if not paragraph.children:
            children = children[1:]
        return Callout(kind=kind, title=title, children=children, source=source)

    def _parse_list(self, tokens: list[Token], i: int):
        opener = tokens[i]
        ordered = opener.type == "ordered_list_open"
        close = "ordered_list_close" if ordered else "bullet_list_close"
        start = int(opener.attrGet("start") or 1) if ordered else 1
        items: list[ListItem] = []
        i += 1
        while i < len(tokens) and tokens[i].type != close:
            if tokens[i].type == "list_item_open":
                pos = self._pos(tokens[i])
                children, i = self._parse_blocks(tokens, i + 1, "list_item_close")
                task_checked = self._extract_task_state(children)
                items.append(ListItem(children=children, task_checked=task_checked, source=pos))
            else:
                i += 1
        i += 1  # list close
        if ordered:
            return OrderedList(items=items, start=start, source=self._pos(opener)), i
        return BulletList(items=items, source=self._pos(opener)), i


    @staticmethod
    def _extract_task_state(children: list) -> bool | None:
        """Recognize GitHub/Pandoc task-list markers without altering normal list text.

        Detection happens at the AST boundary so renderers can emit a native Word
        checkbox instead of baking ``[x]`` into text. Only a marker at the start
        of the first paragraph of a list item is recognized.
        """
        if not children or not isinstance(children[0], Paragraph):
            return None
        paragraph = children[0]
        if not paragraph.children or not isinstance(paragraph.children[0], Text):
            return None
        first = paragraph.children[0]
        match = re.match(r"^\[(?P<state>[ xX])\](?:[ \t]+|$)", first.text)
        if not match:
            return None
        first.text = first.text[match.end():]
        return match.group("state").lower() == "x"

    _ATTR_RE = re.compile(r"\{(?P<body>[^{}]+)\}\s*$")

    @staticmethod
    def _parse_attrs_text(text: str) -> tuple[str | None, dict[str, str]]:
        parsed = parse_attribute_list(text)
        values = dict(parsed.values)
        if parsed.classes:
            values["class"] = " ".join(parsed.classes)
        return parsed.identifier, values

    def _extract_trailing_attrs(self, children: list) -> tuple[str | None, dict[str, str]]:
        if not children or not isinstance(children[-1], Text):
            return None, {}
        m = self._ATTR_RE.search(children[-1].text)
        if not m:
            return None, {}
        identifier, attrs = self._parse_attrs_text("{" + m.group("body") + "}")
        children[-1].text = children[-1].text[:m.start()].rstrip()
        if not children[-1].text:
            children.pop()
        return identifier, attrs

    def _parse_fence_info(self, info: str) -> tuple[str | None, str | None, dict[str, str]]:
        if not info:
            return None, None, {}
        m = re.match(r"^(\S+?)(?:\s+(\{.*\}))?$", info.strip())
        if not m:
            return info.strip() or None, None, {}
        language = m.group(1) or None
        identifier, attrs = self._parse_attrs_text(m.group(2) or "")
        return language, identifier, attrs

    def _postprocess_blocks(self, nodes: list) -> list:
        out: list = []
        for node in nodes:
            if isinstance(node, Paragraph):
                text = self._plain_text(node.children).strip()
                identifier, attrs = self._parse_attrs_text(text)
                if (identifier or attrs) and out and isinstance(out[-1], (MathBlock, Table, ImageBlock, CodeBlock, ChartBlock, DataTableBlock)):
                    target = out[-1]
                    if identifier:
                        target.identifier = identifier
                    if attrs.get("caption"):
                        target.caption = attrs["caption"]
                    if isinstance(target, ImageBlock):
                        width = attrs.get("width")
                        if width and width.endswith("%"):
                            try:
                                target.width_percent = float(width[:-1])
                            except ValueError:
                                pass
                        target.align = attrs.get("align") or target.align
                        if "decorative" in attrs:
                            target.decorative = attrs["decorative"].lower() in {"1", "true", "yes"}
                    continue
                cap = re.match(r"^(Figure|Table|Equation|Listing)\s*:\s*(.+?)(?:\s+(\{.*\}))?$", text, re.I)
                if cap and out and isinstance(out[-1], (MathBlock, Table, ImageBlock, CodeBlock, ChartBlock, DataTableBlock)):
                    target = out[-1]
                    target.caption = cap.group(2).strip()
                    if cap.group(3):
                        ident, more = self._parse_attrs_text(cap.group(3))
                        if ident:
                            target.identifier = ident
                        if more.get("caption"):
                            target.caption = more["caption"]
                    continue
            out.append(node)
        return out

    @staticmethod
    def _plain_text(nodes: list) -> str:
        parts: list[str] = []
        for node in nodes:
            if isinstance(node, Text):
                parts.append(node.text)
            elif hasattr(node, "children"):
                parts.append(MarkdownParser._plain_text(node.children))
        return "".join(parts)

    _COMBINED_REF_RE = re.compile(r"\[(?P<prefix>Figure|Table|Equation|Listing|Section)\s+@(?P<target>[A-Za-z0-9_.:-]+)\]", re.I)

    def _split_refs_and_citations(self, text: str) -> list:
        nodes: list = []
        pos = 0
        combined: dict[str, tuple[str, str]] = {}
        def repl(match):
            key = f"MDDOCXREF{len(combined)}TOKEN"
            combined[key] = (match.group("prefix"), match.group("target"))
            return key
        text = self._COMBINED_REF_RE.sub(repl, text)
        pattern = re.compile(r"MDDOCXREF\d+TOKEN|\[@[^\]]+\]|(?<![\w@])@(?:fig|tbl|eq|lst|sec)-[A-Za-z0-9_.:-]+")
        for match in pattern.finditer(text):
            if match.start() > pos:
                nodes.append(Text(text=text[pos:match.start()]))
            token = match.group(0)
            if token in combined:
                prefix, target = combined[token]
                nodes.append(CrossReference(target=target, prefix=prefix.title()))
            elif token.startswith("[@"):
                content = token[2:-1].strip()
                parts = [p.strip() for p in content.split(";") if p.strip()]
                keys: list[str] = []
                suffixes: list[str] = []
                for part in parts:
                    if part.startswith("@"):
                        part = part[1:]
                    key, _, suffix = part.partition(",")
                    keys.append(key.strip())
                    if suffix.strip():
                        suffixes.append(suffix.strip())
                nodes.append(Citation(keys=keys, suffix="; ".join(suffixes) or None))
            else:
                raw_target = token[1:]
                target = raw_target.rstrip(".,;:!?")
                trailing = raw_target[len(target):]
                nodes.append(CrossReference(target=target, prefix=None))
                if trailing:
                    nodes.append(Text(text=trailing))
            pos = match.end()
        if pos < len(text):
            nodes.append(Text(text=text[pos:]))
        return nodes

    def _parse_table(self, tokens: list[Token], i: int):
        opener = tokens[i]
        rows: list[TableRow] = []
        header_section = False
        current_cells: list[TableCell] | None = None
        i += 1
        while i < len(tokens) and tokens[i].type != "table_close":
            t = tokens[i]
            if t.type == "thead_open":
                header_section = True
            elif t.type == "thead_close":
                header_section = False
            elif t.type == "tr_open":
                current_cells = []
            elif t.type in {"th_open", "td_open"}:
                is_header = t.type == "th_open" or header_section
                align = None
                style = t.attrGet("style") or ""
                if "text-align:" in style:
                    align = style.split("text-align:", 1)[1].split(";", 1)[0].strip()
                inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
                cell_children = self._inline(inline.children or []) if inline else []
                if current_cells is not None:
                    current_cells.append(TableCell(children=cell_children, alignment=align, header=is_header, source=self._pos(t)))
            elif t.type == "tr_close" and current_cells is not None:
                rows.append(TableRow(cells=current_cells, header=header_section or all(c.header for c in current_cells), source=self._pos(t)))
                current_cells = None
            i += 1
        return Table(rows=rows, source=self._pos(opener)), i + 1

    def _inline(self, tokens: list[Token]) -> list:
        nodes, _ = self._inline_range(tokens, 0, None)
        return nodes

    def _inline_range(self, tokens: list[Token], i: int, stop: str | None):
        nodes = []
        while i < len(tokens):
            t = tokens[i]
            if stop and t.type == stop:
                return nodes, i + 1
            custom = parse_custom_inline(self.extensions, self, tokens, i)
            if custom is not None:
                custom_node, i = custom
                if custom_node is not None:
                    if isinstance(custom_node, list):
                        nodes.extend(custom_node)
                    else:
                        nodes.append(custom_node)
                continue
            if t.type == "text":
                for kind, value in split_text_math(t.content):
                    if kind == "math":
                        nodes.append(InlineMath(source_text=value))
                    else:
                        for comment_kind, comment_value in split_comment_markup(value):
                            if comment_kind == "comment":
                                nodes.append(Comment(text=comment_value))
                                continue
                            for subkind, subvalue in split_footnote_references(comment_value):
                                if subkind == "footnote":
                                    nodes.append(FootnoteReference(label=subvalue))
                                else:
                                    nodes.extend(self._split_refs_and_citations(subvalue))
                i += 1
            elif t.type == "code_inline":
                nodes.append(InlineCode(code=t.content)); i += 1
            elif t.type == "softbreak":
                nodes.append(SoftBreak()); i += 1
            elif t.type == "hardbreak":
                nodes.append(HardBreak()); i += 1
            elif t.type in {"strong_open", "em_open", "s_open", "link_open"}:
                close = {"strong_open":"strong_close", "em_open":"em_close", "s_open":"s_close", "link_open":"link_close"}[t.type]
                inner, i = self._inline_range(tokens, i + 1, close)
                if t.type == "strong_open":
                    nodes.append(Strong(children=inner))
                elif t.type == "em_open":
                    nodes.append(Emphasis(children=inner))
                elif t.type == "s_open":
                    nodes.append(Strikethrough(children=inner))
                else:
                    nodes.append(Link(href=t.attrGet("href") or "", title=t.attrGet("title"), children=inner))
            elif t.type == "image":
                alt = t.content or ""
                nodes.append(Image(src=t.attrGet("src") or "", alt=alt, title=t.attrGet("title")))
                i += 1
            else:
                i += 1
        return nodes, i
