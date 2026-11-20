"""Table surface: Markdown tables, widths, shading, and landscape planning."""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, Twips

from mddocx.ast.block import Table
from mddocx.diagnostics import Diagnostic, MddocxError
from mddocx.layout import LayoutPlanner, _plain_text, allocate_table_widths_mm
from mddocx.table_grid import repeatable_header_rows, table_grid
from mddocx.ooxml.sequence import get_or_add
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
    use_landscape = table_should_landscape(renderer, node)
    restore_orientation = current_orientation(renderer)
    if use_landscape and restore_orientation != "landscape":
        body = renderer.document._element.body
        sec = (
            renderer.document.add_section(WD_SECTION.NEW_PAGE)
            if len(body) > 1
            else renderer.document.sections[-1]
        )
        sections.configure_section(
            renderer,
            sec,
            orientation="landscape",
            preserve_page=bool(
                renderer.config.template and renderer.config.preserve_template_page_setup
            ),
        )
        renderer.reporter.info("TABLE301", "Wide table rendered in an automatic landscape section.")
    below = bool(caption and renderer.config.references.table_caption_position == "below")
    if caption and not below:
        citations.render_caption(renderer, "Table", caption, node.identifier)
    render_table(renderer, node, caption_below=below)
    if caption and below:
        citations.render_caption(renderer, "Table", caption, node.identifier, keep_with_next=False)
    if (
        use_landscape
        and restore_orientation != "landscape"
        and renderer.config.table.restore_portrait_after_landscape
    ):
        sec = renderer.document.add_section(WD_SECTION.NEW_PAGE)
        renderer._table_section_restorations.append(renderer.document._element.body[-2])
        sections.configure_section(
            renderer,
            sec,
            orientation=restore_orientation,
            preserve_page=bool(
                renderer.config.template and renderer.config.preserve_template_page_setup
            ),
        )


def remove_empty_table_sections(renderer: DocxRenderer) -> None:
    """Remove empty sections introduced by automatic portrait restoration."""
    for marker in renderer._table_section_restorations:
        following = marker.getnext()
        if following is None:
            continue
        if following.tag == qn("w:sectPr"):
            empty_section = following
        elif following.tag == qn("w:p") and len(following) == 1 and following[0].tag == qn("w:pPr"):
            empty_section = following[0].find(qn("w:sectPr"))
        else:
            continue
        if empty_section is not None:
            landscape = marker[0].find(qn("w:sectPr"))
            empty_section.getparent().replace(empty_section, landscape)
            marker.getparent().remove(marker)


def current_orientation(renderer: DocxRenderer) -> str:
    sec = renderer.document.sections[-1]
    return "landscape" if sec.page_width > sec.page_height else "portrait"


def table_should_landscape(renderer: DocxRenderer, node: Table) -> bool:
    if (
        not renderer.config.table.auto_landscape
        or current_orientation(renderer) == "landscape"
        or not node.rows
    ):
        return False
    decision = renderer._layout_plan.for_table(node)
    preserve_page = renderer.config.template and renderer.config.preserve_template_page_setup
    if decision is not None and not preserve_page:
        return decision.orientation == "landscape"
    cols, _ = table_grid(node, renderer.config.limits.max_table_cells)
    if not preserve_page:
        return LayoutPlanner(renderer.config).landscape_reason(node, cols) is not None
    if cols >= renderer.config.table.landscape_min_columns:
        return True
    sec = renderer.document.sections[-1]
    available_mm = float(sec.page_width - sec.left_margin - sec.right_margin) / 36000.0
    allocation = allocate_table_widths_mm(node, renderer.config, available_mm)
    return (
        allocation.intrinsic_total_mm > available_mm * renderer.config.table.landscape_width_ratio
    )


def render_table(renderer: DocxRenderer, node: Table, *, caption_below: bool = False) -> None:
    if not node.rows:
        return
    cols, placements = table_grid(node, renderer.config.limits.max_table_cells)
    if not cols:
        return
    widths = table_widths(renderer, node, cols)
    body = renderer.document._element.body
    if len(body) > 1 and body[-2].tag == qn("w:tbl"):
        # Word can combine adjacent same-style tables unless separated by a paragraph.
        spacer = renderer.document.add_paragraph()
        spacer.paragraph_format.space_before = Pt(0)
        spacer.paragraph_format.space_after = Pt(0)
        spacer.paragraph_format.line_spacing = Pt(1)
    table = renderer.document.add_table(rows=len(node.rows), cols=cols)
    table.style = "Table Grid"
    table.autofit = False
    set_table_fixed_layout(table)
    set_table_grid_widths(table, [width.twips for width in widths])
    header_fill = renderer.config.table.header_shading
    if header_fill == "EDEDED" and renderer.config.theme != "default":
        header_fill = renderer._theme.table_header_fill
    text_style = (
        "MD Table Text" if renderer._theme.table_paragraph_after_pt is not None else "MD Normal"
    )
    body_style_id = table.part.get_style_id(renderer._style(text_style), WD_STYLE_TYPE.PARAGRAPH)
    grid = [list(row.cells) for row in table.rows]
    for cells in grid:
        for cell, width in zip(cells, widths):
            cell.width = width
    header_prefix = repeatable_header_rows(node)
    for r_idx, (row, entries) in enumerate(zip(table.rows, placements)):
        if r_idx < header_prefix and renderer.config.table.repeat_header:
            set_repeat_table_header(row)
        cell_texts = [_plain_text(cell.children) for _, cell in entries]
        row_chars = sum(map(len, cell_texts)) + 60 * sum(text.count("\n") for text in cell_texts)
        short_row = row_chars <= renderer.config.table.short_row_character_limit
        set_row_cant_split(row, short_row)
        for (column, cell_node), text in zip(entries, cell_texts):
            cell = grid[r_idx][column]
            if cell_node.row_span > 1 or cell_node.column_span > 1:
                cell = cell.merge(
                    grid[r_idx + cell_node.row_span - 1][column + cell_node.column_span - 1]
                )
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            set_cell_margins(cell, *(renderer.config.table.cell_padding_twips for _ in range(4)))
            p = cell.paragraphs[0]
            p._p.style = body_style_id
            if r_idx < header_prefix and r_idx + 1 < len(node.rows):
                p.paragraph_format.keep_with_next = True
            if caption_below and r_idx == len(node.rows) - 1 and short_row:
                p.paragraph_format.keep_with_next = True
            renderer._render_inlines(p, cell_node.children)
            renderer._apply_text_direction(p._p, text)
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
    widths = [Twips(int(width * 56.6929133858)) for width in allocation.allocated_widths_mm[:cols]]
    if any(width.twips <= 2 * renderer.config.table.cell_padding_twips for width in widths):
        source = node.source
        raise MddocxError(
            Diagnostic(
                "error",
                "TABLE403",
                "Table columns are narrower than the cell margins. Split the table or enable auto-landscape.",
                source.file if source else None,
                source.line if source else None,
            )
        )
    return widths


def remove_table_borders(table) -> None:
    """Strip every border from a table (used by the numbered-equation surface)."""
    borders = get_or_add(table._tbl.tblPr, "w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        get_or_add(borders, f"w:{edge}").set(qn("w:val"), "nil")
