"""Content-model conformance checking for a finished DOCX package.

A document whose ``w:pPr`` follows a run, whose bookmark precedes the paragraph
properties, or whose ``w:suff`` follows ``w:lvlText`` is still well-formed XML
and usually still opens, so nothing in package validation catches it: Word
either reports unreadable content or quietly ignores the misplaced element.

This module answers one question — where does a parsed part depart from the
sequence in :mod:`mddocx.ooxml.sequence` — for the parts mddocx writes. It is
read-only and imported by :mod:`mddocx.inspection`, which surfaces the
violations to ``mddocx inspect --strict`` and to render-time validation.
"""

from __future__ import annotations

from collections.abc import Mapping

from lxml import etree

from .ooxml.sequence import LEADING, REPEATABLE, REQUIRED, SEQUENCES, TRAILING, local_name

# Distinct violations kept per document; a hostile package cannot grow this.
MAX_COLLECTED = 200

# Parts whose content model mddocx guarantees. Wider than the body-text scope
# inspection counts equations in: mddocx writes numbering and styles too.
_VALIDATED_PARTS = (
    "word/document.xml",
    "word/footnotes.xml",
    "word/endnotes.xml",
    "word/comments.xml",
    "word/styles.xml",
    "word/numbering.xml",
)


def find_schema_order_violations(roots: Mapping[str, etree._Element]) -> list[str]:
    """Return distinct content-model violations found in the given parsed parts."""
    violations: list[str] = []
    reported: set[str] = set()
    for part in sorted(roots):
        if not _is_validated_part(part):
            continue
        for element in roots[part].iter():
            tag = local_name(element.tag)
            if tag is None:
                continue
            for message in _element_violations(part, tag, element):
                if message not in reported:
                    reported.add(message)
                    violations.append(message)
                    if len(violations) >= MAX_COLLECTED:
                        return violations
    return violations


def _is_validated_part(part: str) -> bool:
    return (
        part in _VALIDATED_PARTS or part.startswith("word/header") or part.startswith("word/footer")
    )


def _element_violations(part: str, tag: str, element: etree._Element) -> list[str]:
    names = _children(element)
    found: list[str] = []
    leading = LEADING.get(tag)
    if leading is not None:
        found.extend(_leading_violations(part, tag, names, leading))
    sequence = SEQUENCES.get(tag)
    if sequence is not None:
        found.extend(_sequence_violations(part, tag, names, sequence))
    trailing = TRAILING.get(tag)
    if trailing is not None:
        found.extend(_trailing_violations(part, tag, names, trailing))
    return found


def _leading_violations(part: str, tag: str, names: list[str], rule: tuple[str, ...]) -> list[str]:
    """Check children that must precede every other child of their parent."""
    out: list[str] = []
    first_other = next((i for i, name in enumerate(names) if name not in rule), None)
    if first_other is not None:
        leader = names[first_other]
        for name in names[first_other + 1 :]:
            if name in rule:
                out.append(f"{part}: w:{name} must precede w:{leader} inside w:{tag}")

    present = [(rule.index(name), name) for name in names if name in rule]
    for (earlier_rank, earlier), (later_rank, later) in zip(present, present[1:]):
        if later_rank < earlier_rank:
            out.append(f"{part}: w:{later} must precede w:{earlier} inside w:{tag}")

    out.extend(_duplicate_violations(part, tag, names, rule))
    for name in _required_children(tag, rule):
        if name not in names:
            out.append(f"{part}: w:{tag} is missing required w:{name}")
    return out


def _sequence_violations(part: str, tag: str, names: list[str], rule: tuple[str, ...]) -> list[str]:
    """Check the relative order of children that have a fixed position."""
    rank = {name: index for index, name in enumerate(rule)}
    out: list[str] = []
    highest = -1
    highest_name = ""
    for name in names:
        if name not in rank:
            continue
        if rank[name] < highest:
            out.append(f"{part}: w:{name} must follow w:{highest_name} inside w:{tag}")
        else:
            highest = rank[name]
            highest_name = name
    out.extend(_duplicate_violations(part, tag, names, rule))
    return out


def _trailing_violations(part: str, tag: str, names: list[str], rule: tuple[str, ...]) -> list[str]:
    """Check children that must close their parent."""
    out: list[str] = []
    last = max((i for i, name in enumerate(names) if name in rule), default=None)
    if last is not None and last != len(names) - 1:
        out.append(f"{part}: w:{names[last]} must be the final child of w:{tag}")
    out.extend(_duplicate_violations(part, tag, names, rule))
    return out


def _duplicate_violations(
    part: str, tag: str, names: list[str], rule: tuple[str, ...]
) -> list[str]:
    """Report children the schema allows at most once but the parent repeats."""
    return [
        f"{part}: w:{tag} contains {count} w:{name} elements"
        for name in dict.fromkeys(names)
        if name in rule and name not in REPEATABLE and (count := names.count(name)) > 1
    ]


def _required_children(tag: str, rule: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in REQUIRED.get(tag, ()) if name in rule)


def _children(element: etree._Element) -> list[str]:
    """Return the local name of each WordprocessingML child, in document order."""
    names: list[str] = []
    for child in element:
        name = local_name(child.tag)
        if name is not None:
            names.append(name)
    return names
