"""Normalize chart declarations for rendering and offline verification."""

from math import isfinite

from .ast.block import ChartBlock
from .config import RenderConfig
from .data import coerce_number, load_tabular_data, resolve_data_path
from .diagnostics import Diagnostic, DiagnosticReporter, MddocxError
from .ooxml.charts import ChartEntry


def prepare_chart_entry(
    node: ChartBlock, config: RenderConfig, reporter: DiagnosticReporter
) -> ChartEntry:
    categories = list(node.categories)
    raw_series = list(node.series)
    if node.source_path:
        path = resolve_data_path(config.base_dir, node.source_path, node.source)
        data = load_tabular_data(
            path,
            max_rows=config.data.max_rows,
            max_columns=config.data.max_columns,
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
    if len(raw_series) > config.charts.max_series:
        raise MddocxError(
            Diagnostic(
                "error",
                "CHART204",
                f"Chart exceeds {config.charts.max_series} series.",
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
        values = item.get("values")
        if values is None:
            values = []
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
        for point, value in enumerate(values, start=1):
            if value is None or isinstance(value, str) and not value.strip():
                numeric.append(None)
                continue
            try:
                number = coerce_number(value)
            except (TypeError, ValueError, OverflowError):
                number = None
            if number is None or not isfinite(number):
                raise MddocxError(
                    Diagnostic(
                        "error",
                        "CHART205",
                        f"Chart series '{name}', point {point} must be a finite number or blank.",
                        getattr(node.source, "file", None),
                        getattr(node.source, "line", None),
                    )
                )
            numeric.append(number)
        max_points = max(max_points, len(numeric))
        series.append((name, numeric))
    max_points = max(max_points, len(categories))
    if max_points > config.charts.max_points:
        raise MddocxError(
            Diagnostic(
                "error",
                "CHART206",
                f"Chart exceeds {config.charts.max_points} data points.",
                getattr(node.source, "file", None),
                getattr(node.source, "line", None),
            )
        )
    if not categories:
        categories = list(range(1, max_points + 1))
    else:
        categories.extend([None] * (max_points - len(categories)))
    for _, values in series:
        values.extend([None] * (max_points - len(values)))
    if node.chart_type.lower() == "pie" and len(series) > 1:
        reporter.warn(
            "CHART207",
            "Pie charts use only the first series.",
            getattr(node.source, "file", None),
            getattr(node.source, "line", None),
        )
        series = series[:1]
    if node.chart_type.lower() == "scatter":
        converted: list[object] = []
        for value in categories:
            if value is None or isinstance(value, str) and not value.strip():
                converted.append(None)
                continue
            try:
                number = coerce_number(value)
            except (TypeError, ValueError, OverflowError):
                number = None
            if number is None or not isfinite(number):
                raise MddocxError(
                    Diagnostic(
                        "error",
                        "CHART208",
                        "Scatter chart x/category values must be finite numbers or blank.",
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
        reporter.warn(
            "CHART209",
            f"Secondary-axis series was not found: {name}",
            getattr(node.source, "file", None),
            getattr(node.source, "line", None),
        )
    if secondary and node.chart_type.lower() not in {"column", "bar", "line"}:
        reporter.warn(
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
        width_mm=node.width_mm or config.charts.default_width_mm,
        height_mm=node.height_mm or config.charts.default_height_mm,
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
