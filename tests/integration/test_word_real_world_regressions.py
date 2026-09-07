from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from mddocx import render_string
from mddocx.ast.block import Table
from mddocx.parser import MarkdownParser

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}


def _parts(blob: bytes):
    with ZipFile(BytesIO(blob)) as z:
        return (
            etree.fromstring(z.read("word/document.xml")),
            etree.fromstring(z.read("word/styles.xml")),
            etree.fromstring(z.read("word/numbering.xml")),
        )


def test_word_list_markers_use_unicode_capable_fonts_black_headings_and_good_spacing():
    blob = render_string("# Heading\n\n- Alpha\n  - Beta\n    - Gamma\n\n1. First\n2. Second\n")
    _, styles, numbering = _parts(blob)

    h1 = styles.xpath('.//w:style[@w:styleId="MDHeading1"]', namespaces=NS)[0]
    assert h1.xpath('./w:rPr/w:color/@w:val', namespaces=NS) == ["000000"]

    bullet_lvls = numbering.xpath('.//w:lvl[@w:ilvl="0"][w:lvlText[@w:val="•"]]', namespaces=NS)
    assert bullet_lvls
    assert bullet_lvls[-1].xpath('./w:rPr/w:rFonts/@w:ascii', namespaces=NS) == ["Arial"]
    assert bullet_lvls[-1].xpath('./w:suff/@w:val', namespaces=NS) == ["space"]
    assert bullet_lvls[-1].xpath('./w:pPr/w:ind/@w:left', namespaces=NS) == ["360"]

    decimal = numbering.xpath('.//w:abstractNum[w:lvl[@w:ilvl="8"] and w:lvl/w:numFmt[@w:val="decimal"]]', namespaces=NS)[-1]
    assert decimal.xpath('./w:lvl[@w:ilvl="0"]/w:suff/@w:val', namespaces=NS) == ["space"]
    assert decimal.xpath('./w:lvl[@w:ilvl="0"]/w:rPr/w:rFonts/@w:ascii', namespaces=NS)


def test_pandoc_simple_tables_are_normalized_to_native_tables():
    md = """
  ------------------- -------------------
  Name                Result
  ------------------- -------------------
  Alpha               10

  Beta                20
  ---------------------------------------

  Left       Center         Right
  ------- ------------ ----------
  alpha      12.345           100
  beta       0.001          2,500
"""
    doc = MarkdownParser().parse(md)
    tables = [n for n in doc.children if isinstance(n, Table)]
    assert len(tables) == 2
    assert len(tables[0].rows) == 3
    assert len(tables[1].rows) == 3
    blob = render_string(md)
    document, _, _ = _parts(blob)
    assert document.xpath('count(.//w:tbl)', namespaces=NS) == 2


def test_full_stress_fixture_has_no_nary_or_root_placeholders_and_keeps_tables():
    fixture = Path(__file__).parents[1] / "fixtures" / "markdown_stress_test.md"
    markdown = fixture.read_text(encoding="utf-8")
    blob = render_string(markdown)
    document, styles, _ = _parts(blob)

    assert document.xpath('count(.//w:tbl)', namespaces=NS) >= 2
    assert not document.xpath('.//m:nary/m:e[not(*)]', namespaces=NS)
    assert not document.xpath('.//m:rad[not(m:deg)]', namespaces=NS)
    assert document.xpath('count(.//m:acc)', namespaces=NS) >= 1
    assert document.xpath('count(.//m:borderBox)', namespaces=NS) >= 1
    h1 = styles.xpath('.//w:style[@w:styleId="MDHeading1"]/w:rPr/w:color/@w:val', namespaces=NS)
    assert h1 == ["000000"]
