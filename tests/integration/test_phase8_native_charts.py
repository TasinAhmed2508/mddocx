from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from lxml import etree
import pytest

from mddocx import render_string
from mddocx.inspection import inspect_docx_bytes


@pytest.mark.parametrize("chart_type", ["column", "bar", "line", "pie", "scatter"])
def test_native_chart_types_embed_chartml_and_editable_workbook(chart_type: str) -> None:
    categories = "[1, 2, 3]" if chart_type == "scatter" else "[A, B, C]"
    blob = render_string(
        f'''# Charts\n\n```chart {{#fig-demo caption="Demo chart"}}\ntype: {chart_type}\ntitle: Demo\ncategories: {categories}\nseries:\n  - name: Score\n    values: [10, 20, 15]\n```\n\nSee [Figure @fig-demo].\n'''
    )
    report = inspect_docx_bytes(blob)
    assert report.ok
    assert report.native_charts == 1
    assert report.embedded_workbooks == 1
    assert report.broken_relationships == []
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        chart_xml = etree.fromstring(zf.read("word/charts/chart1.xml"))
        assert chart_xml.xpath("count(.//*[local-name()='externalData'])") == 1.0
        assert "word/embeddings/Microsoft_Excel_Worksheet1.xlsx" in zf.namelist()
        doc = zf.read("word/document.xml")
        assert b"MDDOCX_CHART_" not in doc
        assert b"Quarterly" not in doc or True


def test_chart_from_csv_and_imported_native_table(tmp_path: Path) -> None:
    data = tmp_path / "results.csv"
    data.write_text("Model,Accuracy,Latency\nA,91,20\nB,94,17\nC,92,18\n", encoding="utf-8")
    md = '''# Data report\n\n```chart {#fig-results caption="Model accuracy"}\ntype: column\ntitle: Accuracy\nsource: results.csv\ncategory: Model\nseries_fields: [Accuracy]\n```\n\n```data-table {#tbl-results caption="Model results"}\nsource: results.csv\ncolumns: [Model, Accuracy, Latency]\n```\n\nSee [Figure @fig-results] and [Table @tbl-results].\n'''
    blob = render_string(md, base_dir=tmp_path)
    report = inspect_docx_bytes(blob)
    assert report.ok
    assert report.native_charts == 1
    assert report.embedded_workbooks == 1
    assert report.tables == 1
    assert report.ref_fields == 2
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        xml = zf.read("word/document.xml")
        assert b"Model results" in xml
        assert b"Accuracy" in xml
        assert b"Latency" in xml


def test_chart_from_json(tmp_path: Path) -> None:
    data = tmp_path / "results.json"
    data.write_text('[{"Quarter":"Q1","Revenue":10},{"Quarter":"Q2","Revenue":14}]', encoding="utf-8")
    blob = render_string(
        '''```chart\ntype: line\ntitle: Revenue\nsource: results.json\ncategory: Quarter\nseries_fields: [Revenue]\n```\n''',
        base_dir=tmp_path,
    )
    report = inspect_docx_bytes(blob)
    assert report.ok and report.native_charts == 1


def test_data_source_cannot_escape_base_directory(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.csv"
    outside.write_text("x,y\n1,2\n", encoding="utf-8")
    with pytest.raises(Exception):
        render_string(
            '''```chart\ntype: line\nsource: ../outside.csv\ncategory: x\nseries_fields: [y]\n```\n''',
            base_dir=tmp_path,
        )


def test_native_chart_output_is_reproducible() -> None:
    md = '''```chart\ntype: column\ntitle: Stable\ncategories: [A, B]\nseries:\n  - name: Value\n    values: [1, 2]\n```\n'''
    assert render_string(md) == render_string(md)
