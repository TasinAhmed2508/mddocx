from __future__ import annotations

import hashlib
import re
from collections import Counter
from unicodedata import normalize

from lxml import etree

from .latex import (
    INTEGRAL_SYMBOLS,
    NARY,
    UnsupportedLatexError,
    _ENVIRONMENT_TOKEN,
    _MATRIX_ENVIRONMENTS,
    _Parser,
    array_preambles,
    array_row_rules,
    array_span_preambles,
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
_EXPLICIT_NARY_LIMITS = re.compile(
    rf"(?<!\\)\\({'|'.join(NARY)})(?![A-Za-z])\s*\\(limits|nolimits)\s*(?=[_^])"
)
_PHANTOM_COMMAND = re.compile(
    r"(?<!\\)\\(?:(phantom|hphantom|vphantom)(?![A-Za-z])"
    r"|(smash)(?![A-Za-z])(?:\s*\[\s*(tb|bt|t|b)\s*\])?)"
)
_PHANTOM_FLAGS = ("zeroWid", "zeroAsc", "zeroDesc")
_PHANTOM_LAYOUTS = {
    "hphantom": ("zeroAsc", "zeroDesc"),
    "vphantom": ("zeroWid",),
    "smash": ("zeroAsc", "zeroDesc"),
    "t": ("zeroAsc",),
    "b": ("zeroDesc",),
}


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


def explicit_nary_limits_preserved(latex: str, omml: etree._Element) -> bool:
    if r"\sideset" in latex or "phantom" in latex:
        # Sided operators and hidden elements use different Word structures.
        return True
    expected = Counter(
        (NARY[command], "undOvr" if mode == "limits" else "subSup")
        for command, mode in _EXPLICIT_NARY_LIMITS.findall(latex)
    )
    if not expected:
        return True
    actual = Counter()
    for operator in visible_omml(omml):
        if operator.tag != _M + "nary":
            continue
        props = operator.find(_M + "naryPr")
        glyph = props.find(_M + "chr") if props is not None else None
        location = props.find(_M + "limLoc") if props is not None else None
        character = glyph.get(_M + "val", "") if glyph is not None else "∫"
        default = "subSup" if character in INTEGRAL_SYMBOLS else "undOvr"
        actual[
            character, location.get(_M + "val", default) if location is not None else default
        ] += 1
    return expected <= actual


def semantic_tokens_preserved(mathml_root, omml: object) -> bool:
    expected = _node_tokens(mathml_root)
    actual = _node_tokens(omml)
    return not expected or _contains_tokens(expected, actual)


def source_phantoms_preserved(latex: str, omml: etree._Element) -> bool:
    if "phantom" not in latex and r"\smash" not in latex:
        return True
    expected: Counter[tuple[bool, tuple[str, ...]]] = Counter()
    for phantom, smash, option in _PHANTOM_COMMAND.findall(latex):
        if phantom:
            expected[False, ()] += 1
        if phantom != "phantom":
            layout = option if option in {"t", "b"} else phantom or smash
            expected[True, _PHANTOM_LAYOUTS[layout]] += 1
    if not expected:
        return True
    actual = Counter()
    for node in visible_omml(omml):
        if node.tag != _M + "phant":
            continue
        props = node.find(_M + "phantPr")
        if props is None:
            continue
        collapsed = tuple(name for name in _PHANTOM_FLAGS if _math_flag(props, name))
        show = _math_flag(props, "show", default=True)
        actual[show, collapsed] += 1
    return expected <= actual


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
        if node.tag != _M + "d":
            continue
        props = node.find(_M + "dPr")
        if props is None:
            continue
        separator = props.find(_M + "sepChr")
        if separator is not None and separator.get(_M + "val") == "|":
            dividers[node] = node.findall(_M + "e")
        elif separator is None:
            # Bracketless groups use the default vertical separator after a Word save.
            begin, end = props.find(_M + "begChr"), props.find(_M + "endChr")
            if all(edge is not None and edge.get(_M + "val", "") == "" for edge in (begin, end)):
                groups = node.findall(_M + "e")
                if len(groups) > 1 and all(group.find(_M + "m") is not None for group in groups):
                    dividers[node] = groups
    positions, row_groups = _row_rule_positions(visible) if r"\hline" in latex else ({}, {})
    fragments = {
        matrix
        for sections in row_groups.values()
        for section in sections
        for matrix in (section.findall(f"./{_M}e/{_M}m") if section.tag == _M + "d" else [section])
    }
    if r"\multicolumn" in latex:
        try:
            spans = Counter((count, align) for _, _, count, align in array_span_preambles(latex))
        except ValueError:
            return False
        retained, span_fragments = _spanning_layout(visible)
        if not spans <= retained:
            return False
        fragments.update(span_fragments)
    native_arrays = 0
    for node in visible:
        if node.tag in {_M + "m", _M + "eqArr"} and node not in fragments:
            argument = node.getparent()
            group = dividers.get(argument.getparent()) if argument is not None else None
            if not group or argument is group[0]:
                native_arrays += 1
    return native_arrays >= expected and _array_layout_preserved(
        latex, visible, dividers, positions, row_groups
    )


def visible_omml(root: etree._Element):
    """Skip hidden measurements added to align ruled arrays."""
    walker = etree.iterwalk(root, events=("start",))
    for _, node in walker:
        if node.tag == _M + "phant":
            props = node.find(_M + "phantPr")
            if (
                props is not None
                and not _math_flag(props, "show", default=True)
                and (
                    _math_flag(props, "zeroWid")
                    or (_math_flag(props, "zeroAsc") and _math_flag(props, "zeroDesc"))
                )
            ):
                walker.skip_subtree()
                continue
        yield node


def _math_flag(props, name, *, default=False):
    flag = props.find(_M + name)
    return default if flag is None else flag.get(_M + "val", "1") in {"1", "true", "on"}


def _spanning_layout(visible):
    retained: Counter[tuple[int, str]] = Counter()
    fragments = set()
    for matrix in visible:
        if matrix.tag != _M + "m":
            continue
        rows = matrix.findall(_M + "mr")
        if len(rows) != 2 or any(len(row) != 1 for row in rows) or len(rows[1][0]) != 1:
            continue
        width = rows[1][0][0]
        props = width.find(_M + "phantPr") if width.tag == _M + "phant" else None
        if props is None or _math_flag(props, "show", default=True):
            continue
        if not (_math_flag(props, "zeroAsc") and _math_flag(props, "zeroDesc")):
            continue
        measurement = width.find(f"./{_M}e/{_M}m")
        if measurement is None:
            continue
        fragments.add(matrix)
        columns = _measured_columns(measurement)
        contents = rows[0][0]
        if len(contents) == 1 and contents[0].tag == _M + "box":
            justification = matrix.find(f"./{_M}mPr/{_M}mcs/{_M}mc/{_M}mcPr/{_M}mcJc")
            align = "center" if justification is None else justification.get(_M + "val", "center")
            retained[columns, align] += 1
        elif columns > 1 and len(contents) == 1 and contents[0].tag == _M + "m":
            fragments.add(contents[0])
    return retained, fragments


def _measured_columns(measurement):
    rows = measurement.findall(_M + "mr")
    if not rows:
        return 0
    # The final row of a group measures its partition. Other rows measure individual cells.
    partition = rows[-1].find(f"./{_M}e/{_M}m")
    if partition is None:
        return 1
    children = partition.findall(f"./{_M}mr/{_M}e/{_M}m")
    return sum(_measured_columns(child) for child in children)


def _array_layout_preserved(latex, visible, dividers, positions, row_groups):
    expected_rules = 0
    expected_row_rules: Counter[int] = Counter()
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
            if literals or r"\hline" in latex:
                parser = _Parser(latex)
                parser.i = end
                rows, row_breaks, edges = array_row_rules(
                    parser._environment_rows("array", grid=True)
                )
                expected_edges.update(edges)
                expected_row_rules.update(row_breaks)
                for literal in literals:
                    insertions[literal] += len(rows)
    except ValueError:
        return False
    vertical_rules = {
        node: max(0, len(group) - 1)
        for node, group in dividers.items()
        if _math_flag(node.find(_M + "dPr"), "grow", default=True)
    }
    if expected_row_rules and not expected_row_rules <= positions:
        return False
    # Every horizontal section must retain the shared vertical divisions.
    grouped_vertical_rules = sum(
        min((vertical_rules.pop(section, 0) for section in sections), default=0)
        for sections in row_groups.values()
    )
    if expected_rules > grouped_vertical_rules + sum(vertical_rules.values()):
        return False
    if expected_edges:
        edges: Counter[str] = Counter()
        for node in visible:
            if node.tag != _M + "borderBox":
                continue
            argument = node.find(_M + "e")
            if argument is None or not any(
                child.tag == _M + "m" or child in dividers for child in argument
            ):
                continue
            props = node.find(_M + "borderBoxPr")
            for edge, flag in (
                ("left", "hideLeft"),
                ("right", "hideRight"),
                ("top", "hideTop"),
                ("bottom", "hideBot"),
            ):
                if props is None or not _math_flag(props, flag):
                    edges[edge] += 1
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


def _row_rule_positions(visible):
    positions: Counter[int] = Counter()
    groups = set()
    visible_set = set(visible)
    for bar in visible:
        if (
            bar.tag != _M + "bar"
            or bar.getparent().tag != _M + "e"
            or bar.getparent().getparent().tag != _M + "mr"
        ):
            continue
        position = bar.find(f"./{_M}barPr/{_M}pos")
        # Word omits the default bottom position when saving a document.
        if position is not None and position.get(_M + "val") != "bot":
            continue
        body = bar.find(_M + "e")
        if body is None or len(body) != 1:
            continue
        section = body[0]
        matrix = section.find(f"./{_M}e/{_M}m") if section.tag == _M + "d" else section
        if matrix is None or matrix.tag != _M + "m":
            continue
        if matrix.find(f"./{_M}mPr/{_M}rSpRule[@{_M}val='3']") is None:
            continue
        rows = matrix.findall(_M + "mr")
        content_rows = [
            index
            for index, row in enumerate(rows, 1)
            if any(child in visible_set for cell in row for child in cell)
        ]
        if not content_rows or len(content_rows) == len(rows):
            continue
        positions[content_rows[-1]] += 1
        groups.add(bar.getparent().getparent().getparent())
    sections = {}
    for group in groups:
        arguments = []
        for item in group.findall(f"./{_M}mr/{_M}e/*"):
            section = item.find(f"./{_M}e/*") if item.tag == _M + "bar" else item
            if section is not None:
                arguments.append(section)
        sections[group] = arguments
    return positions, sections


def source_tokens_preserved(latex: str, mathml_root: object) -> bool:
    """Detect clear identifier/numeral loss by an external TeX parser."""
    source = _GENFRAC_CONTROLS.sub("", latex.strip())
    if r"\smash" in source:
        source = _PHANTOM_COMMAND.sub(lambda match: r"\smash" if match[3] else match[0], source)
    try:
        declarations = [
            (start, end, "".join(text for kind, text in columns if kind == "@"))
            for start, end, columns in array_preambles(source)
        ]
        declarations.extend((start, end, "") for start, end, _, _ in array_span_preambles(source))
    except ValueError:
        return False
    for start, end, retained in sorted(declarations, reverse=True):
        source = source[:start] + retained + source[end:]
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
