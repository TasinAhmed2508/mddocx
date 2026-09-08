from __future__ import annotations

from dataclasses import dataclass
import re

from mddocx.ast.block import (
    Heading,
    ImageBlock,
    Table,
    MathBlock,
    CodeBlock,
    ChartBlock,
    DataTableBlock,
)


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
    ) -> "ReferenceRegistry":
        reg = cls()
        section = 0
        equation_in_section = 0
        caption_in_section = {"Figure": 0, "Table": 0, "Listing": 0}
        for node in document.children:
            if isinstance(node, Heading):
                title = plain_text(node.children)
                if node.level == 1:
                    section += 1
                    equation_in_section = 0
                    caption_in_section = {"Figure": 0, "Table": 0, "Listing": 0}
                if node.identifier:
                    reg.register(node.identifier, "Section", title)
            elif isinstance(node, ImageBlock):
                if node.identifier and caption_number_format == "section":
                    caption_in_section["Figure"] += 1
                    reg.register(
                        node.identifier,
                        "Figure",
                        node.caption or node.title or node.alt,
                        f"{max(1, section)}.{caption_in_section['Figure']}",
                    )
                else:
                    reg.register(node.identifier, "Figure", node.caption or node.title or node.alt)
            elif isinstance(node, ChartBlock):
                if node.identifier and caption_number_format == "section":
                    caption_in_section["Figure"] += 1
                    reg.register(
                        node.identifier,
                        "Figure",
                        node.caption or node.title or "",
                        f"{max(1, section)}.{caption_in_section['Figure']}",
                    )
                else:
                    reg.register(node.identifier, "Figure", node.caption or node.title or "")
            elif isinstance(node, (Table, DataTableBlock)):
                if node.identifier and caption_number_format == "section":
                    caption_in_section["Table"] += 1
                    reg.register(
                        node.identifier,
                        "Table",
                        node.caption or "",
                        f"{max(1, section)}.{caption_in_section['Table']}",
                    )
                else:
                    reg.register(node.identifier, "Table", node.caption or "")
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
                kind = "Figure" if (node.language or "").lower() == "mermaid" else "Listing"
                if node.identifier and caption_number_format == "section":
                    caption_in_section[kind] += 1
                    reg.register(
                        node.identifier,
                        kind,
                        node.caption or "",
                        f"{max(1, section)}.{caption_in_section[kind]}",
                    )
                else:
                    reg.register(node.identifier, kind, node.caption or "")
        return reg
