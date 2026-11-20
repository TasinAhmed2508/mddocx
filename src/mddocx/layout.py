from __future__ import annotations

from dataclasses import dataclass, fields
from math import sqrt
import re
from typing import Any, Literal
from unicodedata import combining, east_asian_width

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
from .ast.inline import HardBreak, Image, InlineCode, Link, SoftBreak, Text
from .config import RenderConfig
from .table_grid import table_grid

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
        decisions: list[TableLayoutDecision] = []
        blocks: list[BlockLayoutDecision] = []
        section_orientation = self.config.page.orientation
        for node in _walk(document):
            block = self._block_decision(node)
            if block is not None:
                blocks.append(block)
            if isinstance(node, SectionBreak):
                section_orientation = node.orientation or self.config.page.orientation
            if not isinstance(node, Table) or not node.rows:
                continue
            decision = self._plan_table(node, section_orientation)
            decisions.append(decision)
            if not self.config.table.restore_portrait_after_landscape:
                section_orientation = decision.orientation
        return LayoutPlan(tuple(decisions), tuple(blocks))

    def landscape_reason(
        self, table: Table, columns: int, intrinsic_mm: float | None = None
    ) -> str | None:
        if not columns or not self.config.table.auto_landscape:
            return None
        if columns >= self.config.table.landscape_min_columns:
            return "column threshold"
        available = self._portrait_available_width_mm()
        if intrinsic_mm is None:
            intrinsic_mm = allocate_table_widths_mm(
                table, self.config, available
            ).intrinsic_total_mm
        if intrinsic_mm > available * self.config.table.landscape_width_ratio:
            return "estimated intrinsic width"
        return None

    def _plan_table(
        self, table: Table, orientation: Literal["portrait", "landscape"]
    ) -> TableLayoutDecision:
        available = self._portrait_available_width_mm()
        portrait = allocate_table_widths_mm(table, self.config, available)
        columns = len(portrait.intrinsic_widths_mm)
        intrinsic = portrait.intrinsic_total_mm
        reason = "document orientation"
        if orientation == "portrait" and self.config.table.auto_landscape:
            rotation = self.landscape_reason(table, columns, intrinsic)
            if rotation is not None:
                orientation = "landscape"
                reason = rotation
            else:
                reason = "fits portrait width"
        target_width = (
            self._landscape_available_width_mm() if orientation == "landscape" else available
        )
        allocation = (
            portrait
            if target_width == available
            else _fit_table_widths(portrait.intrinsic_widths_mm, self.config, target_width)
        )
        return TableLayoutDecision(
            node_identity=id(table),
            columns=columns,
            intrinsic_width_mm=intrinsic,
            available_width_mm=target_width,
            orientation=orientation,
            reason=reason,
            column_widths_mm=allocation.allocated_widths_mm,
        )

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
            position = (
                self.config.references.figure_caption_position
                if has_caption and self.config.references.captions
                else None
            )
            return BlockLayoutDecision(
                id(node),
                keep_with_next=position == "below" and self.config.figures.caption_keep_with_figure,
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
    columns, rows = table_grid(table, config.limits.max_table_cells)
    samples: list[list[tuple[str, int]]] = [[] for _ in range(columns)]
    for row in rows:
        for start, cell in row:
            text = _plain_text(cell.children)
            for column in range(start, start + cell.column_span):
                samples[column].append((text, cell.column_span))
    intrinsic = tuple(_column_intrinsic_width_mm(texts, config) for texts in samples)
    return _fit_table_widths(intrinsic, config, available_width_mm)


def _fit_table_widths(
    intrinsic: tuple[float, ...], config: RenderConfig, available_width_mm: float
) -> TableWidthAllocation:
    columns = len(intrinsic)
    if not columns:
        return TableWidthAllocation(available_width_mm, (), ())
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
        tuple(widths),
    )


def _column_intrinsic_width_mm(texts: list[tuple[str, int]], config: RenderConfig) -> float:
    if not texts:
        return config.table.min_column_width_mm

    def display_width(text: str) -> int:
        return sum(2 if east_asian_width(c) in {"W", "F"} else 1 for c in text if not combining(c))

    lines = [(line, span) for text, span in texts for line in text.split("\n")]
    max_word = max(
        (
            display_width(word) / span
            for line, span in lines
            for word in re.findall(r"[^\s/]+", line)
        ),
        default=1,
    )
    lengths = [display_width(line) / span for line, span in lines]
    peak = max(lengths, default=1)
    average = sum(lengths) / len(lengths)
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
    if isinstance(value, InlineCode):
        return value.code
    if isinstance(value, Image):
        return value.alt
    if isinstance(value, Link):
        return _plain_text(value.children)
    if isinstance(value, HardBreak):
        return "\n"
    if isinstance(value, SoftBreak):
        return " "
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
