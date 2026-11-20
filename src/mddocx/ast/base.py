from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, fields
from typing import Any


@dataclass(slots=True)
class SourcePosition:
    file: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(slots=True)
class Node:
    source: SourcePosition | None = field(default=None, kw_only=True)


@dataclass(slots=True)
class Document(Node):
    children: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    footnotes: dict[str, list[Any]] = field(default_factory=dict)


def iter_nodes(value: Any) -> Iterator[Node]:
    if isinstance(value, dict):
        for item in value.values():
            yield from iter_nodes(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_nodes(item)
    elif isinstance(value, Node):
        yield value
        for item in fields(value):
            if item.name not in {"source", "metadata"}:
                yield from iter_nodes(getattr(value, item.name))
