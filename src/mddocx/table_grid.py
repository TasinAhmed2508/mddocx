from __future__ import annotations

from collections.abc import Iterator
from typing import Literal, NamedTuple, NoReturn

from .ast.base import SourcePosition
from .ast.block import Table, TableCell
from .diagnostics import Diagnostic, MddocxError

WORD_COLUMNS = 63


class GridCell(NamedTuple):
    column: int
    span: int
    cell: TableCell | None
    merge: Literal["restart", "continue"] | None = None


def check_grid_size(columns: int, rows: int, budget: int, source: SourcePosition | None) -> None:
    if columns > WORD_COLUMNS:
        _fail("TABLE401", "Table exceeds 63 Word columns. Split it into narrower tables.", source)
    if columns * rows > budget:
        _fail("LIMIT404", "Expanded table grid exceeds the configured cell limit.", source)


def _fail(code: str, message: str, source: SourcePosition | None) -> NoReturn:
    raise MddocxError(
        Diagnostic(
            "error", code, message, source.file if source else None, source.line if source else None
        )
    )


def table_grid(
    table: Table, budget: int = 100_000
) -> tuple[int, list[list[tuple[int, TableCell]]]]:
    """Map row-major input cells to grid columns, independently of Word."""
    width = 0
    rows: list[list[tuple[int, TableCell]]] = []
    occupied_until = [0] * WORD_COLUMNS

    for index, row in enumerate(table.rows):
        column = 0
        placements = []
        for cell in row.cells:
            while column < WORD_COLUMNS and occupied_until[column] > index:
                column += 1
            height, span = cell.row_span, cell.column_span
            if (
                type(span) is not int
                or type(height) is not int
                or span < 1
                or height < 1
                or index + height > len(table.rows)
            ):
                _fail("TABLE402", "Invalid table cell span.", table.source)
            right = column + span
            if right > width:
                check_grid_size(right, len(table.rows), budget, table.source)
                width = right
            if span > 1 and any(end > index for end in occupied_until[column:right]):
                _fail("TABLE402", "Overlapping table cell spans.", table.source)
            occupied_until[column:right] = [index + height] * span
            placements.append((column, cell))
            column = right
        rows.append(placements)
    return width, rows


def iter_grid_rows(
    columns: int, placements: list[list[tuple[int, TableCell]]]
) -> Iterator[list[GridCell]]:
    """Expand validated placements to the physical cells of each Word row."""
    active: dict[int, tuple[int, int]] = {}
    for index, entries in enumerate(placements):
        row = dict(entries)
        cells = []
        column = 0
        while column < columns:
            end, span = active.get(column, (0, 1))
            if end > index:
                cells.append(GridCell(column, span, None, "continue"))
            elif (cell := row.get(column)) is not None:
                span = cell.column_span
                merge: Literal["restart"] | None = "restart" if cell.row_span > 1 else None
                if merge:
                    active[column] = (index + cell.row_span, span)
                cells.append(GridCell(column, span, cell, merge))
            else:
                span = 1
                cells.append(GridCell(column, span, None))
            column += span
        yield cells


def repeatable_header_rows(table: Table) -> int:
    count = 0
    for row in table.rows:
        if not row.header:
            break
        count += 1
    for index, row in enumerate(table.rows[:count]):
        if any(index + cell.row_span > count for cell in row.cells):
            return 0
    return count


def has_ragged_rows(table: Table) -> bool:
    """Count both newly emitted cells and the columns occupied by earlier spans."""
    ends = [0] * (len(table.rows) + 1)
    active = 0
    widths = set()
    for index, row in enumerate(table.rows):
        active -= ends[index]
        for cell in row.cells:
            height, span = cell.row_span, cell.column_span
            if (
                type(height) is not int
                or type(span) is not int
                or height < 1
                or span < 1
                or index + height > len(table.rows)
            ):
                return False  # The grid validator reports the invalid span.
            active += span
            ends[index + height] += span
        widths.add(active)
    return len(widths) > 1
