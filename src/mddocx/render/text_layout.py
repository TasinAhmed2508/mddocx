"""Editable layouts for high-confidence plain-text document forms."""

from __future__ import annotations

from itertools import repeat
import re
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Mm, Pt
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from mddocx.layout_table import parse_layout_table
from mddocx.ooxml.sequence import get_or_add
from mddocx.ooxml.text import clean_xml_text
from mddocx.ooxml.utils import set_table_fixed_layout, set_table_grid_widths
from mddocx.table_grid import GridCell, iter_grid_rows

from .tables import append_grid_rows


def render_text_layout(renderer, node) -> bool:
    structured = (node.language or "").lower() == "layout-table"
    if not structured and (node.language or "").lower() not in {
        "text",
        "plain",
        "plaintext",
        "form",
        "",
    }:
        return False
    lines = node.code.splitlines()
    # A box and paired address columns distinguish forms from code samples.
    form = (
        any("┌" in line and "┐" in line for line in lines)
        and sum(":" in line or "ঃ" in line for line in lines) >= 5
        and sum("|" in line for line in lines) >= 3
    )
    ruled = (
        sum(bool(re.fullmatch(r"\s*-{5,}\s*", line)) for line in lines) >= 2
        and sum(line.count("|") == 2 for line in lines) >= 3
    )
    if not structured and not form and not ruled:
        return False

    def table(rows, widths, borders=False, placements=None):
        # Google Docs merges adjacent DOCX tables and inherits the first grid.
        # A small real paragraph keeps independent form/address grids intact.
        body = renderer.document._element.body
        previous = body[-2] if len(body) > 1 else None
        if previous is not None and previous.tag == qn("w:tbl"):
            spacer = renderer.document.add_paragraph()
            spacer.paragraph_format.space_before = Pt(0)
            spacer.paragraph_format.space_after = Pt(0)
            spacer.paragraph_format.line_spacing = Pt(1)
            spacer.add_run().font.size = Pt(1)
        result = renderer.document.add_table(rows=0, cols=len(widths))
        result.autofit = False
        set_table_fixed_layout(result)
        result.style = "Table Grid" if borders else "Normal Table"
        grid = (
            iter_grid_rows(len(widths), placements)
            if placements is not None
            else repeat([GridCell(column, 1, None) for column in range(len(widths))], len(rows))
        )
        native = append_grid_rows(result, [Mm(width).twips for width in widths], grid)
        style_id = renderer._paragraph_style_id("MD Normal")
        for row_index, (row, cells) in enumerate(native):
            get_or_add(row._tr.get_or_add_trPr(), "w:cantSplit")
            for cell, entry in cells:
                if placements is not None:
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                if entry.merge == "continue":
                    continue
                value = clean_xml_text(rows[row_index][entry.column])
                p = cell.paragraphs[0]
                p._p.style = style_id
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.line_spacing = 1
                run = p.add_run(value)
                renderer._configure_run(run, value)
                if borders:
                    p.paragraph_format.keep_with_next = row_index < len(rows) - 1
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return result

    section = renderer.document.sections[-1]
    available = (section.page_width - section.left_margin - section.right_margin) / 36000
    if structured:
        rows, weights, placements = parse_layout_table(node, renderer.config.limits.max_table_cells)
        total_weight = sum(weights)
        table(rows, [available * weight / total_weight for weight in weights], True, placements)
        return True
    if ruled:
        rows = []
        continuation = False
        for line in lines:
            if re.fullmatch(r"\s*-{5,}\s*", line):
                continuation = False
                continue
            if line.count("|") != 2:
                return False
            cells = [part.strip() for part in line.split("|")]
            if continuation and not cells[0]:
                rows[-1] = [
                    old + ("\n" if old and new else "") + new for old, new in zip(rows[-1], cells)
                ]
            else:
                rows.append(cells)
            continuation = True
        table(rows, [available * 0.16, available * 0.42, available * 0.42], True)
        return True

    fields, addresses, signatures = [], [], []
    for line in lines:
        line = re.split("[┌│└]", line, maxsplit=1)[0].strip()
        if not line:
            continue
        if "|" in line:
            addresses.append([part.strip() for part in line.split("|", 1)])
        elif re.match(r"\.{3,}", line):
            signatures.append(line)
        else:
            fields.append([line])
    outer = table([["", ""]], [available * 0.76, available * 0.24])
    left, photo = outer.rows[0].cells
    for index, values in enumerate(fields):
        p = left.paragraphs[0] if index == 0 else left.add_paragraph()
        p._p.style = renderer._paragraph_style_id("MD Normal")
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1
        # Use tab stops rather than Unicode character counts for shaped Bangla.
        p.paragraph_format.tab_stops.add_tab_stop(Mm(34))
        value = re.sub(r"\s*:\s*", "\t: ", values[0], count=1)
        renderer._configure_run(p.add_run(value), value)
    p = photo.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    renderer._configure_run(p.add_run("ছবি"), "ছবি")
    # Draw an actual bordered photo box inside the right-hand layout cell.
    box = photo.add_table(rows=1, cols=1)
    box.cell(0, 0).vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    bp = box.cell(0, 0).paragraphs[0]
    bp._p.style = renderer._paragraph_style_id("MD Normal")
    renderer._configure_run(bp.add_run("ছবি"), "ছবি")
    box.autofit = False
    set_table_fixed_layout(box)
    set_table_grid_widths(box, [1361])
    box.cell(0, 0).width = Mm(24)
    box.rows[0].height = Mm(24)
    box.columns[0].width = Mm(24)
    box.style = "Table Grid"
    box.cell(0, 0).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    photo._tc.remove(p._p)
    if addresses:
        table(addresses, [available / 2, available / 2])
    for value in signatures:
        p = renderer._add_paragraph("MD Normal")
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.paragraph_format.space_after = Pt(3)
        renderer._configure_run(p.add_run(value), value)
    return True
