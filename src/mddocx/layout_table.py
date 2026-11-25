"""Recognize plain-text layouts and validate explicit native table grids."""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

import yaml

from .ast.block import CodeBlock, TableCell
from .diagnostics import Diagnostic, MddocxError
from .table_grid import check_grid_size

_RULED_LINE = re.compile(r"\s*-{5,}\s*")


def text_layout_kind(node: CodeBlock) -> Literal["form", "ruled", "structured"] | None:
    language = (node.language or "").lower()
    if language == "layout-table":
        return "structured"
    if language not in {"text", "plain", "plaintext", "form", ""}:
        return None
    lines = node.code.splitlines()
    ruled = (
        sum(bool(_RULED_LINE.fullmatch(line)) for line in lines) >= 2
        and sum(line.count("|") == 2 for line in lines) >= 3
    )
    if ruled:
        if all(_RULED_LINE.fullmatch(line) or line.count("|") == 2 for line in lines):
            return "ruled"
        return None
    # A box and paired address columns distinguish forms from code samples.
    if (
        any("┌" in line and "┐" in line for line in lines)
        and sum(":" in line or "ঃ" in line for line in lines) >= 5
        and sum("|" in line for line in lines) >= 3
    ):
        return "form"
    return None


class LayoutTable(NamedTuple):
    rows: list[list[str]]
    weights: list[float]
    placements: list[list[tuple[int, TableCell]]]


def parse_layout_table(node: CodeBlock, cell_budget: int) -> LayoutTable:
    try:
        spec = yaml.safe_load(node.code)
        if not isinstance(spec, dict):
            raise ValueError("expected a mapping")
        rows = spec.get("rows")
        if not isinstance(rows, list) or not rows or any(not isinstance(row, list) for row in rows):
            raise ValueError("rows must be a nonempty list of cell lists")
        cols = len(rows[0])
        if not cols or any(len(row) != cols for row in rows):
            raise ValueError("all rows must have the same number of cells")
        check_grid_size(cols, len(rows), cell_budget, node.source)
        if any(not isinstance(cell, str) for row in rows for cell in row):
            raise ValueError("cells must be strings; use empty strings for merged placeholders")
        weights = spec.get("widths", [1] * cols)
        if (
            not isinstance(weights, list)
            or len(weights) != cols
            or any(type(w) not in {int, float} or not 0 < w < 100000 for w in weights)
        ):
            raise ValueError("widths must contain one positive finite weight per column")
        merges = spec.get("merges", [])
        if not isinstance(merges, list):
            raise ValueError("merges must be a list")
        occupied: set[tuple[int, int]] = set()
        spans: dict[tuple[int, int], tuple[int, int]] = {}
        for merge in merges:
            if not isinstance(merge, dict):
                raise ValueError("each merge must contain from and to coordinates")
            start, end = merge.get("from"), merge.get("to")
            if (
                not isinstance(start, list)
                or not isinstance(end, list)
                or len(start) != 2
                or len(end) != 2
                or any(type(n) is not int for n in (*start, *end))
            ):
                raise ValueError("merge coordinates must be [row, column] integer pairs")
            r1, c1 = start
            r2, c2 = end
            if not (0 <= r1 <= r2 < len(rows) and 0 <= c1 <= c2 < cols):
                raise ValueError("merge rectangle is outside the table or reversed")
            rectangle = {(r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)}
            if occupied & rectangle:
                raise ValueError("merge rectangles cannot overlap")
            if any(rows[r][c] for r, c in rectangle - {(r1, c1)}):
                raise ValueError("covered merge cells must be empty to prevent data loss")
            occupied.update(rectangle)
            spans[r1, c1] = (r2 - r1 + 1, c2 - c1 + 1)
    except (ValueError, TypeError, yaml.YAMLError) as exc:
        raise MddocxError(
            Diagnostic(
                "error",
                "LAYOUT401",
                f"Invalid layout-table: {exc}",
                node.source.file if node.source else None,
                node.source.line if node.source else None,
            )
        ) from exc

    placements = []
    for row in range(len(rows)):
        entries = []
        for column in range(cols):
            coord = (row, column)
            if coord in spans or coord not in occupied:
                height, width = spans.get(coord, (1, 1))
                entries.append((column, TableCell(row_span=height, column_span=width)))
        placements.append(entries)
    return LayoutTable(rows, weights, placements)
