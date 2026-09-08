from __future__ import annotations

from dataclasses import dataclass, fields
from math import sqrt
import re
from typing import Any, Literal

from .ast.base import Document, Node
from .ast.block import Table
from .ast.inline import Text
from .config import RenderConfig


@dataclass(frozen=True, slots=True)
class TableLayoutDecision:
    """A deterministic, renderer-independent decision for one table."""

    node_identity: int
    columns: int
    intrinsic_width_mm: float
    available_width_mm: float
    orientation: Literal["portrait", "landscape"]
    reason: str


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    """Pre-render decisions that can be inspected and tested independently."""

    tables: tuple[TableLayoutDecision, ...] = ()

    def for_table(self, table: Table) -> TableLayoutDecision | None:
        identity = id(table)
        return next((item for item in self.tables if item.node_identity == identity), None)


class LayoutPlanner:
    """Plan page-sensitive structures before OOXML is emitted."""

    def __init__(self, config: RenderConfig) -> None:
        self.config = config

    def plan(self, document: Document) -> LayoutPlan:
        available = self._portrait_available_width_mm()
        decisions: list[TableLayoutDecision] = []
        for node in _walk(document):
            if not isinstance(node, Table) or not node.rows:
                continue
            columns = max(len(row.cells) for row in node.rows)
            intrinsic = sum(self._column_intrinsic_width_mm(node, i) for i in range(columns))
            orientation: Literal["portrait", "landscape"] = self.config.page.orientation
            reason = "document orientation"
            if self.config.page.orientation == "portrait" and self.config.table.auto_landscape:
                if columns >= self.config.table.landscape_min_columns:
                    orientation = "landscape"
                    reason = "column threshold"
                elif intrinsic > available * self.config.table.landscape_width_ratio:
                    orientation = "landscape"
                    reason = "estimated intrinsic width"
                else:
                    reason = "fits portrait width"
            decisions.append(
                TableLayoutDecision(
                    node_identity=id(node),
                    columns=columns,
                    intrinsic_width_mm=intrinsic,
                    available_width_mm=available,
                    orientation=orientation,
                    reason=reason,
                )
            )
        return LayoutPlan(tuple(decisions))

    def _portrait_available_width_mm(self) -> float:
        width = 210.0 if self.config.page.size == "A4" else 215.9
        return max(1.0, width - self.config.page.margins.left - self.config.page.margins.right)

    def _column_intrinsic_width_mm(self, table: Table, index: int) -> float:
        texts = [_plain_text(row.cells[index]) for row in table.rows if index < len(row.cells)]
        if not texts:
            return self.config.table.min_column_width_mm
        max_word = max(
            (len(word) for text in texts for word in re.split(r"\s+", text) if word), default=1
        )
        peak = max(map(len, texts), default=1)
        average = sum(map(len, texts)) / max(len(texts), 1)
        estimated = 5.0 + max_word * 1.75 + sqrt(peak) * 1.1 + sqrt(average) * 0.7
        return max(
            self.config.table.min_column_width_mm,
            min(self.config.table.max_column_width_mm, estimated),
        )


def _plain_text(value: Any) -> str:
    if isinstance(value, Text):
        return value.text
    if isinstance(getattr(value, "source_text", None), str):
        return value.source_text
    if isinstance(value, (list, tuple)):
        return "".join(_plain_text(item) for item in value)
    if isinstance(value, Node):
        return "".join(
            _plain_text(getattr(value, item.name))
            for item in fields(value)
            if item.name != "source"
        )
    return ""


def _walk(value: Any):
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk(item)
        return
    if not isinstance(value, Node):
        return
    yield value
    for item in fields(value):
        if item.name == "source":
            continue
        child = getattr(value, item.name)
        if isinstance(child, dict):
            for entry in child.values():
                yield from _walk(entry)
        else:
            yield from _walk(child)
