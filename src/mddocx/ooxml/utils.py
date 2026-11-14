"""Table, cell and paragraph property helpers shared by the block surfaces."""

from __future__ import annotations

from docx.oxml.ns import qn

from mddocx.ooxml.sequence import get_or_add


def set_cell_shading(cell, fill: str) -> None:
    shd = get_or_add(cell._tc.get_or_add_tcPr(), "w:shd")
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top: int = 90, start: int = 90, bottom: int = 90, end: int = 90) -> None:
    tc_mar = get_or_add(cell._tc.get_or_add_tcPr(), "w:tcMar")
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = get_or_add(tc_mar, f"w:{tag}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_fixed_layout(table) -> None:
    """Make explicit grid/cell widths authoritative in Word and LibreOffice."""
    layout = get_or_add(table._tbl.tblPr, "w:tblLayout")
    layout.set(qn("w:type"), "fixed")


def set_table_grid_widths(table, widths_twips: list[int]) -> None:
    grid = table._tbl.tblGrid
    for grid_col, width in zip(grid.findall(qn("w:gridCol")), widths_twips):
        grid_col.set(qn("w:w"), str(width))
    for row in table.rows:
        for cell, width in zip(row.cells, widths_twips):
            tc_w = get_or_add(cell._tc.get_or_add_tcPr(), "w:tcW")
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    header = get_or_add(row._tr.get_or_add_trPr(), "w:tblHeader")
    header.set(qn("w:val"), "true")


def set_row_cant_split(row, value: bool = True) -> None:
    cant = get_or_add(row._tr.get_or_add_trPr(), "w:cantSplit")
    cant.set(qn("w:val"), "1" if value else "0")


def set_paragraph_bottom_border(paragraph, color: str = "B7B7B7", size: str = "6") -> None:
    p_bdr = get_or_add(paragraph._p.get_or_add_pPr(), "w:pBdr")
    bottom = get_or_add(p_bdr, "w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
