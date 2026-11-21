from __future__ import annotations

import hashlib
import re
from collections import Counter
from unicodedata import normalize

from lxml import etree

from .latex import (
    UnsupportedLatexError,
    _ENVIRONMENT_TOKEN,
    _MATRIX_ENVIRONMENTS,
    _Parser,
    array_preambles,
)

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_M = f"{{{OMML_NS}}}"
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
    "mlabeledtr",
    "mtd",
    "mstyle",
    "mphantom",
    "mpadded",
    "semantics",
    "annotation",
}
_FORBIDDEN_ATTRIBUTES = {"href", "src", "actiontype"}
_GENFRAC_CONTROLS = re.compile(r"(?<!\\)\\genfrac(?![A-Za-z])\s*(?:\{(?:\\.|[^{}\\])*\}\s*){4}")


def validate_mathml(mathml: str):
    if "<!DOCTYPE" in mathml.upper() or "<!ENTITY" in mathml.upper():
        raise UnsupportedLatexError("MathML declarations and entities are not allowed")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,
        remove_comments=True,
        remove_pis=True,
    )
    try:
        root = etree.fromstring(mathml.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as exc:
        raise UnsupportedLatexError(f"Math engine returned invalid MathML: {exc}") from exc
    if etree.QName(root).localname != "math" or etree.QName(root).namespace != MATHML_NS:
        raise UnsupportedLatexError("MathML root must use the MathML namespace")
    has_annotation = False
    for node in root.iter():
        name = etree.QName(node).localname
        namespace = etree.QName(node).namespace
        if namespace != MATHML_NS or name not in ALLOWED_MATHML:
            raise UnsupportedLatexError(f"Unsupported or foreign MathML element: {name}")
        for attribute in node.attrib:
            local = etree.QName(attribute).localname.lower()
            if local.startswith("on") or local in _FORBIDDEN_ATTRIBUTES:
                raise UnsupportedLatexError(f"Unsafe MathML attribute: {local}")
        if name == "annotation":
            has_annotation = True
            if len(node) or (node.get("encoding") or "").lower() not in {
                "",
                "application/x-tex",
                "text/plain",
            }:
                raise UnsupportedLatexError("Unsupported MathML annotation content")
    presentation_text = (
        root.xpath(".//text()[not(parent::m:annotation)]", namespaces={"m": MATHML_NS})
        if has_annotation
        else root.itertext()
    )
    literal = re.search(r"\\([A-Za-z]+)", "".join(presentation_text))
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


def semantic_fingerprint(mathml_root) -> str:
    mathml_tokens = _node_tokens(mathml_root)
    structure = ",".join(etree.QName(node).localname for node in mathml_root.iter())
    return hashlib.sha256((structure + "|" + "".join(mathml_tokens)).encode()).hexdigest()


def semantic_tokens_preserved(mathml_root, omml: object) -> bool:
    expected = _node_tokens(mathml_root)
    actual = _node_tokens(omml)
    return not expected or _contains_tokens(expected, actual)


def source_matrices_preserved(latex: str, omml: etree._Element) -> bool:
    if r"\begin" not in latex:
        return True
    expected = sum(
        match[1] == "begin" and match[2].strip() in _MATRIX_ENVIRONMENTS
        for match in _ENVIRONMENT_TOKEN.finditer(latex)
    )
    if not expected:
        return True
    visible = list(visible_omml(omml))
    dividers = {}
    for node in visible:
        separator = node.find(f"./{_M}dPr/{_M}sepChr") if node.tag == _M + "d" else None
        if separator is not None and separator.get(_M + "val") == "|":
            dividers[node] = node.findall(_M + "e")
    native_arrays = 0
    for node in visible:
        if node.tag in {_M + "m", _M + "eqArr"}:
            argument = node.getparent()
            group = dividers.get(argument.getparent()) if argument is not None else None
            if not group or argument is group[0]:
                native_arrays += 1
    return native_arrays >= expected and _array_layout_preserved(latex, visible, dividers)


def visible_omml(root: etree._Element):
    """Skip the hidden, zero-width row measurements added by the ruled array layout."""
    walker = etree.iterwalk(root, events=("start",))
    for _, node in walker:
        if node.tag == _M + "phant":
            props = node.find(_M + "phantPr")
            if (
                props is not None
                and not _math_flag(props, "show", default=True)
                and _math_flag(props, "zeroWid")
            ):
                walker.skip_subtree()
                continue
        yield node


def _math_flag(props, name, *, default=False):
    flag = props.find(_M + name)
    return default if flag is None else flag.get(_M + "val", "1") in {"1", "true", "on"}


def _array_layout_preserved(latex, visible, dividers):
    expected_rules = 0
    expected_edges: Counter[str] = Counter()
    insertions: Counter[str] = Counter()
    try:
        for _, end, columns in array_preambles(latex):
            if columns and columns[0][0] == "|":
                expected_edges["left"] += 1
                columns = columns[1:]
            if columns and columns[-1][0] == "|":
                expected_edges["right"] += 1
                columns = columns[:-1]
            expected_rules += sum(kind == "|" for kind, _ in columns)
            literals = [
                text.strip() for kind, text in columns if kind == "@" and len(text.strip()) == 1
            ]
            if literals:
                parser = _Parser(latex)
                parser.i = end
                row_count = len(parser._environment_rows("array", grid=True))
                for literal in literals:
                    insertions[literal] += row_count
    except ValueError:
        return False
    if expected_rules > sum(
        max(0, len(group) - 1)
        for node, group in dividers.items()
        if _math_flag(node.find(_M + "dPr"), "grow", default=True)
    ):
        return False
    if expected_edges:
        edges: Counter[str] = Counter()
        for node in visible:
            if (
                node.tag == _M + "borderBoxPr"
                and _math_flag(node, "hideTop")
                and _math_flag(node, "hideBot")
            ):
                if not _math_flag(node, "hideLeft"):
                    edges["left"] += 1
                if not _math_flag(node, "hideRight"):
                    edges["right"] += 1
        if not expected_edges <= edges:
            return False
    if insertions:
        compact_matrices = {
            node
            for node in visible
            if node.tag == _M + "m"
            and node.find(f"./{_M}mPr/{_M}cGpRule[@{_M}val='3']") is not None
            and (
                (gap := node.find(f"./{_M}mPr/{_M}cGp")) is None or gap.get(_M + "val", "0") == "0"
            )
        }
        cells = Counter(
            "".join(item.text or "" for item in visible_omml(node) if item.tag == _M + "t")
            .replace("\u200b", "")
            .strip()
            for node in visible
            if node.tag == _M + "e"
            and node.getparent().tag == _M + "mr"
            and node.getparent().getparent() in compact_matrices
        )
        if not insertions <= cells:
            return False
    return True


def source_tokens_preserved(latex: str, mathml_root: object) -> bool:
    """Detect clear identifier/numeral loss by an external TeX parser."""
    source = _GENFRAC_CONTROLS.sub("", latex.strip())
    try:
        arrays = list(array_preambles(source))
    except ValueError:
        return False
    for start, end, columns in reversed(arrays):
        source = (
            source[:start] + "".join(text for kind, text in columns if kind == "@") + source[end:]
        )
    # mhchem expands scientific notation and converts a standalone v to a precipitate arrow.
    source = re.sub(
        r"(\\pu\s*\{\s*[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))[eE](?=[+-]?\d)",
        r"\g<1>10",
        source,
    )
    source = re.sub(
        r"\\ce\s*\{[^{}]*\}",
        lambda group: re.sub(r"(?<=\s)(?:v|\(v\))(?=\s*(?:\+|\}))", "↓", group[0]),
        source,
    )
    source = re.sub(
        r"\\begin\s*\{(?:alignedat|alignat\*?)\}\s*(?:\[\s*[tcb]\s*\]\s*)?\{[^{}]*\}",
        "",
        source,
    )
    source = re.sub(r"\\begin\s*\{(?:aligned|gathered)\}\s*\[\s*[tcb]\s*\]", "", source)
    source = re.sub(r"\\(?:begin|end)\s*\{[^{}]+\}", "", source)
    source = re.sub(
        r"\\(?:hspace|vspace|textcolor|color|colorbox)\*?(?:\[[^\]]*\])?\s*\{[^{}]*\}",
        "",
        source,
    )
    source = re.sub(r"\\[A-Za-z]+\*?", "", source)
    expected = _tokens(source)
    actual = _node_tokens(mathml_root)
    return not expected or _contains_tokens(expected, actual)


def _tokens(text: str) -> list[str]:
    # Structural validation covers operators and layout. Identifiers and numerals are
    # the stable semantic payload across MathML/OMML (accents, n-ary operators, and
    # invisible function application are intentionally encoded as properties).
    # TeX source may write "2xy", but MathML stores the three atoms separately.
    return [character for character in normalize("NFKC", text) if character.isalnum()]


def _node_tokens(root: object) -> list[str]:
    tokens: list[str] = []
    nodes = visible_omml(root) if root.tag.startswith(_M) else root.iter()
    for node in nodes:
        if (
            isinstance(node.tag, str)
            and node.text
            and etree.QName(node).localname not in {"annotation", "annotation-xml"}
        ):
            tokens.extend(_tokens(node.text))
    return tokens


def _contains_tokens(expected: list[str], actual: list[str]) -> bool:
    # OMML stores degrees, limits, and matrix cells in schema order rather than visual
    # MathML order. Token multiplicity catches loss without rejecting that reordering.
    wanted, present = Counter(expected), Counter(actual)
    return all(present[token] >= count for token, count in wanted.items())
