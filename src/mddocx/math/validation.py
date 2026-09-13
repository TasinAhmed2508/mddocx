from __future__ import annotations

import hashlib
import re
from collections import Counter

from lxml import etree

from .latex import UnsupportedLatexError

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
ALLOWED_MATHML = {
    "math",
    "mrow",
    "mi",
    "mn",
    "mo",
    "mtext",
    "ms",
    "mspace",
    "mfrac",
    "msqrt",
    "mroot",
    "msup",
    "msub",
    "msubsup",
    "mmultiscripts",
    "mprescripts",
    "none",
    "munder",
    "mover",
    "munderover",
    "mfenced",
    "menclose",
    "mtable",
    "mtr",
    "mtd",
    "mstyle",
    "mphantom",
    "mpadded",
    "semantics",
    "annotation",
}
_FORBIDDEN_ATTRIBUTES = {"href", "src", "actiontype"}


def validate_mathml(mathml: str):
    if "<!DOCTYPE" in mathml.upper() or "<!ENTITY" in mathml.upper():
        raise UnsupportedLatexError("MathML declarations and entities are not allowed")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, recover=False)
    try:
        root = etree.fromstring(mathml.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as exc:
        raise UnsupportedLatexError(f"Math engine returned invalid MathML: {exc}") from exc
    if etree.QName(root).localname != "math" or etree.QName(root).namespace != MATHML_NS:
        raise UnsupportedLatexError("MathML root must use the MathML namespace")
    for node in root.iter():
        name = etree.QName(node).localname
        namespace = etree.QName(node).namespace
        if namespace != MATHML_NS or name not in ALLOWED_MATHML:
            raise UnsupportedLatexError(f"Unsupported or foreign MathML element: {name}")
        for attribute in node.attrib:
            local = etree.QName(attribute).localname.lower()
            if local.startswith("on") or local in _FORBIDDEN_ATTRIBUTES:
                raise UnsupportedLatexError(f"Unsafe MathML attribute: {local}")
        if name == "annotation" and (node.get("encoding") or "").lower() not in {
            "",
            "application/x-tex",
            "text/plain",
        }:
            raise UnsupportedLatexError("Unsupported MathML annotation encoding")
    literal = re.search(r"\\([A-Za-z]+)", "".join(root.itertext()))
    if literal:
        raise UnsupportedLatexError(
            f"Unsupported LaTeX command left unconverted: \\{literal.group(1)}"
        )
    return root


def validate_omml(omml: object) -> None:
    root = omml
    if etree.QName(root).localname != "oMath" or etree.QName(root).namespace != OMML_NS:
        raise UnsupportedLatexError("OMML converter did not return an Office Math equation")
    text = "".join(root.itertext()).strip()
    if not text:
        raise UnsupportedLatexError("OMML equation is empty")
    if re.search(r"\\[A-Za-z]+", text):
        raise UnsupportedLatexError("OMML contains an unconverted TeX command")
    ns = {"m": OMML_NS}
    for fraction in root.xpath(".//m:f", namespaces=ns):
        if not fraction.xpath("./m:num/*", namespaces=ns) or not fraction.xpath(
            "./m:den/*", namespaces=ns
        ):
            raise UnsupportedLatexError("OMML fraction has an empty operand")
    for matrix in root.xpath(".//m:m", namespaces=ns):
        widths = [
            len(row.xpath("./m:e", namespaces=ns)) for row in matrix.xpath("./m:mr", namespaces=ns)
        ]
        if widths and (not widths[0] or len(set(widths)) != 1):
            raise UnsupportedLatexError("OMML matrix is not rectangular")


def semantic_fingerprint(mathml_root, omml: object) -> str:
    mathml_tokens = _node_tokens(mathml_root)
    structure = ",".join(etree.QName(node).localname for node in mathml_root.iter())
    return hashlib.sha256((structure + "|" + "".join(mathml_tokens)).encode()).hexdigest()


def semantic_tokens_preserved(mathml_root, omml: object) -> bool:
    expected = _node_tokens(mathml_root)
    actual = _node_tokens(omml)
    return not expected or _ordered_overlap(expected, actual)


def source_tokens_preserved(latex: str, mathml_root: object) -> bool:
    """Detect clear identifier/numeral loss by an external TeX parser."""
    source = re.sub(r"\\(?:begin|end)\s*\{[^{}]+\}", "", latex)
    source = re.sub(r"\\[A-Za-z]+\*?", "", source)
    expected = _tokens(source)
    actual = _node_tokens(mathml_root)
    return not expected or _ordered_overlap(expected, actual)


def _tokens(text: str) -> list[str]:
    # Structural validation covers operators and layout. Identifiers and numerals are
    # the stable semantic payload across MathML/OMML (accents, n-ary operators, and
    # invisible function application are intentionally encoded as properties).
    return re.findall(r"[A-Za-z0-9]+", text)


def _node_tokens(root: object) -> list[str]:
    tokens: list[str] = []
    for node in root.iter():
        if node.text:
            tokens.extend(_tokens(node.text))
    return tokens


def _ordered_overlap(expected: list[str], actual: list[str]) -> bool:
    # OMML stores degrees, limits, and matrix cells in schema order rather than visual
    # MathML order. Token multiplicity catches loss without rejecting that reordering.
    wanted, present = Counter(expected), Counter(actual)
    return all(present[token] >= count for token, count in wanted.items())
