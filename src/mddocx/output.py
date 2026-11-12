from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Iterable
from uuid import uuid4

from .diagnostics import Diagnostic, MddocxError


def validate_output_path(path: Path, protected_paths: Iterable[Path]) -> Path:
    target = path.expanduser().resolve()
    for protected in protected_paths:
        source = protected.expanduser().resolve()
        if target == source or (target.exists() and source.exists() and target.samefile(source)):
            raise MddocxError(
                Diagnostic(
                    "error",
                    "OUTPUT401",
                    f"Output path conflicts with another file: {source}",
                    remediation="Choose a different output path.",
                )
            )
    return target


def write_docx(path: Path, blob: bytes, *, protected_paths: Iterable[Path] = ()) -> None:
    """Write a complete document without replacing any of its protected inputs."""
    atomic_write_bytes(validate_output_path(path, protected_paths), blob)


def atomic_write_bytes(target: Path, data: bytes) -> None:
    """Replace a file after writing to a unique sibling on the same filesystem."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".mddocx-{uuid4().hex}.tmp")
    created = False
    try:
        with temporary.open("xb") as stream:
            created = True
            stream.write(data)
        if os.name != "nt" and target.exists():
            shutil.copymode(target, temporary)
        temporary.replace(target)
    finally:
        if created:
            temporary.unlink(missing_ok=True)
