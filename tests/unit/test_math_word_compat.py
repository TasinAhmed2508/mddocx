from lxml import etree

from mddocx.math.mathml import MathMLToOMML

M = "http://www.w3.org/1998/Math/MathML"
OMML = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"m": OMML}


def _convert(body: str):
    return MathMLToOMML().convert(f'<math xmlns="{M}">{body}</math>')


def test_sqrt_has_required_degree_node_and_all_radicand_children():
    omml = _convert("<msqrt><mn>2</mn><mi>π</mi></msqrt>")
    xml = etree.tostring(omml).decode()
    assert "m:degHide" in xml
    assert "<m:deg" in xml
    text = "".join(omml.xpath(".//m:rad/m:e//m:t/text()", namespaces=NS))
    assert text == "2π"


def test_single_sided_nary_limits_are_hidden_not_word_placeholders():
    omml = _convert("<mrow><msub><mo>∮</mo><mi>γ</mi></msub><mi>f</mi></mrow>")
    assert omml.xpath("count(.//m:nary)", namespaces=NS) == 1
    assert omml.xpath(".//m:nary/m:naryPr/m:supHide/@m:val", namespaces=NS) == ["1"]
    assert not omml.xpath(".//m:nary/m:e[not(*)]", namespaces=NS)


def test_consecutive_integrals_nest_around_real_operand_without_empty_body():
    body = """
    <mrow>
      <msubsup><mo>∫</mo><mi>a</mi><mi>b</mi></msubsup>
      <msubsup><mo>∫</mo><mi>c</mi><mi>d</mi></msubsup>
      <msup><mi>e</mi><mi>x</mi></msup><mi>d</mi><mi>x</mi>
    </mrow>
    """
    omml = _convert(body)
    assert omml.xpath("count(.//m:nary)", namespaces=NS) == 2
    assert not omml.xpath(".//m:nary/m:e[not(*)]", namespaces=NS)
    text = "".join(omml.xpath(".//m:t/text()", namespaces=NS))
    assert "e" in text and "x" in text


def test_hat_like_mover_is_native_accent_even_without_accent_attribute():
    omml = _convert("<mover><mi>f</mi><mo>^</mo></mover>")
    assert omml.xpath("count(.//m:acc)", namespaces=NS) == 1
    assert not omml.xpath(".//m:limUpp", namespaces=NS)


def test_math_variants_and_box_are_preserved_as_native_omml():
    omml = _convert('<menclose notation="box"><mstyle mathvariant="bold"><mi>E</mi></mstyle></menclose>')
    xml = etree.tostring(omml).decode()
    assert "m:borderBox" in xml
    assert 'm:sty' in xml and 'm:val="b"' in xml


def test_scripts_after_closing_delimiters_group_the_expression_and_do_not_absorb_punctuation():
    from mddocx.math.latex import BasicLatexToMathML

    mathml = BasicLatexToMathML().convert(r"\mathbb E[X]^2.")
    root = etree.fromstring(mathml.encode())
    mns = {"m": M}
    sup = root.xpath(".//m:msup", namespaces=mns)[-1]
    assert sup[0].tag.endswith("}mrow")
    assert "".join(sup[0].itertext()) == "[X]"
    assert "".join(sup[1].itertext()) == "2"
    assert root[-1].tag.endswith("}mo") and root[-1].text == "."
