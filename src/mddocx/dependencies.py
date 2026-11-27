from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from .ast.base import Document, iter_nodes
from .ast.block import ChartBlock, DataTableBlock, ImageBlock
from .ast.inline import Image
from .config import RenderConfig
from .diagnostics import MddocxError
from .resources.paths import local_image_path


def local_dependencies(document: Document, config: RenderConfig, base: Path) -> set[Path]:
    """Collect paths read by the core renderer, including missing local assets."""
    paths = set()
    if config.template is not None:
        paths.add(Path(config.template).expanduser().resolve())
    for resource in (config.citations.bibliography, config.citations.style_file):
        if resource is not None:
            paths.add((base / resource).expanduser().resolve())
    base = base.resolve()

    for node in iter_nodes(document):
        if not isinstance(node, (Image, ImageBlock, ChartBlock, DataTableBlock)):
            continue
        raw = node.src if isinstance(node, (Image, ImageBlock)) else node.source_path
        if not raw:
            continue
        try:
            url = urlparse(raw)
        except ValueError:
            # The resource resolver reports malformed URLs with their source location.
            continue
        if not url.scheme and not url.netloc:
            try:
                path = (
                    local_image_path(base, raw)
                    if isinstance(node, (Image, ImageBlock))
                    else (base / raw).resolve()
                )
            except MddocxError:
                continue
            if path.is_relative_to(base):
                paths.add(path)
    return paths
