from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .diagnostics import Diagnostic, MddocxError


@dataclass(frozen=True, slots=True)
class SourceDocument:
    text: str
    source_file: str | None
    base_dir: Path


def acquire_markdown_source(path: str | Path, max_bytes: int) -> SourceDocument:
    """Read one bounded UTF-8 Markdown source with stable failures."""
    source = Path(path)
    try:
        if source.stat().st_size > max_bytes:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "LIMIT401",
                    f"Markdown input exceeds {max_bytes} bytes.",
                    str(source),
                )
            )
        data = source.read_bytes()
    except MddocxError:
        raise
    except OSError as exc:
        raise MddocxError(
            Diagnostic(
                "error",
                "SOURCE401",
                "Markdown source could not be read.",
                str(source),
                remediation="Verify that the file exists and is readable.",
            )
        ) from exc
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MddocxError(
            Diagnostic(
                "error",
                "SOURCE402",
                "Markdown source is not valid UTF-8 text.",
                str(source),
                remediation="Save the Markdown file as UTF-8 (a UTF-8 BOM is accepted).",
            )
        ) from exc
    return SourceDocument(text, str(source), source.parent)
