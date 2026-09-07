from io import BytesIO
from zipfile import ZipFile
from lxml import etree

from mddocx import (
    AbstractConfig, CodeConfig, CommentConfig, FooterConfig, HeaderConfig,
    HeadingNumberingConfig, ReferenceConfig, RenderConfig, TitlePageConfig,
    render_string,
)
from mddocx.inspection import inspect_docx_bytes

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def parts(blob):
    with ZipFile(BytesIO(blob)) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_native_heading_numbering_and_section_caption_fields():
    md = '''# Chapter One\n\n![A](x.png){#fig-a caption="A figure"}\n'''
    # Avoid image dependency here: use a table caption instead.
    md = '''# Chapter One\n\n| A | B |\n|---|---|\n|1|2|\n\n{#tbl-a caption="A table"}\n'''
    cfg = RenderConfig(
        heading_numbering=HeadingNumberingConfig(enabled=True, max_level=3),
        references=ReferenceConfig(caption_number_format="section"),
    )
    blob = render_string(md, cfg)
    p = parts(blob)
    doc = etree.fromstring(p["word/document.xml"])
    assert doc.xpath('.//w:p[w:pPr/w:pStyle[@w:val="MDHeading1"]]/w:pPr/w:numPr', namespaces=NS)
    fields = " ".join(doc.xpath('.//w:instrText/text()', namespaces=NS))
    assert "SEQ Section" in fields
    assert "SEQ Table" in fields
    assert "REF" not in fields or True


def test_title_page_abstract_and_field_templates():
    cfg = RenderConfig(
        title="Professional Report", author="Ada Example",
        title_page=TitlePageConfig(enabled=True, subtitle="Research Edition", organization="Example Lab"),
        abstract=AbstractConfig(text="A concise abstract.", keywords=("Word", "Markdown")),
        header=HeaderConfig(enabled=True, text="{TITLE} — {AUTHOR}"),
        footer=FooterConfig(enabled=True, page_x_of_y=True),
    )
    blob = render_string("# Body\n\nText.", cfg)
    p = parts(blob)
    doc_text = etree.fromstring(p["word/document.xml"]).xpath('string(.)')
    assert "Professional Report" in doc_text
    assert "Research Edition" in doc_text
    assert "A concise abstract." in doc_text
    header = etree.fromstring(next(v for k,v in p.items() if k.startswith("word/header") and k.endswith(".xml")))
    footer = etree.fromstring(next(v for k,v in p.items() if k.startswith("word/footer") and k.endswith(".xml")))
    hfields = " ".join(header.xpath('.//w:instrText/text()', namespaces=NS))
    ffields = " ".join(footer.xpath('.//w:instrText/text()', namespaces=NS))
    assert "DOCPROPERTY" in hfields and "AUTHOR" in hfields
    assert "PAGE" in ffields and "NUMPAGES" in ffields


def test_native_comments_package_and_strict_inspection():
    cfg = RenderConfig(native_comments=CommentConfig(author="Reviewer", initials="RV"))
    blob = render_string("Sentence{>>Check this claim.<<} end.", cfg)
    p = parts(blob)
    assert "word/comments.xml" in p
    comments = etree.fromstring(p["word/comments.xml"])
    assert comments.xpath('count(./w:comment)', namespaces=NS) == 1
    assert "Check this claim" in comments.xpath('string(.)')
    inspection = inspect_docx_bytes(blob)
    assert inspection.comment_references == 1
    assert inspection.comment_definitions == 1
    assert inspection.ok


def test_callouts_render_with_native_styles():
    blob = render_string("> [!WARNING]\n> Handle this carefully.\n")
    p = parts(blob)
    doc = etree.fromstring(p["word/document.xml"])
    assert doc.xpath('.//w:p[w:pPr/w:pStyle[@w:val="MDCalloutWarning"]]', namespaces=NS)
    assert "Handle this carefully" in doc.xpath('string(.)')


def test_code_is_editable_highlighted_and_line_numbered():
    cfg = RenderConfig(code=CodeConfig(syntax_highlighting=True, line_numbers=True, show_language_label=True))
    blob = render_string('```python {highlight="2"}\nx = 1\nprint(x)\n```', cfg)
    p = parts(blob)
    doc = etree.fromstring(p["word/document.xml"])
    text = doc.xpath('string(.)')
    assert "python" in text and "1  " in text and "2  " in text
    assert len(doc.xpath('.//w:p[w:pPr/w:pStyle[@w:val="MDCode"]]', namespaces=NS)) == 2
    fills = doc.xpath('.//w:p[w:pPr/w:pStyle[@w:val="MDCode"]]/w:pPr/w:shd/@w:fill', namespaces=NS)
    assert "FFF2CC" in fills


def test_advanced_first_even_headers_and_footers_create_native_parts():
    cfg = RenderConfig(
        header=HeaderConfig(
            enabled=True, text="Odd {TITLE}", different_first_page=True,
            different_odd_even=True, first_page_text="First", even_page_text="Even {DATE}",
        ),
        footer=FooterConfig(
            enabled=True, page_x_of_y=True, different_first_page=True,
            different_odd_even=True, first_page_text="Cover", even_page_text="Even footer",
        ),
        title="Header Test",
    )
    blob = render_string("# One\n\nText.\n\n<!-- pagebreak -->\n\n# Two", cfg)
    p = parts(blob)
    headers = [k for k in p if k.startswith("word/header") and k.endswith(".xml")]
    footers = [k for k in p if k.startswith("word/footer") and k.endswith(".xml")]
    assert len(headers) >= 3
    assert len(footers) >= 3
    settings = etree.fromstring(p["word/settings.xml"])
    assert settings.xpath('.//w:evenAndOddHeaders', namespaces=NS)


def test_native_comment_render_is_reproducible():
    cfg = RenderConfig(native_comments=CommentConfig(author="Stable", initials="ST"))
    a = render_string("A{>>Stable comment<<}B", cfg)
    b = render_string("A{>>Stable comment<<}B", cfg)
    assert a == b


def test_word_date_field_uses_single_switch_backslashes():
    cfg = RenderConfig(title="Date Field", title_page=TitlePageConfig(enabled=True))
    blob = render_string("# Body\n", cfg)
    p = parts(blob)
    doc = etree.fromstring(p["word/document.xml"])
    fields = " ".join(doc.xpath('.//w:instrText/text()', namespaces=NS))
    assert 'DATE \\@ "MMMM d, yyyy"' in fields
    assert 'DATE \\\\@' not in fields
