from __future__ import annotations

from dataclasses import dataclass, field
from .base import Node


@dataclass(slots=True)
class Heading(Node):
    level: int = 1
    children: list[Node] = field(default_factory=list)
    identifier: str | None = None


@dataclass(slots=True)
class Paragraph(Node):
    children: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class BlockQuote(Node):
    children: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class Callout(Node):
    kind: str = "note"
    title: str | None = None
    children: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class BulletList(Node):
    items: list["ListItem"] = field(default_factory=list)


@dataclass(slots=True)
class OrderedList(Node):
    items: list["ListItem"] = field(default_factory=list)
    start: int = 1


@dataclass(slots=True)
class ListItem(Node):
    children: list[Node] = field(default_factory=list)
    task_checked: bool | None = None


@dataclass(slots=True)
class CodeBlock(Node):
    code: str = ""
    language: str | None = None
    identifier: str | None = None
    caption: str | None = None
    line_numbers: bool | None = None
    highlight_lines: tuple[int, ...] = ()
    show_language_label: bool | None = None


@dataclass(slots=True)
class MathBlock(Node):
    source_text: str = ""
    format: str = "latex"
    identifier: str | None = None
    caption: str | None = None


@dataclass(slots=True)
class TableCell(Node):
    children: list[Node] = field(default_factory=list)
    alignment: str | None = None
    header: bool = False


@dataclass(slots=True)
class TableRow(Node):
    cells: list[TableCell] = field(default_factory=list)
    header: bool = False


@dataclass(slots=True)
class Table(Node):
    rows: list[TableRow] = field(default_factory=list)
    identifier: str | None = None
    caption: str | None = None


@dataclass(slots=True)
class ImageBlock(Node):
    src: str = ""
    alt: str = ""
    title: str | None = None
    identifier: str | None = None
    caption: str | None = None
    width_percent: float | None = None
    align: str | None = None
    decorative: bool = False


@dataclass(slots=True)
class ChartBlock(Node):
    chart_type: str = "column"
    title: str = ""
    categories: list[object] = field(default_factory=list)
    series: list[dict[str, object]] = field(default_factory=list)
    source_path: str | None = None
    category_field: str | None = None
    series_fields: tuple[str, ...] = ()
    identifier: str | None = None
    caption: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    x_axis_title: str | None = None
    y_axis_title: str | None = None
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    x_number_format: str | None = None
    y_number_format: str | None = None
    legend_position: str = "right"
    data_labels: bool = False
    show_gridlines: bool = True
    secondary_series: tuple[str, ...] = ()
    secondary_axis_title: str | None = None
    secondary_min: float | None = None
    secondary_max: float | None = None
    secondary_number_format: str | None = None
    style: int | None = None


@dataclass(slots=True)
class DataTableBlock(Node):
    source_path: str = ""
    columns: tuple[str, ...] = ()
    identifier: str | None = None
    caption: str | None = None


@dataclass(slots=True)
class DefinitionItem(Node):
    term: list[Node] = field(default_factory=list)
    definition: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class DefinitionList(Node):
    items: list[DefinitionItem] = field(default_factory=list)

@dataclass(slots=True)
class BibliographyBlock(Node):
    pass


@dataclass(slots=True)
class HorizontalRule(Node):
    pass


@dataclass(slots=True)
class PageBreak(Node):
    pass


@dataclass(slots=True)
class SectionBreak(Node):
    pass
