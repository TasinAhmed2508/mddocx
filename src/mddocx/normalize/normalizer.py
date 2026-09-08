from __future__ import annotations

from dataclasses import fields
import re
from typing import Any

from mddocx.ast.base import Document, Node
from mddocx.ast.block import Heading, MathBlock, Table
from mddocx.ast.inline import InlineMath, Text
from mddocx.diagnostics import Diagnostic, DiagnosticReporter, MddocxError


class Normalizer:
    """Turn parser or extension output into a stable, renderer-safe AST.

    This stage owns semantic invariants shared by all renderers: text
    coalescing, math source normalization, heading bounds, table shape checks,
    and document-wide identifier checks.
    """

    def __init__(self, reporter: DiagnosticReporter | None = None) -> None:
        self.reporter = reporter or DiagnosticReporter()
        self._identifiers: dict[str, Node] = {}

    def normalize(self, document: Document) -> Document:
        if not isinstance(document, Document):
            raise TypeError("Normalizer requires a Document root.")
        self._identifiers = {}
        document.children = self._normalize_list(document.children)
        for label, nodes in list(document.footnotes.items()):
            document.footnotes[label] = self._normalize_list(nodes)
        return document

    def _stable_heading_identifier(self, heading: Heading) -> str:
        text = "".join(
            node.text for node in self._walk_nodes(heading.children) if isinstance(node, Text)
        )
        base = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "heading"
        candidate = base
        suffix = 2
        while candidate in self._identifiers:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _walk_nodes(self, value: Any):
        if isinstance(value, list):
            for item in value:
                yield from self._walk_nodes(item)
        elif isinstance(value, Node):
            yield value
            for item in fields(value):
                if item.name != "source":
                    yield from self._walk_nodes(getattr(value, item.name))

    def _normalize_list(self, values: list[Any]) -> list[Any]:
        normalized: list[Any] = []
        for value in values:
            value = self._normalize_value(value)
            if isinstance(value, Text) and not value.text:
                continue
            if isinstance(value, Text) and normalized and isinstance(normalized[-1], Text):
                normalized[-1].text += value.text
                continue
            normalized.append(value)
        return normalized

    def _normalize_value(self, value: Any) -> Any:
        if not isinstance(value, Node):
            return value
        if isinstance(value, Heading) and not 1 <= value.level <= 6:
            diagnostic = Diagnostic(
                "error",
                "NORM401",
                f"Heading level must be between 1 and 6, got {value.level}.",
                getattr(value.source, "file", None),
                getattr(value.source, "line", None),
            )
            raise MddocxError(diagnostic)
        if isinstance(value, Heading) and not value.identifier:
            value.identifier = self._stable_heading_identifier(value)
        if isinstance(value, (MathBlock, InlineMath)):
            value.source_text = value.source_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if isinstance(value, Table):
            widths = {len(row.cells) for row in value.rows}
            if len(widths) > 1:
                self.reporter.warn(
                    "NORM201",
                    "Table rows contain different numbers of cells; missing cells will be padded.",
                    getattr(value.source, "file", None),
                    getattr(value.source, "line", None),
                )
        identifier = getattr(value, "identifier", None)
        if identifier:
            if identifier in self._identifiers:
                self.reporter.warn(
                    "NORM202",
                    f"Duplicate document identifier: {identifier}",
                    getattr(value.source, "file", None),
                    getattr(value.source, "line", None),
                )
            else:
                self._identifiers[identifier] = value
        for item in fields(value):
            if item.name == "source":
                continue
            child = getattr(value, item.name)
            if isinstance(child, list):
                setattr(value, item.name, self._normalize_list(child))
            elif isinstance(child, Node):
                setattr(value, item.name, self._normalize_value(child))
            elif (
                isinstance(child, dict)
                and child
                and all(isinstance(nodes, list) for nodes in child.values())
            ):
                setattr(
                    value,
                    item.name,
                    {key: self._normalize_list(nodes) for key, nodes in child.items()},
                )
        return value
