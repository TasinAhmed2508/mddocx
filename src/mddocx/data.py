from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import csv
import json
from pathlib import Path
from typing import Any

from mddocx.ast.base import Node, SourcePosition
from mddocx.ast.block import DataTableBlock, Table, TableCell, TableRow
from mddocx.ast.inline import HardBreak, Text
from mddocx.config import RenderConfig
from mddocx.diagnostics import Diagnostic, MddocxError
from mddocx.table_grid import check_grid_size


@dataclass(slots=True)
class TabularData:
    columns: list[str]
    rows: list[list[Any]]

    def column_index(self, name: str) -> int:
        try:
            idx = self.columns.index(name)
        except ValueError as exc:
            raise MddocxError(
                Diagnostic("error", "DATA204", f"Unknown data column: {name}")
            ) from exc
        if name in self.columns[idx + 1 :]:
            raise MddocxError(Diagnostic("error", "DATA204", f"Ambiguous data column: {name}"))
        return idx

    def column(self, name: str) -> list[Any]:
        idx = self.column_index(name)
        return [row[idx] if idx < len(row) else None for row in self.rows]


def resolve_data_path(
    base_dir: str | Path | None, source_path: str, source: SourcePosition | None = None
) -> Path:
    base = Path(base_dir or ".").expanduser().resolve()
    target = (base / source_path).expanduser().resolve()
    if not target.is_relative_to(base):
        raise MddocxError(
            Diagnostic(
                "error",
                "DATA209",
                "Data source escapes the document base directory.",
                source.file if source else None,
                source.line if source else None,
            )
        )
    return target


def load_data_table(node: DataTableBlock, config: RenderConfig) -> Table:
    path = resolve_data_path(config.base_dir, node.source_path, node.source)
    data = load_tabular_data(
        path, max_rows=config.data.max_rows, max_columns=config.data.max_columns
    )
    columns = node.columns or data.columns
    check_grid_size(len(columns), len(data.rows) + 1, config.limits.max_table_cells, node.source)
    indices: Sequence[int] = range(len(columns))
    if node.columns:
        try:
            indices = [data.column_index(name) for name in columns]
        except MddocxError as exc:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "DATA208",
                    exc.diagnostic.message,
                    node.source.file if node.source else None,
                    node.source.line if node.source else None,
                )
            ) from exc
    rows = []
    if columns:
        rows.append(
            TableRow(cells=[_data_cell(name, header=True) for name in columns], header=True)
        )
        rows.extend(
            TableRow(cells=[_data_cell(raw[index]) for index in indices]) for raw in data.rows
        )
    return Table(rows=rows, identifier=node.identifier, caption=node.caption, source=node.source)


def _data_cell(value: Any, *, header: bool = False) -> TableCell:
    text = "" if value is None else str(value)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    children: list[Node] = [Text(text=lines[0])]
    for line in lines[1:]:
        children.extend((HardBreak(), Text(text=line)))
    return TableCell(children=children, header=header)


def load_tabular_data(path: Path, *, max_rows: int = 10_000, max_columns: int = 100) -> TabularData:
    path = Path(path)
    if not path.is_file():
        raise MddocxError(Diagnostic("error", "DATA201", f"Data source not found: {path.name}"))
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(path, max_rows=max_rows, max_columns=max_columns)
    if suffix == ".json":
        return _load_json(path, max_rows=max_rows, max_columns=max_columns)
    raise MddocxError(
        Diagnostic("error", "DATA202", f"Unsupported data format: {suffix or '<none>'}")
    )


def _load_csv(path: Path, *, max_rows: int, max_columns: int) -> TabularData:
    rows: list[list[Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            width = len(header)
            if width > max_columns:
                raise MddocxError(
                    Diagnostic("error", "DATA205", f"Data source exceeds {max_columns} columns.")
                )
            for row in reader:
                if len(rows) >= max_rows:
                    raise MddocxError(
                        Diagnostic("error", "DATA206", f"Data source exceeds {max_rows} rows.")
                    )
                width = max(width, len(row))
                if width > max_columns:
                    raise MddocxError(
                        Diagnostic(
                            "error", "DATA205", f"Data source exceeds {max_columns} columns."
                        )
                    )
                rows.append(row)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise MddocxError(
            Diagnostic("error", "DATA203", f"Unable to read CSV data: {path.name}")
        ) from exc
    header.extend([""] * (width - len(header)))
    columns = [name.strip() or f"Column {index + 1}" for index, name in enumerate(header)]
    for row in rows:
        row.extend([""] * (width - len(row)))
    return TabularData(columns, rows)


def _load_json(path: Path, *, max_rows: int, max_columns: int) -> TabularData:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MddocxError(
            Diagnostic("error", "DATA203", f"Unable to read JSON data: {path.name}")
        ) from exc
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        rows_value = value["rows"]
    elif isinstance(value, list):
        rows_value = value
    else:
        raise MddocxError(
            Diagnostic(
                "error",
                "DATA207",
                "JSON data must be an array of objects or an object with a 'rows' array.",
            )
        )
    if len(rows_value) > max_rows:
        raise MddocxError(Diagnostic("error", "DATA206", f"Data source exceeds {max_rows} rows."))
    if not rows_value:
        return TabularData([], [])
    if not all(isinstance(row, dict) for row in rows_value):
        raise MddocxError(Diagnostic("error", "DATA207", "JSON data rows must be objects."))
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows_value:
        for key in row.keys():
            name = str(key)
            if name not in seen:
                seen.add(name)
                columns.append(name)
    if len(columns) > max_columns:
        raise MddocxError(
            Diagnostic("error", "DATA205", f"Data source exceeds {max_columns} columns.")
        )
    rows = [[row.get(col, "") for col in columns] for row in rows_value]
    return TabularData(columns, rows)


def coerce_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
