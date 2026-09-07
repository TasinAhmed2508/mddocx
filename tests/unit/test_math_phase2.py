from lxml import etree
from mddocx.math import DefaultMathConverter


def _xml(latex: str) -> str:
    omml = DefaultMathConverter().latex_to_omml(latex, display=True)
    return etree.tostring(omml).decode("utf-8")


def test_phase2_nary_roots_limits_and_accents_are_native_omml():
    xml = _xml(r"\sum_{i=1}^{n} i^2 + \int_0^\infty e^{-x}\,dx + \sqrt[3]{x} + \vec{v}")
    assert "m:nary" in xml
    assert "m:chr" in xml
    assert "m:rad" in xml and "m:deg" in xml
    assert "m:acc" in xml
    delim_xml = _xml(r"\left(\frac{x}{y}\right)")
    assert "m:d" in delim_xml and "m:begChr" in delim_xml and "m:endChr" in delim_xml


def test_phase2_limit_matrix_and_cases_are_native_omml():
    limit_xml = _xml(r"\lim_{x\to0}\frac{\sin x}{x}")
    matrix_xml = _xml(r"\begin{bmatrix}a & b \\ c & d\end{bmatrix}")
    cases_xml = _xml(r"\begin{cases}x^2 & x>0 \\ -x & x\le0\end{cases}")
    aligned_xml = _xml(r"\begin{aligned}a&=b+c \\ d&=e-f\end{aligned}")
    assert "m:limLow" in limit_xml
    assert "m:m" in matrix_xml and "m:d" in matrix_xml
    assert "m:m" in cases_xml and 'm:val="{"' in cases_xml
    assert "m:m" in aligned_xml
