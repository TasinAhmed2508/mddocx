from __future__ import annotations

from lxml import etree
import pytest

from mddocx.math.converter import DefaultMathConverter
from mddocx.math.validation import OMML_NS

from equation_corpus import EQUATION_CORPUS


REQUIRED_FAMILIES = {
    "fractions",
    "nested-scripts",
    "roots",
    "nary-limits",
    "matrices",
    "aligned",
    "accents",
    "binomials",
    "piecewise",
    "text-and-chemistry",
}


def test_equation_corpus_has_250_deterministic_cases_and_required_families():
    assert len(EQUATION_CORPUS) == 250
    assert {case.family for case in EQUATION_CORPUS} == REQUIRED_FAMILIES
    assert len({(case.family, case.latex) for case in EQUATION_CORPUS}) == 250


@pytest.mark.parametrize("case", EQUATION_CORPUS, ids=lambda case: case.family)
def test_equation_corpus_converts_to_valid_editable_omml(case):
    converter = DefaultMathConverter(cache=False)
    converter._external = None

    conversion = converter.convert(case.latex, display=True)
    root = conversion.omml

    assert etree.QName(root).namespace == OMML_NS
    assert etree.QName(root).localname == "oMath"
    assert root.xpath(f".//m:{case.expected_omml}", namespaces={"m": OMML_NS})
    assert not any(text.startswith("\\") for text in root.itertext())
    assert conversion.structural_valid
    assert conversion.semantic_valid
    assert conversion.semantic_fingerprint
