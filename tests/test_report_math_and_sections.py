from io import BytesIO
from types import SimpleNamespace

from docx import Document
from docx.oxml.ns import qn
import pytest

from mddocx import Compiler, RenderConfig
from mddocx.math.converter import DefaultMathConverter
from mddocx.math.mathml import MathMLToOMML


@pytest.mark.parametrize(
    "source, native",
    [
        (r"2x+abc+42y", "m:r"),
        (r"\begin{array}{rr}a & b\\c\end{array}", "m:m"),
        (r"\underline{m} + \widetilde{abc}", "m:bar"),
        (r"\hspace{1em}x", "m:r"),
        (r"x=\phantom{99}2", "m:phant"),
        (r"\prescript{14}{6}{\mathrm{C}}", "m:sPre"),
    ],
)
def test_complex_latex_stays_native_without_node(source, native):
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))
    equation = converter.convert(source, display=True)
    assert equation.semantic_valid
    assert equation.engine == "latex2mathml"
    assert next(equation.omml.iter(qn(native)), None) is not None
    if native == "m:m":
        assert [len(row.findall(qn("m:e"))) for row in equation.omml.iter(qn("m:mr"))] == [2, 2]
        assert [prop.get(qn("m:val")) for prop in equation.omml.iter(qn("m:mcJc"))] == [
            "right",
            "right",
        ]


def test_mathml_prescripts_and_equation_row_labels_keep_semantics():
    mathml = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mtable>'
        "<mlabeledtr><mtd><mtext>(7)</mtext></mtd><mtd>"
        "<mmultiscripts><mi>A</mi><mi>j</mi><none/><mprescripts/>"
        "<mi>i</mi><mn>2</mn></mmultiscripts></mtd></mlabeledtr></mtable></math>"
    )
    equation = MathMLToOMML().convert(mathml)
    pre = next(equation.iter(qn("m:sPre")))
    assert [node.tag for node in pre] == [qn(n) for n in ("m:sub", "m:sup", "m:e")]
    assert [node.text for node in equation.iter(qn("m:t"))] == ["i", "2", "A", "j", "\u200b", "(7)"]


def test_word_matrix_column_limit_is_reported_before_emission():
    cells = "<mtd><mn>1</mn></mtd>" * 65
    source = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mtable>'
        f"<mtr>{cells}</mtr></mtable></math>"
    )
    with pytest.raises(ValueError, match="64 columns"):
        MathMLToOMML().convert(source)


@pytest.mark.parametrize(
    "source, opening, closing",
    [
        (r"\begin{bmatrix}a&b\\c&d\end{bmatrix}", "[", "]"),
        (r"\begin{cases}x^2,&x\ge0\\-x,&x<0\end{cases}", "{", ""),
        (r"\left(\frac{a}{b}\right)", "(", ")"),
    ],
)
def test_native_delimiters_grow_to_fit_complex_math(source, opening, closing):
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))
    equation = converter.convert(source, display=True).omml
    properties = next(equation.iter(qn("m:dPr")))
    assert properties.find(qn("m:begChr")).get(qn("m:val")) == opening
    assert properties.find(qn("m:endChr")).get(qn("m:val")) == closing
    assert properties.find(qn("m:grow")).get(qn("m:val")) == "1"


def test_report_theme_styles_native_heading_and_table():
    result = Compiler(RenderConfig(theme="report")).compile_string(
        "# Results\n\n| Site | Count |\n| --- | ---: |\n| A | 12 |"
    )
    word = Document(BytesIO(result.output_bytes))
    heading = word.paragraphs[0].style
    assert heading.font.size.pt == 25
    assert str(heading.font.color.rgb) == "16375D"
    assert heading.paragraph_format.keep_with_next
    shading = next(word.tables[0].cell(0, 0)._tc.iter(qn("w:shd")))
    assert shading.get(qn("w:fill")) == "E3ECF8"


def test_small_table_after_explicit_portrait_section_respects_current_orientation():
    config = RenderConfig()
    config.page.orientation = "landscape"
    config.table.auto_landscape = True
    source = (
        "# Landscape introduction\n\n<!-- sectionbreak orientation=portrait -->\n\n"
        "# Portrait results\n\n| Site | Count |\n| --- | --- |\n| A | 12 |\n\nMore text."
    )
    word = Document(BytesIO(Compiler(config).compile_string(source).output_bytes))
    assert [section.page_width > section.page_height for section in word.sections] == [True, False]


def test_unnumbered_listing_retains_caption_and_reference(tmp_path):
    config = RenderConfig()
    config.references.listing_numbering = False
    source = tmp_path / "listing.md"
    source.write_text(
        'See [Listing @lst:demo].\n\n```python {#lst:demo caption="Input setup"}\nvalue = 2\n```\n',
        encoding="utf-8",
    )
    compiler = Compiler(config)
    result = compiler.compile_file(source, tmp_path / "listing.docx")
    word = Document(BytesIO(result.output_bytes))
    instructions = [node.text.strip() for node in word._element.iter(qn("w:instrText"))]
    assert any(text.startswith("REF lst_demo") for text in instructions)
    assert not any(text.startswith("SEQ Listing") for text in instructions)
    assert any(p.text == "Input setup" for p in word.paragraphs)
    assert compiler.verify(source, result.output_bytes).ok
