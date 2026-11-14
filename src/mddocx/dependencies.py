from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path
from urllib.parse import urlparse

from .ast.base import Document, Node
from .ast.block import ChartBlock, DataTableBlock, ImageBlock
from .ast.inline import Image
from .config import RenderConfig


def local_dependencies(document: Document, config: RenderConfig, base: Path) -> set[Path]:
    """Collect paths read by the core renderer, including missing local assets."""
    paths = set()
    if config.template is not None:
        paths.add(Path(config.template).expanduser().resolve())
    for resource in (config.citations.bibliography, config.citations.style_file):
        if resource is not None:
            paths.add((base / resource).expanduser().resolve())
    base = base.resolve()

    def visit(node) -> None:
        if isinstance(node, (list, tuple)):
            for item in node:
                visit(item)
        elif isinstance(node, Node) and is_dataclass(node):
            if isinstance(node, (Image, ImageBlock, ChartBlock, DataTableBlock)):
                raw = node.src if isinstance(node, (Image, ImageBlock)) else node.source_path
                url = urlparse(raw) if raw else None
                if raw and url and not url.scheme and not url.netloc:
                    path = (base / raw).resolve()
                    if path.is_relative_to(base):
                        paths.add(path)
            for field in fields(node):
                if field.name not in {"source", "metadata", "footnotes"}:
                    visit(getattr(node, field.name))

    visit(document)
    for note in document.footnotes.values():
        visit(note)
    return paths
