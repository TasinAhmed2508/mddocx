from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from mddocx import MarkdownWord, NotesConfig, RenderConfig, inspect_docx_bytes
from mddocx.math.converter import DefaultMathConverter
from mddocx.ooxml.comments import COMMENT_CT, COMMENT_REL


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
    converter._sidecar.executable = None
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
        root = etree.fromstring(package.read("word/endnotes.xml"))

    assert "word/endnotes.xml" in names
    assert inspection.endnote_references == 1
    assert inspection.endnote_definitions == 1
    assert inspection.duplicate_note_ids == 0
    assert inspection.broken_relationships == []
    # Separator items belong to the part they live in; a footnote item inside
    # endnotes.xml is invalid and makes Word treat the part as damaged.
    assert root.tag.endswith("}endnotes")
    assert not root.xpath(".//w:footnote", namespaces=NS)
    separators = root.xpath("./w:endnote", namespaces=NS)[:2]
    assert [item.get(f"{{{NS['w']}}}type") for item in separators] == [
        "separator",
        "continuationSeparator",
    ]


def test_section_scoped_counter_fields_use_word_switches():
    config = RenderConfig()
    config.references.equation_number_format = "section"
    config.references.caption_number_format = "section"
    config.heading_numbering.enabled = True
    markdown = '# Section\n\n$$\nE=mc^2\n$$ {#eq-a caption="Energy"}\n\nSee [Equation @eq-a].\n'
    blob = MarkdownWord(config).render_string(markdown)
    with ZipFile(BytesIO(blob)) as package:
        root = etree.fromstring(package.read("word/document.xml"))
    instructions = [node.text or "" for node in root.xpath(".//w:instrText", namespaces=NS)]

    # A carriage return here means the reset switch is missing, so Word never
    # restarts section-scoped figure, table, or listing numbering.
    assert instructions
    assert not any("\r" in instruction or "\n" in instruction for instruction in instructions)
    for label in ("Figure", "Table", "Listing"):
        assert any(instruction.strip() == f"SEQ {label} \\r 0" for instruction in instructions)
    # Word field switches start with a backslash; chr(92) keeps this assertion
    # immune to test-file escaping rules.
    switch = chr(92)
    assert any(f"{switch}r 1 {switch}s 1" in instruction for instruction in instructions)


def test_paragraph_properties_precede_bookmarks():
    blob = MarkdownWord().render_string("# First {#sec-one}\n\nBody.\n\n## Second\n")
    with ZipFile(BytesIO(blob)) as package:
        root = etree.fromstring(package.read("word/document.xml"))
    marked = [
        p
        for p in root.xpath(".//w:p", namespaces=NS)
        if p.xpath("./w:bookmarkStart", namespaces=NS)
    ]

    assert marked
    for paragraph in marked:
        children = [child.tag for child in paragraph if isinstance(child.tag, str)]
        first_bookmark = next(
            index for index, tag in enumerate(children) if tag.endswith("}bookmarkStart")
        )
        properties = [index for index, tag in enumerate(children) if tag.endswith("}pPr")]
        assert properties, "every rendered paragraph should carry properties"
        assert properties[0] < first_bookmark


def test_package_part_registration_is_idempotent():
    from mddocx.ooxml.package import (
        add_content_type_override,
        add_document_relationship,
        read_parts,
    )

    blob = MarkdownWord().render_string("# Report")
    parts = read_parts(blob)
    for _ in range(2):
        add_content_type_override(parts, "/word/comments.xml", COMMENT_CT)
        add_document_relationship(parts, COMMENT_REL, "comments.xml")

    content_types = etree.fromstring(parts["[Content_Types].xml"])
    relationships = etree.fromstring(parts["word/_rels/document.xml.rels"])
    overrides = [
        element.get("PartName")
        for element in content_types
        if element.get("PartName") == "/word/comments.xml"
    ]
    matching = [rel for rel in relationships if rel.get("Type") == COMMENT_REL]

    assert overrides == ["/word/comments.xml"]
    assert len(matching) == 1
    assert matching[0].get("Target") == "comments.xml"
