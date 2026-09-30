"""The Word renderer: shared state, orchestration, and text policy.

Per-surface work lives in sibling modules (``front_matter``, ``text_blocks``,
``tables``, ``figures``, ...), which receive this renderer and are the only way
Word content is produced. This module owns the per-render state, the block
dispatch table, the inline engine, and the one place that decides text
direction and run fonts — see ``docs/ARCHITECTURE.md``.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from mddocx.ast.base import Document
from mddocx.ast.block import (
    BibliographyBlock,
    BlockQuote,
    BulletList,
    Callout,
    ChartBlock,
    CodeBlock,
    DataTableBlock,
    DefinitionList,
    Heading,
    HorizontalRule,
    ImageBlock,
    MathBlock,
    OrderedList,
    PageBreak,
    Paragraph,
    SectionBreak,
    Table,
)
from mddocx.ast.inline import (
    Citation,
    Comment,
    CrossReference,
    Emphasis,
    FootnoteReference,
    HardBreak,
    Image,
    InlineCode,
    InlineMath,
    Link,
    SoftBreak,
    Strikethrough,
    Strong,
    Text,
)
from mddocx.bibliography import BibliographyDatabase
from mddocx.config import RenderConfig
from mddocx.diagnostics import DiagnosticReporter
from mddocx.extensions.base import render_custom_block, render_custom_inline
from mddocx.layout import LayoutPlan, LayoutPlanner
from mddocx.math import DefaultMathConverter
from mddocx.ooxml.charts import ChartEntry, inject_charts
from mddocx.ooxml.comments import append_comment_reference, inject_comments
from mddocx.ooxml.fields import add_hyperlink, add_internal_hyperlink
from mddocx.ooxml.notes import (
    append_endnote_reference,
    append_footnote_reference,
    inject_endnotes,
    inject_footnotes,
)
from mddocx.ooxml.numbering import NumberingEngine
from mddocx.ooxml.text import clean_xml_text, configure_xml_run, set_xml_paragraph_rtl
from mddocx.references import ReferenceRegistry
from mddocx.resources import ResourceResolver
from mddocx.scripts import is_rtl_text
from mddocx.styles import (
    FontSlots,
    ensure_styles,
    get_theme,
    resolve_style_name,
    validate_style_mapping,
)

from . import (
    charts,
    citations,
    code_blocks,
    data_tables,
    document_setup,
    figures,
    front_matter,
    lists,
    math_blocks,
    tables,
    text_blocks,
)
from .context import RenderContext
from .math_renderer import NativeMathRenderer


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
        self._layout_plan = LayoutPlan()
        self.context: RenderContext | None = None
        self._math_renderer: NativeMathRenderer | None = None

    def render(
        self,
        document: Document,
        config: RenderConfig | None = None,
        layout_plan: LayoutPlan | None = None,
    ) -> bytes:
        self.config = config or RenderConfig()
        self._layout_plan = layout_plan or LayoutPlanner(self.config).plan(document)
        self._theme = get_theme(self.config.theme)
        self.fonts = FontSlots.resolve(self.config, self._theme)
        self.document = document_setup.open_document(self)
        validate_style_mapping(self.document, self.config, self.reporter)
        ensure_styles(self.document, self.config)
        document_setup.configure_document(self)
        self.numbering = NumberingEngine(
            self.document,
            self.config.lists,
            body_font=(self.config.fonts.body or self._theme.body_font),
        )
        self.resolver = ResourceResolver(
            Path(self.config.base_dir or "."), self.config.resources, self.config.images
        )
        self.math = DefaultMathConverter(cache=self.config.performance.cache_math)
        self._footnote_definitions = dict(getattr(document, "footnotes", {}) or {})
        self._footnote_ids = {}
        self._footnote_entries = {}
        self.references = ReferenceRegistry.from_document(
            document,
            self._plain_inline_text,
            self.config.references.equation_number_format,
            self.config.references.caption_number_format,
        )
        self.context = RenderContext(
            word_document=self.document,
            config=self.config,
            reporter=self.reporter,
            math=self.math,
            numbering=self.numbering,
            references=self.references,
            resolver=self.resolver,
        )
        self._math_renderer = NativeMathRenderer(self.context)
        bib_path = self.config.citations.bibliography
        if bib_path is not None and not Path(bib_path).is_absolute():
            bib_path = Path(self.config.base_dir or ".") / bib_path
        self.bibliography = BibliographyDatabase.load(bib_path)
        style_file = getattr(self.config.citations, "style_file", None)
        if style_file is not None and not Path(style_file).is_absolute():
            style_file = Path(self.config.base_dir or ".") / style_file
        self._citation_style = self.bibliography.resolve_style(
            self.config.citations.style, style_file
        )
        for diagnostic in self.bibliography.diagnostics:
            code, _, message = diagnostic.partition(" ")
            self.reporter.warn(code, message or diagnostic)
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
            )
            if self.config.heading_numbering.enabled
            else None
        )
        try:
            if self.config.title_page.enabled:
                front_matter.render_title_page(self)
            if self.config.abstract.text or self.config.abstract.keywords:
                front_matter.render_abstract(self)
            if self.config.toc.enabled:
                front_matter.render_toc(self)
            for node in document.children:
                self._render_block(node)
            if (
                self.config.citations.auto_bibliography
                and self._cited_keys
                and not self._bibliography_rendered
            ):
                citations.render_bibliography(self)
            document_setup.request_field_updates(self)
            stream = BytesIO()
            self.document.save(stream)
            blob = stream.getvalue()
            if self._footnote_entries:
                configure_run = self._configure_xml_run
                configure_paragraph = self._apply_text_direction
                if self.config.notes.style == "endnote":
                    blob = inject_endnotes(
                        blob, self._footnote_entries, self.math, configure_run, configure_paragraph
                    )
                else:
                    blob = inject_footnotes(
                        blob, self._footnote_entries, self.math, configure_run, configure_paragraph
                    )
            if self._comment_entries and self.config.native_comments.enabled:
                blob = inject_comments(
                    blob,
                    self._comment_entries,
                    author=self.config.native_comments.author,
                    initials=self.config.native_comments.initials,
                )
            if self._chart_entries:
                blob = inject_charts(blob, self._chart_entries)
            from mddocx.ooxml.bangla import apply_bangla_font

            return apply_bangla_font(blob, self.config.fonts.bengali)
        finally:
            self.resolver.close()

    def _style(self, canonical: str) -> str:
        return resolve_style_name(self.document, self.config, canonical)

    def _apply_planned_paragraph_layout(self, paragraph, node) -> None:
        decision = self._layout_plan.for_node(node)
        if decision is None:
            return
        paragraph.paragraph_format.keep_with_next = decision.keep_with_next
        paragraph.paragraph_format.keep_together = decision.keep_together
        paragraph.paragraph_format.page_break_before = decision.page_break_before

    def _render_block(self, node, list_level=0):
        """Dispatch one block node to the surface module that owns it."""
        if render_custom_block(self.config.extensions, self, node):
            return
        if isinstance(node, Heading):
            text_blocks.render_heading(self, node)
        elif isinstance(node, Paragraph):
            text_blocks.render_paragraph(self, node)
        elif isinstance(node, Callout):
            text_blocks.render_callout(self, node)
        elif isinstance(node, BlockQuote):
            text_blocks.render_block_quote(self, node)
        elif isinstance(node, CodeBlock):
            code_blocks.render_code_block(self, node)
        elif isinstance(node, MathBlock):
            math_blocks.render_math_block(self, node)
        elif isinstance(node, (BulletList, OrderedList)):
            lists.render_list(self, node, list_level)
        elif isinstance(node, Table):
            tables.render_table_block(self, node)
        elif isinstance(node, ImageBlock):
            figures.render_image_block(self, node)
        elif isinstance(node, ChartBlock):
            charts.render_chart(self, node)
        elif isinstance(node, DataTableBlock):
            data_tables.render_data_table(self, node)
        elif isinstance(node, BibliographyBlock):
            citations.render_bibliography(self)
        elif isinstance(node, DefinitionList):
            text_blocks.render_definition_list(self, node)
        elif isinstance(node, HorizontalRule):
            text_blocks.render_horizontal_rule(self)
        elif isinstance(node, PageBreak):
            text_blocks.render_page_break(self)
        elif isinstance(node, SectionBreak):
            text_blocks.render_section_break(self)
        else:
            source = getattr(node, "source", None)
            self.reporter.warn(
                "EXT301",
                f"No renderer registered for AST node {type(node).__name__}.",
                getattr(source, "file", None),
                getattr(source, "line", None),
            )

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
                        r = paragraph.add_run(text)
                        self._configure_run(r, text)
                        self.reporter.warn(
                            "REF201",
                            f"Unresolved internal link: {node.href}",
                            getattr(node.source, "file", None),
                            getattr(node.source, "line", None),
                        )
                else:
                    add_hyperlink(
                        paragraph,
                        text,
                        node.href,
                        bold,
                        italic,
                        strike,
                        font_name=self.fonts.for_text(rtl=self._rtl_for_text(text)),
                        rtl=self._rtl_for_text(text),
                    )
            elif isinstance(node, CrossReference):
                citations.render_cross_reference(self, paragraph, node)
            elif isinstance(node, Citation):
                for key in node.keys:
                    if key not in self._cited_keys:
                        self._cited_keys.append(key)
                    if key not in self.bibliography.entries:
                        self.reporter.warn(
                            "CITE201",
                            f"Unresolved citation key: {key}",
                            getattr(node.source, "file", None),
                            getattr(node.source, "line", None),
                        )
                text = self.bibliography.cite(node.keys, self._citation_style, node.suffix)
                if (
                    getattr(self.config.citations, "hyperlink_citations", True)
                    and len(node.keys) == 1
                    and node.keys[0] in self.bibliography.entries
                ):
                    add_internal_hyperlink(
                        paragraph,
                        clean_xml_text(text),
                        f"cite_{ReferenceRegistry.safe_bookmark(node.keys[0])}"[:40],
                    )
                else:
                    r = paragraph.add_run(clean_xml_text(text))
                    self._configure_run(r, text)
            elif isinstance(node, InlineMath):
                self._append_math(paragraph, node.source_text, False, node.source)
            elif isinstance(node, FootnoteReference):
                definition = self._footnote_definitions.get(node.label)
                if definition is None:
                    self.reporter.warn(
                        "FOOTNOTE201",
                        f"Undefined footnote reference: {node.label}",
                        getattr(node.source, "file", None),
                        getattr(node.source, "line", None),
                    )
                    r = paragraph.add_run(f"[^{node.label}]")
                    self._configure_run(r, r.text)
                else:
                    footnote_id = self._footnote_ids.get(node.label)
                    if footnote_id is None:
                        footnote_id = len(self._footnote_ids) + 1
                        self._footnote_ids[node.label] = footnote_id
                        self._footnote_entries[footnote_id] = definition
                    (
                        append_endnote_reference
                        if self.config.notes.style == "endnote"
                        else append_footnote_reference
                    )(paragraph, footnote_id)
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
                figures.add_image(self, paragraph, node.src, node.alt, source=node.source)

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
        if self._math_renderer is None:
            raise RuntimeError("Math renderer is unavailable before render context initialization.")
        self._math_renderer.append(paragraph, latex, display=display, source=source)

    def _rtl_for_text(self, text: str) -> bool:
        if self.config.rtl == "force":
            return True
        if self.config.rtl == "off":
            return False
        return is_rtl_text(text)

    def _configure_run(self, run, text: str, code: bool = False) -> None:
        """Configure a python-docx run with the document's script font slots."""
        self._configure_xml_run(run._r, text, code=code)

    def _configure_xml_run(self, run, text: str, code: bool = False) -> None:
        """Configure any raw ``w:r`` element, including note and header runs.

        Bound as the note-part callback, so it accepts ``(run, text)``.
        """
        if not text:
            return
        rtl = self._rtl_for_text(text)
        configure_xml_run(
            run,
            text,
            self.fonts.for_text(rtl=rtl, code=code),
            self.fonts.east_asia,
            self.fonts.complex_script,
            rtl,
        )

    def _apply_text_direction(self, paragraph_element, text: str) -> None:
        """Apply bidi direction and right alignment to any ``w:p`` element."""
        if not text or not self._rtl_for_text(text):
            return
        set_xml_paragraph_rtl(paragraph_element, True)
        ppr = paragraph_element.find(qn("w:pPr"))
        if ppr is not None and ppr.find(qn("w:jc")) is None:
            justify = OxmlElement("w:jc")
            justify.set(qn("w:val"), "right")
            ppr.append(justify)

    def _apply_text_policy(self, paragraph, text: str | None = None) -> None:
        """Apply script fonts and direction to a paragraph built outside block rendering."""
        if text is None:
            text = "".join(node.text or "" for node in paragraph._p.iter(qn("w:t")))
        for run in paragraph._p.iter(qn("w:r")):
            run_text = "".join(node.text or "" for node in run.iter(qn("w:t")))
            self._configure_xml_run(run, run_text)
        self._apply_text_direction(paragraph._p, text)
