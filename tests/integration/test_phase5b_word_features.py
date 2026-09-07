from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from PIL import Image
import pytest

from mddocx import CitationConfig, NotesConfig, ReferenceConfig, RenderConfig, render, render_string
from mddocx.inspection import inspect_docx_bytes

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
ADEC = "http://schemas.microsoft.com/office/drawing/2017/decorative"
NS = {"w":W, "wp":WP, "adec":ADEC}


def xml_part(blob, name="word/document.xml"):
    with ZipFile(BytesIO(blob)) as z:
        return etree.fromstring(z.read(name))


def test_captions_seq_fields_crossrefs_and_internal_heading_link():
    md = """# Results {#sec-results}\n\nSee [Equation @eq-energy], [Table @tbl-r], and [Results](#sec-results).\n\n$$ E=mc^2 $$ {#eq-energy}\n\n| A | B |\n|---|---|\n|1|2|\n\nTable: Results {#tbl-r}\n"""
    blob = render_string(md)
    report = inspect_docx_bytes(blob)
    assert report.seq_fields == 2
    assert report.ref_fields == 2
    assert report.internal_hyperlinks == 1
    assert report.bookmarks >= 3
    assert report.ok


def test_equation_number_is_native_omml_and_seq_field():
    blob = render_string("$$ \\frac{x}{y} $$ {#eq-frac}\n")
    report = inspect_docx_bytes(blob)
    assert report.equations >= 1
    assert report.seq_fields == 1
    root = xml_part(blob)
    assert root.xpath(".//w:instrText[contains(., 'SEQ Equation')]", namespaces=NS)


def test_listing_caption_and_reference():
    md = 'See [Listing @lst-one].\n\n```python {#lst-one caption="Demo"}\nprint(1)\n```\n'
    blob = render_string(md)
    report = inspect_docx_bytes(blob)
    assert report.seq_fields == 1
    assert report.ref_fields == 1


def test_definition_list_renders_as_term_and_indented_definition():
    blob = render_string("Compiler\n: Converts Markdown to Word.\n")
    root = xml_part(blob)
    text = "".join(root.itertext())
    assert "Compiler" in text and "Converts Markdown to Word." in text


def test_native_endnote_part_and_reference():
    cfg = RenderConfig(notes=NotesConfig(style="endnote"))
    blob = render_string("Text.[^a]\n\n[^a]: Endnote with $x^2$.\n", config=cfg)
    report = inspect_docx_bytes(blob)
    assert report.endnote_references == 1
    assert report.endnote_definitions == 1
    assert report.footnote_references == 0
    with ZipFile(BytesIO(blob)) as z:
        assert "word/endnotes.xml" in z.namelist()


def test_native_footnotes_remain_default():
    blob = render_string("Text.[^a]\n\n[^a]: Footnote.\n")
    report = inspect_docx_bytes(blob)
    assert report.footnote_references == 1
    assert report.endnote_references == 0


def test_bibtex_citation_and_bibliography(tmp_path):
    (tmp_path / "refs.bib").write_text('@article{smith2025, author={Smith, Jane}, title={Word Systems}, year={2025}}')
    md = "Research [@smith2025].\n\n::: bibliography\n:::\n"
    cfg = RenderConfig(citations=CitationConfig(bibliography=Path("refs.bib"), style="apa"))
    blob = render_string(md, config=cfg, base_dir=tmp_path)
    root = xml_part(blob)
    text = " ".join("".join(root.itertext()).split())
    assert "Smith, 2025" in text
    assert "Word Systems" in text


def test_auto_bibliography(tmp_path):
    (tmp_path / "refs.bib").write_text('@article{k1, author={Lee, Ada}, title={Compiler Design}, year={2026}}')
    cfg = RenderConfig(citations=CitationConfig(bibliography=Path("refs.bib"), auto_bibliography=True))
    blob = render_string("Text [@k1].\n", config=cfg, base_dir=tmp_path)
    text = "".join(xml_part(blob).itertext())
    assert "References" in text and "Compiler Design" in text


def test_figure_alt_title_width_alignment_and_caption(tmp_path):
    Image.new("RGB", (1200, 400), "white").save(tmp_path / "figure.png", dpi=(300,300))
    md = '![Architecture](figure.png "Architecture title"){#fig-a width=50% align=right caption="System architecture"}\n\nSee [Figure @fig-a].\n'
    blob = render_string(md, base_dir=tmp_path)
    root = xml_part(blob)
    docpr = root.xpath(".//wp:docPr", namespaces=NS)[0]
    assert docpr.get("descr") == "Architecture"
    assert docpr.get("title") == "Architecture title"
    report = inspect_docx_bytes(blob)
    assert report.images_missing_alt == 0
    assert report.seq_fields == 1 and report.ref_fields == 1


def test_decorative_figure_marks_word_decorative_extension(tmp_path):
    Image.new("RGB", (200,100), "white").save(tmp_path / "deco.png")
    blob = render_string('![](deco.png){decorative=true}\n', base_dir=tmp_path)
    root = xml_part(blob)
    assert root.xpath(".//adec:decorative[@val='1']", namespaces=NS)
    assert inspect_docx_bytes(blob).images_missing_alt == 0


@pytest.mark.parametrize("kind, prefix", [
    ("Table", "tbl"), ("Equation", "eq"), ("Listing", "lst")
])
def test_reference_prefixes_are_rendered(kind, prefix):
    if kind == "Table":
        md = f"See [{kind} @{prefix}-x].\n\n|A|\n|-|\n|1|\n\nTable: X {{#{prefix}-x}}\n"
    elif kind == "Equation":
        md = f"See [{kind} @{prefix}-x].\n\n$$ x=1 $$ {{#{prefix}-x}}\n"
    else:
        md = f'See [{kind} @{prefix}-x].\n\n```text {{#{prefix}-x caption="X"}}\nx\n```\n'
    blob = render_string(md)
    text = "".join(xml_part(blob).itertext())
    assert kind in text
    assert inspect_docx_bytes(blob).ref_fields == 1


def test_section_scoped_equation_numbering_uses_hidden_native_sequences():
    cfg = RenderConfig(references=ReferenceConfig(equation_number_format="section"))
    md = "# One {#sec-one}\n\n$$x=1$$ {#eq-one}\n\n# Two {#sec-two}\n\n$$y=2$$ {#eq-two}\n\nSee [Equation @eq-two].\n"
    blob = render_string(md, config=cfg)
    with ZipFile(BytesIO(blob)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "SEQ Section" in xml
    assert "SEQ Equation" in xml
    assert "2.1" in xml
    assert inspect_docx_bytes(blob).ref_fields == 1


def test_explicit_references_heading_is_not_duplicated(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text('@article{k1, author={Ada Lee}, title={Compiler Design}, year={2026}}', encoding='utf-8')
    cfg = RenderConfig(citations=CitationConfig(bibliography=bib))
    blob = render_string('# References\n\n::: bibliography\n:::\n', config=cfg, base_dir=tmp_path)
    root = xml_part(blob)
    paragraphs = [''.join(p.itertext()).strip() for p in root.xpath('.//w:body/w:p', namespaces=NS)]
    assert sum(text == 'References' for text in paragraphs) == 1


def test_crossrefs_can_render_as_static_text_without_ref_fields():
    cfg = RenderConfig(references=ReferenceConfig(enabled=False))
    blob = render_string('# Results {#results}\n\nSee [Section @results].\n')
    # Baseline config still emits a field.
    assert inspect_docx_bytes(blob).ref_fields == 1
    blob = render_string('# Results {#results}\n\nSee [Section @results].\n', config=cfg)
    text = ''.join(xml_part(blob).itertext())
    assert 'See Section Results.' in text
    assert inspect_docx_bytes(blob).ref_fields == 0
