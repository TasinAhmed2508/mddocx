from __future__ import annotations

from dataclasses import dataclass, field
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
