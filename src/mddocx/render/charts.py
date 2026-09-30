"""Chart surface: queue native ChartML entries for package injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH

from mddocx.ast.block import ChartBlock
from mddocx.data import coerce_number, load_tabular_data
from mddocx.diagnostics import Diagnostic, MddocxError
from mddocx.ooxml.charts import ChartEntry

from . import citations, data_tables

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def render_chart(renderer: DocxRenderer, node: ChartBlock) -> None:
    if not renderer.config.charts.enabled:
        renderer.reporter.warn(
            "CHART101",
            "Chart rendering is disabled; source was omitted.",
            getattr(node.source, "file", None),
            getattr(node.source, "line", None),
        )
        return
    caption = (
        (node.caption or node.title or ("Chart" if node.identifier else None))
        if renderer.config.references.captions
        else None
    )
    if caption and renderer.config.references.figure_caption_position == "above":
        citations.render_caption(renderer, "Figure", caption, node.identifier)
    entry = prepare_chart_entry(renderer, node)
    token = f"MDDOCX_CHART_{len(renderer._chart_entries) + 1}_PLACEHOLDER"
    entry.token = token
    renderer._chart_entries.append(entry)
    p = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_together = True
    if caption and renderer.config.references.figure_caption_position == "below":
        p.paragraph_format.keep_with_next = True
    p.add_run(token)
    if caption and renderer.config.references.figure_caption_position == "below":
        citations.render_caption(renderer, "Figure", caption, node.identifier)
    renderer.reporter.info(
        "CHART100",
        f"Queued native editable {node.chart_type} chart.",
        getattr(node.source, "file", None),
        getattr(node.source, "line", None),
    )


def prepare_chart_entry(renderer: DocxRenderer, node: ChartBlock) -> ChartEntry:
    categories = list(node.categories)
    raw_series = list(node.series)
    if node.source_path:
        path = data_tables.resolve_data_path(renderer, node.source_path, node.source)
        data = load_tabular_data(
            path,
            max_rows=renderer.config.data.max_rows,
            max_columns=renderer.config.data.max_columns,
        )
        if not data.columns:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "CHART203",
                    "Chart data source is empty.",
                    getattr(node.source, "file", None),
                    getattr(node.source, "line", None),
                )
            )
        category_field = node.category_field or data.columns[0]
        categories = data.column(category_field)
        fields = list(node.series_fields) or [c for c in data.columns if c != category_field]
        raw_series = [{"name": field, "values": data.column(field)} for field in fields]
    if not raw_series:
        raise MddocxError(
            Diagnostic(
                "error",
                "CHART203",
                "Chart requires at least one data series.",
                getattr(node.source, "file", None),
                getattr(node.source, "line", None),
            )
        )
    if len(raw_series) > renderer.config.charts.max_series:
        raise MddocxError(
            Diagnostic(
                "error",
                "CHART204",
                f"Chart exceeds {renderer.config.charts.max_series} series.",
                getattr(node.source, "file", None),
                getattr(node.source, "line", None),
            )
        )
    series: list[tuple[str, list[object]]] = []
    max_points = 0
    for idx, item in enumerate(raw_series, start=1):
        if not isinstance(item, dict):
            raise MddocxError(
                Diagnostic(
                    "error",
                    "CHART205",
                    "Each chart series must be a mapping with name and values.",
                    getattr(node.source, "file", None),
                    getattr(node.source, "line", None),
                )
            )
        name = str(item.get("name") or f"Series {idx}")
        values = item.get("values") or []
        if not isinstance(values, list):
            raise MddocxError(
                Diagnostic(
                    "error",
                    "CHART205",
                    f"Chart series '{name}' values must be a list.",
                    getattr(node.source, "file", None),
                    getattr(node.source, "line", None),
                )
            )
        numeric: list[object] = []
        for value in values:
            number = coerce_number(value)
            numeric.append(number if number is not None else 0.0)
        max_points = max(max_points, len(numeric))
        series.append((name, numeric))
    max_points = max(max_points, len(categories))
    if max_points > renderer.config.charts.max_points:
        raise MddocxError(
            Diagnostic(
                "error",
                "CHART206",
                f"Chart exceeds {renderer.config.charts.max_points} data points.",
                getattr(node.source, "file", None),
                getattr(node.source, "line", None),
            )
        )
    if not categories:
        categories = list(range(1, max_points + 1))
    if node.chart_type.lower() == "pie" and len(series) > 1:
        renderer.reporter.warn(
            "CHART207",
            "Pie charts use only the first series.",
            getattr(node.source, "file", None),
            getattr(node.source, "line", None),
        )
        series = series[:1]
    if node.chart_type.lower() == "scatter":
        converted: list[object] = []
        for value in categories:
            number = coerce_number(value)
            if number is None:
                raise MddocxError(
                    Diagnostic(
                        "error",
                        "CHART208",
                        "Scatter chart x/category values must be numeric.",
                        getattr(node.source, "file", None),
                        getattr(node.source, "line", None),
                    )
                )
            converted.append(number)
        categories = converted
    secondary = tuple(name for name in node.secondary_series if name in {n for n, _ in series})
    unknown_secondary = [
        name for name in node.secondary_series if name not in {n for n, _ in series}
    ]
    for name in unknown_secondary:
        renderer.reporter.warn(
            "CHART209",
            f"Secondary-axis series was not found: {name}",
            getattr(node.source, "file", None),
            getattr(node.source, "line", None),
        )
    if secondary and node.chart_type.lower() not in {"column", "bar", "line"}:
        renderer.reporter.warn(
            "CHART210",
            f"Secondary axes are not supported for {node.chart_type} charts; using the primary axis.",
            getattr(node.source, "file", None),
            getattr(node.source, "line", None),
        )
        secondary = ()
    return ChartEntry(
        token="",
        chart_type=node.chart_type,
        title=node.title,
        categories=categories,
        series=series,
        width_mm=node.width_mm or renderer.config.charts.default_width_mm,
        height_mm=node.height_mm or renderer.config.charts.default_height_mm,
        alt_text=node.caption or node.title or "Chart",
        x_axis_title=node.x_axis_title,
        y_axis_title=node.y_axis_title,
        x_min=node.x_min,
        x_max=node.x_max,
        y_min=node.y_min,
        y_max=node.y_max,
        x_number_format=node.x_number_format,
        y_number_format=node.y_number_format,
        legend_position=node.legend_position,
        data_labels=node.data_labels,
        show_gridlines=node.show_gridlines,
        secondary_series=secondary,
        secondary_axis_title=node.secondary_axis_title,
        secondary_min=node.secondary_min,
        secondary_max=node.secondary_max,
        secondary_number_format=node.secondary_number_format,
        style=node.style,
    )
