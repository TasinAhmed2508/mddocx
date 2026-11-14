"""WordprocessingML sibling sequences and order-aware element insertion.

Word enforces the ECMA-376 element sequences with a strict XML schema, so an
element written in the wrong position is either rejected or silently ignored.
This module is the single owner of the sequences mddocx emits — one entry per
parent element, listing its ordered children — and the two ways writers use
them: :func:`insert_ordered` places a hand-built element where the sequence
requires, and :func:`get_or_add` reuses an existing child instead of writing a
second one where the schema allows at most one.

:mod:`mddocx.schema_order` reads the same tables to report departures in a
finished document, so the sequence has exactly one definition.
"""

from __future__ import annotations

from functools import lru_cache

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Parents whose listed children have a fixed relative order. Children that are
# not listed (extension markup) are ignored, so a valid document never raises.
SEQUENCES: dict[str, tuple[str, ...]] = {
    # CT_PPr (§17.3.1.26)
    "pPr": (
        "pStyle",
        "keepNext",
        "keepLines",
        "pageBreakBefore",
        "framePr",
        "widowControl",
        "numPr",
        "suppressLineNumbers",
        "pBdr",
        "shd",
        "tabs",
        "suppressAutoHyphens",
        "kinsoku",
        "wordWrap",
        "overflowPunct",
        "topLinePunct",
        "autoSpaceDE",
        "autoSpaceDN",
        "bidi",
        "adjustRightInd",
        "snapToGrid",
        "spacing",
        "ind",
        "contextualSpacing",
        "mirrorIndents",
        "suppressOverlap",
        "jc",
        "textDirection",
        "textAlignment",
        "textboxTightWrap",
        "outlineLvl",
        "divId",
        "cnfStyle",
        "rPr",
        "sectPr",
        "pPrChange",
    ),
    # CT_RPr (§17.3.2.27)
    "rPr": (
        "rStyle",
        "rFonts",
        "b",
        "bCs",
        "i",
        "iCs",
        "caps",
        "smallCaps",
        "strike",
        "dstrike",
        "outline",
        "shadow",
        "emboss",
        "imprint",
        "noProof",
        "snapToGrid",
        "vanish",
        "webHidden",
        "color",
        "spacing",
        "w",
        "kern",
        "position",
        "sz",
        "szCs",
        "highlight",
        "u",
        "effect",
        "bdr",
        "shd",
        "fitText",
        "vertAlign",
        "rtl",
        "cs",
        "em",
        "lang",
        "eastAsianLayout",
        "specVanish",
        "oMath",
    ),
    # CT_TblPr (§17.4.60)
    "tblPr": (
        "tblStyle",
        "tblpPr",
        "tblOverlap",
        "bidiVisual",
        "tblStyleRowBandSize",
        "tblStyleColBandSize",
        "tblW",
        "jc",
        "tblCellSpacing",
        "tblInd",
        "tblBorders",
        "shd",
        "tblLayout",
        "tblCellMar",
        "tblLook",
        "tblCaption",
        "tblDescription",
    ),
    # CT_TrPr (§17.4.81)
    "trPr": (
        "cnfStyle",
        "divId",
        "gridBefore",
        "gridAfter",
        "wBefore",
        "wAfter",
        "cantSplit",
        "trHeight",
        "tblHeader",
        "tblCellSpacing",
        "jc",
        "hidden",
    ),
    # CT_TcPr (§17.4.71)
    "tcPr": (
        "cnfStyle",
        "tcW",
        "gridSpan",
        "hMerge",
        "vMerge",
        "tcBorders",
        "shd",
        "noWrap",
        "tcMar",
        "textDirection",
        "tcFitText",
        "vAlign",
        "hideMark",
    ),
    # CT_SectPr (§17.6.18)
    "sectPr": (
        "headerReference",
        "footerReference",
        "footnotePr",
        "endnotePr",
        "type",
        "pgSz",
        "pgMar",
        "paperSrc",
        "pgBorders",
        "lnNumType",
        "pgNumType",
        "cols",
        "formProt",
        "vAlign",
        "noEndnote",
        "titlePg",
        "textDirection",
        "bidi",
        "rtlGutter",
        "docGrid",
        "printerSettings",
        "sectPrChange",
    ),
    # CT_Lvl (§17.9.6)
    "lvl": (
        "start",
        "numFmt",
        "lvlRestart",
        "pStyle",
        "isLgl",
        "suff",
        "lvlText",
        "lvlPicBulletId",
        "legacy",
        "lvlJc",
        "pPr",
        "rPr",
    ),
    # CT_Num (§17.9.15)
    "num": ("abstractNumId", "lvlOverride"),
    # CT_AbstractNum (§17.9.1)
    "abstractNum": ("nsid", "multiLevelType", "tmpl", "name", "styleLink", "numStyleLink", "lvl"),
    # CT_PBdr (§17.3.1.24)
    "pBdr": ("top", "left", "bottom", "right", "between", "bar"),
    # CT_TcMar (§17.4.70)
    "tcMar": ("top", "start", "left", "bottom", "end", "right"),
    # CT_TblBorders (§17.4.39)
    "tblBorders": ("top", "start", "left", "bottom", "end", "right", "insideH", "insideV"),
}

# Parents whose listed children must precede every other child. Unlike a
# sequence entry, an unlisted child placed before these children is a violation.
LEADING: dict[str, tuple[str, ...]] = {
    "p": ("pPr",),
    "r": ("rPr",),
    "tc": ("tcPr",),
    "tr": ("tblPrEx", "trPr"),
    "tbl": ("tblPr", "tblGrid"),
}

# Children the schema requires (minOccurs=1) among the leading children.
REQUIRED: dict[str, tuple[str, ...]] = {
    "tbl": ("tblPr", "tblGrid"),
    "tc": ("tcPr",),
}

# Parents whose listed children must close the element.
TRAILING: dict[str, tuple[str, ...]] = {
    "body": ("sectPr",),
}

# Names that may legitimately repeat where the other sequence entries cannot.
REPEATABLE = frozenset({"headerReference", "footerReference", "lvl", "lvlOverride"})


def insert_ordered(parent: etree._Element, child: etree._Element) -> None:
    """Insert ``child`` into ``parent`` where its sequence requires it.

    A hand-built element appended to a parent lands at the end, which is the
    out-of-sequence XML :mod:`mddocx.schema_order` reports. Use this instead of
    ``append`` for any element whose parent appears above.
    """
    ranks = _ranks(local_name(parent.tag))
    name = local_name(child.tag)
    if ranks is None or name is None or name not in ranks:
        parent.append(child)
        return
    rank = ranks[name]
    limit = len(ranks)
    for index, sibling in enumerate(parent):
        sibling_name = local_name(sibling.tag)
        if sibling_name is None or ranks.get(sibling_name, limit) > rank:
            parent.insert(index, child)
            return
    parent.append(child)


def get_or_add(parent: etree._Element, tag: str) -> etree._Element:
    """Return the ``tag`` child of ``parent``, creating it in sequence order.

    The schema allows at most one of these children, so a writer that creates a
    second one produces a document Word will not accept; reuse is the only
    correct behavior.
    """
    existing = parent.find(qn(tag))
    if existing is not None:
        return existing
    child = OxmlElement(tag)
    insert_ordered(parent, child)
    return child


@lru_cache(maxsize=512)
def _local_name(tag: str) -> str | None:
    prefix = "{" + _W + "}"
    return tag[len(prefix) :] if tag.startswith(prefix) else None


def local_name(tag: object) -> str | None:
    """Return the WordprocessingML local name of ``tag``, if it has one.

    Memoized because every element of every part is looked up, and bounded
    because namespace names come from the document.
    """
    return _local_name(tag) if isinstance(tag, str) else None


def _ranks(tag: str | None) -> dict[str, int] | None:
    if tag is None:
        return None
    rule = SEQUENCES.get(tag) or LEADING.get(tag)
    if rule is None:
        return None
    return {name: index for index, name in enumerate(rule)}
