from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from mddocx import MarkdownWord, NotesConfig, RenderConfig, inspect_docx_bytes
from mddocx.math.converter import DefaultMathConverter


NS = {
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


@pytest.mark.parametrize(
    ("latex", "native_xpath"),
    [
        (r"\frac{a+b}{c}", ".//m:f"),
        (r"x_i^2", ".//m:sSubSup"),
        (r"\sqrt[3]{x}", ".//m:rad"),
        (r"\begin{bmatrix}a & b \\ c & d\end{bmatrix}", ".//m:m"),
        (r"\left(\frac{x}{y}\right)", ".//m:d"),
        (r"\widehat{x}+\vec{v}", ".//m:acc"),
        (r"\sum_{i=1}^{n} i", ".//m:nary"),
        (r"\begin{aligned}x&=1 \\ y&=2\end{aligned}", ".//m:m"),
    ],
)
def test_builtin_math_conformance_corpus_is_native(latex: str, native_xpath: str):
    converter = DefaultMathConverter(cache=False)
    converter._external = None

    omml = converter.latex_to_omml(latex, display=True)

    assert omml.xpath(native_xpath, namespaces=NS)
    assert "\\" not in "".join(omml.itertext())


def test_mixed_nested_and_restarted_lists_use_native_numbering():
    markdown = """4. Fourth
5. Fifth

   - Nested bullet
   - Another bullet

7. Seventh after explicit source restart

- Outer
  1. Nested ordered
  2. Nested second
"""
    blob = MarkdownWord().render_string(markdown)
    inspection = inspect_docx_bytes(blob)
    with ZipFile(BytesIO(blob)) as package:
        numbering = etree.fromstring(package.read("word/numbering.xml"))

    assert inspection.native_list_paragraphs >= 8
    assert numbering.xpath(".//w:start[@w:val='4']", namespaces=NS)
    assert numbering.xpath(".//w:numFmt[@w:val='decimal']", namespaces=NS)
    assert numbering.xpath(".//w:numFmt[@w:val='bullet']", namespaces=NS)


def test_native_endnotes_are_packaged_and_related_consistently():
    markdown = "A claim.[^source]\n\n[^source]: Endnote with inline math \\(x^2\\)."
    blob = MarkdownWord(RenderConfig(notes=NotesConfig(style="endnote"))).render_string(markdown)
    inspection = inspect_docx_bytes(blob)
    with ZipFile(BytesIO(blob)) as package:
        names = set(package.namelist())

    assert "word/endnotes.xml" in names
    assert inspection.endnote_references == 1
    assert inspection.endnote_definitions == 1
    assert inspection.duplicate_note_ids == 0
    assert inspection.broken_relationships == []
