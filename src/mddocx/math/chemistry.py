"""Replace mhchem's typesetting scaffolding with native script operands."""

from lxml import etree

from .validation import MATHML_NS

_M = f"{{{MATHML_NS}}}"
_SCRIPTS = {_M + "msub", _M + "msup", _M + "msubsup"}


def attach_chemistry_scripts(root: etree._Element) -> bool:
    changed = False
    for row in list(root.iter(_M + "mrow")):
        node = row[0] if len(row) else None
        while node is not None:
            following = node.getnext()
            if _is_script(node) and following is not None and following.tag == _M + "mspace":
                actual = following.getnext()
                base = actual.getnext() if _is_script(actual) else None
                if (
                    base is not None
                    and following.get("width") == "-0.083em"
                    and _is_chemical_base(base)
                ):
                    sub, sup = _isotope_scripts(actual)
                    if sub is not None or sup is not None:
                        scripts = etree.Element(_M + "mmultiscripts")
                        node.addprevious(scripts)
                        scripts.extend(
                            [
                                base,
                                etree.Element(_M + "mprescripts"),
                                sub if sub is not None else etree.Element(_M + "none"),
                                sup if sup is not None else etree.Element(_M + "none"),
                            ]
                        )
                        for obsolete in (node, following, actual):
                            row.remove(obsolete)
                        node, following = scripts, scripts.getnext()
                        changed = True
            if _is_chemical_base(node) and _is_script(following):
                sub, sup = _script_pair(following)
                attached = [following]
                adjacent = following.getnext()
                if (
                    following.tag == _M + "msub"
                    and _is_script(adjacent)
                    and adjacent.tag == _M + "msup"
                ):
                    sup = adjacent[1]
                    attached.append(adjacent)
                following = attached[-1].getnext()
                tag = (
                    "msubsup"
                    if sub is not None and sup is not None
                    else attached[0].tag.removeprefix(_M)
                )
                scripts = etree.Element(_M + tag)
                node.addprevious(scripts)
                scripts.append(node)
                scripts.extend(_script_operand(part) for part in (sub, sup) if part is not None)
                for obsolete in attached:
                    row.remove(obsolete)
                changed = True
            node = following
    return changed


def _unwrap_rows(node: etree._Element) -> etree._Element:
    while node.tag == _M + "mrow" and len(node) == 1:
        node = node[0]
    return node


def _is_chemical_base(node: etree._Element) -> bool:
    atom = _unwrap_rows(node)
    return atom.tag in {_M + "mi", _M + "mmultiscripts"} or (
        atom.tag == _M + "mo" and atom.text in {")", "]", "}"}
    )


def _is_script(node: etree._Element | None) -> bool:
    if node is None or node.tag not in _SCRIPTS:
        return False
    if len(node) != (3 if node.tag == _M + "msubsup" else 2):
        return False
    base = _unwrap_rows(node[0])
    return (
        base.tag == _M + "mpadded"
        and base.get("width") == "0"
        and bool(base.xpath("m:mphantom/m:mi[text()='A']", namespaces={"m": MATHML_NS}))
    )


def _script_pair(node: etree._Element) -> tuple:
    if node.tag == _M + "msubsup":
        return node[1], node[2]
    return (node[1], None) if node.tag == _M + "msub" else (None, node[1])


def _script_operand(node: etree._Element) -> etree._Element:
    # Native scripts supply their own positioning after detaching the mhchem operand.
    padded = _unwrap_rows(node)
    while padded.tag == _M + "mpadded" and (
        padded.attrib == {"height": "0"} or padded.get("lspace") == "-1width"
    ):
        if len(padded) != 1:
            padded.tag = _M + "mrow"
            padded.attrib.clear()
            break
        node = padded[0]
        padded = _unwrap_rows(node)
    return node


def _isotope_scripts(node: etree._Element) -> tuple:
    pads = (
        next(
            (pad for pad in script.iter(_M + "mpadded") if pad.get("lspace") == "-1width"),
            None,
        )
        if script is not None
        else None
        for script in _script_pair(node)
    )
    return tuple(_script_operand(pad) if pad is not None else None for pad in pads)
