"""Data surfaces: base-directory containment and imported data tables."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mddocx.ast.block import DataTableBlock, Table, TableCell, TableRow
from mddocx.ast.inline import Text
from mddocx.data import load_tabular_data
from mddocx.diagnostics import Diagnostic, MddocxError

from . import citations, tables

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def resolve_data_path(renderer: DocxRenderer, source_path: str, source_meta=None) -> Path:
    base = Path(renderer.config.base_dir or ".").expanduser().resolve()
    target = (base / source_path).expanduser().resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise MddocxError(
            Diagnostic(
                "error",
                "DATA209",
                "Data source escapes the document base directory.",
                getattr(source_meta, "file", None),
                getattr(source_meta, "line", None),
            )
        ) from exc
    return target


def render_data_table(renderer: DocxRenderer, node: DataTableBlock) -> None:
    path = resolve_data_path(renderer, node.source_path, node.source)
    data = load_tabular_data(
        path,
        max_rows=renderer.config.data.max_rows,
        max_columns=renderer.config.data.max_columns,
    )
    columns = list(node.columns) or list(data.columns)
    for name in columns:
        if name not in data.columns:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "DATA208",
                    f"Unknown data-table column: {name}",
                    getattr(node.source, "file", None),
                    getattr(node.source, "line", None),
                )
            )
    rows = [
        TableRow(
            cells=[TableCell(children=[Text(text=name)], header=True) for name in columns],
            header=True,
        )
    ]
    indices = [data.columns.index(name) for name in columns]
    for raw in data.rows:
        cells = [
            TableCell(
                children=[Text(text="" if idx >= len(raw) or raw[idx] is None else str(raw[idx]))]
            )
            for idx in indices
        ]
        rows.append(TableRow(cells=cells))
    table_node = Table(
        rows=rows, identifier=node.identifier, caption=node.caption, source=node.source
    )
    caption = (
        (node.caption or ("Table" if node.identifier else None))
        if renderer.config.references.captions
        else None
    )
    if caption and renderer.config.references.table_caption_position == "above":
        citations.render_caption(renderer, "Table", caption, node.identifier)
    tables.render_table_with_layout(renderer, table_node)
    if caption and renderer.config.references.table_caption_position == "below":
        citations.render_caption(renderer, "Table", caption, node.identifier)
    renderer.reporter.info(
        "DATA100",
        f"Rendered {len(data.rows)} rows from {Path(node.source_path).name} as a native Word table.",
        getattr(node.source, "file", None),
        getattr(node.source, "line", None),
    )
