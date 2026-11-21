from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from .base import Node


@dataclass(slots=True)
class Text(Node):
    text: str = ""


@dataclass(slots=True)
class Strong(Node):
    children: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class Emphasis(Node):
    children: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class Strikethrough(Node):
    children: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class InlineCode(Node):
    code: str = ""


@dataclass(slots=True)
class Link(Node):
    href: str = ""
    title: str | None = None
    children: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class InlineMath(Node):
    source_text: str = ""
    format: str = "latex"


@dataclass(slots=True)
class CrossReference(Node):
    target: str = ""
    prefix: str | None = None


@dataclass(slots=True)
class Citation(Node):
    keys: list[str] = field(default_factory=list)
    suffix: str | None = None
    suppress_author: bool = False


@dataclass(slots=True)
class Comment(Node):
    text: str = ""


@dataclass(slots=True)
class SoftBreak(Node):
    pass


@dataclass(slots=True)
class HardBreak(Node):
    pass


@dataclass(slots=True)
class Image(Node):
    src: str = ""
    alt: str = ""
    title: str | None = None


@dataclass(slots=True)
class FootnoteReference(Node):
    label: str = ""


def link_content(nodes: list[Node]) -> Iterator[str | Image]:
    """Yield the text and native pictures that make up a hyperlink."""
    for node in nodes:
        if isinstance(node, Text):
            yield node.text
        elif isinstance(node, InlineCode):
            yield node.code
        elif isinstance(node, InlineMath):
            yield node.source_text
        elif isinstance(node, (SoftBreak, HardBreak)):
            yield " "
        elif isinstance(node, Image):
            yield node
        elif hasattr(node, "children"):
            yield from link_content(node.children)
