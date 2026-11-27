from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from mddocx.diagnostics import Diagnostic, MddocxError


def local_image_path(base_dir: Path, source: str) -> Path:
    """Decode a local image URI once, before each caller's containment check."""
    try:
        return (base_dir / unquote(source)).resolve()
    except ValueError as exc:
        raise MddocxError(
            Diagnostic("error", "RESOURCE208", "Malformed local image path.")
        ) from exc
