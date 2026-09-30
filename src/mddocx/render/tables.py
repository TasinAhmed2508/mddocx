"""Table surface: Markdown tables, widths, shading, and landscape planning."""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm

from mddocx.ast.block import Table
from mddocx.layout import allocate_table_widths_mm
from mddocx.ooxml.utils import (
    set_cell_margins,
    set_cell_shading,
    set_repeat_table_header,
    set_row_cant_split,
    set_table_fixed_layout,
    set_table_grid_widths,
)

from . import citations, sections

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def render_table_block(renderer: DocxRenderer, node: Table) -> None:
    caption = (
        (node.caption or ("Table" if node.identifier else None))
        if renderer.config.references.captions
        else None
    )
    if caption and renderer.config.references.table_caption_position == "above":
        citations.render_caption(renderer, "Table", caption, node.identifier)
    render_table_with_layout(renderer, node)
    if caption and renderer.config.references.table_caption_position == "below":
        citations.render_caption(renderer, "Table", caption, node.identifier)


def render_table_with_layout(renderer: DocxRenderer, node: Table) -> None:
    use_landscape = table_should_landscape(renderer, node)
    restore_orientation = current_orientation(renderer)
    if use_landscape and restore_orientation != "landscape":
        sec = renderer.document.add_section(WD_SECTION.NEW_PAGE)
        sections.configure_section(
            renderer,
            sec,
            orientation="landscape",
            preserve_page=bool(
                renderer.config.template and renderer.config.preserve_template_page_setup
            ),
        )
        renderer.reporter.info("TABLE301", "Wide table rendered in an automatic landscape section.")
    render_table(renderer, node)
    if (
        use_landscape
        and restore_orientation != "landscape"
        and renderer.config.table.restore_portrait_after_landscape
    ):
        sec = renderer.document.add_section(WD_SECTION.NEW_PAGE)
        sections.configure_section(
            renderer,
            sec,
            orientation=restore_orientation,
            preserve_page=bool(
                renderer.config.template and renderer.config.preserve_template_page_setup
            ),
        )


def current_orientation(renderer: DocxRenderer) -> str:
    sec = renderer.document.sections[-1]
    return "landscape" if sec.page_width > sec.page_height else "portrait"


def table_should_landscape(renderer: DocxRenderer, node: Table) -> bool:
    decision = renderer._layout_plan.for_table(node)
    if decision is not None:
        return decision.orientation == "landscape" and current_orientation(renderer) != "landscape"
    if (
        not renderer.config.table.auto_landscape
        or current_orientation(renderer) == "landscape"
        or not node.rows
    ):
        return False
    cols = max(len(r.cells) for r in node.rows)
    if cols >= renderer.config.table.landscape_min_columns:
        return True
    sec = renderer.document.sections[-1]
    available_mm = float(sec.page_width - sec.left_margin - sec.right_margin) / 36000.0
    allocation = allocate_table_widths_mm(node, renderer.config, available_mm)
    return (
        allocation.intrinsic_total_mm > available_mm * renderer.config.table.landscape_width_ratio
    )


def render_table(renderer: DocxRenderer, node: Table) -> None:
    if not node.rows:
        return
    cols = max(len(r.cells) for r in node.rows)
    table = renderer.document.add_table(rows=len(node.rows), cols=cols)
    table.style = "Table Grid"
    table.autofit = False
    widths = table_widths(renderer, node, cols)
    set_table_fixed_layout(table)
    set_table_grid_widths(table, [int(width.mm * 56.6929133858) for width in widths])
    for c_idx, width in enumerate(widths):
        for row in table.rows:
            row.cells[c_idx].width = width
    header_fill = renderer.config.table.header_shading
    if header_fill == "EDEDED" and renderer.config.theme != "default":
        header_fill = renderer._theme.table_header_fill
    for r_idx, row_node in enumerate(node.rows):
        row = table.rows[r_idx]
        if row_node.header and renderer.config.table.repeat_header:
            set_repeat_table_header(row)
        row_chars = sum(len(renderer._plain_inline_text(c.children)) for c in row_node.cells)
        set_row_cant_split(row, row_chars <= renderer.config.table.short_row_character_limit)
        for c_idx, cell_node in enumerate(row_node.cells):
            cell = row.cells[c_idx]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            set_cell_margins(cell, *(renderer.config.table.cell_padding_twips for _ in range(4)))
            p = cell.paragraphs[0]
            p.style = renderer._style("MD Normal")
            renderer._render_inlines(p, cell_node.children)
            renderer._apply_text_direction(p._p, renderer._plain_inline_text(cell_node.children))
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


def table_widths(renderer: DocxRenderer, node: Table, cols: int):
    sec = renderer.document.sections[-1]
    usable_emu = int(sec.page_width - sec.left_margin - sec.right_margin)
    available_mm = usable_emu / 36000.0
    allocation = allocate_table_widths_mm(node, renderer.config, available_mm)
    return [Mm(width) for width in allocation.allocated_widths_mm[:cols]]


def remove_table_borders(table) -> None:
    """Strip every border from a table (used by the numbered-equation surface)."""
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), "nil")
