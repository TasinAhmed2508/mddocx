from __future__ import annotations

from mddocx import MarkdownWord
from mddocx.parser import MarkdownParser
from mddocx.ast.inline import CrossReference, InlineMath


def test_inline_nodes_inherit_their_block_source_location():
    document = MarkdownParser().parse(
        "# Heading\n\nLine with \\(x\\) and [Equation @missing].",
        source_file="source.md",
    )
    paragraph = document.children[1]
    math = next(node for node in paragraph.children if isinstance(node, InlineMath))
    reference = next(node for node in paragraph.children if isinstance(node, CrossReference))

    assert math.source.file == "source.md"
    assert math.source.line == 3
    assert reference.source.file == "source.md"
    assert reference.source.line == 3


def test_unresolved_reference_diagnostic_contains_file_and_line():
    compiler = MarkdownWord()
    compiler.parser.source_file = "source.md"
    document = compiler.parser.parse(
        "# Heading\n\nSee [Equation @missing].",
        source_file="source.md",
    )
    compiler.render_ast(document)

    diagnostic = next(item for item in compiler.diagnostics if item.code == "REF202")
    assert diagnostic.source_file == "source.md"
    assert diagnostic.line == 3
