from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

import mddocx
from mddocx import MarkdownWord, RenderConfig, render_string


NS = {
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


def _part(blob: bytes, name: str):
    with ZipFile(BytesIO(blob)) as package:
        assert package.testzip() is None
        return etree.fromstring(package.read(name))


def test_gfm_core_constructs_render_as_native_word_structures():
    markdown = """# Report

Paragraph with **bold**, *emphasis*, and [a link](https://example.com).

1. First
2. Second

| Metric | Value |
| --- | ---: |
| Growth | 18% |
"""
    blob = render_string(markdown)
    document = _part(blob, "word/document.xml")

    assert document.xpath(".//w:pStyle[@w:val='MDHeading1']", namespaces=NS)
    assert document.xpath(".//w:b", namespaces=NS)
    assert document.xpath(".//w:i", namespaces=NS)
    assert document.xpath(".//w:hyperlink[@r:id]", namespaces=NS)
    assert len(document.xpath(".//w:numPr", namespaces=NS)) == 2
    assert len(document.xpath(".//w:tbl", namespaces=NS)) == 1


def test_default_render_is_byte_reproducible():
    markdown = "# Stable\n\nText with \\(x^2\\)."

    assert render_string(markdown) == render_string(markdown)


def test_public_manifest_names_exist_on_package():
    manifest = mddocx.get_public_api_manifest()

    assert manifest.api_version == "1"
    assert all(hasattr(mddocx, name) for name in manifest.names)


def test_public_manifest_retains_the_frozen_v1_snapshot():
    snapshot = json.loads(
        (Path(__file__).parent / "fixtures" / "public_api_v1.json").read_text(encoding="utf-8")
    )
    manifest = mddocx.get_public_api_manifest()

    assert snapshot["api_version"] == manifest.api_version
    assert set(snapshot["names"]).issubset(manifest.names)
    assert len(manifest.names) == len(set(manifest.names))


def test_warning_fallback_still_produces_valid_docx_package():
    compiler = MarkdownWord(RenderConfig())
    blob = compiler.render_string("# Before\n\n$$\\unknowncommand{x}$$\n\nAfter")

    document = _part(blob, "word/document.xml")
    text = document.xpath("string(.//w:body)", namespaces=NS)
    assert "Before" in text and "After" in text and "\\unknowncommand{x}" in text
    assert [diagnostic.code for diagnostic in compiler.diagnostics] == ["MATH201"]


def test_raw_html_policy_preserves_source_as_literal_editable_text():
    markdown = "Before <mark>inline</mark>.\n\n<div>block</div>\n\nAfter."
    blob = render_string(markdown)
    document = _part(blob, "word/document.xml")
    text = document.xpath("string(.//w:body)", namespaces=NS)

    assert "Before <mark>inline</mark>." in text
    assert "<div>block</div>" in text
    assert "After." in text
