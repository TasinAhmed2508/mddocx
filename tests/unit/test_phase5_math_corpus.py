from __future__ import annotations

from lxml import etree

from mddocx.math import DefaultMathConverter

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _corpus() -> list[str]:
    vars_ = ["x", "y", "z", "a", "b", "t", "r", "u", "v", "n"]
    formulas: list[str] = []
    for x in vars_:
        formulas.extend([
            rf"{x}^2",
            rf"{x}_i",
            rf"{x}_i^{{n+1}}",
            rf"\frac{{{x}+1}}{{n+1}}",
            rf"\frac{{1}}{{1+\frac{{1}}{{{x}}}}}",
            rf"\sqrt{{{x}^2+1}}",
            rf"\sqrt[3]{{{x}+1}}",
            rf"\sum_{{i=1}}^n i{x}",
            rf"\prod_{{i=1}}^n ({x}+i)",
            rf"\int_0^1 {x}^2\,d{x}",
            rf"\int_{{-\infty}}^{{\infty}} e^{{-{x}^2}}\,d{x}",
            rf"\oint_\gamma \frac{{1}}{{z-{x}}}\,dz",
            rf"\lim_{{{x}\to0}} \frac{{\sin {x}}}{{{x}}}",
            rf"\left({x}+1\right)^2",
            rf"\left[\frac{{{x}}}{{1+{x}}}\right]_0^1",
            rf"\hat{{{x}}}+\bar{{{x}}}+\vec{{{x}}}",
            rf"\mathbf{{{x}}}+\mathit{{{x}}}+\mathrm{{d{x}}}",
            rf"\mathbb{{R}} \ni {x}",
            rf"\mathcal{{F}}({x})",
            rf"\operatorname{{Var}}({x})",
            rf"\boxed{{{x}^2+1}}",
            rf"\begin{{bmatrix}} {x} & 1 \\ 0 & {x} \end{{bmatrix}}",
            rf"\begin{{pmatrix}} 1 & {x} \\ {x} & 1 \end{{pmatrix}}",
            rf"\begin{{cases}} {x}^2,&{x}<0\\ \sin {x},&{x}\ge0 \end{{cases}}",
            rf"\begin{{aligned}} f({x})&={x}^2\\ f'({x})&=2{x} \end{{aligned}}",
            rf"\nabla {x}+\partial {x}",
            rf"\alpha {x}+\beta {x}+\Gamma {x}",
            rf"({x}+1)^n+[{x}-1]^2",
            rf"E[{x}]^2+({x}+1)^3",
            rf"\frac{{d^2 {x}}}{{dt^2}}+\omega^2{x}=0",
        ])
    for i in range(1, 11):
        for j in range(1, 31):
            x = vars_[(i + j) % len(vars_)]
            formulas.append(rf"\frac{{{x}^{i}+{j}}}{{{i}+{x}_{j}}}+\sqrt{{{x}+{i*j}}}")
    assert len(formulas) == 600
    return formulas


def test_600_equation_word_native_regression_corpus():
    converter = DefaultMathConverter(cache=True)
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    for latex in _corpus():
        omml = converter.latex_to_omml(latex, display=True)
        xml = etree.tostring(omml)
        root = etree.fromstring(xml, parser=parser)
        assert root.tag == f"{{{M}}}oMath"
        assert "□" not in "".join(root.itertext())
        for nary in root.xpath(".//m:nary", namespaces={"m": M}):
            operands = nary.xpath("./m:e", namespaces={"m": M})
            assert operands and len(operands[0]) > 0
