from io import BytesIO
import json
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from lxml import etree
import pytest

from mddocx import Compiler, RenderConfig
from mddocx.ast.base import iter_nodes
from mddocx.ast.block import CodeBlock, Heading, Table
from mddocx.ast.codec import document_from_json
from mddocx.ast.inline import InlineCode, InlineMath
from mddocx.cli import main
from mddocx.diagnostics import MddocxError
from mddocx.interactive.shell import InteractiveConsole
from mddocx.math.preflight import inspect_math
from mddocx.ooxml.package import read_parts, write_parts


def test_shell_lists_direct_children_and_refreshes(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    child = root / "subdir"
    child.mkdir()
    nested = child / "deep"
    nested.mkdir()
    for index in range(1000):
        (nested / f"chapter-{index}.md").touch()
    (child / "inside.markdown").touch()
    (root / "Report.MD").touch()
    (root / "notes.mkd").touch()
    original = Path.iterdir
    visits = []

    def list_directory(path):
        visits.append(path)
        return original(path)

    monkeypatch.setattr(Path, "iterdir", list_directory)
    shell = InteractiveConsole(root, writer=lambda _: None)
    assert [p.name for p in shell.summary.markdown_files] == ["notes.mkd", "Report.MD"]
    assert len(shell._matching_files({".md", ".mkd"})) == 2
    assert visits == [root, root]
    shell.cmd_cd(["subdir"])
    assert shell.summary.markdown_files == (child / "inside.markdown",)
    shell.cmd_cd(["deep"])
    assert len(shell.summary.markdown_files) == 1000


def test_pipe_table_preserves_extra_cell_and_code_pipe(tmp_path):
    source = tmp_path / "report.md"
    source.write_text(
        "# Report\n\n| Food | Math |\n| --- | --- |\n| A | `x|y` | extra |\n| B |\nordinary prose\n",
        encoding="utf-8",
    )
    output = source.with_suffix(".docx")
    compiler = Compiler()
    result = compiler.compile_file(source, output)
    assert [(d.code, d.line) for d in result.diagnostics] == [("TABLE201", 5)]
    doc = Document(BytesIO(result.output_bytes))
    assert [c.text for c in doc.tables[0].rows[1].cells] == ["A", "x|y", "extra"]
    assert [c.text for c in doc.tables[0].rows[2].cells] == ["B", "", ""]
    assert doc.paragraphs[-1].text == "ordinary prose"
    assert compiler.verify(source, output).ok


def test_adjacent_tables_keep_their_own_word_grids(tmp_path):
    source = tmp_path / "report.md"
    source.write_text(
        "| A |\n| --- |\n| first |\n| B | C |\n| --- | --- |\n| second | third |",
        encoding="utf-8",
    )
    output = source.with_suffix(".docx")
    compiler = Compiler()
    compiler.compile_file(source, output)
    body = Document(output)._element.body
    assert [child.tag for child in body] == [
        qn(name) for name in ("w:tbl", "w:p", "w:tbl", "w:sectPr")
    ]
    assert compiler.verify(source, output).ok


def test_fixed_width_table_stops_at_real_block_and_leaves_fence_alone():
    data = "Name     Value\n----     -----\nitem     here\n"
    document = Compiler().parse_string(data + "# Heading\n\n~~~text\n" + data + "~~~").document
    table, heading, code = document.children
    assert isinstance(table, Table) and table.rows[1].source.line == 3
    assert isinstance(heading, Heading) and heading.source.line == 4
    assert isinstance(code, CodeBlock) and code.code == data.rstrip()


def test_native_html_spans_and_verify_drift(tmp_path):
    source = tmp_path / "report.md"
    source.write_text(
        "<table><caption>Results</caption><thead><tr><th colspan='2'>Summary</th></tr></thead>\n"
        "<tbody><tr><td rowspan='2'><strong>Bangla বাংলা</strong></td><td>A<br>B</td></tr>\n"
        "<tr><td>C</td></tr></tbody></table>\n# Following\n",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.fonts.bengali = None
    compiler = Compiler(config)
    output = source.with_suffix(".docx")
    blob = compiler.compile_file(source, output).output_bytes
    table = Document(BytesIO(blob)).tables[0]
    assert table.cell(1, 0).text == table.cell(2, 0).text == "Bangla বাংলা"
    assert table.cell(1, 1).text == "A\nB"
    report = compiler.verify(source, output)
    assert report.ok, report.findings
    parts = read_parts(blob)
    root = etree.fromstring(parts["word/document.xml"])
    marker = next(root.iter(qn("w:tblHeader")))
    marker.getparent().remove(marker)
    parts["word/document.xml"] = etree.tostring(root)
    assert not compiler.verify(source, write_parts(parts)).ok


@pytest.mark.parametrize("kind", ["html", "layout-table"])
def test_vertical_merges_over_a_thousand_rows_render_and_verify(tmp_path, kind):
    height = 1061
    if kind == "html":
        body = "<tr><td>Reading</td></tr>\n" * (height - 1)
        text = (
            '<table><tbody><tr><td rowspan="0">Station</td><td>First</td></tr>\n'
            + body
            + "</tbody></table>\n"
        )
    else:
        rows = '  - ["", "Reading"]\n' * (height - 1)
        text = (
            '```layout-table\nrows:\n  - ["Station", "First\\nSample"]\n'
            + rows
            + f"merges: [{{from: [0, 0], to: [{height - 1}, 0]}}]\n```\n"
        )
    source = tmp_path / "long.md"
    source.write_text(text, encoding="utf-8")
    compiler = Compiler()
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    parts = read_parts(blob)
    root = etree.fromstring(parts["word/document.xml"])
    rows = list(root.iter(qn("w:tr")))
    merges = list(root.iter(qn("w:vMerge")))
    assert len(rows) == height
    assert [merge.get(qn("w:val"), "continue") for merge in merges] == ["restart"] + [
        "continue"
    ] * (height - 1)
    assert "".join(rows[-1].itertext()) == "Reading"
    assert compiler.verify(source, blob).ok
    body = root.find(qn("w:body"))
    body.insert(len(body) - 1, etree.Element(qn("w:p")))
    parts["word/document.xml"] = etree.tostring(root)
    assert compiler.verify(source, write_parts(parts)).ok
    merges[-1].getparent().remove(merges[-1])
    parts["word/document.xml"] = etree.tostring(root)
    assert any(
        finding.code == "VERIFY303"
        for finding in compiler.verify(source, write_parts(parts)).findings
    )


@pytest.mark.parametrize("custom_border", [False, True])
def test_shaded_merged_header_boundaries_use_the_grid_style(tmp_path, custom_border):
    config = RenderConfig(theme="report")
    if custom_border:
        template = Document()
        style = template.styles["Table Grid"]._element
        edge = style.find("./w:tblPr/w:tblBorders/w:insideH", style.nsmap)
        edge.set(qn("w:val"), "nil")
        config.template = tmp_path / "template.docx"
        template.save(config.template)
    source = (
        '<table><thead><tr><th rowspan="2">Region</th><th colspan="2">Readings</th></tr>'
        "<tr><th>Low</th><th>High</th></tr></thead>"
        "<tbody><tr><td>A</td><td>1</td><td>2</td></tr></tbody></table>"
    )
    blob = Compiler(config).compile_string(source).output_bytes
    root = etree.fromstring(read_parts(blob)["word/document.xml"])
    borders = list(root.iter(qn("w:tcBorders")))
    if custom_border:
        assert not borders
    else:
        assert len(borders) == 2
        assert [border.find(qn("w:bottom")).get(qn("w:sz")) for border in borders] == ["8", "8"]


def test_html_row_groups_keep_merges_headers_and_footer_order(tmp_path):
    source = tmp_path / "groups.md"
    source.write_text(
        '<table><thead><tr><th rowspan="0">Station</th><th colspan="2">Readings</th></tr>\n'
        "<tr><th>Minimum</th><th>Maximum</th></tr></thead>\n"
        '<tfoot><tr><th colspan="2">Total</th><td>4</td></tr></tfoot>\n'
        '<tbody><tr><td rowspan="0">A</td><td>1</td><td>2</td></tr>\n'
        "<tr><td>2</td><td>3</td></tr></tbody>\n"
        "<tbody><tr><td>B</td><td>3</td><td>4</td></tr></tbody></table>\n",
        encoding="utf-8",
    )
    compiler = Compiler()
    output = source.with_suffix(".docx")
    docx = Document(BytesIO(compiler.compile_file(source, output).output_bytes))
    (table,) = docx.tables
    assert [row.cells[0].text for row in table.rows] == [
        "Station",
        "Station",
        "A",
        "A",
        "B",
        "Total",
    ]
    assert table.cell(0, 1).text == table.cell(0, 2).text == "Readings"
    assert all(
        row._tr.find("./w:trPr/w:tblHeader", row._tr.nsmap) is not None for row in table.rows[:2]
    )
    assert table.rows[-1]._tr.find("./w:trPr/w:tblHeader", table._tbl.nsmap) is None
    assert compiler.verify(source, output).ok


def test_html_cell_math_leaves_markup_code_and_link_targets_intact(tmp_path):
    source = tmp_path / "formulas.md"
    markdown = (
        "<table><tbody><tr><td><code>\\(literal $x$</code> and <strong>\\(\\frac{1}{2}\\)</strong>\n"
        '<a href="https://example.com/?q=$x$">Review</a></td>\n'
        "<td>\\[x&lt;y\\]<br>$z_2$<p>\n$$\n\\sqrt{x^2+1}\n$$\n</p></td></tr></tbody></table>\n"
        "# Following\n"
    )
    source.write_text(markdown, encoding="utf-8")
    preflight = inspect_math(markdown, source_file=str(source))
    assert preflight.native == 4 and not preflight.syntax_issues
    compiler = Compiler()
    output = source.with_suffix(".docx")
    blob = compiler.compile_file(source, output).output_bytes
    parts = read_parts(blob)
    root = etree.fromstring(parts["word/document.xml"])
    assert len(list(root.iter(qn("m:oMath")))) == 4
    assert r"\(literal $x$" in "".join(root.itertext())
    assert b"MDDOCXMATH" not in parts["word/document.xml"]
    relationships = etree.fromstring(parts["word/_rels/document.xml.rels"])
    assert any(rel.get("Target") == "https://example.com/?q=$x$" for rel in relationships)
    assert compiler.verify(source, blob).ok
    math = next(root.iter(qn("m:oMath")))
    math.getparent().remove(math)
    parts["word/document.xml"] = etree.tostring(root)
    assert any(
        finding.code == "VERIFY303"
        for finding in compiler.verify(source, write_parts(parts)).findings
    )


def test_math_preflight_counts_unclosed_cell_delimiters_but_ignores_literal_code():
    report = inspect_math(
        "<table><tr><td><code>\\(literal</code>\n<span>\\(unclosed</span>\n</td></tr></table>"
    )
    (issue,) = report.syntax_issues
    assert issue.line == 2 and "Unterminated table math delimiter" in issue.message


@pytest.mark.parametrize(
    "source, literal",
    [
        (r"- > <table><tr><td><code>$value$</code> \(x\)</td></tr></table>", "$value$"),
        (
            "<table><tr><td><code>\n```\n$value$\n```\n</code> \\(x\\)</td></tr></table>\n# After",
            "\n```\n$value$\n```\n",
        ),
    ],
)
def test_html_table_boundary_keeps_literal_code_and_cell_math(source, literal):
    parsed = Compiler().parse_string(source)
    nodes = list(iter_nodes(parsed.document))
    assert not parsed.diagnostics
    assert [node.code for node in nodes if isinstance(node, InlineCode)] == [literal]
    assert [node.source_text for node in nodes if isinstance(node, InlineMath)] == ["x"]


def test_invalid_html_preserves_source_and_v2_ast_uses_unit_spans():
    report = Compiler().parse_string("<table><tr><td rowspan='3'>keep me</td></tr></table>")
    assert report.diagnostics[0].code == "TABLE202"
    assert "keep me" in report.document.children[0].children[0].text
    cell = {"__node__": "TableCell", "children": []}
    payload = {
        "schema": "mddocx-ast",
        "version": 2,
        "document": {
            "__node__": "Document",
            "children": [
                {"__node__": "Table", "rows": [{"__node__": "TableRow", "cells": [cell]}]}
            ],
        },
    }
    decoded = document_from_json(json.dumps(payload))
    restored = decoded.children[0].rows[0].cells[0]
    assert restored.row_span == restored.column_span == 1


@pytest.mark.parametrize(
    "text",
    [
        '<table><tr><td colspan="4">Wide</td></tr></table>',
        '```layout-table\nrows: [["Wide", "", "", ""]]\nmerges: [{from: [0,0], to: [0,3]}]\n```',
    ],
)
def test_table_over_budget_keeps_previous_docx(tmp_path, text):
    source = tmp_path / "report.md"
    output = source.with_suffix(".docx")
    output.write_bytes(b"previous")
    source.write_text(text, encoding="utf-8")
    config = RenderConfig()
    config.limits.max_table_cells = 3
    with pytest.raises(MddocxError, match="LIMIT404"):
        Compiler(config).compile_file(source, output)
    assert output.read_bytes() == b"previous"


def test_csv_table_retains_duplicate_columns_extra_values_and_line_breaks(tmp_path):
    data = tmp_path / "survey.csv"
    data.write_bytes(b'Site,Reading,Reading\r\nA,10,20,late value\r\nB,"First\r\nSecond",30\r\n')
    source = tmp_path / "report.md"
    source.write_text(
        "# Before\n\n~~~data-table\nsource: survey.csv\n~~~\n\n# After\n", encoding="utf-8"
    )
    config = RenderConfig(theme="report")
    config.table.auto_landscape = True
    config.table.landscape_min_columns = 4
    compiler = Compiler(config)
    output = source.with_suffix(".docx")
    blob = compiler.compile_file(source, output).output_bytes
    word = Document(output)
    assert [[cell.text for cell in row.cells] for row in word.tables[0].rows] == [
        ["Site", "Reading", "Reading", "Column 4"],
        ["A", "10", "20", "late value"],
        ["B", "First\nSecond", "30", ""],
    ]
    assert [section.page_width > section.page_height for section in word.sections] == [
        False,
        True,
        False,
    ]
    assert compiler.verify(source, output).ok

    parts = read_parts(blob)
    parts["word/document.xml"] = parts["word/document.xml"].replace(b"late value", b"lost value")
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.line, finding.part) == ("VERIFY303", 3, "word/document.xml")
    data.write_bytes(data.read_bytes().replace(b"late value", b"new value"))
    assert not compiler.verify(source, output).ok


def test_explicit_column_selection_reports_duplicate_header_and_can_recover(tmp_path):
    (tmp_path / "survey.csv").write_text("Reading,Reading\n10,20\n", encoding="utf-8")
    source = tmp_path / "report.md"
    source.write_text(
        "~~~data-table\nsource: survey.csv\ncolumns: [Reading]\n~~~\n", encoding="utf-8"
    )
    output = source.with_suffix(".docx")
    with pytest.raises(MddocxError, match="DATA208.*Ambiguous data column: Reading"):
        Compiler().compile_file(source, output)
    assert not output.exists()
    recovered = Compiler(RenderConfig(recover=True)).compile_file(source, output)
    assert recovered.recovered
    assert "DATA208" in Document(output).paragraphs[0].text


def test_csv_data_width_and_grid_budgets_keep_previous_docx(tmp_path):
    (tmp_path / "survey.csv").write_text("A,B\n1,2,3\n", encoding="utf-8")
    source = tmp_path / "report.md"
    source.write_text("~~~data-table\nsource: survey.csv\n~~~\n", encoding="utf-8")
    output = source.with_suffix(".docx")
    original = Compiler().compile_file(source, output).output_bytes
    config = RenderConfig()
    config.data.max_columns = 2
    with pytest.raises(MddocxError, match="DATA205"):
        Compiler(config).compile_file(source, output)
    config.data.max_columns = 3
    config.limits.max_table_cells = 5
    with pytest.raises(MddocxError, match="LIMIT404"):
        Compiler(config).compile_file(source, output)
    assert output.read_bytes() == original


def test_verify_imported_json_uses_explicit_base_and_checks_containment(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "survey.json").write_text(
        '[{"Site":"A","Reading":2,"Status":null}]', encoding="utf-8"
    )
    (tmp_path / "other.json").write_text('[{"Site":"B","Status":"x"}]', encoding="utf-8")
    source = tmp_path / "report.md"
    source.write_text(
        "~~~data-table\nsource: survey.json\ncolumns: [Status, Site]\n~~~\n", encoding="utf-8"
    )
    compiler = Compiler(RenderConfig(base_dir=data_dir))
    output = source.with_suffix(".docx")
    compiler.compile_file(source, output)
    assert compiler.verify(source, output).ok
    rows = Document(output).tables[0].rows
    assert [[cell.text for cell in row.cells] for row in rows] == [["Status", "Site"], ["", "A"]]
    source.write_text(
        source.read_text(encoding="utf-8").replace("survey.json", "../other.json"),
        encoding="utf-8",
    )
    with pytest.raises(MddocxError, match="DATA209"):
        compiler.verify(source, output)


def test_json_conversion_recovery_and_batch_outcomes(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text("# Report", encoding="utf-8")
    recovered = tmp_path / "recovered.md"
    recovered.write_text("~~~chart\nseries: broken\n~~~", encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text("---\ntitle: [\n---", encoding="utf-8")
    out = tmp_path / "out"
    for paths, code, states in (
        ([good], 0, ["ok"]),
        ([recovered], 3, ["recovered"]),
        ([recovered, good, bad], 2, ["failed", "ok", "recovered"]),
    ):
        assert (
            main([*(str(p) for p in paths), "--output-dir", str(out), "--recover", "--json"])
            == code
        )
        result = json.loads(capsys.readouterr().out)
        assert result["exit_code"] == code
        assert [r["status"] for r in result["results"]] == states
