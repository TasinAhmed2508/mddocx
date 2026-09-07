from lxml import etree
from mddocx.math import DefaultMathConverter


def test_phase1_math_to_omml():
    c = DefaultMathConverter()
    omml = c.latex_to_omml(r"x=\frac{-b\pm\sqrt{b^2}}{2a}")
    xml = etree.tostring(omml).decode()
    assert "m:f" in xml
    assert "m:rad" in xml
    assert "m:sSup" in xml
