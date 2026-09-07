from mddocx.parser import MarkdownParser


def test_yaml_front_matter_is_preserved_and_source_lines_are_adjusted():
    doc = MarkdownParser().parse("""---
title: Phase Two
toc: true
page_numbers: true
---
# Heading
""", "report.md")
    assert doc.metadata["title"] == "Phase Two"
    assert doc.metadata["toc"] is True
    assert doc.children[0].source.line == 6


def test_phase6_frontmatter_keys_are_preserved_for_config_layer():
    doc = MarkdownParser().parse("""---\ntitle_page: true\nsubtitle: Professional\nabstract: Summary\nheading_numbering: true\ncaption_numbering: section\ncode_line_numbers: true\n---\n# Body\n""")
    assert doc.metadata["title_page"] is True
    assert doc.metadata["subtitle"] == "Professional"
    assert doc.metadata["caption_numbering"] == "section"
