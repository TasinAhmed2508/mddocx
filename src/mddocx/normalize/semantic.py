from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from mddocx.ast.base import Document, Node
from mddocx.ast.block import ChartBlock, CodeBlock, Heading, ImageBlock, MathBlock, Table
from mddocx.ast.inline import Citation, CrossReference, FootnoteReference


@dataclass(frozen=True, slots=True)
class SemanticIndex:
    """Renderer-independent inventory and resolution state for a document."""

    target_ids: tuple[str, ...] = ()
    heading_ids: tuple[str, ...] = ()
    figure_ids: tuple[str, ...] = ()
    table_ids: tuple[str, ...] = ()
    equation_ids: tuple[str, ...] = ()
    listing_ids: tuple[str, ...] = ()
    citation_keys: tuple[str, ...] = ()
    note_labels: tuple[str, ...] = ()
    unresolved_crossrefs: tuple[str, ...] = ()
    unresolved_notes: tuple[str, ...] = ()


def build_semantic_index(document: Document) -> SemanticIndex:
    headings: list[str] = []
    figures: list[str] = []
    tables: list[str] = []
    equations: list[str] = []
    listings: list[str] = []
    citations: list[str] = []
    note_references: list[str] = []
    crossrefs: list[str] = []
    for node in _walk(document.children):
        identifier = getattr(node, "identifier", None)
        if isinstance(node, Heading) and identifier:
            headings.append(identifier)
        elif isinstance(node, (ImageBlock, ChartBlock)) and identifier:
            figures.append(identifier)
        elif isinstance(node, Table) and identifier:
            tables.append(identifier)
        elif isinstance(node, MathBlock) and identifier:
            equations.append(identifier)
        elif isinstance(node, CodeBlock) and identifier:
            listings.append(identifier)
        elif isinstance(node, CrossReference):
            crossrefs.append(node.target)
        elif isinstance(node, Citation):
            citations.extend(node.keys)
        elif isinstance(node, FootnoteReference):
            note_references.append(node.label)

    targets = tuple(dict.fromkeys(headings + figures + tables + equations + listings))
    target_set = set(targets)
    note_labels = tuple(document.footnotes)
    return SemanticIndex(
        target_ids=targets,
        heading_ids=tuple(headings),
        figure_ids=tuple(figures),
        table_ids=tuple(tables),
        equation_ids=tuple(equations),
        listing_ids=tuple(listings),
        citation_keys=tuple(dict.fromkeys(citations)),
        note_labels=note_labels,
        unresolved_crossrefs=tuple(
            dict.fromkeys(ref for ref in crossrefs if ref not in target_set)
        ),
        unresolved_notes=tuple(
            dict.fromkeys(label for label in note_references if label not in document.footnotes)
        ),
    )


def _walk(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, Node):
        yield value
        for item in fields(value):
            if item.name != "source":
                yield from _walk(getattr(value, item.name))
