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
from mddocx.math.validation import visible_omml
from mddocx.ooxml import bangla
from mddocx.ooxml.package import read_parts, write_parts
from lxml import etree


@pytest.mark.parametrize("use_sidecar", [False, True])
def test_styled_array_preserves_rules_repeated_columns_and_cell_content(use_sidecar):
    sidecar = MathJaxSidecar() if use_sidecar else SimpleNamespace(available=False)
    if use_sidecar and not sidecar.available:
        pytest.skip("MathJax runtime is unavailable")
    converter = DefaultMathConverter(sidecar=sidecar)
    expression = r"\left[\begin{array}{*{2}{r}|l}a&b&c\\\frac{1}{2}&y&z\end{array}\right]"
    equation = converter.convert(expression, display=True)
    assert equation.engine == ("mathjax-sidecar" if use_sidecar else "mddocx-basic")
    visible = list(visible_omml(equation.omml))
    (divider,) = (node for node in visible if node.tag == qn("m:sepChr"))
    assert divider.get(qn("m:val")) == "|"
    matrices = [node for node in visible if node.tag == qn("m:m")]
    assert [[len(row) for row in matrix.findall(qn("m:mr"))] for matrix in matrices] == [
        [2, 2],
        [1, 1],
    ]
    assert [node.get(qn("m:val")) for node in visible if node.tag == qn("m:mcJc")] == [
        "right",
        "right",
        "left",
    ]
    assert sum(node.tag == qn("m:f") for node in visible) == 1
    assert len(list(equation.omml.iter(qn("m:f")))) > 1


@pytest.mark.parametrize("use_sidecar", [False, True])
def test_decimal_array_preserves_separators_in_native_zero_gap_columns(use_sidecar):
    sidecar = MathJaxSidecar() if use_sidecar else SimpleNamespace(available=False)
    if use_sidecar and not sidecar.available:
        pytest.skip("MathJax runtime is unavailable")
    equation = DefaultMathConverter(sidecar=sidecar).convert(
        r"\begin{array}{r@{.}l}12&34\\5&6\end{array}", display=True
    )
    assert equation.engine == ("mathjax-sidecar" if use_sidecar else "mddocx-basic")
    matrix = next(equation.omml.iter(qn("m:m")))
    assert next(matrix.iter(qn("m:cGpRule"))).get(qn("m:val")) == "3"
    assert next(matrix.iter(qn("m:cGp"))).get(qn("m:val")) == "0"
    assert [["".join(cell.itertext()) for cell in row] for row in matrix.iter(qn("m:mr"))] == [
        ["12", ".", "34"],
        ["5", ".", "6"],
    ]


@pytest.mark.parametrize("use_sidecar", [False, True])
def test_array_horizontal_rules_and_frame_remain_editable(use_sidecar):
    sidecar = MathJaxSidecar() if use_sidecar else SimpleNamespace(available=False)
    if use_sidecar and not sidecar.available:
        pytest.skip("MathJax runtime is unavailable")
    converter = DefaultMathConverter(sidecar=sidecar)
    equation = converter.convert(
        r"\begin{array}{|l|r|}\hline a&\frac{2}{3}\\\hline b&18\\\hline co&5\\\hline\end{array}",
        display=True,
    )
    assert equation.engine == ("mathjax-sidecar" if use_sidecar else "mddocx-basic")
    assert equation.semantic_valid
    box = equation.omml.find(qn("m:borderBox"))
    assert box is not None and box.find(qn("m:borderBoxPr")) is None
    assert len(list(box.iter(qn("m:bar")))) == 2
    assert len(list(box.iter(qn("m:sepChr")))) == 3
    visible = list(visible_omml(box))
    assert sum(node.tag == qn("m:f") for node in visible) == 1
    assert "".join(node.text or "" for node in visible if node.tag == qn("m:t")) == "a23b18co5"


@pytest.mark.parametrize("directive", [r"\hdashline", r"\hline\hline", r"\cline{1-2}"])
def test_unsupported_array_rules_are_reported(directive):
    expression = rf"\begin{{array}}{{rr}}{directive}a&b\\c&d\end{{array}}"
    result = Compiler().compile_string(f"$$\n{expression}\n$$")
    (finding,) = result.diagnostics
    assert finding.code == "MATH201"


def test_nested_column_spans_remain_editable_with_native_math_and_row_rules():
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))
    expression = (
        r"\begin{array}{lrrr}\multicolumn{4}{l}{\text{All values}}\\\hline"
        r"\multicolumn{2}{c}{x^2}&\multicolumn{2}{r}{\frac{1}{2}}\\a&2&b&3\end{array}"
    )
    equation = converter.convert(expression, display=True)
    assert equation.engine == "mddocx-basic" and equation.semantic_valid
    visible = list(visible_omml(equation.omml))
    assert sum(node.tag == qn("m:bar") for node in visible) == 1
    assert sum(node.tag == qn("m:f") for node in visible) == 1
    assert sum(node.tag == qn("m:sSup") for node in visible) == 1
    assert sum(node.tag == qn("m:box") for node in visible) == 3
    assert (
        "".join(node.text or "" for node in visible if node.tag == qn("m:t"))
        == "All valuesx212a2b3"
    )


@pytest.mark.parametrize(
    "expression, message",
    [
        (
            r"\begin{array}{ccc}\multicolumn{2}{c}{a}&b\\c&\multicolumn{2}{c}{d}\end{array}",
            "Overlapping",
        ),
        (r"\begin{array}{cc}\multicolumn{3}{c}{x}\end{array}", "exceeds the declared array width"),
        (r"\begin{array}{c|c}\multicolumn{2}{c}{x}\end{array}", "column rules or inserts"),
    ],
)
def test_unsupported_column_spans_report_why_they_could_not_render(expression, message):
    result = Compiler().compile_string(f"$$\n{expression}\n$$")
    (finding,) = result.diagnostics
    assert finding.code == "MATH201"
    assert message in finding.message


@pytest.mark.parametrize("change", ["alignment", "span_width", "ordinary_matrix"])
def test_verify_detects_altered_column_span_layout(tmp_path, change):
    source = tmp_path / "span.md"
    tex = (
        r"\begin{array}{lr}\multicolumn{2}{r}{\text{Title}}\\a&b\end{array}"
        r"+\begin{bmatrix}c&d\\e&f\end{bmatrix}"
    )
    source.write_text(f"$$\n{tex}\n$$\n", encoding="utf-8")
    compiler = Compiler()
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert compiler.verify(source, result.output_bytes).ok
    parts = read_parts(result.output_bytes)
    root = etree.fromstring(parts["word/document.xml"])
    box = next(root.iter(qn("m:box")))
    anchor = next(box.iterancestors(qn("m:m")))
    ns = {"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
    if change == "alignment":
        anchor.find("./m:mPr/m:mcs/m:mc/m:mcPr/m:mcJc", ns).set(qn("m:val"), "left")
    elif change == "span_width":
        partition = anchor.findall(qn("m:mr"))[1].find("./m:e/m:phant/m:e/m:m", ns)
        columns = partition.findall(qn("m:mr"))[-1].find("./m:e/m:m/m:mr", ns)
        columns.remove(columns[0])
    else:
        ordinary = root.find(".//m:d/m:e/m:m", ns)
        body = ordinary.getparent()
        for run in list(ordinary.iter(qn("m:r"))):
            body.append(run)
        body.remove(ordinary)
    parts["word/document.xml"] = etree.tostring(root)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.line) == ("VERIFY303", 1)
    assert "matrix layout" in finding.message


@pytest.mark.parametrize(
    "change",
    ["vertical", "row_group_vertical", "horizontal", "frame", "decimal", "spacing", "word_saved"],
)
def test_verify_reads_array_geometry_in_edited_packages(tmp_path, change):
    source = tmp_path / "array.md"
    tex = {
        "vertical": r"\begin{array}{r|l}a&b\\c&d\end{array}",
        "row_group_vertical": r"\begin{array}{r|l}a&b\\\hline c&d\end{array}",
        "horizontal": r"\begin{array}{r|l}a&b\\\hline c&d\end{array}",
        "frame": r"\begin{array}{|rl|}\hline a&b\\c&d\\\hline\end{array}",
        "word_saved": (
            r"\begin{array}{rl}\multicolumn{2}{c}{A}\\\hline c&d\end{array}"
            r"+\begin{array}{r|l}a&b\\\hline c&d\end{array}"
        ),
    }.get(change, r"\begin{array}{r@{.}l}12&34\\5&6\end{array}")
    source.write_text(f"$$\n{tex}\n$$\n", encoding="utf-8")
    compiler = Compiler()
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert compiler.verify(source, result.output_bytes).ok
    parts = read_parts(result.output_bytes)
    root = etree.fromstring(parts["word/document.xml"])
    if change in {"vertical", "row_group_vertical"}:
        next(root.iter(qn("m:sepChr"))).set(qn("m:val"), "")
    elif change == "horizontal":
        bar = next(root.iter(qn("m:bar")))
        bar.getparent().replace(bar, bar.find(qn("m:e"))[0])
    elif change == "frame":
        frame = next(root.iter(qn("m:borderBox")))
        props = etree.Element(qn("m:borderBoxPr"))
        etree.SubElement(props, qn("m:hideTop")).set(qn("m:val"), "1")
        frame.insert(0, props)
    elif change == "word_saved":
        for tag in ("m:pos", "m:sepChr"):
            for default in list(root.iter(qn(tag))):
                default.getparent().remove(default)
        box = next(root.iter(qn("m:box")))
        props = etree.Element(qn("m:boxPr"))
        etree.SubElement(props, qn("m:ctrlPr"))
        box.insert(0, props)
    elif change == "spacing":
        next(root.iter(qn("m:cGp"))).set(qn("m:val"), "40")
    else:
        next(node for node in root.iter(qn("m:t")) if node.text == ".").text = ","
    parts["word/document.xml"] = etree.tostring(root)
    report = compiler.verify(source, write_parts(parts))
    if change == "word_saved":
        assert report.ok
        return
    (finding,) = report.findings
    assert (finding.code, finding.line) == ("VERIFY303", 1)
    assert "matrix layout" in finding.message


@pytest.mark.parametrize(
    "source, normalized, expected",
    [
        (
            r"\newcommand{\squareof}[1]{(#1)^2}\squareof{\frac{1}{2}}",
            r"(\frac{1}{2})^2",
            "m:f",
        ),
        (
            r"\newcommand{\fn}[2][x]{#1^2+#2}\fn{3}+\fn[y]{4}",
            r"x^2+3+y^2+4",
            "m:sSup",
        ),
        (
            r"\newcommand{\q}[2]{\frac{#2}{5}}\newcommand{\n}{8}\q{9}{\n}",
            r"\frac{8}{5}",
            "m:f",
        ),
        (r"\newcommand{\sym}{\alpha}\sym x_3", r"\alpha x_3", "m:sSub"),
    ],
)
def test_equation_local_commands_render_with_python(source, normalized, expected):
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))
    conversion = converter.convert(source, display=True)
    assert conversion.normalized_text == normalized
    assert conversion.semantic_valid
    assert next(conversion.omml.iter(qn(expected)), None) is not None


@pytest.mark.parametrize("use_sidecar", [False, True])
def test_generalized_fraction_keeps_native_delimiters_and_rule(use_sidecar):
    sidecar = MathJaxSidecar() if use_sidecar else SimpleNamespace(available=False)
    if use_sidecar and not sidecar.available:
        pytest.skip("MathJax runtime is unavailable")
    converter = DefaultMathConverter(sidecar=sidecar)
    result = converter.convert(r"\genfrac{[}{]}{0.0pt}{}{n+1}{k}", display=True)
    fraction = next(result.omml.iter(qn("m:f")))
    delimiter = next(result.omml.iter(qn("m:d")))
    assert next(fraction.iter(qn("m:type"))).get(qn("m:val")) == "noBar"
    assert next(delimiter.iter(qn("m:begChr"))).get(qn("m:val")) == "["
    assert next(delimiter.iter(qn("m:endChr"))).get(qn("m:val")) == "]"
    assert "".join(fraction.itertext()) == "n+1k"


def test_generalized_fraction_rejects_invalid_delimiter_without_node():
    converter = DefaultMathConverter(sidecar=SimpleNamespace(available=False))

    with pytest.raises(UnsupportedLatexError, match="Invalid delimiter"):
        converter.convert(r"\genfrac{x}{]}{0pt}{}{n}{k}", display=True)


def test_macro_expansion_and_offline_fidelity_in_strict_conversion(tmp_path, monkeypatch):
    monkeypatch.setenv("MDDOCX_MATHJAX_SIDECAR", str(tmp_path / "no-sidecar"))
    source = tmp_path / "macros.md"
    source.write_text(
        "Before.\n\n"
        r"$\newcommand{\fn}[2][x]{#1^2+#2}\fn{3}$"
        "\n\n$$\n"
        r"\newcommand{\unused}{\sqrt{99}}"
        r"\newcommand{\rate}[1]{\genfrac{[}{]}{0pt}{}{#1}{42}}\rate{y}"
        "\n$$\n\nAfter.\n",
        encoding="utf-8",
    )
    config = RenderConfig()
    config.math_failure.mode = "error"
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert compiler.verify(source, result.output_bytes).ok
    parts = read_parts(result.output_bytes)
    main = etree.fromstring(parts["word/document.xml"])
    fraction = next(main.iter(qn("m:f")))
    denominator = fraction.find(qn("m:den"))
    token = next(denominator.iter(qn("m:t")))
    assert token.text == "42"
    token.text = "43"
    parts["word/document.xml"] = etree.tostring(main)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.line) == ("VERIFY303", 5)


def test_recursive_macro_uses_normal_conversion_failure_policy():
    compiler = Compiler()
    result = compiler.compile_string(r"Before $\newcommand{\r}{\r}\r$ after.")
    (finding,) = result.diagnostics
    assert finding.code == "MATH201"
    assert "macro expansion exceeded its step limit" in finding.message
    assert Document(BytesIO(result.output_bytes)).paragraphs[0].text.endswith(" after.")


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


@pytest.mark.parametrize("engine", ["mathjax-sidecar", "latex2mathml", "mddocx-basic"])
def test_phantoms_and_smashes_preserve_native_spacing(engine, monkeypatch):
    sidecar = MathJaxSidecar() if engine == "mathjax-sidecar" else SimpleNamespace(available=False)
    if engine == "mathjax-sidecar" and not sidecar.available:
        pytest.skip("MathJax runtime is unavailable")
    converter = DefaultMathConverter(sidecar=sidecar)
    if engine == "mddocx-basic":
        monkeypatch.setattr(converter, "_external", None)
    layouts = {
        r"\phantom": [{"show": "0"}],
        r"\hphantom": [{"zeroAsc": "1", "zeroDesc": "1"}, {"show": "0"}],
        r"\vphantom": [{"zeroWid": "1"}, {"show": "0"}],
        r"\smash": [{"zeroAsc": "1", "zeroDesc": "1"}],
        r"\smash[t]": [{"zeroAsc": "1"}],
        r"\smash[b]": [{"zeroDesc": "1"}],
    }
    for command, expected in layouts.items():
        equation = converter.convert(command + r"{\frac{x}{y}}+z", display=True)
        assert equation.semantic_valid and equation.engine == engine
        actual = [
            {etree.QName(flag).localname: flag.get(qn("m:val")) for flag in props}
            for props in equation.omml.iter(qn("m:phantPr"))
        ]
        assert actual == expected
        assert len(list(equation.omml.iter(qn("m:f")))) == 1
    for command in (r"\smash[tb]", r"\smash[bt]"):
        equation = converter.convert(command + r"{\frac{x}{y}}+z", display=True)
        assert equation.semantic_valid
        props = next(equation.omml.iter(qn("m:phantPr")))
        assert [etree.QName(flag).localname for flag in props] == ["zeroAsc", "zeroDesc"]


@pytest.mark.parametrize("removed_flag", ["show", "zeroWid", "zeroAsc", "zeroDesc"])
def test_verify_detects_changed_phantom_or_smash_spacing(tmp_path, removed_flag):
    source = tmp_path / "spacing.md"
    source.write_text(
        r"$z+\vphantom{\frac{x}{y}}+\smash[t]{\sqrt{u}}+\smash[b]{v}$",
        encoding="utf-8",
    )
    compiler = Compiler()
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert not result.diagnostics
    assert compiler.verify(source, result.output_bytes).ok
    parts = read_parts(result.output_bytes)
    document = etree.fromstring(parts["word/document.xml"])
    flag = next(document.iter(qn(f"m:{removed_flag}")))
    flag.getparent().remove(flag)
    parts["word/document.xml"] = etree.tostring(document)
    (finding,) = compiler.verify(source, write_parts(parts)).findings
    assert (finding.code, finding.line) == ("VERIFY303", 1)
    assert "phantom or smash spacing" in finding.message


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

    def flatten(latex, *, display):
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


@pytest.mark.parametrize("engine", ["mathjax-sidecar", "latex2mathml", "mddocx-basic"])
def test_large_operator_limits_use_native_word_placement(engine):
    converter = DefaultMathConverter(cache=False)
    if engine == "mathjax-sidecar" and not converter._sidecar.available:
        pytest.skip("optional MathJax sidecar is unavailable")
    if engine != "mathjax-sidecar":
        converter._sidecar.executable = None
    if engine == "mddocx-basic":
        converter._external = None

    cases = [
        (r"\sum_{i=1}^{n} i", False, "∑", "subSup"),
        (r"\sum_{i=1}^{n} i", True, "∑", "undOvr"),
        (r"\sum\nolimits_{i=1}^{n} i", True, "∑", "subSup"),
        (r"\sum\limits_{i=1}^{n} i", False, "∑", "undOvr"),
        (r"\int_0^1 x\,dx", True, "∫", "subSup"),
        (r"\int\limits_0^1 x\,dx", True, "∫", "undOvr"),
        (r"\bigcup_{i=1}^{n} A_i", True, "⋃", "undOvr"),
        (r"\bigcup\limits_{i=1}^{n} A_i", True, "⋃", "undOvr"),
        (r"\frac{\sum_{i=1}^{n} i}{n}", True, "∑", "subSup"),
    ]
    for source, display, glyph, placement in cases:
        equation = converter.convert(source, display=display)
        assert equation.engine == engine
        (operator,) = equation.omml.iter(qn("m:nary"))
        props = operator.find(qn("m:naryPr"))
        assert props.find(qn("m:chr")).get(qn("m:val")) == glyph
        assert props.find(qn("m:limLoc")).get(qn("m:val")) == placement
        assert "".join(operator.find(qn("m:sub")).itertext()).strip()
        assert "".join(operator.find(qn("m:sup")).itertext()).strip()
        assert "".join(operator.find(qn("m:e")).itertext()).strip()

    mixed = converter.convert(r"\bigcup_{i=1}^{n} A_i+\sum\nolimits_{i=1}^n i", display=True)
    assert mixed.engine == engine
    assert [limit.get(qn("m:val")) for limit in mixed.omml.iter(qn("m:limLoc"))] == [
        "undOvr",
        "subSup",
    ]


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

    combined = DefaultMathConverter().convert(r"\ce{H2O}+\smash[t]{2}")
    (spacing,) = combined.omml.iter(qn("m:phantPr"))
    assert [etree.QName(flag).localname for flag in spacing] == ["zeroAsc"]
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


@pytest.mark.parametrize("bengali_font", ["Nirmala UI", "SutonnyMJ"])
def test_heading_honors_its_typography_and_script_fonts(tmp_path, monkeypatch, bengali_font):
    monkeypatch.setattr(bangla, "installed_font_stems", lambda: frozenset({"nirmala", "sutonnymj"}))
    config = RenderConfig(theme="report")
    config.fonts.headings = "Georgia"
    config.fonts.body = "Calibri"
    config.fonts.bengali = bengali_font
    config.fonts.east_asia = "Microsoft YaHei"
    source = tmp_path / "report.md"
    source.write_text(
        "# Results *review* `index` [中文](https://example.com) বাংলা\n\nBody text.\n",
        encoding="utf-8",
    )
    compiler = Compiler(config)
    result = compiler.compile_file(source, source.with_suffix(".docx"))
    heading, body = Document(BytesIO(result.output_bytes)).paragraphs
    normal, emphasis = heading.runs[:2]
    code = next(run for run in heading.runs if run.text == "index")

    assert heading.style.font.name == "Georgia"
    assert (normal.font.name, normal.bold, normal.italic) == (None, None, None)
    assert emphasis.italic is True
    assert code.font.name == "Consolas"
    linked_font = heading.hyperlinks[0].runs[0]._r.rPr.rFonts
    assert linked_font.get(qn("w:ascii")) is None
    assert linked_font.get(qn("w:eastAsia")) == "Microsoft YaHei"
    assert any(run.font.name == bengali_font for run in heading.runs)
    assert body.runs[0].font.name == "Calibri"
    assert compiler.verify(source, result.output_bytes).ok


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
