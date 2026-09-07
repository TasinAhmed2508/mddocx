from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
from typing import Any

from mddocx.diagnostics import Diagnostic, MddocxError


@dataclass(slots=True)
class TabularData:
    columns: list[str]
    rows: list[list[Any]]

    def column(self, name: str) -> list[Any]:
        try:
            idx = self.columns.index(name)
        except ValueError as exc:
            raise MddocxError(Diagnostic("error", "DATA204", f"Unknown data column: {name}")) from exc
        return [row[idx] if idx < len(row) else None for row in self.rows]


def load_tabular_data(path: Path, *, max_rows: int = 10_000, max_columns: int = 100) -> TabularData:
    path = Path(path)
    if not path.is_file():
        raise MddocxError(Diagnostic("error", "DATA201", f"Data source not found: {path.name}"))
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(path, max_rows=max_rows, max_columns=max_columns)
    if suffix == ".json":
        return _load_json(path, max_rows=max_rows, max_columns=max_columns)
    raise MddocxError(Diagnostic("error", "DATA202", f"Unsupported data format: {suffix or '<none>'}"))


def _load_csv(path: Path, *, max_rows: int, max_columns: int) -> TabularData:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise MddocxError(Diagnostic("error", "DATA203", f"Unable to read CSV data: {path.name}")) from exc
    if not rows:
        return TabularData([], [])
    columns = [str(v).strip() or f"Column {i + 1}" for i, v in enumerate(rows[0])]
    if len(columns) > max_columns:
        raise MddocxError(Diagnostic("error", "DATA205", f"Data source exceeds {max_columns} columns."))
    body = rows[1: max_rows + 1]
    if len(rows) - 1 > max_rows:
        raise MddocxError(Diagnostic("error", "DATA206", f"Data source exceeds {max_rows} rows."))
    normalized = [list(row) + [""] * max(0, len(columns) - len(row)) for row in body]
    return TabularData(columns, [row[: len(columns)] for row in normalized])


def _load_json(path: Path, *, max_rows: int, max_columns: int) -> TabularData:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MddocxError(Diagnostic("error", "DATA203", f"Unable to read JSON data: {path.name}")) from exc
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        rows_value = value["rows"]
    elif isinstance(value, list):
        rows_value = value
    else:
        raise MddocxError(Diagnostic("error", "DATA207", "JSON data must be an array of objects or an object with a 'rows' array."))
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
        raise MddocxError(Diagnostic("error", "DATA205", f"Data source exceeds {max_columns} columns."))
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
