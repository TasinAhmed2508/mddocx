from io import BytesIO

from docx import Document
from docx.oxml.ns import qn
from lxml import etree
from PIL import Image
import pytest

from mddocx import Compiler, RenderConfig
from mddocx.layout import _plain_text
from mddocx.ooxml.package import read_parts, write_parts
from mddocx.ooxml.fields import read_field_instructions
from mddocx.references import ReferenceRegistry


def _caption_block(kind, caption, identifier=None):
    attrs = (f"#{identifier} " if identifier else "") + f'caption="{caption}"'
    if kind == "table":
        return f"| Value |\n| --- |\n| 1 |\n\nTable: {caption}" + (
            f" {{#{identifier}}}" if identifier else ""
        )
    if kind == "image":
        return f"![Plot](plot.png) {{{attrs}}}"
    if kind == "chart":
        return f"~~~chart {{{attrs}}}\ntype: bar\nseries: {{Value: [1, 2]}}\n~~~"
    if kind == "data-table":
        return f"~~~data-table {{{attrs}}}\nsource: data.csv\n~~~"
    return f"~~~python {{{attrs}}}\nprint(1)\n~~~"


@pytest.mark.parametrize("kind", ["table", "image", "chart", "data-table", "listing"])
@pytest.mark.parametrize("scope", ["document", "section"])
@pytest.mark.parametrize("crossrefs", [True, False])
@pytest.mark.parametrize("position", ["above", "below"])
def test_anonymous_captions_advance_numbers_and_forward_references(
    tmp_path, kind, scope, crossrefs, position
):
    Image.new("RGB", (12, 8), "navy").save(tmp_path / "plot.png")
    (tmp_path / "data.csv").write_text("Value\n1\n", encoding="utf-8")
    label = {"table": "Table", "data-table": "Table", "listing": "Listing"}.get(kind, "Figure")
    source = tmp_path / "report.md"
    source.write_text(
        "# First section\n\n"
        f"Forward [{label} @second].\n\n"
        + _caption_block(kind, "First")
        + "\n\n"
        + _caption_block(kind, "Second", "second")
        + "\n\n# Next section\n\n"
        + _caption_block(kind, "Third", "third")
        + f"\n\nBackward [{label} @second] and [{label} @third].\n",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.references.caption_number_format = scope
    config.references.enabled = crossrefs
    setattr(config.references, label.lower() + "_caption_position", position)
    compiler = Compiler(config)
    references = ReferenceRegistry.from_document(
        compiler.check_file(source).document, _plain_text, caption_number_format=scope
    )
    expected_numbers = [2, 3] if scope == "document" else ["1.2", "2.1"]
    assert [references.get(key).number for key in ("second", "third")] == expected_numbers
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    document = Document(BytesIO(result.output_bytes))
    captions = [
        paragraph.text for paragraph in document.paragraphs if paragraph.style.name == "MD Caption"
    ]
    numbers = ["1", "2", "3"] if scope == "document" else ["1.1", "1.2", "2.1"]
    assert captions == [
        f"{label} {number} — {caption}"
        for number, caption in zip(numbers, ["First", "Second", "Third"])
    ]
    assert f"Forward {label} {numbers[1]}." in [p.text for p in document.paragraphs]
    assert f"Backward {label} {numbers[1]} and {label} {numbers[2]}." in [
        p.text for p in document.paragraphs
    ]
    if crossrefs:
        assert compiler.verify(source, result.output_bytes).ok


@pytest.mark.parametrize("kind,line", [("SEQ", 1), ("REF", 7)])
def test_verifier_detects_changed_cached_number(tmp_path, kind, line):
    source = tmp_path / "report.md"
    source.write_text(
        _caption_block("table", "First", "first") + "\n\nSee [Table @first].\n", encoding="utf-8"
    )
    compiler = Compiler()
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    parts = read_parts(result.output_bytes)
    root = etree.fromstring(parts["word/document.xml"])
    field = next(
        node for node in root.iter(qn("w:instrText")) if node.text.strip().startswith(kind)
    )
    field.getparent().getnext().getnext().find(qn("w:t")).text = "99"
    parts["word/document.xml"] = etree.tostring(root)
    report = compiler.verify(source, write_parts(parts))
    assert not report.ok
    assert any(finding.code == "VERIFY303" and finding.line == line for finding in report.findings)


@pytest.mark.parametrize("kind", ["chart", "data-table", "diagram"])
def test_recovered_block_does_not_leave_a_gap_or_stale_forward_reference(tmp_path, kind):
    Image.new("RGB", (12, 8), "navy").save(tmp_path / "plot.png")
    (tmp_path / "data.csv").write_text("Value\n1\n", encoding="utf-8")
    invalid, valid, label, code = {
        "chart": (
            '~~~chart {#broken caption="Broken"}\ntype: bar\nseries: {Value: [bad]}\n~~~',
            _caption_block("chart", "Second", "second"),
            "Figure",
            "CHART205",
        ),
        "data-table": (
            '~~~data-table {#broken caption="Broken"}\nsource: data.csv\ncolumns: [Missing]\n~~~',
            _caption_block("data-table", "Second", "second"),
            "Table",
            "DATA208",
        ),
        "diagram": (
            '~~~mermaid {#broken caption="Broken"}\nunsupportedDiagram\nA --> B\n~~~',
            _caption_block("image", "Second", "second"),
            "Figure",
            "DIAGRAM201",
        ),
    }[kind]
    source = tmp_path / "recovered.md"
    source.write_text(
        f"Forward [{label} @second].\n\n{invalid}\n\n{valid}",
        encoding="utf-8",
    )
    compiler = Compiler(RenderConfig(recover=True))
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert result.completed_with_fallbacks
    paragraphs = [p.text for p in Document(BytesIO(result.output_bytes)).paragraphs]
    assert f"Forward {label} 1." in paragraphs
    assert f"{label} 1 — Second" in paragraphs
    assert any(code in p for p in paragraphs)


@pytest.mark.parametrize("from_title", [True, False])
def test_image_title_policy_controls_caption_numbering(tmp_path, from_title):
    Image.new("RGB", (12, 8), "navy").save(tmp_path / "plot.png")
    source = tmp_path / "images.md"
    source.write_text(
        '![No caption](plot.png)\n\n![Plot](plot.png "Title")\n\n'
        + _caption_block("image", "Second", "second")
        + "\n\nSee [Figure @second].",
        encoding="utf-8",
    )
    config = RenderConfig(image_captions_from_title=from_title)
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    captions = [
        p.text
        for p in Document(BytesIO(result.output_bytes)).paragraphs
        if p.style.name == "MD Caption"
    ]
    assert captions == (
        ["Figure 1 — Title", "Figure 2 — Second"] if from_title else ["Figure 1 — Second"]
    )
    assert compiler.verify(source, result.output_bytes).ok


def test_disabled_listing_numbering_keeps_plain_captions_and_reference_titles(tmp_path):
    source = tmp_path / "listings.md"
    source.write_text(
        "Forward [Listing @second].\n\n"
        + _caption_block("listing", "First")
        + "\n\n"
        + _caption_block("listing", "Second", "second"),
        encoding="utf-8",
    )
    config = RenderConfig()
    config.references.listing_numbering = False
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    paragraphs = [p.text for p in Document(BytesIO(result.output_bytes)).paragraphs]
    assert "First" in paragraphs and "Second" in paragraphs
    assert "Forward Listing Second." in paragraphs
    assert compiler.verify(source, result.output_bytes).ok


def test_disabled_mermaid_uses_listing_reference_title(tmp_path):
    source = tmp_path / "diagram.md"
    source.write_text(
        'Forward [Listing @diagram].\n\n~~~mermaid {#diagram caption="Diagram"}\n'
        "flowchart TD\nA --> B\n~~~",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.mermaid.enabled = False
    config.references.listing_numbering = False
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert Document(BytesIO(result.output_bytes)).paragraphs[0].text == "Forward Listing Diagram."
    assert compiler.verify(source, result.output_bytes).ok


@pytest.mark.parametrize("numbered_headings", [False, True])
@pytest.mark.parametrize("kind", ["table", "equation"])
def test_section_fields_use_a_source_counter_without_heading_number_dependency(
    tmp_path, numbered_headings, kind
):
    def content(identifier):
        if kind == "equation":
            return f"$$\nx^2\n$$ {{#{identifier}}}"
        return _caption_block("table", identifier.title(), identifier)

    source = tmp_path / "sections.md"
    source.write_text(
        "# Chapter one\n\n" + content("first") + "\n\n# Chapter two\n\n" + content("second"),
        encoding="utf-8",
    )
    config = RenderConfig()
    config.heading_numbering.enabled = numbered_headings
    config.references.caption_number_format = "section"
    config.references.equation_number_format = "section"
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    root = etree.fromstring(read_parts(result.output_bytes)["word/document.xml"])
    fields = list(read_field_instructions(root))
    assert fields.count(("SEQ", "Section", r"\c")) == 2
    assert ("SEQ", "Section", r"\r", "1") in fields
    assert ("SEQ", "Section", r"\*", "ARABIC") in fields
    assert not any(field[0] == "STYLEREF" for field in fields)
    assert compiler.verify(source, result.output_bytes).ok


@pytest.mark.parametrize("kind", ["table", "equation"])
def test_section_counter_is_initialized_without_a_heading(tmp_path, kind):
    source = tmp_path / "without-heading.md"
    source.write_text(
        _caption_block("table", "First", "first") if kind == "table" else "$$\nx^2\n$$ {#first}",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.references.caption_number_format = "section"
    config.references.equation_number_format = "section"
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    root = etree.fromstring(read_parts(result.output_bytes)["word/document.xml"])
    fields = list(read_field_instructions(root))
    assert fields[0] == ("SEQ", "Section", r"\r", "1")
    assert fields[1] == ("SEQ", "Section", r"\c")
    assert compiler.verify(source, result.output_bytes).ok


def test_numbered_equation_cell_widths_match_the_grid(tmp_path):
    source = tmp_path / "equation.md"
    source.write_text("$$\nx^2+1\n$$ {#energy}", encoding="utf-8")
    result = Compiler().compile_file(source, source.with_suffix(".docx"))
    document = Document(BytesIO(result.output_bytes))
    table = document.tables[0]
    grid_widths = [column.width.twips for column in table.columns]
    cell_widths = [cell.width.twips for cell in table.rows[0].cells]
    section = document.sections[0]
    usable = section.page_width - section.left_margin - section.right_margin
    assert cell_widths == grid_widths
    assert sum(grid_widths) == round(usable / 635)
    assert grid_widths[0] / sum(grid_widths) == pytest.approx(0.88, abs=0.001)


@pytest.mark.parametrize("position", ["above", "below"])
def test_section_counter_does_not_create_a_blank_page_before_first_landscape_table(
    tmp_path, position
):
    row = "|" + "|".join(["Value"] * 10) + "|"
    separator = "|" + "|".join(["---"] * 10) + "|"
    source = tmp_path / "wide.md"
    source.write_text(
        f"{row}\n{separator}\n{row}\n\nTable: Measurements {{#wide}}", encoding="utf-8"
    )
    config = RenderConfig()
    config.table.auto_landscape = True
    config.references.caption_number_format = "section"
    config.references.table_caption_position = position
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    document = Document(BytesIO(result.output_bytes))
    assert len(document.sections) == 1
    assert document.sections[0].page_width > document.sections[0].page_height
    assert compiler.verify(source, result.output_bytes).ok
