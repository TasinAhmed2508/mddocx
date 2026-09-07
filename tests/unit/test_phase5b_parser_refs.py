from mddocx.ast.block import BibliographyBlock, CodeBlock, DefinitionList, Heading, ImageBlock, MathBlock, Table
from mddocx.ast.inline import Citation, CrossReference, Link
from mddocx.parser import MarkdownParser


def test_heading_identifier_is_removed_from_visible_text():
    doc = MarkdownParser().parse("# Results {#sec-results}\n")
    h = doc.children[0]
    assert isinstance(h, Heading)
    assert h.identifier == "sec-results"
    assert h.children[0].text == "Results"


def test_math_identifier_after_display_close():
    doc = MarkdownParser().parse("$$\nx^2\n$$ {#eq-square}\n")
    assert isinstance(doc.children[0], MathBlock)
    assert doc.children[0].identifier == "eq-square"


def test_one_line_math_identifier():
    doc = MarkdownParser().parse("$$ E=mc^2 $$ {#eq-energy}\n")
    assert isinstance(doc.children[0], MathBlock)
    assert doc.children[0].identifier == "eq-energy"


def test_image_attribute_list():
    doc = MarkdownParser().parse('![A diagram](a.png "Title"){#fig-a width=55% align=right caption="Architecture"}\n')
    image = doc.children[0]
    assert isinstance(image, ImageBlock)
    assert image.identifier == "fig-a"
    assert image.width_percent == 55.0
    assert image.align == "right"
    assert image.caption == "Architecture"


def test_decorative_image_attribute():
    doc = MarkdownParser().parse('![](a.png){#fig-deco decorative=true}\n')
    assert isinstance(doc.children[0], ImageBlock)
    assert doc.children[0].decorative is True


def test_table_caption_and_identifier():
    doc = MarkdownParser().parse("|A|B|\n|-|-|\n|1|2|\n\nTable: Results {#tbl-results}\n")
    table = doc.children[0]
    assert isinstance(table, Table)
    assert table.identifier == "tbl-results"
    assert table.caption == "Results"


def test_listing_attributes_from_fence_info():
    doc = MarkdownParser().parse('```python {#lst-demo caption="Demo code"}\nprint(1)\n```\n')
    block = doc.children[0]
    assert isinstance(block, CodeBlock)
    assert block.identifier == "lst-demo"
    assert block.caption == "Demo code"
    assert block.language == "python"


def test_cross_reference_explicit_prefix():
    doc = MarkdownParser().parse("See [Figure @fig-a].\n")
    ref = next(n for n in doc.children[0].children if isinstance(n, CrossReference))
    assert ref.target == "fig-a"
    assert ref.prefix == "Figure"


def test_cross_reference_shorthand():
    doc = MarkdownParser().parse("See @eq-energy.\n")
    ref = next(n for n in doc.children[0].children if isinstance(n, CrossReference))
    assert ref.target == "eq-energy"
    assert ref.prefix is None


def test_citation_single_with_suffix():
    doc = MarkdownParser().parse("Research [@smith2025, p. 42].\n")
    cite = next(n for n in doc.children[0].children if isinstance(n, Citation))
    assert cite.keys == ["smith2025"]
    assert cite.suffix == "p. 42"


def test_citation_multiple_keys():
    doc = MarkdownParser().parse("Research [@smith2025; @jones2024].\n")
    cite = next(n for n in doc.children[0].children if isinstance(n, Citation))
    assert cite.keys == ["smith2025", "jones2024"]


def test_internal_markdown_link_preserved_for_renderer():
    doc = MarkdownParser().parse("See [Results](#sec-results).\n")
    link = next(n for n in doc.children[0].children if isinstance(n, Link))
    assert link.href == "#sec-results"


def test_bibliography_directive_becomes_semantic_block():
    doc = MarkdownParser().parse("::: bibliography\n:::\n")
    assert isinstance(doc.children[0], BibliographyBlock)


def test_definition_list_becomes_semantic_ast():
    doc = MarkdownParser().parse("Compiler\n: Converts source semantics to Word semantics.\n")
    assert isinstance(doc.children[0], DefinitionList)
    assert doc.children[0].items[0].term[0].text == "Compiler"
