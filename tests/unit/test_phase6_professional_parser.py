from mddocx.attributes import parse_attribute_list, parse_line_spec
from mddocx.ast.block import Callout, CodeBlock, Heading
from mddocx.ast.inline import Comment
from mddocx.parser import MarkdownParser


def test_central_attribute_parser_classes_values_and_lines():
    attrs = parse_attribute_list('{#code .python linenos=true highlight="2-4,7" caption="Demo"}')
    assert attrs.identifier == "code"
    assert attrs.classes == ("python",)
    assert attrs.bool("linenos") is True
    assert attrs.get("caption") == "Demo"
    assert parse_line_spec(attrs.get("highlight")) == (2, 3, 4, 7)


def test_github_callout_and_container_callout_promote_to_ast():
    doc = MarkdownParser().parse("> [!NOTE]\n> Useful text.\n\n::: warning Custom title\nDanger.\n:::\n")
    assert isinstance(doc.children[0], Callout)
    assert doc.children[0].kind == "note"
    assert isinstance(doc.children[1], Callout)
    assert doc.children[1].kind == "warning"
    assert doc.children[1].title == "Custom title"


def test_fenced_code_attributes_are_canonicalized():
    doc = MarkdownParser().parse('```python {#demo linenos=true highlight="2-3" label=true caption="Example"}\na=1\nb=2\nc=3\n```')
    node = doc.children[0]
    assert isinstance(node, CodeBlock)
    assert node.identifier == "demo"
    assert node.line_numbers is True
    assert node.highlight_lines == (2, 3)
    assert node.show_language_label is True
    assert node.caption == "Example"


def test_criticmarkup_comment_becomes_comment_node():
    doc = MarkdownParser().parse("Review this{>>Please verify this sentence.<<} carefully.")
    paragraph = doc.children[0]
    assert any(isinstance(n, Comment) and "verify" in n.text for n in paragraph.children)


def test_heading_attribute_still_uses_central_parser():
    doc = MarkdownParser().parse("## Results {#results .important}")
    assert isinstance(doc.children[0], Heading)
    assert doc.children[0].identifier == "results"
