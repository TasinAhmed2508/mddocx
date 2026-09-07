from pathlib import Path
from lxml import etree

from mddocx.ast.inline import FootnoteReference, InlineMath, Text
from mddocx.diagrams import MermaidRenderer
from mddocx.math.mathml import MathMLToOMML
from mddocx.parser import MarkdownParser


def test_footnotes_are_extracted_and_escaped_reference_stays_literal():
    doc = MarkdownParser().parse(
        "A note.[^1] Escaped: \\[^x]. `[^code]`\n\n[^1]: Body with $x^2$.\n"
    )
    assert "1" in doc.footnotes
    assert any(isinstance(n, InlineMath) for n in doc.footnotes["1"])
    children = doc.children[0].children
    assert any(isinstance(n, FootnoteReference) and n.label == "1" for n in children)
    assert any(isinstance(n, Text) and "[^x]" in n.text for n in children)


def test_omml_delimiters_explicitly_grow():
    converter = MathMLToOMML()
    omml = converter.convert(
        '<math><mfenced open="[" close="]"><mtable><mtr><mtd><mi>a</mi></mtd></mtr>'
        '<mtr><mtd><mi>b</mi></mtd></mtr></mtable></mfenced></math>'
    )
    xml = etree.tostring(omml, encoding="unicode")
    assert 'm:grow' in xml
    assert 'm:val="1"' in xml


def test_mermaid_common_diagrams_render_offline(tmp_path: Path):
    renderer = MermaidRenderer()
    flow = renderer.render("flowchart TD\nA[Start] --> B{Ready?}\nB -- Yes --> C[Done]", tmp_path)
    graph = renderer.render("graph LR\nA((A)) --> B((B))", tmp_path)
    seq = renderer.render(
        "sequenceDiagram\nparticipant U as User\nparticipant R as Renderer\nU->>R: Go\nR-->>U: Done",
        tmp_path,
    )
    for path in (flow, graph, seq):
        assert path.suffix == ".png"
        assert path.stat().st_size > 1000
