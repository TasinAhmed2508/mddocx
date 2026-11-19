from __future__ import annotations

from .ast.block import Table, TableCell
from .diagnostics import Diagnostic, MddocxError

WORD_COLUMNS = 63


def table_grid(
    table: Table, budget: int = 100_000
) -> tuple[int, list[list[tuple[int, TableCell]]]]:
    """Map row-major input cells to grid columns, independently of Word."""
    width = 0
    rows: list[list[tuple[int, TableCell]]] = []
    occupied_until = [0] * WORD_COLUMNS

    def _fail(code: str, message: str) -> None:
        source = table.source
        raise MddocxError(
            Diagnostic(
                "error",
                code,
                message,
                source.file if source else None,
                source.line if source else None,
            )
        )

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
                _fail("TABLE402", "Invalid table cell span.")
            right = column + span
            if right > WORD_COLUMNS:
                _fail("TABLE401", "Table exceeds 63 Word columns. Split it into narrower tables.")
            if any(occupied_until[i] > index for i in range(column, right)):
                _fail("TABLE402", "Overlapping table cell spans.")
            width = max(width, right)
            if width * len(table.rows) > budget:
                _fail("LIMIT404", "Expanded table grid exceeds the configured cell limit.")
            occupied_until[column:right] = [index + height] * span
            placements.append((column, cell))
            column = right
        rows.append(placements)
    return width, rows


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
