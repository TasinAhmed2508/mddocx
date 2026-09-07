from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from lxml import etree

from mddocx import render_string
from mddocx.cli import main

C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"c": C, "a": A}

ADVANCED = '''```chart {#fig-advanced caption="Revenue and margin"}
type: column
title: Quarterly performance
categories: [Q1, Q2, Q3, Q4]
series:
  - name: Revenue
    values: [100, 120, 135, 150]
  - name: Margin
    values: [20, 24, 30, 32]
secondary_series: [Margin]
secondary_axis:
  title: Margin %
  min: 0
  max: 40
  number_format: '0'
legend: bottom
data_labels: true
gridlines: false
style: 10
x_axis:
  title: Quarter
y_axis:
  title: Revenue USD
  min: 0
  max: 200
  number_format: '0'
```
'''


def test_advanced_chart_emits_axis_titles_labels_style_legend_and_secondary_axes():
    blob = render_string(ADVANCED)
    with ZipFile(BytesIO(blob), "r") as zf:
        root = etree.fromstring(zf.read("word/charts/chart1.xml"))
    assert root.xpath("./c:style[@val='10']", namespaces=NS)
    assert root.xpath(".//c:dLbls/c:showVal[@val='1']", namespaces=NS)
    assert root.xpath(".//c:legend/c:legendPos[@val='b']", namespaces=NS)
    assert len(root.xpath(".//c:barChart", namespaces=NS)) == 2
    axes = root.xpath(".//c:valAx", namespaces=NS)
    assert len(axes) == 2
    assert root.xpath(".//c:valAx[c:axPos[@val='l']]/c:scaling/c:min[@val='0.0']", namespaces=NS)
    assert root.xpath(".//c:valAx[c:axPos[@val='l']]/c:scaling/c:max[@val='200.0']", namespaces=NS)
    assert root.xpath(".//c:valAx[c:axPos[@val='r']]/c:scaling/c:max[@val='40.0']", namespaces=NS)
    text = " ".join(root.xpath(".//a:t/text()", namespaces=NS))
    assert "Quarter" in text and "Revenue USD" in text and "Margin %" in text


def test_cli_v1_api_accessibility_and_benchmark(tmp_path, capsys):
    assert main(["api", "--json"]) == 0
    assert '"api_version": "1"' in capsys.readouterr().out

    docx = tmp_path / "good.docx"
    docx.write_bytes(render_string("# Report", config=None))
    assert main(["accessibility", str(docx)]) == 0
    assert "accessibility audit" in capsys.readouterr().out

    assert main(["benchmark", "--sections", "1", "--max-seconds", "30", "--max-peak-mb", "256"]) == 0
    assert "performance gate: PASS" in capsys.readouterr().out
