from __future__ import annotations

from io import BytesIO
from math import sqrt
from pathlib import Path
import re
from lxml import etree

from docx import Document as WordDocument
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, RGBColor

from mddocx.ast.base import Document
from mddocx.ast.block import (
    BlockQuote,
    BulletList,
    CodeBlock,
    Heading,
    HorizontalRule,
    ImageBlock,
    MathBlock,
    OrderedList,
    PageBreak,
    Paragraph,
    SectionBreak,
    Table,
    TableRow,
    TableCell,
    ChartBlock,
    DataTableBlock,
    BibliographyBlock,
    DefinitionList,
    Callout,
)
from mddocx.ast.inline import (
    Emphasis,
    HardBreak,
    Image,
    InlineCode,
    InlineMath,
    Link,
    SoftBreak,
    Strikethrough,
    Strong,
    Text,
    FootnoteReference,
    CrossReference,
    Citation,
    Comment,
)
from mddocx.config import RenderConfig
from mddocx.data import load_tabular_data, coerce_number
from mddocx.diagnostics import Diagnostic, DiagnosticReporter, MddocxError
from mddocx.diagrams import MermaidRenderer, MermaidRenderError
from mddocx.extensions.base import render_custom_block, render_custom_inline
from mddocx.math import DefaultMathConverter
from mddocx.ooxml.fields import (
    add_bookmark,
    add_hyperlink,
    add_internal_hyperlink,
    add_ref_field,
    add_seq_field,
    add_hidden_field,
    add_section_equation_number,
    add_page_number,
    add_num_pages,
    add_page_x_of_y,
    add_style_ref,
    add_toc,
    render_field_template,
    add_chapter_seq_field,
    add_section_caption_number,
    bookmark_name,
)
from mddocx.ooxml.numbering import NumberingEngine
from mddocx.ooxml.tasks import append_checkbox, set_task_indent
from mddocx.ooxml.footnotes import append_footnote_reference, inject_footnotes
from mddocx.ooxml.endnotes import append_endnote_reference, inject_endnotes
from mddocx.ooxml.comments import append_comment_reference, inject_comments
from mddocx.ooxml.charts import ChartEntry, inject_charts
from mddocx.references import ReferenceRegistry
from mddocx.bibliography import BibliographyDatabase
from mddocx.ooxml.text import clean_xml_text, configure_run_fonts, is_rtl_text, set_paragraph_rtl
from mddocx.ooxml.utils import (
    set_cell_margins,
    set_cell_shading,
    set_paragraph_bottom_border,
    set_repeat_table_header,
    set_row_cant_split,
)
from mddocx.resources import ResourceResolver
from mddocx.styles import ensure_styles, get_theme


class DocxRenderer:
    def __init__(self, reporter: DiagnosticReporter | None = None):
        self.reporter = reporter or DiagnosticReporter()
        self.document = None
        self.config = None
        self.numbering = None
        self.resolver = None
        self.math = None
        self._bookmark_id = 1
        self._bookmark_names: set[str] = set()
        self._theme = None
        self._footnote_definitions: dict[str, list] = {}
        self._footnote_ids: dict[str, int] = {}
        self._footnote_entries: dict[int, list] = {}
        self._task_control_id = 1000
        self.references = None
        self.bibliography = BibliographyDatabase()
        self._cited_keys: list[str] = []
        self._bibliography_rendered = False
        self._comment_entries: dict[int, str] = {}
        self._comment_id = 0
        self._heading_num_id: int | None = None
        self._chart_entries: list[ChartEntry] = []

    def render(self, document: Document, config: RenderConfig | None = None) -> bytes:
        self.config = config or RenderConfig()
        self._theme = get_theme(self.config.theme)
        self.document = self._open_document()
        ensure_styles(self.document, self.config)
        self._configure_document()
        self.numbering = NumberingEngine(self.document, self.config.lists, body_font=(self.config.fonts.body or self._theme.body_font))
        self.resolver = ResourceResolver(Path(self.config.base_dir or "."), self.config.resources, self.config.images)
        self.math = DefaultMathConverter(cache=self.config.performance.cache_math)
        self._footnote_definitions = dict(getattr(document, "footnotes", {}) or {})
        self._footnote_ids = {}
        self._footnote_entries = {}
        self.references = ReferenceRegistry.from_document(
            document, self._plain_inline_text,
            self.config.references.equation_number_format,
            self.config.references.caption_number_format,
        )
        bib_path = self.config.citations.bibliography
        if bib_path is not None and not Path(bib_path).is_absolute():
            bib_path = Path(self.config.base_dir or ".") / bib_path
        self.bibliography = BibliographyDatabase.load(bib_path)
        self._cited_keys = []
        self._bibliography_rendered = False
        self._comment_entries = {}
        self._comment_id = 0
        self._chart_entries = []
        self._heading_num_id = (
            self.numbering.create_heading_scheme(
                self.config.heading_numbering.max_level,
                self.config.heading_numbering.separator,
                self.config.heading_numbering.suffix,
            ) if self.config.heading_numbering.enabled else None
        )
        try:
            if self.config.title_page.enabled:
                self._render_title_page()
            if self.config.abstract.text or self.config.abstract.keywords:
                self._render_abstract()
            if self.config.toc.enabled:
                self._render_toc()
            for node in document.children:
                self._render_block(node)
            if self.config.citations.auto_bibliography and self._cited_keys and not self._bibliography_rendered:
                self._render_bibliography()
            self._request_field_updates()
            stream = BytesIO()
            self.document.save(stream)
            blob = stream.getvalue()
            if self._footnote_entries:
                if self.config.notes.style == "endnote":
                    blob = inject_endnotes(blob, self._footnote_entries, self.math)
                else:
                    blob = inject_footnotes(blob, self._footnote_entries, self.math)
            if self._comment_entries and self.config.native_comments.enabled:
                blob = inject_comments(
                    blob, self._comment_entries,
                    author=self.config.native_comments.author,
                    initials=self.config.native_comments.initials,
                )
            if self._chart_entries:
                blob = inject_charts(blob, self._chart_entries)
            return blob
        finally:
            self.resolver.close()

    def _open_document(self):
        if self.config.template is None:
            return WordDocument()
        template = Path(self.config.template).expanduser().resolve()
        if not template.is_file():
            raise MddocxError(Diagnostic("error", "CONFIG301", f"DOCX template not found: {template.name}"))
        if template.suffix.lower() != ".docx":
            raise MddocxError(Diagnostic("error", "CONFIG302", "Template must be a .docx file."))
        try:
            return WordDocument(str(template))
        except Exception as exc:
            raise MddocxError(Diagnostic("error", "DOCX301", f"Unable to open template: {template.name}")) from exc

    def _configure_document(self) -> None:
        preserve_page = bool(self.config.template and self.config.preserve_template_page_setup)
        self._configure_section(self.document.sections[0], preserve_page=preserve_page)
        props = self.document.core_properties
        if self.config.title:
            props.title = self.config.title
        if self.config.author:
            props.author = self.config.author
        if self.config.subject:
            props.subject = self.config.subject
        if self.config.keywords:
            props.keywords = self.config.keywords
        if self.config.comments:
            props.comments = self.config.comments
        if self.config.created_at:
            props.created = self.config.created_at

    def _render_title_page(self) -> None:
        cfg = self.config.title_page
        if not self.config.title and not cfg.subtitle and not cfg.organization:
            return
        p = self.document.add_paragraph(style="MD Title")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Mm(42)
        p.add_run(clean_xml_text(self.config.title or "Untitled Document"))
        if cfg.subtitle:
            sp = self.document.add_paragraph(style="MD Subtitle")
            sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sp.add_run(clean_xml_text(cfg.subtitle))
        if self.config.author:
            ap = self.document.add_paragraph(style="MD Normal")
            ap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            ap.add_run(clean_xml_text(self.config.author))
        if cfg.organization:
            op = self.document.add_paragraph(style="MD Normal")
            op.alignment = WD_ALIGN_PARAGRAPH.CENTER
            op.add_run(clean_xml_text(cfg.organization))
        dp = self.document.add_paragraph(style="MD Normal")
        dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if cfg.date:
            render_field_template(dp, cfg.date, {"AUTHOR": self.config.author or ""})
        else:
            render_field_template(dp, "{DATE}")
        if cfg.page_break_after:
            self.document.add_page_break()

    def _render_abstract(self) -> None:
        cfg = self.config.abstract
        if cfg.text:
            hp = self.document.add_paragraph(style="MD Heading 1")
            hp.add_run(clean_xml_text(cfg.title))
            bp = self.document.add_paragraph(style="MD Abstract")
            bp.add_run(clean_xml_text(cfg.text))
        if cfg.keywords:
            kp = self.document.add_paragraph(style="MD Abstract")
            r = kp.add_run(clean_xml_text(cfg.keywords_label) + ": ")
            r.bold = True
            kp.add_run(clean_xml_text(", ".join(cfg.keywords)))

    def _configure_section(self, sec, orientation: str | None = None, preserve_page: bool = False) -> None:
        target_orientation = orientation or self.config.page.orientation
        if not preserve_page:
            if self.config.page.size == "A4":
                width, height = Mm(210), Mm(297)
            else:
                width, height = Mm(215.9), Mm(279.4)
            sec.page_width, sec.page_height = width, height
            if target_orientation == "landscape":
                sec.orientation = WD_ORIENT.LANDSCAPE
                sec.page_width, sec.page_height = height, width
            else:
                sec.orientation = WD_ORIENT.PORTRAIT
                sec.page_width, sec.page_height = width, height
            m = self.config.page.margins
            sec.top_margin, sec.bottom_margin = Mm(m.top), Mm(m.bottom)
            sec.left_margin, sec.right_margin = Mm(m.left), Mm(m.right)
        elif orientation is not None:
            current_landscape = sec.page_width > sec.page_height
            want_landscape = orientation == "landscape"
            if current_landscape != want_landscape:
                sec.page_width, sec.page_height = sec.page_height, sec.page_width
            sec.orientation = WD_ORIENT.LANDSCAPE if want_landscape else WD_ORIENT.PORTRAIT
        self._configure_header_footer(sec)

    def _configure_header_footer(self, sec) -> None:
        header_cfg = self.config.header
        footer_cfg = self.config.footer
        if header_cfg.different_first_page or footer_cfg.different_first_page:
            sec.different_first_page_header_footer = True
        if header_cfg.different_odd_even or footer_cfg.different_odd_even:
            settings = self.document.settings.element
            even = settings.find(qn("w:evenAndOddHeaders"))
            if even is None:
                even = OxmlElement("w:evenAndOddHeaders"); settings.append(even)
            even.set(qn("w:val"), "true")

        def render_header(header, text: str | None, include_defaults: bool = True) -> None:
            header.is_linked_to_previous = False
            p = header.paragraphs[0]; p.clear()
            pieces: list[str] = []
            if text:
                pieces.append(text)
            if include_defaults and header_cfg.document_title and self.config.title:
                pieces.append("{TITLE}")
            if pieces:
                render_field_template(p, " — ".join(pieces), {"TITLE": self.config.title or "", "AUTHOR": self.config.author or ""})
            if include_defaults and header_cfg.section_title:
                if pieces: p.add_run(" — ")
                add_style_ref(p, "MD Heading 1")

        def render_footer(footer, text: str | None, include_defaults: bool = True) -> None:
            footer.is_linked_to_previous = False
            p = footer.paragraphs[0]; p.clear()
            if text:
                render_field_template(p, text, {"TITLE": self.config.title or "", "AUTHOR": self.config.author or ""})
            if not include_defaults:
                return
            has_text = bool(text)
            if footer_cfg.page_x_of_y:
                if has_text: p.add_run("  •  ")
                add_page_x_of_y(p)
            elif footer_cfg.page_number:
                if has_text: p.add_run("  •  ")
                add_page_number(p)
                if footer_cfg.num_pages:
                    p.add_run(" / "); add_num_pages(p)
            elif footer_cfg.num_pages:
                if has_text: p.add_run("  •  ")
                add_num_pages(p)

        if header_cfg.enabled or header_cfg.text or header_cfg.document_title or header_cfg.section_title:
            render_header(sec.header, header_cfg.text)
        if header_cfg.different_first_page and header_cfg.first_page_text is not None:
            render_header(sec.first_page_header, header_cfg.first_page_text, False)
        if header_cfg.different_odd_even and header_cfg.even_page_text is not None:
            render_header(sec.even_page_header, header_cfg.even_page_text, False)

        if footer_cfg.enabled or footer_cfg.text or footer_cfg.page_number or footer_cfg.num_pages or footer_cfg.page_x_of_y:
            render_footer(sec.footer, footer_cfg.text)
        if footer_cfg.different_first_page and footer_cfg.first_page_text is not None:
            render_footer(sec.first_page_footer, footer_cfg.first_page_text, False)
        if footer_cfg.different_odd_even and footer_cfg.even_page_text is not None:
            render_footer(sec.even_page_footer, footer_cfg.even_page_text, False)

    def _render_toc(self) -> None:
        if self.config.toc.title:
            p = self.document.add_paragraph(style="MD Normal")
            r = p.add_run(clean_xml_text(self.config.toc.title))
            r.bold = True
            r.font.size = Mm(5.5)
            p.paragraph_format.keep_with_next = True
        p = self.document.add_paragraph(style="MD Normal")
        add_toc(p, self.config.toc.min_level, self.config.toc.max_level)
        self.document.add_paragraph(style="MD Normal")

    def _request_field_updates(self) -> None:
        if not self.config.fields.update_on_open:
            return
        settings = self.document.settings.element
        node = settings.find(qn("w:updateFields"))
        if node is None:
            node = OxmlElement("w:updateFields")
            settings.append(node)
        node.set(qn("w:val"), "true")

    def _render_block(self, node, list_ctx=None, list_level=0):
        if render_custom_block(self.config.extensions, self, node):
            return
        if isinstance(node, Heading):
            p = self.document.add_paragraph(style=f"MD Heading {node.level}")
            if self._heading_num_id is not None and node.level <= self.config.heading_numbering.max_level:
                self.numbering.apply(p, self._heading_num_id, node.level - 1)
            self._render_inlines(p, node.children)
            self._apply_paragraph_direction(p, self._plain_inline_text(node.children))
            if self.config.heading_bookmarks:
                plain = self._plain_inline_text(node.children) or f"Heading {self._bookmark_id}"
                target = self.references.get(node.identifier) if node.identifier and self.references else None
                name = target.bookmark if target else bookmark_name(plain, self._bookmark_id)
                base = name
                n = 2
                while name in self._bookmark_names:
                    suffix = f"_{n}"
                    name = base[: 40 - len(suffix)] + suffix
                    n += 1
                self._bookmark_names.add(name)
                add_bookmark(p, name, self._bookmark_id)
                self._bookmark_id += 1
            if self.config.references.enabled and node.level == 1 and (
                self.config.references.equation_number_format == "section"
                or self.config.references.caption_number_format == "section"
            ):
                counter_p = self.document.add_paragraph(style="MD Normal")
                counter_p.paragraph_format.space_before = 0
                counter_p.paragraph_format.space_after = 0
                counter_p.paragraph_format.line_spacing = 0.01
                counter_p.paragraph_format.keep_with_next = True
                add_hidden_field(counter_p, r" SEQ Section \* ARABIC ", "1")
                if self.config.references.equation_number_format == "section":
                    add_hidden_field(counter_p, r" SEQ Equation \r 0 ", "0")
                if self.config.references.caption_number_format == "section":
                    for label in ("Figure", "Table", "Listing"):
                        add_hidden_field(counter_p, f" SEQ {label} \r 0 ", "0")
        elif isinstance(node, Paragraph):
            p = self.document.add_paragraph(style="MD Normal")
            self._render_inlines(p, node.children)
            self._apply_paragraph_direction(p, self._plain_inline_text(node.children))
        elif isinstance(node, Callout):
            self._render_callout(node)
        elif isinstance(node, BlockQuote):
            for child in node.children:
                before = len(self.document.paragraphs)
                self._render_block(child)
                for p in self.document.paragraphs[before:]:
                    p.style = "MD Quote"
        elif isinstance(node, CodeBlock):
            if (node.language or "").strip().lower() == "mermaid" and self.config.mermaid.enabled:
                renderer = MermaidRenderer(
                    max_source_chars=self.config.mermaid.max_source_chars,
                    max_nodes=self.config.mermaid.max_nodes,
                    max_edges=self.config.mermaid.max_edges,
                )
                try:
                    path = renderer.render(node.code, self.resolver.temp_dir)
                except MermaidRenderError as exc:
                    if self.config.mermaid.fallback == "error":
                        raise MddocxError(Diagnostic("error", "DIAGRAM201", str(exc))) from exc
                    self.reporter.warn("DIAGRAM201", f"Mermaid kept as editable code: {exc}", getattr(node.source, "file", None), getattr(node.source, "line", None))
                    self._render_code_block(node)
                else:
                    diagram_caption = (node.caption or ("Diagram" if node.identifier else None)) if self.config.references.captions else None
                    if diagram_caption and self.config.references.figure_caption_position == "above":
                        self._render_caption("Figure", diagram_caption, node.identifier)
                    p = self.document.add_paragraph(style="MD Normal")
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.keep_together = True
                    self._add_image_path(p, path, diagram_caption or "Mermaid diagram", title=diagram_caption)
                    if diagram_caption and self.config.references.figure_caption_position == "below":
                        self._render_caption("Figure", diagram_caption, node.identifier)
                    self.reporter.info("DIAGRAM101", "Rendered Mermaid diagram locally.", getattr(node.source, "file", None), getattr(node.source, "line", None))
            else:
                listing_caption = (node.caption or ("Code listing" if node.identifier else None)) if self.config.references.captions else None
                if listing_caption and self.config.references.listing_caption_position == "above":
                    self._render_caption("Listing", listing_caption, node.identifier)
                self._render_code_block(node)
                if listing_caption and self.config.references.listing_caption_position == "below":
                    self._render_caption("Listing", listing_caption, node.identifier)
        elif isinstance(node, MathBlock):
            if self.config.references.enabled and node.identifier and self.config.references.equation_numbering:
                self._render_numbered_equation(node)
            else:
                p = self.document.add_paragraph(style="MD Equation")
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.keep_together = True
                self._append_math(p, node.source_text, display=True, source=node.source)
            if node.caption:
                cp = self.document.add_paragraph(style="MD Caption")
                cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cp.add_run(clean_xml_text(node.caption))
        elif isinstance(node, (BulletList, OrderedList)):
            self._render_list(node, list_level)
        elif isinstance(node, Table):
            caption = (node.caption or ("Table" if node.identifier else None)) if self.config.references.captions else None
            if caption and self.config.references.table_caption_position == "above":
                self._render_caption("Table", caption, node.identifier)
            self._render_table_with_layout(node)
            if caption and self.config.references.table_caption_position == "below":
                self._render_caption("Table", caption, node.identifier)
        elif isinstance(node, ImageBlock):
            caption = (node.caption or (node.title if self.config.image_captions_from_title else None) or (node.alt if node.identifier else None)) if self.config.references.captions else None
            if caption and self.config.references.figure_caption_position == "above":
                self._render_caption("Figure", caption, node.identifier)
            p = self.document.add_paragraph(style="MD Normal")
            p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT, "right": WD_ALIGN_PARAGRAPH.RIGHT}.get(node.align or self.config.figures.default_align, WD_ALIGN_PARAGRAPH.CENTER)
            if caption:
                p.paragraph_format.keep_with_next = True
            self._add_image(p, node.src, node.alt, title=node.title, width_percent=node.width_percent, decorative=node.decorative)
            if caption and self.config.references.figure_caption_position == "below":
                self._render_caption("Figure", caption, node.identifier)
        elif isinstance(node, ChartBlock):
            self._render_chart(node)
        elif isinstance(node, DataTableBlock):
            self._render_data_table(node)
        elif isinstance(node, BibliographyBlock):
            self._render_bibliography()
        elif isinstance(node, DefinitionList):
            for item in node.items:
                tp = self.document.add_paragraph(style="MD Normal")
                tp.paragraph_format.keep_with_next = True
                self._render_inlines(tp, item.term, bold=True)
                dp = self.document.add_paragraph(style="MD Normal")
                dp.paragraph_format.left_indent = Mm(8)
                self._render_inlines(dp, item.definition)
        elif isinstance(node, HorizontalRule):
            p = self.document.add_paragraph(style="MD Normal")
            set_paragraph_bottom_border(p)
        elif isinstance(node, PageBreak):
            self.document.add_page_break()
        elif isinstance(node, SectionBreak):
            sec = self.document.add_section(WD_SECTION.NEW_PAGE)
            self._configure_section(sec, preserve_page=bool(self.config.template and self.config.preserve_template_page_setup))
        else:
            source = getattr(node, "source", None)
            self.reporter.warn(
                "EXT301",
                f"No renderer registered for AST node {type(node).__name__}.",
                getattr(source, "file", None),
                getattr(source, "line", None),
            )

    def _resolve_data_path(self, source_path: str, source_meta=None) -> Path:
        base = Path(self.config.base_dir or ".").expanduser().resolve()
        target = (base / source_path).expanduser().resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise MddocxError(Diagnostic("error", "DATA209", "Data source escapes the document base directory.", getattr(source_meta, "file", None), getattr(source_meta, "line", None))) from exc
        return target

    def _render_chart(self, node: ChartBlock) -> None:
        if not self.config.charts.enabled:
            self.reporter.warn("CHART101", "Chart rendering is disabled; source was omitted.", getattr(node.source, "file", None), getattr(node.source, "line", None))
            return
        caption = (node.caption or node.title or ("Chart" if node.identifier else None)) if self.config.references.captions else None
        if caption and self.config.references.figure_caption_position == "above":
            self._render_caption("Figure", caption, node.identifier)
        entry = self._prepare_chart_entry(node)
        token = f"MDDOCX_CHART_{len(self._chart_entries) + 1}_PLACEHOLDER"
        entry.token = token
        self._chart_entries.append(entry)
        p = self.document.add_paragraph(style="MD Normal")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_together = True
        if caption and self.config.references.figure_caption_position == "below":
            p.paragraph_format.keep_with_next = True
        p.add_run(token)
        if caption and self.config.references.figure_caption_position == "below":
            self._render_caption("Figure", caption, node.identifier)
        self.reporter.info("CHART100", f"Queued native editable {node.chart_type} chart.", getattr(node.source, "file", None), getattr(node.source, "line", None))

    def _prepare_chart_entry(self, node: ChartBlock) -> ChartEntry:
        categories = list(node.categories)
        raw_series = list(node.series)
        if node.source_path:
            path = self._resolve_data_path(node.source_path, node.source)
            data = load_tabular_data(path, max_rows=self.config.data.max_rows, max_columns=self.config.data.max_columns)
            if not data.columns:
                raise MddocxError(Diagnostic("error", "CHART203", "Chart data source is empty.", getattr(node.source, "file", None), getattr(node.source, "line", None)))
            category_field = node.category_field or data.columns[0]
            categories = data.column(category_field)
            fields = list(node.series_fields) or [c for c in data.columns if c != category_field]
            raw_series = [{"name": field, "values": data.column(field)} for field in fields]
        if not raw_series:
            raise MddocxError(Diagnostic("error", "CHART203", "Chart requires at least one data series.", getattr(node.source, "file", None), getattr(node.source, "line", None)))
        if len(raw_series) > self.config.charts.max_series:
            raise MddocxError(Diagnostic("error", "CHART204", f"Chart exceeds {self.config.charts.max_series} series.", getattr(node.source, "file", None), getattr(node.source, "line", None)))
        series: list[tuple[str, list[object]]] = []
        max_points = 0
        for idx, item in enumerate(raw_series, start=1):
            if not isinstance(item, dict):
                raise MddocxError(Diagnostic("error", "CHART205", "Each chart series must be a mapping with name and values.", getattr(node.source, "file", None), getattr(node.source, "line", None)))
            name = str(item.get("name") or f"Series {idx}")
            values = item.get("values") or []
            if not isinstance(values, list):
                raise MddocxError(Diagnostic("error", "CHART205", f"Chart series '{name}' values must be a list.", getattr(node.source, "file", None), getattr(node.source, "line", None)))
            numeric: list[object] = []
            for value in values:
                number = coerce_number(value)
                numeric.append(number if number is not None else 0.0)
            max_points = max(max_points, len(numeric))
            series.append((name, numeric))
        max_points = max(max_points, len(categories))
        if max_points > self.config.charts.max_points:
            raise MddocxError(Diagnostic("error", "CHART206", f"Chart exceeds {self.config.charts.max_points} data points.", getattr(node.source, "file", None), getattr(node.source, "line", None)))
        if not categories:
            categories = list(range(1, max_points + 1))
        if node.chart_type.lower() == "pie" and len(series) > 1:
            self.reporter.warn("CHART207", "Pie charts use only the first series.", getattr(node.source, "file", None), getattr(node.source, "line", None))
            series = series[:1]
        if node.chart_type.lower() == "scatter":
            converted: list[object] = []
            for value in categories:
                number = coerce_number(value)
                if number is None:
                    raise MddocxError(Diagnostic("error", "CHART208", "Scatter chart x/category values must be numeric.", getattr(node.source, "file", None), getattr(node.source, "line", None)))
                converted.append(number)
            categories = converted
        secondary = tuple(name for name in node.secondary_series if name in {n for n, _ in series})
        unknown_secondary = [name for name in node.secondary_series if name not in {n for n, _ in series}]
        for name in unknown_secondary:
            self.reporter.warn("CHART209", f"Secondary-axis series was not found: {name}", getattr(node.source, "file", None), getattr(node.source, "line", None))
        if secondary and node.chart_type.lower() not in {"column", "bar", "line"}:
            self.reporter.warn("CHART210", f"Secondary axes are not supported for {node.chart_type} charts; using the primary axis.", getattr(node.source, "file", None), getattr(node.source, "line", None))
            secondary = ()
        return ChartEntry(
            token="", chart_type=node.chart_type, title=node.title, categories=categories, series=series,
            width_mm=node.width_mm or self.config.charts.default_width_mm,
            height_mm=node.height_mm or self.config.charts.default_height_mm,
            alt_text=node.caption or node.title or "Chart",
            x_axis_title=node.x_axis_title, y_axis_title=node.y_axis_title,
            x_min=node.x_min, x_max=node.x_max, y_min=node.y_min, y_max=node.y_max,
            x_number_format=node.x_number_format, y_number_format=node.y_number_format,
            legend_position=node.legend_position, data_labels=node.data_labels,
            show_gridlines=node.show_gridlines, secondary_series=secondary,
            secondary_axis_title=node.secondary_axis_title, secondary_min=node.secondary_min,
            secondary_max=node.secondary_max, secondary_number_format=node.secondary_number_format,
            style=node.style,
        )

    def _render_data_table(self, node: DataTableBlock) -> None:
        path = self._resolve_data_path(node.source_path, node.source)
        data = load_tabular_data(path, max_rows=self.config.data.max_rows, max_columns=self.config.data.max_columns)
        columns = list(node.columns) or list(data.columns)
        for name in columns:
            if name not in data.columns:
                raise MddocxError(Diagnostic("error", "DATA208", f"Unknown data-table column: {name}", getattr(node.source, "file", None), getattr(node.source, "line", None)))
        rows = [TableRow(cells=[TableCell(children=[Text(text=name)], header=True) for name in columns], header=True)]
        indices = [data.columns.index(name) for name in columns]
        for raw in data.rows:
            cells = [TableCell(children=[Text(text="" if idx >= len(raw) or raw[idx] is None else str(raw[idx]))]) for idx in indices]
            rows.append(TableRow(cells=cells))
        table_node = Table(rows=rows, identifier=node.identifier, caption=node.caption, source=node.source)
        caption = (node.caption or ("Table" if node.identifier else None)) if self.config.references.captions else None
        if caption and self.config.references.table_caption_position == "above":
            self._render_caption("Table", caption, node.identifier)
        self._render_table_with_layout(table_node)
        if caption and self.config.references.table_caption_position == "below":
            self._render_caption("Table", caption, node.identifier)
        self.reporter.info("DATA100", f"Rendered {len(data.rows)} rows from {Path(node.source_path).name} as a native Word table.", getattr(node.source, "file", None), getattr(node.source, "line", None))

    def _render_callout(self, node: Callout) -> None:
        kind = (node.kind or "note").lower()
        label = self.config.callouts.labels.get(kind, kind.title())
        style_name = f"MD Callout {kind.title()}"
        first_paragraph = True
        for child in node.children or [Paragraph(children=[])]:
            if isinstance(child, Paragraph):
                p = self.document.add_paragraph(style=style_name if style_name in self.document.styles else "MD Quote")
                if first_paragraph:
                    r = p.add_run(clean_xml_text(node.title or label) + (" — " if child.children else ""))
                    r.bold = True
                self._render_inlines(p, child.children)
                self._apply_paragraph_direction(p, self._plain_inline_text(child.children))
                first_paragraph = False
            elif isinstance(child, (BulletList, OrderedList)):
                if first_paragraph:
                    p = self.document.add_paragraph(style=style_name if style_name in self.document.styles else "MD Quote")
                    r = p.add_run(clean_xml_text(node.title or label)); r.bold = True
                    first_paragraph = False
                self._render_list(child)
            else:
                self._render_block(child)

    def _display_label(self, kind: str) -> str:
        return {
            "Figure": self.config.references.figure_label,
            "Table": self.config.references.table_label,
            "Equation": self.config.references.equation_label,
            "Listing": self.config.references.listing_label,
        }.get(kind, kind)

    def _render_caption(self, label: str, caption: str, identifier: str | None) -> None:
        p = self.document.add_paragraph(style="MD Caption")
        p.paragraph_format.keep_together = True
        p.paragraph_format.keep_with_next = True
        target = self.references.get(identifier) if identifier and self.references else None
        p.add_run(self._display_label(label) + " ")
        if target and target.number is not None:
            if self.config.references.caption_number_format == "section" and isinstance(target.number, str) and "." in target.number:
                section_no, item_no = target.number.split(".", 1)
                add_chapter_seq_field(p, label, section_no, item_no, target.bookmark, self._bookmark_id)
            else:
                add_seq_field(p, label, str(target.number), target.bookmark, self._bookmark_id)
            self._bookmark_id += 1
        else:
            add_seq_field(p, label, "1")
        if caption:
            p.add_run(" — " + clean_xml_text(caption))

    def _render_numbered_equation(self, node: MathBlock) -> None:
        table = self.document.add_table(rows=1, cols=2)
        table.autofit = False
        sec = self.document.sections[-1]
        usable = sec.page_width - sec.left_margin - sec.right_margin
        table.columns[0].width = int(usable * 0.88)
        table.columns[1].width = int(usable * 0.12)
        self._remove_table_borders(table)
        p = table.cell(0, 0).paragraphs[0]
        p.style = "MD Equation"; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_together = True
        self._append_math(p, node.source_text, display=True, source=node.source)
        np = table.cell(0, 1).paragraphs[0]
        np.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        target = self.references.get(node.identifier) if self.references else None
        np.add_run("(")
        if target and target.number is not None:
            if self.config.references.equation_number_format == "section" and isinstance(target.number, str) and "." in target.number:
                section_no, equation_no = target.number.split(".", 1)
                add_chapter_seq_field(np, "Equation", section_no, equation_no, target.bookmark, self._bookmark_id)
            else:
                add_seq_field(np, "Equation", str(target.number), target.bookmark, self._bookmark_id)
            self._bookmark_id += 1
        else:
            add_seq_field(np, "Equation", "1")
        np.add_run(")")
        set_row_cant_split(table.rows[0], True)

    @staticmethod
    def _remove_table_borders(table) -> None:
        tbl_pr = table._tbl.tblPr
        borders = tbl_pr.find(qn("w:tblBorders"))
        if borders is None:
            borders = OxmlElement("w:tblBorders"); tbl_pr.append(borders)
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = borders.find(qn(f"w:{edge}"))
            if el is None:
                el = OxmlElement(f"w:{edge}"); borders.append(el)
            el.set(qn("w:val"), "nil")

    def _render_cross_reference(self, paragraph, node: CrossReference) -> None:
        target = self.references.get(node.target) if self.references else None
        if not target:
            text = (node.prefix + " " if node.prefix else "") + "@" + node.target
            r = paragraph.add_run(text); self._configure_run(r, text)
            self.reporter.warn("REF202", f"Unresolved cross-reference: {node.target}")
            return
        prefix = node.prefix
        if not self.config.references.enabled:
            if prefix is None and self.config.references.include_prefix_in_crossrefs and target.kind != "Section":
                prefix = self._display_label(target.kind)
            if target.kind == "Section":
                value = target.title or node.target
                if prefix and value.lower().startswith(prefix.lower()):
                    prefix = None
            else:
                value = str(target.number or "?")
            text = ((prefix + " ") if prefix else "") + value
            r = paragraph.add_run(text); self._configure_run(r, text)
            return
        if prefix is None and self.config.references.include_prefix_in_crossrefs and target.kind != "Section":
            prefix = self._display_label(target.kind)
        if target.kind == "Section" and prefix and (target.title or "").lower().startswith(prefix.lower()):
            prefix = None
        if prefix:
            r = paragraph.add_run(prefix + " "); self._configure_run(r, r.text)
        if target.kind == "Section":
            add_ref_field(paragraph, target.bookmark, target.title or node.target)
        else:
            add_ref_field(paragraph, target.bookmark, str(target.number or "?"))

    def _render_bibliography(self) -> None:
        if self._bibliography_rendered:
            return
        self._bibliography_rendered = True
        title = clean_xml_text(self.config.citations.bibliography_title)
        last = self.document.paragraphs[-1] if self.document.paragraphs else None
        has_explicit_heading = bool(
            last
            and last.text.strip().casefold() == title.strip().casefold()
            and last.style is not None
            and (last.style.name or "").startswith(("MD Heading", "Heading"))
        )
        if not has_explicit_heading:
            p = self.document.add_paragraph(style="MD Heading 1")
            p.add_run(title)
        entries = self.bibliography.formatted_entries(self.config.citations.style)
        cited = set(self._cited_keys)
        for key, text in entries:
            if cited and key not in cited:
                continue
            bp = self.document.add_paragraph(style="MD Normal")
            bp.paragraph_format.left_indent = Mm(6)
            bp.paragraph_format.first_line_indent = Mm(-6)
            run = bp.add_run(clean_xml_text(text)); self._configure_run(run, text)

    def _render_list(self, node, level: int = 0):
        kind = "bullet" if isinstance(node, BulletList) else "decimal"
        num_id = self.numbering.create(kind, getattr(node, "start", 1))
        for item in node.items:
            numbered = False
            for child in item.children:
                if isinstance(child, Paragraph) and not numbered:
                    p = self.document.add_paragraph(style="MD Normal")
                    if item.task_checked is None:
                        self.numbering.apply(p, num_id, level)
                    else:
                        set_task_indent(
                            p,
                            level,
                            self.config.lists.indent_twips_per_level,
                            self.config.lists.hanging_twips,
                        )
                        append_checkbox(p, item.task_checked, self._task_control_id)
                        self._task_control_id += 1
                        spacer = p.add_run(" ")
                        self._configure_run(spacer, spacer.text)
                    self._render_inlines(p, child.children)
                    self._apply_paragraph_direction(p, self._plain_inline_text(child.children))
                    numbered = True
                elif isinstance(child, (BulletList, OrderedList)):
                    self._render_list(child, level + 1)
                else:
                    self._render_block(child, list_ctx=num_id, list_level=level)
            if not numbered:
                p = self.document.add_paragraph(style="MD Normal")
                if item.task_checked is None:
                    self.numbering.apply(p, num_id, level)
                else:
                    set_task_indent(
                        p,
                        level,
                        self.config.lists.indent_twips_per_level,
                        self.config.lists.hanging_twips,
                    )
                    append_checkbox(p, item.task_checked, self._task_control_id)
                    self._task_control_id += 1

    def _render_table_with_layout(self, node: Table) -> None:
        use_landscape = self._table_should_landscape(node)
        restore_orientation = self._current_orientation()
        if use_landscape and restore_orientation != "landscape":
            sec = self.document.add_section(WD_SECTION.NEW_PAGE)
            self._configure_section(sec, orientation="landscape", preserve_page=bool(self.config.template and self.config.preserve_template_page_setup))
            self.reporter.info("TABLE301", "Wide table rendered in an automatic landscape section.")
        self._render_table(node)
        if use_landscape and restore_orientation != "landscape" and self.config.table.restore_portrait_after_landscape:
            sec = self.document.add_section(WD_SECTION.NEW_PAGE)
            self._configure_section(sec, orientation=restore_orientation, preserve_page=bool(self.config.template and self.config.preserve_template_page_setup))

    def _current_orientation(self) -> str:
        sec = self.document.sections[-1]
        return "landscape" if sec.page_width > sec.page_height else "portrait"

    def _table_should_landscape(self, node: Table) -> bool:
        if not self.config.table.auto_landscape or self._current_orientation() == "landscape" or not node.rows:
            return False
        cols = max(len(r.cells) for r in node.rows)
        if cols >= self.config.table.landscape_min_columns:
            return True
        sec = self.document.sections[-1]
        available_mm = float(sec.page_width - sec.left_margin - sec.right_margin) / 36000.0
        intrinsic = sum(self._column_intrinsic_width_mm(node, i) for i in range(cols))
        return intrinsic > available_mm * self.config.table.landscape_width_ratio

    def _render_table(self, node: Table):
        if not node.rows:
            return
        cols = max(len(r.cells) for r in node.rows)
        table = self.document.add_table(rows=len(node.rows), cols=cols)
        table.style = "Table Grid"
        table.autofit = False
        widths = self._table_widths(node, cols)
        for c_idx, width in enumerate(widths):
            for row in table.rows:
                row.cells[c_idx].width = width
        header_fill = self.config.table.header_shading
        if header_fill == "EDEDED" and self.config.theme != "default":
            header_fill = self._theme.table_header_fill
        for r_idx, row_node in enumerate(node.rows):
            row = table.rows[r_idx]
            if row_node.header and self.config.table.repeat_header:
                set_repeat_table_header(row)
            row_chars = sum(len(self._plain_inline_text(c.children)) for c in row_node.cells)
            set_row_cant_split(row, row_chars <= self.config.table.short_row_character_limit)
            for c_idx, cell_node in enumerate(row_node.cells):
                cell = row.cells[c_idx]
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                set_cell_margins(cell, *(self.config.table.cell_padding_twips for _ in range(4)))
                p = cell.paragraphs[0]
                p.style = "MD Normal"
                self._render_inlines(p, cell_node.children)
                self._apply_paragraph_direction(p, self._plain_inline_text(cell_node.children))
                if cell_node.header:
                    set_cell_shading(cell, header_fill)
                    for run in p.runs:
                        run.bold = True
                if cell_node.alignment == "right":
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                elif cell_node.alignment == "center":
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif cell_node.alignment == "left":
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    def _column_intrinsic_width_mm(self, node: Table, idx: int) -> float:
        texts = [self._plain_inline_text(r.cells[idx].children) for r in node.rows if idx < len(r.cells)]
        if not texts:
            return self.config.table.min_column_width_mm
        max_word = max((len(word) for text in texts for word in re.split(r"\s+", text) if word), default=1)
        peak = max(map(len, texts), default=1)
        average = sum(map(len, texts)) / max(len(texts), 1)
        estimated = 5.0 + max_word * 1.75 + sqrt(peak) * 1.1 + sqrt(average) * 0.7
        return max(self.config.table.min_column_width_mm, min(self.config.table.max_column_width_mm, estimated))

    def _table_widths(self, node: Table, cols: int):
        sec = self.document.sections[-1]
        usable_emu = int(sec.page_width - sec.left_margin - sec.right_margin)
        available_mm = usable_emu / 36000.0
        intrinsic = [self._column_intrinsic_width_mm(node, idx) for idx in range(cols)]
        min_mm = min(self.config.table.min_column_width_mm, available_mm / max(cols, 1))
        max_mm = max(min_mm, self.config.table.max_column_width_mm)
        widths = [max(min_mm, min(max_mm, value)) for value in intrinsic]
        total = sum(widths) or 1.0
        if total > available_mm:
            # Preserve minimum widths first, then distribute remaining width by intrinsic demand.
            base = [min(min_mm, available_mm / cols) for _ in widths]
            remaining = max(0.0, available_mm - sum(base))
            demand = [max(0.1, w - b) for w, b in zip(widths, base)]
            demand_total = sum(demand)
            widths = [b + remaining * d / demand_total for b, d in zip(base, demand)]
        elif total < available_mm:
            remaining = available_mm - total
            flexible = [i for i, w in enumerate(widths) if w < max_mm]
            while remaining > 0.05 and flexible:
                add = remaining / len(flexible)
                next_flexible = []
                for i in flexible:
                    room = max_mm - widths[i]
                    delta = min(add, room)
                    widths[i] += delta
                    remaining -= delta
                    if widths[i] < max_mm - 0.05:
                        next_flexible.append(i)
                flexible = next_flexible
        return [Mm(max(3.0, w)) for w in widths]

    def _render_inlines(self, paragraph, nodes, bold=False, italic=False, strike=False):
        for node in nodes:
            state = {"bold": bold, "italic": italic, "strike": strike}
            if render_custom_inline(self.config.extensions, self, paragraph, node, state):
                continue
            if isinstance(node, Text):
                text = clean_xml_text(node.text)
                r = paragraph.add_run(text)
                r.bold = bold
                r.italic = italic
                r.font.strike = strike
                self._configure_run(r, text)
            elif isinstance(node, Strong):
                self._render_inlines(paragraph, node.children, True, italic, strike)
            elif isinstance(node, Emphasis):
                self._render_inlines(paragraph, node.children, bold, True, strike)
            elif isinstance(node, Strikethrough):
                self._render_inlines(paragraph, node.children, bold, italic, True)
            elif isinstance(node, InlineCode):
                text = clean_xml_text(node.code)
                r = paragraph.add_run(text)
                r.bold = bold
                r.italic = italic
                r.font.strike = strike
                self._configure_run(r, text, code=True)
            elif isinstance(node, Link):
                text = clean_xml_text(self._plain_inline_text(node.children))
                if node.href.startswith("#") and self.references:
                    target = self.references.get(node.href[1:])
                    if target:
                        add_internal_hyperlink(paragraph, text, target.bookmark)
                    else:
                        r = paragraph.add_run(text); self._configure_run(r, text)
                        self.reporter.warn("REF201", f"Unresolved internal link: {node.href}")
                else:
                    add_hyperlink(paragraph, text, node.href, bold, italic, strike, font_name=self._font_for_text(text), rtl=self._rtl_for_text(text))
            elif isinstance(node, CrossReference):
                self._render_cross_reference(paragraph, node)
            elif isinstance(node, Citation):
                for key in node.keys:
                    if key not in self._cited_keys:
                        self._cited_keys.append(key)
                    if key not in self.bibliography.entries:
                        self.reporter.warn("CITE201", f"Unresolved citation key: {key}")
                text = self.bibliography.cite(node.keys, self.config.citations.style, node.suffix)
                r = paragraph.add_run(clean_xml_text(text)); self._configure_run(r, text)
            elif isinstance(node, InlineMath):
                self._append_math(paragraph, node.source_text, False, node.source)
            elif isinstance(node, FootnoteReference):
                definition = self._footnote_definitions.get(node.label)
                if definition is None:
                    self.reporter.warn("FOOTNOTE201", f"Undefined footnote reference: {node.label}")
                    r = paragraph.add_run(f"[^{node.label}]")
                    self._configure_run(r, r.text)
                else:
                    footnote_id = self._footnote_ids.get(node.label)
                    if footnote_id is None:
                        footnote_id = len(self._footnote_ids) + 1
                        self._footnote_ids[node.label] = footnote_id
                        self._footnote_entries[footnote_id] = definition
                    (append_endnote_reference if self.config.notes.style == "endnote" else append_footnote_reference)(paragraph, footnote_id)
            elif isinstance(node, Comment):
                if self.config.native_comments.enabled:
                    self._comment_id += 1
                    self._comment_entries[self._comment_id] = node.text
                    append_comment_reference(paragraph, self._comment_id)
            elif isinstance(node, SoftBreak):
                paragraph.add_run(" ")
            elif isinstance(node, HardBreak):
                paragraph.add_run().add_break()
            elif isinstance(node, Image):
                self._add_image(paragraph, node.src, node.alt)

    def _plain_inline_text(self, nodes) -> str:
        out = []
        for n in nodes:
            if isinstance(n, Text):
                out.append(n.text)
            elif isinstance(n, InlineCode):
                out.append(n.code)
            elif isinstance(n, InlineMath):
                out.append(n.source_text)
            elif isinstance(n, Image):
                out.append(n.alt)
            elif isinstance(n, Comment):
                pass
            elif isinstance(n, (SoftBreak, HardBreak)):
                out.append(" ")
            elif hasattr(n, "children"):
                out.append(self._plain_inline_text(n.children))
        return "".join(out)

    def _append_math(self, paragraph, latex: str, display: bool, source=None):
        try:
            omath = self.math.latex_to_omml(latex, display)
            if display:
                para = OxmlElement("m:oMathPara")
                para.append(omath)
                paragraph._p.append(para)
            else:
                paragraph._p.append(omath)
        except Exception as exc:
            line = source.line if source else None
            file = source.file if source else None
            mode = self.config.math_failure.mode
            diag = Diagnostic(
                "error" if mode == "error" else "warning",
                "MATH201",
                f"Unable to convert LaTeX equation: {latex}",
                file,
                line,
            )
            if mode == "error":
                raise MddocxError(diag) from exc
            self.reporter.diagnostics.append(diag)
            paragraph.add_run(clean_xml_text(latex))

    def _render_code_block(self, node: CodeBlock) -> None:
        line_numbers = self.config.code.line_numbers if node.line_numbers is None else node.line_numbers
        show_label = self.config.code.show_language_label if node.show_language_label is None else node.show_language_label
        highlighted = set(self.config.code.highlight_lines) | set(node.highlight_lines)
        language = (node.language or "text").strip() or "text"
        if show_label and language.lower() not in {"text", "plain", "plaintext"}:
            lp = self.document.add_paragraph(style="MD Code Label")
            lp.add_run(clean_xml_text(language))

        lexer = None
        pyg_style = None
        if self.config.code.syntax_highlighting:
            try:
                from pygments.lexers import get_lexer_by_name
                from pygments.styles import get_style_by_name
                lexer = get_lexer_by_name(language)
                pyg_style = get_style_by_name("friendly")
            except Exception:
                lexer = None; pyg_style = None

        lines = node.code.splitlines() or [""]
        width = len(str(len(lines)))
        for line_no, raw_line in enumerate(lines, 1):
            p = self.document.add_paragraph(style="MD Code")
            p.paragraph_format.keep_together = True
            p.paragraph_format.space_before = 0
            p.paragraph_format.space_after = 0
            ppr = p._p.get_or_add_pPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:fill"), "FFF2CC" if line_no in highlighted else "F3F3F3")
            ppr.append(shd)
            if line_numbers:
                prefix = f"{line_no:>{width}}  "
                nr = p.add_run(prefix); self._configure_run(nr, prefix, code=True)
                nr.font.color.rgb = RGBColor(110, 110, 110)
            if lexer is None or pyg_style is None:
                text = clean_xml_text(raw_line)
                run = p.add_run(text); self._configure_run(run, text, code=True)
                continue
            try:
                from pygments import lex
                tokens = list(lex(raw_line, lexer))
            except Exception:
                tokens = []
            if not tokens:
                run = p.add_run(clean_xml_text(raw_line)); self._configure_run(run, raw_line, code=True)
                continue
            for token_type, token_text in tokens:
                token_text = token_text.rstrip("\n")
                if not token_text:
                    continue
                token_text = clean_xml_text(token_text)
                run = p.add_run(token_text); self._configure_run(run, token_text, code=True)
                info = pyg_style.style_for_token(token_type)
                color = info.get("color")
                if color and len(color) == 6:
                    run.font.color.rgb = RGBColor.from_string(color.upper())
                run.bold = bool(info.get("bold")); run.italic = bool(info.get("italic"))
                if info.get("underline"):
                    run.underline = True

    def _add_image(self, paragraph, src: str, alt: str, title: str | None = None, width_percent: float | None = None, decorative: bool = False):
        self._add_image_path(paragraph, self.resolver.resolve(src), alt, title=title, width_percent=width_percent, decorative=decorative)

    def _add_image_path(self, paragraph, path: Path, alt: str, title: str | None = None, width_percent: float | None = None, decorative: bool = False):
        run = paragraph.add_run()
        shape = run.add_picture(str(path))
        sec = self.document.sections[-1]
        usable = sec.page_width - sec.left_margin - sec.right_margin
        requested_percent = width_percent if width_percent is not None else self.config.figures.default_width_percent
        requested_percent = min(requested_percent, self.config.images.max_width_percent)
        max_width = int(usable * max(0.05, min(1.0, requested_percent / 100.0)))
        if shape.width > max_width or (self.config.images.allow_upscale and shape.width < max_width):
            ratio = max_width / shape.width
            shape.width = max_width
            shape.height = int(shape.height * ratio)
        try:
            docpr = shape._inline.docPr
            if decorative and self.config.accessibility.mark_decorative_images:
                docpr.set("descr", "")
                docpr.set("title", "Decorative")
                a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
                adec_ns = "http://schemas.microsoft.com/office/drawing/2017/decorative"
                ext_lst = docpr.find(f"{{{a_ns}}}extLst")
                if ext_lst is None:
                    ext_lst = etree.SubElement(docpr, f"{{{a_ns}}}extLst")
                ext = etree.SubElement(ext_lst, f"{{{a_ns}}}ext")
                ext.set("uri", "{C183D7F6-B498-43B3-948B-1728B52AA6E}")
                dec = etree.SubElement(ext, f"{{{adec_ns}}}decorative", nsmap={"adec": adec_ns})
                dec.set("val", "1")
            else:
                if alt:
                    docpr.set("descr", clean_xml_text(alt))
                if title:
                    docpr.set("title", clean_xml_text(title))
                if self.config.accessibility.image_alt_required and not alt:
                    self.reporter.warn("A11Y201", f"Image has no alt text: {path.name}")
        except Exception:
            pass

    def _rtl_for_text(self, text: str) -> bool:
        if self.config.rtl == "force":
            return True
        if self.config.rtl == "off":
            return False
        return is_rtl_text(text)

    def _font_for_text(self, text: str, code: bool = False) -> str:
        if code:
            return self.config.fonts.code or self._theme.code_font
        if self._rtl_for_text(text) and self.config.fonts.complex_script:
            return self.config.fonts.complex_script
        return self.config.fonts.body or self._theme.body_font

    def _configure_run(self, run, text: str, code: bool = False) -> None:
        rtl = self._rtl_for_text(text)
        configure_run_fonts(
            run,
            text,
            self._font_for_text(text, code=code),
            self.config.fonts.east_asia or (self.config.fonts.fallback[0] if self.config.fonts.fallback else None),
            self.config.fonts.complex_script or (self.config.fonts.fallback[0] if self.config.fonts.fallback else None),
            rtl,
        )

    def _apply_paragraph_direction(self, paragraph, text: str) -> None:
        rtl = self._rtl_for_text(text)
        if rtl:
            set_paragraph_rtl(paragraph, True)
            if paragraph.alignment is None:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
