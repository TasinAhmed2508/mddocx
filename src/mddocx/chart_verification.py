"""Read the data stored in a native Word chart independently of its emitter."""

from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .config import ValidationConfig
from .ooxml.charts import C, ChartEntry

_C = "{" + C + "}"
_KINDS = {
    "column": "barChart",
    "bar": "barChart",
    "line": "lineChart",
    "pie": "pieChart",
    "scatter": "scatterChart",
}


def _numeric(value) -> Decimal:
    number = Decimal(format(float(value), ".16g"))
    if not number.is_finite():
        raise ValueError("Non-finite chart value.")
    return number


def _points(series, path, expected, formula, *, numeric=False) -> bool:
    reference = series.find(path)
    if reference is None:
        return False
    if reference.findtext(_C + "f", "").replace("'Sheet1'!", "Sheet1!") != formula:
        return False
    cache = reference.find(_C + ("numCache" if numeric else "strCache"))
    if cache is None:
        return False
    count = cache.find(_C + "ptCount")
    if count is None or count.get("val") != str(len(expected)):
        return False
    points = cache.findall(_C + "pt")
    actual = {}
    for point in points:
        index = int(point.get("idx", "-1"))
        if index in actual or not 0 <= index < len(expected):
            return False
        actual[index] = point.findtext(_C + "v", "")
    normalize = _numeric if numeric else lambda value: "" if value is None else str(value)
    for index, value in enumerate(expected):
        found = actual.get(index, "")
        if value is None:
            if found != "":
                return False
        elif normalize(found) != normalize(value):
            return False
    return True


def chart_data_issue(root: etree._Element, entry: ChartEntry) -> str | None:
    kind = entry.chart_type.lower()
    plot = root.find(f".//{_C}plotArea")
    if plot is None:
        return "Missing chart plot."
    plots = [child for child in plot if etree.QName(child).localname.endswith("Chart")]
    if not plots or any(etree.QName(child).localname != _KINDS.get(kind) for child in plots):
        return "Chart type changed."
    if kind in {"column", "bar"} and any(
        child.find(_C + "barDir") is None
        or child.find(_C + "barDir").get("val") != ("col" if kind == "column" else "bar")
        for child in plots
    ):
        return "Chart bar orientation changed."
    series = [item for child in plots for item in child.findall(_C + "ser")]
    if len(series) != len(entry.series):
        return "Chart series count changed."
    try:
        indexed = {}
        for item in series:
            index_node = item.find(_C + "idx")
            index = int(index_node.get("val", "-1")) if index_node is not None else -1
            order = item.find(_C + "order")
            if index in indexed or order is None or order.get("val") != str(index):
                return "Chart series order changed."
            indexed[index] = item
        for index, (name, values) in enumerate(entry.series):
            item = indexed.get(index)
            if item is None:
                return f"Chart series {index + 1} is missing."
            column = get_column_letter(index + 2)
            end = len(entry.categories) + 1
            if not _points(item, f"{_C}tx/{_C}strRef", [name], f"Sheet1!${column}$1"):
                return f"Chart series {index + 1} name changed."
            category_path = f"{_C}xVal/{_C}numRef" if kind == "scatter" else f"{_C}cat/{_C}strRef"
            value_path = f"{_C}yVal/{_C}numRef" if kind == "scatter" else f"{_C}val/{_C}numRef"
            if not _points(
                item,
                category_path,
                entry.categories,
                f"Sheet1!$A$2:$A${end}",
                numeric=kind == "scatter",
            ):
                return f"Chart series {index + 1} categories changed."
            if not _points(
                item, value_path, values, f"Sheet1!${column}$2:${column}${end}", numeric=True
            ):
                return f"Chart series {index + 1} values changed."
    except (ValueError, InvalidOperation):
        return "Chart contains invalid point indexes or values."
    return None


def workbook_data_issue(blob: bytes, entry: ChartEntry, limits: ValidationConfig) -> str | None:
    try:
        with ZipFile(BytesIO(blob)) as package:
            parts = package.infolist()
            if (
                len(parts) > limits.max_package_parts
                or sum(part.file_size for part in parts) > limits.max_total_uncompressed_size
                or any(part.file_size > limits.max_xml_part_size for part in parts)
            ):
                return "Chart workbook exceeds package limits."
        workbook = load_workbook(BytesIO(blob), read_only=True, data_only=False, keep_links=False)
        try:
            if "Sheet1" not in workbook.sheetnames:
                return "Chart workbook data sheet is missing."
            sheet = workbook["Sheet1"]
            rows = max([len(entry.categories), *(len(values) for _, values in entry.series)])
            expected = [["Category", *(name for name, _ in entry.series)]]
            for row in range(rows):
                expected.append(
                    [
                        entry.categories[row] if row < len(entry.categories) else None,
                        *(values[row] if row < len(values) else None for _, values in entry.series),
                    ]
                )
            for row_index, (wanted, actual) in enumerate(
                zip(
                    expected,
                    sheet.iter_rows(
                        min_row=1, max_row=rows + 1, min_col=1, max_col=len(entry.series) + 1
                    ),
                    strict=True,
                ),
                1,
            ):
                for column, (value, cell) in enumerate(zip(wanted, actual, strict=True), 1):
                    found = cell.value
                    if isinstance(value, (float, int)) and not isinstance(value, bool):
                        equal = found is not None and _numeric(found) == _numeric(value)
                    else:
                        equal = (found if found is not None else "") == (
                            value if value is not None else ""
                        )
                    if not equal:
                        return f"Chart workbook row {row_index}, column {column} changed."
        finally:
            workbook.close()
    except Exception as exc:
        return f"Chart workbook could not be read ({type(exc).__name__})."
    return None
