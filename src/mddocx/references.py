from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import re

from mddocx.ast.base import Node
from mddocx.ast.block import (
    BlockQuote,
    BulletList,
    Callout,
    Heading,
    ImageBlock,
    Table,
    MathBlock,
    CodeBlock,
    ChartBlock,
    DataTableBlock,
    OrderedList,
)


def _reference_blocks(nodes: list[Node]) -> Iterator[Node]:
    for node in nodes:
        yield node
        if isinstance(node, (BlockQuote, Callout)):
            yield from _reference_blocks(node.children)
        elif isinstance(node, (BulletList, OrderedList)):
            for item in node.items:
                yield from _reference_blocks(item.children)


@dataclass(slots=True)
class ReferenceTarget:
    identifier: str
    kind: str
    number: int | str | None
    bookmark: str
    title: str = ""


class ReferenceRegistry:
    """Document-wide semantic ID -> Word bookmark/sequence registry."""

    def __init__(self) -> None:
        self.targets: dict[str, ReferenceTarget] = {}
        self._counts = {"Figure": 0, "Table": 0, "Equation": 0, "Listing": 0}
        self._bookmark_names: set[str] = set()

    @staticmethod
    def safe_bookmark(identifier: str) -> str:
        value = re.sub(r"[^A-Za-z0-9_]", "_", identifier).strip("_") or "ref"
        if not value[0].isalpha():
            value = "ref_" + value
        return value[:38]

    def register(
        self,
        identifier: str | None,
        kind: str,
        title: str = "",
        number_override: int | str | None = None,
    ) -> ReferenceTarget | None:
        if not identifier:
            return None
        if identifier in self.targets:
            return self.targets[identifier]
        base = self.safe_bookmark(identifier)
        bookmark = base
        n = 2
        while bookmark in self._bookmark_names:
            suffix = f"_{n}"
            bookmark = base[: 40 - len(suffix)] + suffix
            n += 1
        self._bookmark_names.add(bookmark)
        number = number_override
        if kind in self._counts:
            self._counts[kind] += 1
            if number is None:
                number = self._counts[kind]
        target = ReferenceTarget(identifier, kind, number, bookmark, title)
        self.targets[identifier] = target
        return target

    def get(self, identifier: str) -> ReferenceTarget | None:
        return self.targets.get(identifier)

    @classmethod
    def from_document(
        cls,
        document,
        plain_text,
        equation_number_format: str = "document",
        caption_number_format: str = "document",
        listing_numbering: bool = True,
        *,
        reserved_bookmarks: Iterable[str] = (),
        image_captions_from_title: bool = True,
        mermaid_enabled: bool = True,
    ) -> "ReferenceRegistry":
        reg = cls()
        reg._bookmark_names.update(reserved_bookmarks)
        if not listing_numbering:
            reg._counts.pop("Listing")
        section = 0
        equation_in_section = 0
        caption_in_section = {"Figure": 0, "Table": 0, "Listing": 0}

        def caption(node, kind: str, title: str, anonymous_caption: bool) -> None:
            if not node.identifier and not anonymous_caption:
                return
            numbered = kind in reg._counts
            if numbered:
                caption_in_section[kind] += 1
            number = (
                f"{max(1, section)}.{caption_in_section[kind]}"
                if numbered and caption_number_format == "section"
                else None
            )
            reg.register(node.identifier, kind, title, number)
            if numbered and not node.identifier:
                reg._counts[kind] += 1

        for node in _reference_blocks(document.children):
            if isinstance(node, Heading):
                title = plain_text(node.children)
                if node.level == 1:
                    section += 1
                    equation_in_section = 0
                    caption_in_section = {"Figure": 0, "Table": 0, "Listing": 0}
                if node.identifier:
                    reg.register(node.identifier, "Section", title)
            elif isinstance(node, ImageBlock):
                caption(
                    node,
                    "Figure",
                    node.caption or node.title or node.alt,
                    bool(node.caption or (node.title if image_captions_from_title else None)),
                )
            elif isinstance(node, ChartBlock):
                caption(
                    node,
                    "Figure",
                    node.caption or node.title or "",
                    bool(node.caption or node.title),
                )
            elif isinstance(node, (Table, DataTableBlock)):
                caption(node, "Table", node.caption or "", bool(node.caption))
            elif isinstance(node, MathBlock):
                if node.identifier and equation_number_format == "section":
                    equation_in_section += 1
                    reg.register(
                        node.identifier,
                        "Equation",
                        node.caption or "",
                        f"{max(1, section)}.{equation_in_section}",
                    )
                else:
                    reg.register(node.identifier, "Equation", node.caption or "")
            elif isinstance(node, CodeBlock):
                kind = (
                    "Figure"
                    if (node.language or "").strip().lower() == "mermaid" and mermaid_enabled
                    else "Listing"
                )
                title = node.caption or (
                    "Code listing" if kind == "Listing" and not listing_numbering else ""
                )
                caption(node, kind, title, bool(node.caption))
        return reg
