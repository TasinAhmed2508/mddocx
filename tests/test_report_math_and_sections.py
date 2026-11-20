from io import BytesIO
from types import SimpleNamespace

from docx import Document
from docx.oxml.ns import qn
import pytest

from mddocx import Compiler, RenderConfig
from mddocx.math.converter import DefaultMathConverter
from mddocx.math.latex import UnsupportedLatexError
from mddocx.math.mathml import MathMLToOMML
from mddocx.math.sidecar import MathJaxSidecar


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


@pytest.mark.parametrize("bundled", [False, True])
def test_alignedat_keeps_two_pairs_and_top_baseline(bundled):
    sidecar = MathJaxSidecar() if bundled else SimpleNamespace(available=False)
    if bundled and not sidecar.available:
        pytest.skip("Bundled MathJax requires a local Node runtime")
    tex = r"\begin{alignedat}[t]{2}a&=b & c&=d\\uu&=v & x&=\frac{1}{y}\end{alignedat}"
    equation = DefaultMathConverter(sidecar=sidecar).convert(tex, display=True)
    assert equation.engine == ("mathjax-sidecar" if bundled else "mddocx-basic")
    matrix = next(equation.omml.iter(qn("m:m")))
    assert [node.get(qn("m:val")) for node in matrix.iter(qn("m:mcJc"))] == [
        "right",
        "left",
        "right",
        "left",
    ]
    assert [node.get(qn("m:val")) for node in matrix.iter(qn("m:count"))] == ["1"] * 4
    assert next(matrix.iter(qn("m:baseJc"))).get(qn("m:val")) == "top"
    rows = [["".join(cell.itertext()) for cell in row] for row in matrix.findall(qn("m:mr"))]
    assert rows == [["a", "=b", "c", "=d"], ["uu", "=v", "x", "=1y"]]
    assert next(matrix.iter(qn("m:f")), None) is not None


@pytest.mark.parametrize("bundled", [False, True])
def test_nested_matrix_and_ampersand_stay_inside_outer_alignment_cells(bundled):
    sidecar = MathJaxSidecar() if bundled else SimpleNamespace(available=False)
    if bundled and not sidecar.available:
        pytest.skip("Bundled MathJax requires a local Node runtime")
    tex = (
        r"\begin{aligned}[b]F&=\begin{pmatrix}a&b\\c&d\end{pmatrix}"
        r"\\L&=\text{A \& B}\end{aligned}"
    )
    equation = DefaultMathConverter(sidecar=sidecar).convert(tex, display=True).omml
    outer, inner = list(equation.iter(qn("m:m")))
    assert next(outer.iter(qn("m:baseJc"))).get(qn("m:val")) == "bot"
    assert [len(row) for row in outer.findall(qn("m:mr"))] == [2, 2]
    assert ["".join(row.itertext()) for row in inner.findall(qn("m:mr"))] == ["ab", "cd"]
    assert inner in outer.findall(".//" + qn("m:mr") + "/" + qn("m:e") + "//" + qn("m:m"))
    assert "".join(outer.findall(qn("m:mr"))[1][1].itertext()) == "=A & B"


def test_basic_alignedat_preserves_empty_pairs_and_rejects_excess_columns():
    from mddocx.math.latex import BasicLatexToMathML

    parser = BasicLatexToMathML()
    valid = parser.convert(r"\begin{alignedat}{2}a&=b\\c&=d\end{alignedat}")
    result = MathMLToOMML().convert(valid)
    assert [len(row) for row in result.iter(qn("m:mr"))] == [4, 4]
    with pytest.raises(ValueError, match="Too many alignment columns"):
        parser.convert(r"\begin{alignedat}{1}a&b&c\end{alignedat}")


def test_fallback_caches_only_native_alignment_when_external_result_is_flat():
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))
    calls = []

    def flatten(latex):
        calls.append(latex)
        return '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>a</mi><mi>b</mi></math>'

    converter._external = flatten
    source = r"\begin{alignedat}{1}a&=b\end{alignedat}"
    first = converter.convert(source, display=True)
    second = converter.convert(source, display=True)
    assert first.engine == second.engine == "mddocx-basic"
    assert len(calls) == 1
    assert "lost an alignment or matrix" in first.warnings[0]
    assert first.omml is not second.omml
    assert next(second.omml.iter(qn("m:m")), None) is not None


def test_pure_python_sideset_keeps_limit_and_script_positions():
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))
    result = converter.convert(r"\sideset{_a^b}{_c^d}\sum_{i=1}^{n} i", display=True)
    math = result.omml
    assert result.engine == "latex2mathml"
    left = next(math.iter(qn("m:sPre")))
    right = next(left.iter(qn("m:sSubSup")))
    assert ["".join(left.find(qn(tag)).itertext()) for tag in ("m:sub", "m:sup")] == ["a", "b"]
    assert ["".join(right.find(qn(tag)).itertext()) for tag in ("m:e", "m:sub", "m:sup")] == [
        "∑",
        "c",
        "d",
    ]
    assert "".join(math[0].find(qn("m:lim")).itertext()) == "n"
    lower = next(math.iter(qn("m:limLow")))
    assert "".join(lower.find(qn("m:lim")).itertext()) == "i=1"
    assert not list(math.iter(qn("m:phant")))


def test_chemistry_and_units_compile_and_verify_as_native_word_math(tmp_path):
    if not MathJaxSidecar().available:
        pytest.skip("Bundled MathJax requires a local Node runtime")
    source = tmp_path / "chemistry.md"
    formulas = (
        (r"\ce{2H2 + O2 -> 2H2O}", "⟶", "m:sSub"),
        (r"\ce{N2 + 3H2 <=> 2NH3}", "⇌", "m:sSub"),
        (r"\ce{SO4^2- + Ba^2+ -> BaSO4 v}", "↓", "m:sSup"),
        (r"\ce{A ->[\text{heat}] B}", "heat", "m:limUpp"),
        (r"\pu{3.4e-12 V}", "10", "m:sSup"),
        (r"\ce{^{14}_{6}C}", "14", "m:sPre"),
    )
    source.write_text("\n\n".join(f"$$\n{latex}\n$$" for latex, _, _ in formulas), encoding="utf-8")
    config = RenderConfig()
    config.math_failure.mode = "error"
    compiler = Compiler(config)
    output = source.with_suffix(".docx")
    compiler.compile_file(source, output)
    report = compiler.verify(source, output)
    assert report.ok, report
    equations = list(Document(output)._element.iter(qn("m:oMath")))
    for equation, (_, expected, structure) in zip(equations, formulas, strict=True):
        text = "".join(equation.itertext())
        assert expected in text
        assert not any(0xE000 <= ord(character) <= 0xF8FF for character in text)
        assert next(equation.iter(qn(structure)), None) is not None
        assert not list(equation.iter(qn("m:phant")))
    sulphate = next(equations[2].iter(qn("m:sSubSup")))
    assert "".join(sulphate.find(qn("m:e")).itertext()) == "SO"
    assert "".join(sulphate.find(qn("m:sub")).itertext()) == "4"
    assert "".join(sulphate.find(qn("m:sup")).itertext()) == "2−"
    assert next(sulphate.iter(qn("m:sty"))).get(qn("m:val")) == "p"
    isotope = next(equations[-1].iter(qn("m:sPre")))
    assert ["".join(isotope.find(qn(tag)).itertext()) for tag in ("m:sub", "m:sup", "m:e")] == [
        "6",
        "14",
        "C",
    ]


def test_unmapped_chemistry_symbol_reports_word_limitation():
    sidecar = MathJaxSidecar()
    if not sidecar.available:
        pytest.skip("Bundled MathJax requires a local Node runtime")
    with pytest.raises(UnsupportedLatexError, match="no portable Word mapping"):
        DefaultMathConverter(sidecar=sidecar).convert(r"\ce{A <=>> B}")


def test_word_matrix_column_limit_is_reported_before_emission():
    cells = "<mtd><mn>1</mn></mtd>" * 65
    source = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mtable>'
        f"<mtr>{cells}</mtr></mtable></math>"
    )
    with pytest.raises(ValueError, match="64 columns"):
        MathMLToOMML().convert(source)


@pytest.mark.parametrize(
    "source, position, glyph, label",
    [
        (r"\overbrace{a+b+c}^{\text{total}}", "top", "⏞", "total"),
        (r"\underbrace{x+y}_{n}", "bot", "⏟", "n"),
    ],
)
def test_grouping_braces_and_their_labels_stay_editable(source, position, glyph, label):
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))
    result = converter.convert(source, display=True).omml
    properties = next(result.iter(qn("m:groupChrPr")))
    assert properties.find(qn("m:chr")).get(qn("m:val")) == glyph
    assert properties.find(qn("m:pos")).get(qn("m:val")) == position
    limit = next(result.iter(qn("m:lim")))
    assert "".join(limit.itertext()) == label


def test_cancellation_strokes_survive_in_native_word_equations():
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))
    result = converter.convert(r"\cancel{x}+\bcancel{y}+\xcancel{z}").omml
    boxes = list(result.iter(qn("m:borderBoxPr")))
    properties = [[child.tag.split("}")[-1] for child in box] for box in boxes]
    edges = ["hideTop", "hideBot", "hideLeft", "hideRight"]
    assert properties == [
        edges + ["strikeBLTR"],
        edges + ["strikeTLBR"],
        edges + ["strikeBLTR", "strikeTLBR"],
    ]
    assert [node.text for node in result.iter(qn("m:t"))] == ["x", "+", "y", "+", "z"]


def test_mathml_tex_annotations_do_not_count_as_unconverted_presentation_commands():
    xml = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><!-- source follows -->'
        "<mfrac><mi>a</mi><mi>b</mi></mfrac>"
        r'<annotation encoding="application/x-tex">\frac{a}{b}</annotation></semantics></math>'
    )
    output = MathMLToOMML().convert(xml)
    assert next(output.iter(qn("m:f")), None) is not None
    assert "".join(output.itertext()) == "ab"
    with pytest.raises(ValueError, match="left unconverted"):
        MathMLToOMML().convert(xml.replace("<mi>a</mi>", r"<mi>\unknown</mi>"))
    with pytest.raises(ValueError, match="left unconverted"):
        MathMLToOMML().convert(xml.replace("</mfrac>", r"</mfrac>\unknown"))


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
    cell_style = word.tables[0].cell(1, 0).paragraphs[0].style
    assert cell_style.name == "MD Table Text"
    assert cell_style.base_style.name == "MD Normal"
    assert cell_style.paragraph_format.space_after.pt == 0
    assert cell_style.base_style.paragraph_format.space_after.pt == 7


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
