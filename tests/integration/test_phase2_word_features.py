from io import BytesIO
from zipfile import ZipFile

from docx import Document

from mddocx import (
    FooterConfig, HeaderConfig, RenderConfig, TOCConfig, render_string,
)


def _zip_text(blob: bytes, name: str) -> str:
    with ZipFile(BytesIO(blob)) as z:
        return z.read(name).decode("utf-8")


def test_front_matter_drives_metadata_toc_page_fields_bookmarks_and_sections():
    md = r"""---
title: Phase 2 Report
author: Ada Example
subject: Native Word
keywords: math, tables
toc: true
page_numbers: true
---
# First Section

Inline $x^2$.

$$
\sum_{i=1}^{n} i
$$

<!-- sectionbreak -->

# Second Section
"""
    blob = render_string(md)
    Document(BytesIO(blob))
    document_xml = _zip_text(blob, "word/document.xml")
    core_xml = _zip_text(blob, "docProps/core.xml")
    settings_xml = _zip_text(blob, "word/settings.xml")
    with ZipFile(BytesIO(blob)) as z:
        footer_names = [n for n in z.namelist() if n.startswith("word/footer") and n.endswith(".xml")]
        footer_xml = "\n".join(z.read(n).decode("utf-8") for n in footer_names)
    assert "Phase 2 Report" in core_xml and "Ada Example" in core_xml
    assert "TOC" in document_xml
    assert "bookmarkStart" in document_xml
    assert document_xml.count("<w:sectPr") >= 2
    assert "PAGE" in footer_xml
    assert "updateFields" in settings_xml
    assert "m:nary" in document_xml


def test_explicit_config_overrides_front_matter_and_adds_header_footer():
    cfg = RenderConfig(
        title="API Title",
        header=HeaderConfig(enabled=True, document_title=True, section_title=True),
        footer=FooterConfig(enabled=True, text="Confidential", page_number=True),
        toc=TOCConfig(enabled=True, min_level=1, max_level=2),
    )
    blob = render_string("---\ntitle: Front Matter Title\n---\n# A\n\nText", config=cfg)
    core_xml = _zip_text(blob, "docProps/core.xml")
    with ZipFile(BytesIO(blob)) as z:
        headers = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/header") and n.endswith(".xml"))
        footers = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/footer") and n.endswith(".xml"))
    assert "API Title" in core_xml and "Front Matter Title" not in core_xml
    assert "API Title" in headers and "STYLEREF" in headers
    assert "Confidential" in footers and "PAGE" in footers


def test_tables_repeat_headers_size_columns_and_allow_long_rows_to_split():
    long = "word " * 150
    md = f"""| A | B | C |
|---|:---:|---:|
| short | center | 1 |
| {long} | value | 2 |
"""
    blob = render_string(md)
    xml = _zip_text(blob, "word/document.xml")
    assert "tblHeader" in xml
    assert "tblLayout" in xml or "tcW" in xml
    assert 'w:cantSplit w:val="1"' in xml
    assert 'w:cantSplit w:val="0"' in xml
