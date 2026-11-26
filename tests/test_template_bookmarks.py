from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
import pytest

from mddocx import Compiler, RenderConfig, inspect_docx_bytes
from mddocx.diagnostics import MddocxError
from mddocx.ooxml.fields import (
    add_bookmark,
    add_internal_hyperlink,
    add_ref_field,
    read_field_instructions,
)
from mddocx.ooxml.notes import (
    ENDNOTE,
    FOOTNOTE,
    append_note,
    append_note_reference,
    open_note_part,
)
from mddocx.validation import validated_docx_parts


@pytest.mark.parametrize("story", ["body", "header", "footer", "footnote", "endnote"])
@pytest.mark.parametrize("validate", [True, False])
def test_template_bookmarks_reserve_names_and_ids(tmp_path: Path, story: str, validate: bool):
    template = Document()
    if story == "body":
        paragraph = template.add_paragraph("Template content")
    elif story in {"header", "footer"}:
        paragraph = getattr(template.sections[0], story).paragraphs[0]
        paragraph.text = "Template content"
    else:
        spec = FOOTNOTE if story == "footnote" else ENDNOTE
        part = open_note_part(template.part, spec)
        append_note_reference(template.add_paragraph("Template note"), 1, spec)
        paragraph = append_note(part, 1, spec)
        paragraph.add_run("Template content")
    reserved = {"report": 10, "samples": 50, "energy": 90, "report_2": 120}
    for name, bookmark_id in reserved.items():
        add_bookmark(paragraph, name, bookmark_id)
    template_path = tmp_path / "template.docx"
    template.save(template_path)

    config = RenderConfig(template=template_path)
    config.validation.validate_output = validate
    source = (
        "# Report {#report}\n\n"
        "| Reading |\n| --- |\n| 12 |\n\nTable: Samples {#samples}\n\n"
        '$$\nE=mc^2\n$$ {#energy caption="Energy"}\n\n'
        "See [Section @report], [Table @samples], [Equation @energy], and [report](#report)."
    )
    result = Compiler(config).compile_string(source)
    roots = validated_docx_parts(result.output_bytes, RenderConfig().validation)
    starts = [node for root in roots.values() for node in root.iter(qn("w:bookmarkStart"))]
    bookmarks = {node.get(qn("w:name")): int(node.get(qn("w:id"))) for node in starts}
    assert len(bookmarks) == len(starts) == 7
    assert len(set(bookmarks.values())) == 7
    assert {name: bookmarks[name] for name in reserved} == reserved
    assert {name: bookmarks[name] for name in ("report_3", "samples_2", "energy_2")} == {
        "report_3": 121,
        "samples_2": 122,
        "energy_2": 123,
    }
    ends = [node for root in roots.values() for node in root.iter(qn("w:bookmarkEnd"))]
    assert {node.get(qn("w:id")) for node in starts} == {node.get(qn("w:id")) for node in ends}
    body = roots["word/document.xml"]
    assert [words[1] for words in read_field_instructions(body) if words[0] == "REF"] == [
        "report_3",
        "samples_2",
        "energy_2",
    ]
    assert [node.get(qn("w:anchor")) for node in body.iter(qn("w:hyperlink"))] == ["report_3"]


@pytest.mark.parametrize("story", ["header", "footer"])
@pytest.mark.parametrize("duplicate", [False, True])
def test_header_footer_bookmarks_participate_in_validation(story, duplicate):
    document = Document()
    paragraph = getattr(document.sections[0], story).paragraphs[0]
    paragraph.text = "Template text"
    add_bookmark(paragraph, "legacy", 10)
    body = document.add_paragraph()
    add_ref_field(body, "legacy", "Template text")
    add_internal_hyperlink(body, "Template link", "legacy")
    if duplicate:
        add_bookmark(body, "legacy", 11)
    stream = BytesIO()
    document.save(stream)
    blob = stream.getvalue()
    report = inspect_docx_bytes(blob)
    assert report.bookmarks == (2 if duplicate else 1)
    assert report.duplicate_bookmark_names == int(duplicate)
    assert report.dangling_internal_hyperlinks == 0
    assert report.dangling_ref_fields == 0
    if duplicate:
        with pytest.raises(MddocxError) as caught:
            validated_docx_parts(blob, RenderConfig().validation)
        assert caught.value.diagnostic.code == "DOCX416"
    else:
        validated_docx_parts(blob, RenderConfig().validation)
