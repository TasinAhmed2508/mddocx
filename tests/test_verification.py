import json
from io import BytesIO

from docx import Document
from docx.oxml.ns import qn
from lxml import etree
from PIL import Image
from openpyxl import load_workbook
import pytest

from mddocx import (
    Compiler,
    NotesConfig,
    RenderConfig,
    audit_docx_accessibility_bytes,
    inspect_docx_bytes,
)
from mddocx.cli import main
from mddocx.diagnostics import MddocxError
from mddocx.inspection import NS
from mddocx.ooxml import bangla
from mddocx.ooxml.charts import C
from mddocx.ooxml.package import read_parts, write_parts
from mddocx.ooxml.sequence import get_or_add


def test_adjacent_equations_use_a_word_preserved_separator(tmp_path):
    source = tmp_path / "adjacent.md"
    source.write_text(
        "Adjacent $a$\\(b\\).\n\nAuthor's joiner $c$\u2060\\(d\\).\n", encoding="utf-8"
    )
    compiler = Compiler()
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    assert compiler.verify(source, blob).ok
    parts = read_parts(blob)
    document = etree.fromstring(parts["word/document.xml"])
    first, second, third, fourth = document.iter(qn("m:oMath"))
    for start, end in [(first, second), (third, fourth)]:
        run = start.getnext()
        assert run.findtext("w:t", namespaces=NS) == "\u2060"
        assert run.getnext() is end
    assert first.getnext().find("w:rPr/w:noProof", NS) is not None
    assert third.getnext().find("w:rPr/w:noProof", NS) is None
    second.getparent().remove(second)
    parts["word/document.xml"] = etree.tostring(document)
    assert any(
        finding.code == "VERIFY303"
        for finding in compiler.verify(source, write_parts(parts)).findings
    )


@pytest.mark.parametrize("change", ["linked", "missing-id"])
def test_verify_detects_picture_without_embedded_binding(tmp_path, change):
    Image.new("RGB", (8, 8), "white").save(tmp_path / "tile.png")
    source = tmp_path / "image.md"
    source.write_text("![Tile alt](tile.png)\n", encoding="utf-8")
    compiler = Compiler()
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    assert compiler.verify(source, blob).ok
    parts = read_parts(blob)
    main = etree.fromstring(parts["word/document.xml"])
    blip = next(main.iter(qn("a:blip")))
    if change == "linked":
        rid = blip.attrib.pop(qn("r:embed"))
        blip.set(qn("r:link"), rid)
        name = "word/_rels/document.xml.rels"
        rels = etree.fromstring(parts[name])
        rel = next(relation for relation in rels if relation.get("Id") == rid)
        rel.set("TargetMode", "External")
        rel.set("Target", "https://example.com/tile.png")
        parts[name] = etree.tostring(rels)
    else:
        blip.set(qn("r:embed"), "rIdMissing")
    parts["word/document.xml"] = etree.tostring(main)

    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.part) == ("VERIFY303", "word/document.xml")
    assert "embedded image binding" in finding.message


@pytest.mark.parametrize("change", ["destination", "picture", "click"])
def test_verify_detects_changes_to_linked_picture(tmp_path, change):
    Image.new("RGB", (30, 20), "white").save(tmp_path / "tile.png")
    source = tmp_path / "linked-image.md"
    source.write_text(
        "Intro.\n\n[![Tile alt](tile.png)](https://example.com/manual)\n",
        encoding="utf-8",
    )
    compiler = Compiler()
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert compiler.verify(source, result.output_bytes).ok
    parts = read_parts(result.output_bytes)
    main = etree.fromstring(parts["word/document.xml"])
    link = next(main.iter(qn("w:hyperlink")))
    if change == "destination":
        name = "word/_rels/document.xml.rels"
        rels = etree.fromstring(parts[name])
        rid = link.get(qn("r:id"))
        next(item for item in rels if item.get("Id") == rid).set(
            "Target", "https://example.com/other"
        )
        parts[name] = etree.tostring(rels)
    elif change == "picture":
        drawing = next(link.iter(qn("w:drawing")))
        drawing.getparent().remove(drawing)
    else:
        link.getparent().replace(link, link[0])
    parts["word/document.xml"] = etree.tostring(main)

    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.line, finding.part) == ("VERIFY303", 3, "word/document.xml")


def test_linked_picture_targets_a_native_bookmark_from_table(tmp_path):
    Image.new("RGB", (300, 200), "white").save(tmp_path / "tile.png")
    source = tmp_path / "bookmark.md"
    source.write_text(
        "# Details {#details}\n\n| Figure |\n| --- |\n| [![Tile alt](tile.png)](#details) |\n",
        encoding="utf-8",
    )
    compiler = Compiler()
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert compiler.verify(source, result.output_bytes).ok
    word = Document(source.with_suffix(".docx"))
    (link,) = word.tables[0].cell(1, 0).paragraphs[0].hyperlinks
    assert link.fragment == "details"
    assert next(link._element.iter(qn("a:blip"))).get(qn("r:embed"))
    assert audit_docx_accessibility_bytes(result.output_bytes).empty_hyperlinks == 0

    parts = read_parts(result.output_bytes)
    main = etree.fromstring(parts["word/document.xml"])
    next(main.iter(qn("wp:docPr"))).attrib.pop("descr")
    parts["word/document.xml"] = etree.tostring(main)
    assert audit_docx_accessibility_bytes(write_parts(parts)).empty_hyperlinks == 1


@pytest.mark.parametrize("style", ["footnote", "endnote"])
def test_verify_resolves_note_relationships_from_the_owning_part(tmp_path, style):
    Image.new("RGB", (30, 20), "white").save(tmp_path / "tile.png")
    config = RenderConfig(notes=NotesConfig(style=style))
    compiler = Compiler(config)
    source = tmp_path / "notes.md"
    source.write_text(
        "Review.[^tile]\n\n[^tile]: [![Tile](tile.png)](https://example.org/manual)\n",
        encoding="utf-8",
    )
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert compiler.verify(source, result.output_bytes).ok
    parts = read_parts(result.output_bytes)
    note_part = f"word/{style}s.xml"
    rels_part = f"word/_rels/{style}s.xml.rels"
    notes = etree.fromstring(parts[note_part])
    link = next(notes.iter(qn("w:hyperlink")))
    target_id = link.get(qn("r:id"))
    rels = etree.fromstring(parts[rels_part])
    next(item for item in rels if item.get("Id") == target_id).set(
        "Target", "https://example.org/other"
    )
    parts[rels_part] = etree.tostring(rels)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.part, finding.line) == ("VERIFY303", note_part, 3)

    parts = read_parts(result.output_bytes)
    next(notes.iter(qn("a:blip"))).set(qn("r:embed"), "rIdMissing")
    parts[note_part] = etree.tostring(notes)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.part) == ("VERIFY303", note_part)
    assert "embedded image binding" in finding.message


@pytest.mark.parametrize("style", ["footnote", "endnote"])
def test_append_preserves_template_notes_and_media_relationships(tmp_path, style):
    Image.new("RGB", (30, 20), "white").save(tmp_path / "tile.png")
    config = RenderConfig(notes=NotesConfig(style=style))
    first = Compiler(config).compile_string(
        "Original.[^original]\n\n[^original]: [![Original](tile.png)](https://example.org/manual)",
        base_dir=tmp_path,
    )
    config.template = tmp_path / "template.docx"
    config.template.write_bytes(first.output_bytes)
    second = Compiler(config).compile_string(
        "Added.[^new]\n\n[^new]: New note text.", base_dir=tmp_path
    )
    before = read_parts(first.output_bytes)
    after = read_parts(second.output_bytes)
    rels_part = f"word/_rels/{style}s.xml.rels"
    assert before[rels_part] == after[rels_part]
    notes = etree.fromstring(after[f"word/{style}s.xml"])
    real_notes = [item for item in notes if item.get(qn("w:type")) is None]
    assert [item.get(qn("w:id")) for item in real_notes] == ["1", "2"]
    assert next(real_notes[0].iter(qn("wp:docPr"))).get("descr") == "Original"
    assert "".join(real_notes[1].itertext()).strip() == "New note text."
    main = etree.fromstring(after["word/document.xml"])
    assert [ref.get(qn("w:id")) for ref in main.iter(qn(f"w:{style}Reference"))] == ["1", "2"]


@pytest.mark.parametrize("change", ["rotate", "remove", "move", "continuous"])
def test_verify_reports_wide_table_section_edits(tmp_path, capsys, change):
    source = tmp_path / "sections.md"
    source.write_text(
        "# Before\n\n| A | B | C | D | E | F |\n|---|---|---|---|---|---|\n"
        "| 1 | 2 | 3 | 4 | 5 | 6 |\n\n# After\n",
        encoding="utf-8",
    )
    target = source.with_suffix(".docx")
    config = RenderConfig()
    config.table.auto_landscape = True
    Compiler(config).compile_file(source, target)
    arguments = ["verify", str(source), str(target), "--auto-landscape-tables", "--json"]
    assert main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    parts = read_parts(target.read_bytes())
    root = etree.fromstring(parts["word/document.xml"])
    marker = root.find(".//w:p/w:pPr/w:sectPr", NS).getparent().getparent()
    landscape = root.xpath(".//w:sectPr[w:pgSz/@w:orient='landscape']", namespaces=NS)[0]
    page = landscape.find("w:pgSz", NS)
    w = f"{{{NS['w']}}}"
    if change == "rotate":
        page.set(w + "orient", "portrait")
        width, height = page.get(w + "w"), page.get(w + "h")
        page.set(w + "w", height)
        page.set(w + "h", width)
    elif change == "remove":
        marker.getparent().remove(marker)
    elif change == "move":
        root.find(".//w:body/w:tbl", NS).addnext(marker)
    else:
        get_or_add(landscape, "w:type").set(w + "val", "continuous")
    parts["word/document.xml"] = etree.tostring(root)
    target.write_bytes(write_parts(parts))
    assert main(arguments) == 3
    (finding,) = json.loads(capsys.readouterr().out)["findings"]
    assert (finding["code"], finding["part"], finding["line"]) == (
        "VERIFY303",
        "word/document.xml",
        3,
    )
    assert "Word section" in finding["message"]


def test_verify_explicit_same_orientation_break_and_document_page_flags(tmp_path, capsys):
    source = tmp_path / "sections.md"
    source.write_text("# Before\n\n<!-- sectionbreak -->\n\n# After\n", encoding="utf-8")
    target = source.with_suffix(".docx")
    layout = ["--page-size", "Letter", "--orientation", "landscape"]
    assert main([str(source), "-o", str(target), *layout]) == 0
    capsys.readouterr()
    assert main(["verify", str(source), str(target), *layout, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]


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


def test_verify_reports_flattened_nested_math_matrix(tmp_path, monkeypatch):
    monkeypatch.setattr("mddocx.math.sidecar.node_executable", lambda: None)
    source = tmp_path / "alignment.md"
    source.write_text(
        "$$\n"
        r"\begin{alignedat}[t]{2}A&=\begin{bmatrix}a&b\\c&d\end{bmatrix}&x&=1\\B&=2&y&=3\end{alignedat}"
        "\n$$\n",
        encoding="utf-8",
    )
    target = source.with_suffix(".docx")
    config = RenderConfig()
    config.math_failure.mode = "error"
    compiler = Compiler(config)
    payload = compiler.compile_file(source, target).output_bytes
    assert compiler.verify(source, target).ok

    parts = read_parts(payload)
    root = etree.fromstring(parts["word/document.xml"])
    outer, inner = root.findall(".//m:m", NS)
    for run in inner.findall(".//m:r", NS):
        inner.addprevious(run)
    inner.getparent().remove(inner)
    assert len(outer.findall("m:mr", NS)) == 2
    parts["word/document.xml"] = etree.tostring(root)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.part, finding.line) == ("VERIFY303", "word/document.xml", 1)
    assert "lost an alignment array or matrix" in finding.message


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


@pytest.fixture
def section_reference_report(tmp_path):
    source = tmp_path / "references.md"
    source.write_text(
        "# Report {#report}\n\n"
        "| Item | Count |\n| --- | --- |\n| A | 1 |\n\n"
        "Table: Counts {#counts}\n\n"
        '$$\nx^2\n$$ {#eq-square caption="Square"}\n\n'
        "See [Table @counts], [Equation @eq-square], and [Section @report].\n",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.references.caption_number_format = "section"
    config.references.equation_number_format = "section"
    compiler = Compiler(config)
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    assert compiler.verify(source, blob).ok
    return compiler, source, blob


@pytest.mark.parametrize(
    ("before", "after", "line"),
    [
        (rb"REF counts \h", b"REF counts", 13),
        (rb"SEQ Table \* ARABIC", rb"SEQ Table \* ROMAN", 3),
        (rb"SEQ Equation \* ARABIC", rb"SEQ Equation \* ROMAN", 9),
        (rb"SEQ Table \r 0", rb"SEQ Table \r 8", 1),
        (rb"SEQ Section \c", rb"SEQ Section \s 1", 3),
    ],
)
def test_verify_reports_changed_numbering_and_reference_instructions(
    section_reference_report, before, after, line
):
    compiler, source, blob = section_reference_report
    parts = read_parts(blob)
    assert before in parts["word/document.xml"]
    parts["word/document.xml"] = parts["word/document.xml"].replace(before, after, 1)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.part, finding.line) == ("VERIFY303", "word/document.xml", line)


@pytest.mark.parametrize("field_form", ["split instruction", "simple field", "unterminated"])
def test_verify_reads_complete_reference_fields(section_reference_report, field_form):
    compiler, source, blob = section_reference_report
    parts = read_parts(blob)
    document = etree.fromstring(parts["word/document.xml"])
    instruction = next(
        node for node in document.iter(qn("w:instrText")) if "REF counts" in node.text
    )
    run = instruction.getparent()
    begin = run.getprevious()
    separator = run.getnext()
    result = separator.getnext()
    end = result.getnext()
    if field_form == "split instruction":
        remainder = etree.Element(qn("w:r"))
        etree.SubElement(remainder, qn("w:instrText")).text = r"unts \h "
        instruction.text = " REF co"
        run.addnext(remainder)
    elif field_form == "simple field":
        simple = etree.Element(qn("w:fldSimple"))
        simple.set(qn("w:instr"), r' REF "counts" \h ')
        begin.addprevious(simple)
        simple.append(result)
        for removed in (begin, run, separator, end):
            removed.getparent().remove(removed)
    else:
        end.getparent().remove(end)
    parts["word/document.xml"] = etree.tostring(document)
    edited = write_parts(parts)
    report = compiler.verify(source, edited)
    if field_form == "unterminated":
        assert not report.ok and report.findings[0].code == "VERIFY303"
    else:
        assert report.ok, report
        assert inspect_docx_bytes(edited).ref_fields == inspect_docx_bytes(blob).ref_fields


def test_verify_requires_the_end_of_a_caption_bookmark(section_reference_report):
    compiler, source, blob = section_reference_report
    parts = read_parts(blob)
    document = etree.fromstring(parts["word/document.xml"])
    start = document.find(".//w:bookmarkStart[@w:name='counts']", NS)
    end = start.getparent().find(f"w:bookmarkEnd[@w:id='{start.get(qn('w:id'))}']", NS)
    end.getparent().remove(end)
    parts["word/document.xml"] = etree.tostring(document)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.line) == ("VERIFY303", 3)


@pytest.mark.parametrize("kind", ["column", "bar", "line", "pie", "scatter"])
def test_verify_chart_values_from_local_data(tmp_path, kind):
    data = tmp_path / "values.csv"
    data.write_text(
        "Time,Count,Rate\n1,3,1.2345678901234567\n2,5,0.3333333333333333\n", encoding="utf-8"
    )
    source = tmp_path / "chart.md"
    source.write_text(
        f"~~~chart\ntype: {kind}\nsource: values.csv\ncategory: Time\n"
        "secondary_series: [Rate]\n~~~\n",
        encoding="utf-8",
    )
    compiler = Compiler()
    output = compiler.compile_file(source, source.with_suffix(".docx"))
    assert compiler.verify(source, output.output_bytes).ok
    data.write_text(
        "Time,Count,Rate\n1,9,1.2345678901234567\n2,5,0.3333333333333333\n", encoding="utf-8"
    )
    result = compiler.verify(source, output.output_bytes)
    assert not result.ok
    assert any("values changed" in finding.message for finding in result.findings)


@pytest.mark.parametrize("kind", ["column", "bar", "line", "pie", "scatter"])
def test_chart_retains_values_with_short_categories_and_blank_points(tmp_path, kind):
    source = tmp_path / "unequal-chart.md"
    source.write_text(
        f"~~~chart\ntype: {kind}\ncategories: [1, 2]\n"
        "series: {Count: [5, null, 7], Other: [3]}\n~~~\n",
        encoding="utf-8",
    )
    compiler = Compiler()
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    assert compiler.verify(source, blob).ok
    parts = read_parts(blob)
    root = etree.fromstring(parts["word/charts/chart1.xml"])
    value_tag = "yVal" if kind == "scatter" else "val"
    caches = root.findall(f".//{{*}}{value_tag}/{{*}}numRef")
    assert caches[0].findtext("{*}f") == "Sheet1!$B$2:$B$4"
    assert caches[0].find("{*}numCache/{*}ptCount").get("val") == "3"
    points = caches[0].findall("{*}numCache/{*}pt")
    assert [(point.get("idx"), point.findtext("{*}v")) for point in points] == [
        ("0", "5.0"),
        ("2", "7.0"),
    ]
    workbook = load_workbook(BytesIO(parts["word/embeddings/Microsoft_Excel_Worksheet1.xlsx"]))
    try:
        assert workbook.active["A4"].value is None
        assert workbook.active["B3"].value is None
        assert workbook.active["B4"].value == 7
        if kind != "pie":
            assert workbook.active["C3"].value is None
            assert workbook.active["C4"].value is None
    finally:
        workbook.close()
    point = etree.SubElement(caches[0].find("{*}numCache"), f"{{{C}}}pt", idx="1")
    etree.SubElement(point, f"{{{C}}}v").text = "0"
    parts["word/charts/chart1.xml"] = etree.tostring(root)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert finding.code == "VERIFY303" and "values changed" in finding.message


@pytest.mark.parametrize("x", [".nan", ".inf", "1e999", "true", "wrong"])
def test_scatter_rejects_invalid_coordinates_with_source_location(tmp_path, x):
    source = tmp_path / "scatter.md"
    source.write_text(
        f"~~~chart\ntype: scatter\ncategories: [{x}]\nseries: {{Count: [2]}}\n~~~",
        encoding="utf-8",
    )
    with pytest.raises(MddocxError, match="CHART208") as error:
        Compiler().compile_file(source, source.with_suffix(".docx"))
    assert error.value.diagnostic.line == 1


def test_chart_blank_csv_fields_remain_gaps(tmp_path):
    source = tmp_path / "csv-chart.md"
    (tmp_path / "values.csv").write_text("Item,Count\nA,2\nB,\nC,4\n", encoding="utf-8")
    source.write_text("~~~chart\nsource: values.csv\n~~~", encoding="utf-8")
    compiler = Compiler()
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    assert compiler.verify(source, blob).ok
    parts = read_parts(blob)
    root = etree.fromstring(parts["word/charts/chart1.xml"])
    points = root.findall(".//{*}val/{*}numRef/{*}numCache/{*}pt")
    assert [point.get("idx") for point in points] == ["0", "2"]


@pytest.mark.parametrize(
    "change",
    ["value", "category", "name", "formula", "index", "type", "workbook", "corrupt workbook"],
)
def test_verify_detects_chart_and_workbook_edits(tmp_path, change):
    source = tmp_path / "chart.md"
    source.write_text(
        "# Chart\n\n~~~chart\ncategories: [A, B]\nseries: {Count: [2, 4]}\n~~~\n",
        encoding="utf-8",
    )
    compiler = Compiler()
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    assert compiler.verify(source, blob).ok
    parts = read_parts(blob)
    chart_part = "word/charts/chart1.xml"
    workbook_part = "word/embeddings/Microsoft_Excel_Worksheet1.xlsx"
    if change in {"workbook", "corrupt workbook"}:
        if change == "corrupt workbook":
            parts[workbook_part] = b"broken workbook"
        else:
            workbook = load_workbook(BytesIO(parts[workbook_part]))
            workbook.active["B2"] = 9
            stream = BytesIO()
            workbook.save(stream)
            workbook.close()
            parts[workbook_part] = stream.getvalue()
    else:
        root = etree.fromstring(parts[chart_part])
        paths = {
            "value": ".//{*}val/{*}numRef/{*}numCache/{*}pt/{*}v",
            "category": ".//{*}cat/{*}strRef/{*}strCache/{*}pt/{*}v",
            "name": ".//{*}tx/{*}strRef/{*}strCache/{*}pt/{*}v",
            "formula": ".//{*}val/{*}numRef/{*}f",
            "index": ".//{*}val/{*}numRef/{*}numCache/{*}pt",
            "type": ".//{*}barDir",
        }
        item = root.find(paths[change])
        if change == "index":
            item.set("idx", "1")
        elif change == "type":
            item.set("val", "bar")
        else:
            item.text = "9" if change == "value" else "changed"
        parts[chart_part] = etree.tostring(root)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert finding.code == "VERIFY303" and finding.line == 3
    assert finding.part == (workbook_part if "workbook" in change else chart_part)


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


def test_verify_detects_changed_explicit_limit_placement(tmp_path):
    source = tmp_path / "limits.md"
    source.write_text(r"$$\sum\nolimits_{i=1}^{n} i+\int\limits_0^1 x\,dx$$", encoding="utf-8")
    compiler = Compiler()
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    assert compiler.verify(source, blob).ok
    parts = read_parts(blob)
    document = etree.fromstring(parts["word/document.xml"])
    first, second = document.iter(qn("m:limLoc"))
    assert first.get(qn("m:val")) == "subSup"
    assert second.get(qn("m:val")) == "undOvr"
    first.set(qn("m:val"), "undOvr")
    parts["word/document.xml"] = etree.tostring(document)

    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.part, finding.line) == ("VERIFY303", "word/document.xml", 1)
    assert "explicit limit placement" in finding.message


@pytest.mark.parametrize("edit", ["replace", "delete"])
def test_verify_plain_code_in_lists_and_quotes(tmp_path, edit):
    source = tmp_path / "plain-code.md"
    source.write_text(
        "# Guide\n\n    keep $x^2$ literally\n\n"
        "> ~~~text\n> quoted $y^2$\n> ~~~\n>\n> $$y^2$$\n\n"
        "- Example\n\n  ~~~plain\n  listed $z^2$\n  ~~~\n",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.code.show_language_label = True
    compiler = Compiler(config)
    blob = compiler.compile_file(source, source.with_suffix(".docx")).output_bytes
    assert compiler.verify(source, blob).ok

    parts = read_parts(blob)
    document = etree.fromstring(parts["word/document.xml"])
    text = next(t for t in document.iter(qn("w:t")) if t.text == "keep $x^2$ literally")
    if edit == "replace":
        text.text = "keep $x^3$ literally"
    else:
        paragraph = text.getparent().getparent()
        paragraph.getparent().remove(paragraph)
    parts["word/document.xml"] = etree.tostring(document)

    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert finding.code == ("VERIFY303" if edit == "replace" else "VERIFY301")
    assert (finding.part, finding.line) == ("word/document.xml", 3)


def test_verify_distinguishes_ruled_layout_from_plain_text(tmp_path):
    source = tmp_path / "ruled.md"
    ruled = (
        "Floor | East | West\n----------\n4 | Alice | Bob\n | 1125 | 1125\n"
        "----------\n3 | Common | Carol"
    )
    compiler = Compiler()
    output = source.with_suffix(".docx")
    source.write_text(f"~~~text\n{ruled}\n~~~\n", encoding="utf-8")
    layout = compiler.compile_file(source, output)
    assert Document(output).tables[0].cell(1, 1).text == "Alice\n1125"
    assert compiler.verify(source, layout.output_bytes).ok
    parts = read_parts(layout.output_bytes)
    document = etree.fromstring(parts["word/document.xml"])
    continuation = next(node for node in document.iter(qn("w:t")) if node.text == "1125")
    continuation.text = "9999"
    parts["word/document.xml"] = etree.tostring(document)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.part, finding.line) == ("VERIFY303", "word/document.xml", 1)
    assert "row 2, column 2" in finding.message and "9999" in finding.message

    source.write_text(f"~~~text\n{ruled}\nUnstructured line\n~~~\n", encoding="utf-8")
    code = compiler.compile_file(source, output)
    assert not Document(output).tables
    assert compiler.verify(source, code.output_bytes).ok


@pytest.mark.parametrize("change", ["photo-label", "photo-box", "signature"])
def test_verify_text_form_with_native_photo_box(tmp_path, change):
    source = tmp_path / "form.md"
    source.write_text(
        '~~~text {#lst-contact caption="Contact form"}\n'
        "নাম : উদাহরণ ┌────┐\nপিতা : উদাহরণ │ ছবি │\nমাতা : উদাহরণ └────┘\n"
        "ধর্ম : ইসলাম\nপেশা : শিক্ষক\nস্থায়ী | বর্তমান\n"
        "গ্রাম : ক | গ্রাম : খ\nজেলা : ক | জেলা : খ\n"
        ".............. Signature\n~~~\n",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.fonts.bengali = "SutonnyMJ"
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert compiler.verify(source, result.output_bytes).ok
    parts = read_parts(result.output_bytes)
    document = etree.fromstring(parts["word/document.xml"])
    photo = document.find("./w:body/w:tbl/w:tr/w:tc/w:tbl", NS)
    assert photo is not None

    if change == "photo-label":
        next(photo.iter(qn("w:t"))).text = "Changed"
    elif change == "photo-box":
        photo.getparent().remove(photo)
    else:
        signature = next(
            node for node in document.iter(qn("w:t")) if node.text == ".............. Signature"
        )
        signature.text = "Signature"
    parts["word/document.xml"] = etree.tostring(document)

    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.part, finding.line) == ("VERIFY303", "word/document.xml", 1)


def test_verify_cli_respects_listing_flags(tmp_path, capsys):
    source = tmp_path / "code-config.md"
    source.write_text(
        "~~~text\nplain text\n~~~\n\n~~~python\nprint(1)\n~~~\n\n"
        "~~~mermaid\nflowchart TD\nA --> B\n~~~\n",
        encoding="utf-8",
    )
    target = source.with_suffix(".docx")
    flags = ["--code-line-numbers", "--code-language-labels", "--no-mermaid"]

    assert main([str(source), "-o", str(target), *flags]) == 0
    capsys.readouterr()
    assert main(["verify", str(source), str(target), *flags, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
