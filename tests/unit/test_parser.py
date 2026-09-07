from mddocx.parser import MarkdownParser
from mddocx.ast.block import Heading, OrderedList, Table, MathBlock
from mddocx.ast.inline import Strong, InlineMath


def test_parser_emits_canonical_nodes():
    md = """# Title\n\nThis is **bold** with $x^2$.\n\n1. One\n2. Two\n\n| A | B |\n|---|---:|\n| x | 1 |\n\n$$\n\\frac{x}{y}\n$$\n"""
    doc = MarkdownParser().parse(md, "sample.md")
    assert isinstance(doc.children[0], Heading)
    para = doc.children[1]
    assert any(isinstance(n, Strong) for n in para.children)
    assert any(isinstance(n, InlineMath) for n in para.children)
    assert any(isinstance(n, OrderedList) for n in doc.children)
    assert any(isinstance(n, Table) for n in doc.children)
    assert any(isinstance(n, MathBlock) for n in doc.children)


def test_parenthesized_math_is_normalized():
    doc = MarkdownParser().parse(r"Value: \(a_1\).")
    assert any(isinstance(n, InlineMath) and n.source_text == "a_1" for n in doc.children[0].children)
