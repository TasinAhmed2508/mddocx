from __future__ import annotations

from dataclasses import dataclass, fields
from math import sqrt
import re
from typing import Any, Literal

from .ast.base import Document, Node
from .ast.block import (
    ChartBlock,
    CodeBlock,
    Heading,
    ImageBlock,
    MathBlock,
    PageBreak,
    SectionBreak,
    Table,
)
from .ast.inline import Text
from .config import RenderConfig

LAYOUT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class TableLayoutDecision:
    """A deterministic, renderer-independent decision for one table."""

    node_identity: int
    columns: int
    intrinsic_width_mm: float
    available_width_mm: float
    orientation: Literal["portrait", "landscape"]
    reason: str
    column_widths_mm: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class TableWidthAllocation:
    """Documented constrained allocation for native Word table columns."""

    available_width_mm: float
    intrinsic_widths_mm: tuple[float, ...]
    allocated_widths_mm: tuple[float, ...]

    @property
    def intrinsic_total_mm(self) -> float:
        return sum(self.intrinsic_widths_mm)


@dataclass(frozen=True, slots=True)
class BlockLayoutDecision:
    """Paragraph/section intent decided before Word objects are created."""

    node_identity: int
    keep_with_next: bool = False
    keep_together: bool = False
    page_break_before: bool = False
    section_break_before: bool = False
    caption_position: Literal["above", "below"] | None = None
    treatment: str = "normal"


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    """Pre-render decisions that can be inspected and tested independently."""

    tables: tuple[TableLayoutDecision, ...] = ()
    blocks: tuple[BlockLayoutDecision, ...] = ()
    schema_version: int = LAYOUT_SCHEMA_VERSION

    def for_table(self, table: Table) -> TableLayoutDecision | None:
        identity = id(table)
        return next((item for item in self.tables if item.node_identity == identity), None)

    def for_node(self, node: Node) -> BlockLayoutDecision | None:
        identity = id(node)
        return next((item for item in self.blocks if item.node_identity == identity), None)


class LayoutPlanner:
    """Plan page-sensitive structures before OOXML is emitted."""

    def __init__(self, config: RenderConfig) -> None:
        self.config = config

    def plan(self, document: Document) -> LayoutPlan:
        available = self._portrait_available_width_mm()
        decisions: list[TableLayoutDecision] = []
        blocks: list[BlockLayoutDecision] = []
        for node in _walk(document):
            block = self._block_decision(node)
            if block is not None:
                blocks.append(block)
            if not isinstance(node, Table) or not node.rows:
                continue
            columns = max(len(row.cells) for row in node.rows)
            portrait_allocation = allocate_table_widths_mm(node, self.config, available)
            intrinsic = portrait_allocation.intrinsic_total_mm
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
            target_available = (
                self._landscape_available_width_mm() if orientation == "landscape" else available
            )
            target_allocation = allocate_table_widths_mm(node, self.config, target_available)
            decisions.append(
                TableLayoutDecision(
                    node_identity=id(node),
                    columns=columns,
                    intrinsic_width_mm=intrinsic,
                    available_width_mm=target_available,
                    orientation=orientation,
                    reason=reason,
                    column_widths_mm=target_allocation.allocated_widths_mm,
                )
            )
        return LayoutPlan(tuple(decisions), tuple(blocks))

    def _block_decision(self, node: Node) -> BlockLayoutDecision | None:
        if isinstance(node, Heading):
            return BlockLayoutDecision(
                id(node),
                keep_with_next=True,
                keep_together=True,
                page_break_before=node.level == 1 and self.config.h1_page_break_before,
                treatment="heading",
            )
        if isinstance(node, CodeBlock):
            short = len(node.code.splitlines()) <= 40
            return BlockLayoutDecision(
                id(node), keep_together=short, treatment="keep" if short else "allow-split"
            )
        if isinstance(node, MathBlock):
            return BlockLayoutDecision(
                id(node),
                keep_with_next=bool(node.caption),
                keep_together=True,
                caption_position="below" if node.caption else None,
                treatment="native-equation",
            )
        if isinstance(node, ImageBlock):
            has_caption = bool(
                node.caption
                or (self.config.image_captions_from_title and node.title)
                or node.identifier
            )
            position = self.config.references.figure_caption_position if has_caption else None
            return BlockLayoutDecision(
                id(node),
                keep_with_next=position == "below",
                keep_together=True,
                caption_position=position,
                treatment="native-figure",
            )
        if isinstance(node, ChartBlock):
            has_caption = bool(node.caption or node.identifier)
            position = self.config.references.figure_caption_position if has_caption else None
            return BlockLayoutDecision(
                id(node),
                keep_with_next=position == "below",
                keep_together=True,
                caption_position=position,
                treatment="native-chart",
            )
        if isinstance(node, Table):
            has_caption = bool(node.caption or node.identifier)
            position = self.config.references.table_caption_position if has_caption else None
            return BlockLayoutDecision(
                id(node),
                caption_position=position,
                treatment="native-table",
            )
        if isinstance(node, PageBreak):
            return BlockLayoutDecision(id(node), page_break_before=True, treatment="page-break")
        if isinstance(node, SectionBreak):
            return BlockLayoutDecision(
                id(node), section_break_before=True, treatment="section-break"
            )
        return None

    def _portrait_available_width_mm(self) -> float:
        width = 210.0 if self.config.page.size == "A4" else 215.9
        return max(1.0, width - self.config.page.margins.left - self.config.page.margins.right)

    def _landscape_available_width_mm(self) -> float:
        width = 297.0 if self.config.page.size == "A4" else 279.4
        return max(1.0, width - self.config.page.margins.left - self.config.page.margins.right)


def allocate_table_widths_mm(
    table: Table, config: RenderConfig, available_width_mm: float
) -> TableWidthAllocation:
    """Allocate widths from unbreakable content demand within page constraints.

    Each column starts with a deterministic intrinsic estimate derived from its
    longest unbreakable word, peak cell length, and average cell length. Values
    are clamped to configured minima/maxima. Overflow shrinks proportionally
    above the feasible minimum; spare width grows flexible columns up to the
    configured maximum.
    """
    columns = max((len(row.cells) for row in table.rows), default=0)
    if columns == 0:
        return TableWidthAllocation(available_width_mm, (), ())
    intrinsic = tuple(_column_intrinsic_width_mm(table, config, i) for i in range(columns))
    min_mm = min(config.table.min_column_width_mm, available_width_mm / columns)
    max_mm = max(min_mm, config.table.max_column_width_mm)
    widths = [max(min_mm, min(max_mm, value)) for value in intrinsic]
    total = sum(widths) or 1.0
    if total > available_width_mm:
        base = [min(min_mm, available_width_mm / columns) for _ in widths]
        remaining = max(0.0, available_width_mm - sum(base))
        demand = [max(0.1, width - minimum) for width, minimum in zip(widths, base)]
        demand_total = sum(demand)
        widths = [
            minimum + remaining * needed / demand_total for minimum, needed in zip(base, demand)
        ]
    elif total < available_width_mm:
        remaining = available_width_mm - total
        flexible = [index for index, width in enumerate(widths) if width < max_mm]
        while remaining > 0.05 and flexible:
            addition = remaining / len(flexible)
            next_flexible: list[int] = []
            for index in flexible:
                room = max_mm - widths[index]
                delta = min(addition, room)
                widths[index] += delta
                remaining -= delta
                if widths[index] < max_mm - 0.05:
                    next_flexible.append(index)
            flexible = next_flexible
    return TableWidthAllocation(
        available_width_mm,
        intrinsic,
        tuple(max(3.0, width) for width in widths),
    )


def _column_intrinsic_width_mm(table: Table, config: RenderConfig, index: int) -> float:
    texts = [_plain_text(row.cells[index]) for row in table.rows if index < len(row.cells)]
    if not texts:
        return config.table.min_column_width_mm
    max_word = max(
        (len(word) for text in texts for word in re.split(r"\s+", text) if word), default=1
    )
    peak = max(map(len, texts), default=1)
    average = sum(map(len, texts)) / max(len(texts), 1)
    estimated = 5.0 + max_word * 1.75 + sqrt(peak) * 1.1 + sqrt(average) * 0.7
    return max(
        config.table.min_column_width_mm,
        min(config.table.max_column_width_mm, estimated),
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
