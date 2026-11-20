import json

from docx import Document
from lxml import etree
from PIL import Image
import pytest

from mddocx import Compiler, RenderConfig
from mddocx.cli import main
from mddocx.inspection import NS
from mddocx.ooxml import bangla
from mddocx.ooxml.package import read_parts, write_parts


@pytest.fixture
def reference(tmp_path):
    Image.new("RGB", (8, 8), "white").save(tmp_path / "tile.png")
    source = tmp_path / "reference.md"
    source.write_text(
        "# Report {#report}\n\n"
        "First paragraph.  \nSecond line with [a link](https://example.com) and $x^2$.\n\n"
        "1. Ordered\n   - Nested\n\n"
        "| Column | Another |\n| --- | --- |\n| Cell<br>line | Value |\n\n"
        "![Tile alt](tile.png)\n\n[Back](#report)\n",
        encoding="utf-8",
    )
    docx = source.with_suffix(".docx")
    Compiler().compile_file(source, docx)
    return source, docx


def test_clean_document_verifies_offline(reference, monkeypatch, capsys):
    source, docx = reference

    def forbidden(*args, **kwargs):
        pytest.fail("verification attempted to render or launch a process")

    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("mddocx.MarkdownWord._render_document", forbidden)
    assert main(["verify", str(source), str(docx), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] and report["checked_units"] == 7


@pytest.mark.parametrize(
    ("query", "attribute", "value"),
    [
        (".//w:p[w:r/w:t='First paragraph.']", None, None),
        (".//w:t[text()='Cell']", "text", "Edited"),
        (".//m:oMath", None, None),
        (".//m:oMath//m:t[text()='x']", "text", "z"),
        (".//wp:docPr", "descr", ""),
    ],
)
def test_independent_edits_report_drift(reference, query, attribute, value):
    source, docx = reference
    parts = read_parts(docx.read_bytes())
    root = etree.fromstring(parts["word/document.xml"])
    target = root.xpath(query, namespaces=NS)[0]
    if attribute is None:
        target.getparent().remove(target)
    elif attribute == "text":
        target.text = value
    else:
        target.set(attribute, value)
    parts["word/document.xml"] = etree.tostring(root)
    result = Compiler().verify(source, write_parts(parts))
    assert not result.ok
    assert result.findings[0].code in {"VERIFY301", "VERIFY303"}
    assert result.findings[0].line


def test_verification_reports_unsupported_constructs_and_invalid_packages(tmp_path, capsys):
    source = tmp_path / "code.md"
    output = source.with_suffix(".docx")
    source.write_text("~~~mermaid\nflowchart TD\nA --> B\n~~~", encoding="utf-8")
    Compiler().compile_file(source, output)
    assert main(["verify", str(source), str(output)]) == 3
    assert "VERIFY304" in capsys.readouterr().out
    output.write_bytes(b"invalid")
    assert main(["verify", str(source), str(output), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "DOCX401"


def test_verify_sutonny_and_unicode_bangla(tmp_path, monkeypatch):
    monkeypatch.setattr(
        bangla,
        "installed_font_stems",
        lambda: frozenset({"sautonny", "sutonny", "sutonny mj".replace(" ", "")}),
    )
    source = tmp_path / "bangla.md"
    source.write_text("# বাংলা\n\nবাংলা English", encoding="utf-8")
    for font in ("SutonnyMJ", None):
        config = RenderConfig()
        config.fonts.bengali = font
        compiler = Compiler(config)
        output = source.with_suffix(".docx")
        compiler.compile_file(source, output)
        report = compiler.verify(source, output)
        assert report.ok, report


def test_verifies_notes_captions_native_charts_and_cross_references(tmp_path):
    source = tmp_path / "report.md"
    source.write_text(
        "# Report {#report}\n\nSee [Section @report].[^note]\n\n"
        "[^note]: An editable note with $x^2$.\n\n"
        "| Item | Value |\n| --- | --- |\n| A | 1 |\n\n"
        "Table: Sample results {#table}\n\n"
        '~~~chart {#figure caption="Sample chart"}\n'
        "categories: [A]\nseries:\n  - name: Count\n    values: [1]\n~~~\n",
        encoding="utf-8",
    )
    docx = source.with_suffix(".docx")
    compiler = Compiler()
    compiler.compile_file(source, docx)
    result = compiler.verify(source, docx)
    assert result.ok, result
    parts = read_parts(docx.read_bytes())
    parts["word/footnotes.xml"] = parts["word/footnotes.xml"].replace(
        b"editable note", b"edited note"
    )
    assert compiler.verify(source, write_parts(parts)).findings[0].part == "word/footnotes.xml"
    parts = read_parts(docx.read_bytes())
    chart = etree.fromstring(parts["word/charts/chart1.xml"])
    data = next(node for node in chart.iter() if node.tag.endswith("}externalData"))
    data.getparent().remove(data)
    parts["word/charts/chart1.xml"] = etree.tostring(chart)
    assert compiler.verify(source, write_parts(parts)).findings[0].part == "word/charts/chart1.xml"


def test_verify_reports_heading_bookmark_drift(tmp_path):
    source = tmp_path / "simple.md"
    source.write_text("# Heading {#heading}", encoding="utf-8")
    output = source.with_suffix(".docx")
    compiler = Compiler()
    compiler.compile_file(source, output)
    parts = read_parts(output.read_bytes())
    parts["word/document.xml"] = parts["word/document.xml"].replace(
        b'w:name="heading"', b'w:name="changed"'
    )
    findings = compiler.verify(source, write_parts(parts)).findings
    assert findings[0].code == "VERIFY303" and findings[0].line == 1


def test_quoted_heading_keeps_native_style_and_link_target(tmp_path):
    source = tmp_path / "quoted.md"
    source.write_text(
        "# Report\n\n> ## Quoted finding {#finding}\n>\n> Supporting notes.\n>\n"
        "> - Detail\n>   ### Nested finding {#nested}\n\n"
        "[See the finding](#finding) and [the detail](#nested).\n",
        encoding="utf-8",
    )
    output = source.with_suffix(".docx")
    compiler = Compiler()
    compiler.compile_file(source, output)
    result = compiler.verify(source, output)
    assert result.ok, result
    paragraphs = {p.text: p for p in Document(output).paragraphs}
    assert paragraphs["Quoted finding"].style.name == "MD Heading 2"
    assert paragraphs["Nested finding"].style.name == "MD Heading 3"
    assert paragraphs["Supporting notes."].style.name == "MD Quote"
    assert paragraphs["Detail"]._p.pPr.numPr is not None


@pytest.mark.parametrize("note_style", ["footnote", "endnote"])
def test_complex_equations_verify_offline_in_body_and_notes(tmp_path, monkeypatch, note_style):
    source = tmp_path / "equations.md"
    source.write_text(
        "# Equations\n\n$$\n\\frac{f(x)}{1+x^2}+\\sqrt{y}\n$$\n\n"
        "A note.[^n]\n\n[^n]: Math $\\frac{2}{z}$.\n",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.notes.style = note_style
    compiler = Compiler(config)
    output = source.with_suffix(".docx")
    compiler.compile_file(source, output)

    def forbidden(*args, **kwargs):
        pytest.fail("verification attempted to render or launch a process")

    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("mddocx.MarkdownWord._render_document", forbidden)
    result = compiler.verify(source, output)
    assert result.ok, result
    for part in ("word/document.xml", f"word/{note_style}s.xml"):
        parts = read_parts(output.read_bytes())
        root = etree.fromstring(parts[part])
        math = root.find(".//m:oMath", NS)
        assert math is not None
        math.insert(0, etree.Comment(r"Word XML comment: \frac{99}{42}"))
        parts[part] = etree.tostring(root)
        assert compiler.verify(source, write_parts(parts)).ok

        for flatten_fraction in (False, True):
            parts = read_parts(output.read_bytes())
            root = etree.fromstring(parts[part])
            fraction = root.find(".//m:f", NS)
            assert fraction is not None
            if flatten_fraction:
                parent = fraction.getparent()
                for run in fraction.findall(".//m:r", NS):
                    fraction.addprevious(run)
                parent.remove(fraction)
            else:
                fraction.find("m:num//m:t", NS).text = "EDITED"
            parts[part] = etree.tostring(root)
            (finding,) = compiler.verify(source, write_parts(parts)).findings
            assert finding.code == "VERIFY303" and finding.part == part
            if part == "word/document.xml":
                assert finding.line == 3


def test_verify_editable_numbered_listing(tmp_path):
    source = tmp_path / "listing.md"
    source.write_text(
        '~~~python {#code caption="Example" linenos=true}\nprint(1)\n\nprint(2)\n~~~',
        encoding="utf-8",
    )
    output = source.with_suffix(".docx")
    compiler = Compiler()
    compiler.compile_file(source, output)
    assert compiler.verify(source, output).ok
