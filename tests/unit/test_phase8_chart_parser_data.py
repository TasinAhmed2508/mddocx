from __future__ import annotations

from pathlib import Path

import pytest

from mddocx.ast.block import ChartBlock, DataTableBlock
from mddocx.data import load_tabular_data
from mddocx.parser import MarkdownParser


def test_chart_and_data_table_fences_parse_to_semantic_nodes() -> None:
    doc = MarkdownParser().parse(
        '''```chart {#fig-sales caption="Quarterly sales"}\ntype: line\ntitle: Sales\ncategories: [Q1, Q2]\nseries:\n  Revenue: [10, 12]\n```\n\n```data-table {#tbl-data caption="Imported data"}\nsource: data/results.csv\ncolumns: [Model, Score]\n```\n'''
    )
    chart = next(x for x in doc.children if isinstance(x, ChartBlock))
    assert chart.identifier == "fig-sales"
    assert chart.chart_type == "line"
    assert chart.title == "Sales"
    assert chart.series[0]["name"] == "Revenue"
    table = next(x for x in doc.children if isinstance(x, DataTableBlock))
    assert table.source_path == "data/results.csv"
    assert table.columns == ("Model", "Score")


def test_csv_and_json_loaders_are_deterministic(tmp_path: Path) -> None:
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Name,Score\nA,91\nB,94\n", encoding="utf-8")
    csv_data = load_tabular_data(csv_path)
    assert csv_data.columns == ["Name", "Score"]
    assert csv_data.rows == [["A", "91"], ["B", "94"]]

    json_path = tmp_path / "data.json"
    json_path.write_text('[{"Name":"A","Score":91},{"Name":"B","Score":94}]', encoding="utf-8")
    json_data = load_tabular_data(json_path)
    assert json_data.columns == ["Name", "Score"]
    assert json_data.rows == [["A", 91], ["B", 94]]


def test_data_loader_rejects_unknown_formats(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(Exception):
        load_tabular_data(path)
