from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree
import pytest

from mddocx import MarkdownWord, RenderConfig, inspect_docx_bytes
from mddocx.cli import main
from mddocx.config import ValidationConfig
from mddocx.diagnostics import MddocxError
from mddocx.ooxml.sequence import get_or_add, insert_ordered
from mddocx.validation import validate_docx_package


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}

# The defects this validation exists to catch shipped in 1.4.0: heading and
# caption bookmarks were written before ``w:pPr``, and section-scoped counters
# never restarted. Both were found by hand because the package validation only
# checked the ZIP and relationship structure, never the content model.
_HISTORICAL = "# Heading\n\nBody with a note.[^n]\n\n[^n]: note body\n"


def _parts(blob: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(blob)) as package:
        return {name: package.read(name) for name in package.namelist()}


def _rezip(parts: dict[str, bytes]) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w") as package:
        for name, data in parts.items():
            package.writestr(name, data)
    return stream.getvalue()


def _serialize(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _move_properties_to_end(blob: bytes) -> bytes:
    """Reproduce the 1.4.0 bookmark defect: ``w:pPr`` after paragraph content."""
    parts = _parts(blob)
    document = etree.fromstring(parts["word/document.xml"])
    paragraphs = document.xpath(".//w:p[w:pPr][w:bookmarkStart]", namespaces=NS)
    assert paragraphs, "expected a bookmarked heading paragraph"
    target = paragraphs[0]
    properties = target.find(qn("w:pPr"))
    target.remove(properties)
    target.append(properties)
    parts["word/document.xml"] = _serialize(document)
    return _rezip(parts)


def _move_run_properties_to_end(blob: bytes) -> bytes:
    """Put ``w:rPr`` after the run text, which the run sequence forbids."""
    parts = _parts(blob)
    document = etree.fromstring(parts["word/document.xml"])
    runs = document.xpath(".//w:r[w:rPr][w:t]", namespaces=NS)
    assert runs, "expected a run with properties and text"
    target = runs[0]
    properties = target.find(qn("w:rPr"))
    target.remove(properties)
    target.append(properties)
    parts["word/document.xml"] = _serialize(document)
    return _rezip(parts)


def test_bookmark_before_paragraph_properties_is_reported():
    blob = MarkdownWord().render_string(_HISTORICAL)
    report = inspect_docx_bytes(_move_properties_to_end(blob))

    assert not report.ok
    assert any("w:pPr" in violation for violation in report.schema_order_violations)
    assert "Content-model order violations" in report.to_text()


def test_run_properties_after_run_text_is_reported():
    blob = MarkdownWord().render_string(_HISTORICAL)
    report = inspect_docx_bytes(_move_run_properties_to_end(blob))

    assert not report.ok
    assert any("w:rPr" in violation for violation in report.schema_order_violations)


def test_render_validation_rejects_a_content_model_departure():
    blob = MarkdownWord().render_string(_HISTORICAL)
    doctored = _move_properties_to_end(blob)

    validate_docx_package(blob, ValidationConfig())
    with pytest.raises(MddocxError) as error:
        validate_docx_package(doctored, ValidationConfig())
    assert error.value.diagnostic.code == "DOCX422"
    validate_docx_package(doctored, ValidationConfig(validate_schema_order=False))


def test_inspect_strict_fails_on_a_content_model_departure(tmp_path: Path, capsys):
    blob = MarkdownWord().render_string(_HISTORICAL)
    target = tmp_path / "doctored.docx"
    target.write_bytes(_move_properties_to_end(blob))

    assert main(["inspect", str(target)]) == 0
    capsys.readouterr()

    assert main(["inspect", str(target), "--strict"]) == 2
    output = capsys.readouterr().out
    assert "Content-model order violations" in output
    assert "w:pPr" in output

    assert main(["inspect", str(target), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_order_violations"]
    assert payload["ok"] is False


@pytest.mark.parametrize(
    "markdown",
    [
        "- one\n- two\n  - nested\n",
        "# Heading numbering\n\nBody.\n",
        "| A | B |\n| --- | --- |\n| 1 | 2 |\n",
        "```python\nprint('x')\n```\n",
        "Shaded text {>>comment<<}\n",
    ],
)
def test_hand_written_word_xml_keeps_the_content_model_order(markdown: str):
    config = RenderConfig()
    config.heading_numbering.enabled = True
    blob = MarkdownWord(config).render_string(markdown)

    assert inspect_docx_bytes(blob).schema_order_violations == []


@pytest.mark.parametrize(
    "fixture, base_dir",
    [
        ("technical_report/report.md", "technical_report"),
        ("multilingual/polyglot.md", "multilingual"),
        ("ai_markdown/chatgpt_sphere_equations.md", "ai_markdown"),
    ],
)
def test_shipped_fixtures_render_without_content_model_departures(fixture: str, base_dir: str):
    directory = FIXTURES / base_dir
    markdown = (directory / Path(fixture).name).read_text(encoding="utf-8")

    inspection = inspect_docx_bytes(MarkdownWord().render_string(markdown, base_dir=directory))

    assert inspection.schema_order_violations == []
    assert inspection.ok


def test_numbering_suffix_precedes_level_text():
    blob = MarkdownWord().render_string("- one\n- two\n")
    numbering = etree.fromstring(_parts(blob)["word/numbering.xml"])
    levels = numbering.xpath(".//w:lvl[w:suff]", namespaces=NS)

    assert levels, "expected mddocx to write its own list levels"
    for level in levels:
        order = [child.tag.rsplit("}", 1)[1] for child in level]
        assert order.index("numFmt") < order.index("suff") < order.index("lvlText")


def test_insert_ordered_uses_the_parent_sequence():
    ppr = etree.fromstring(
        '<w:pPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:spacing/><w:ind/><w:jc/></w:pPr>"
    )
    shd = OxmlElement("w:shd")
    insert_ordered(ppr, shd)

    assert [child.tag.rsplit("}", 1)[1] for child in ppr] == ["shd", "spacing", "ind", "jc"]

    # A parent outside the rule table keeps the append behavior.
    custom = etree.fromstring(
        '<w:custom xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
    )
    insert_ordered(custom, OxmlElement("w:shd"))
    assert len(custom) == 1


def test_get_or_add_reuses_the_existing_child_in_sequence_order():
    ppr = etree.fromstring(
        '<w:pPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:spacing/></w:pPr>"
    )

    first = get_or_add(ppr, "w:shd")
    first.set(qn("w:fill"), "F3F3F3")
    second = get_or_add(ppr, "w:shd")

    assert first is second
    assert [child.tag.rsplit("}", 1)[1] for child in ppr] == ["shd", "spacing"]


def test_cell_properties_precede_cell_content():
    blob = MarkdownWord().render_string("| A | B |\n| --- | --- |\n| 1 | 2 |\n")
    document = etree.fromstring(_parts(blob)["word/document.xml"])

    for cell in document.xpath(".//w:tc", namespaces=NS):
        names = [child.tag.rsplit("}", 1)[1] for child in cell]
        assert names[0] == "tcPr"
