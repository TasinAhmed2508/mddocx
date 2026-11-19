from __future__ import annotations

from pathlib import Path

from .ast.base import SourcePosition
from .ast.block import BlockQuote, Paragraph
from .ast.inline import Text
from .diagnostics import Diagnostic, DiagnosticReporter


def recovery_block(
    reporter: DiagnosticReporter,
    diagnostic: Diagnostic,
    excerpt: str,
    source: SourcePosition | None,
) -> BlockQuote:
    line = diagnostic.line or (source.line if source else None)
    file = diagnostic.source_file or (source.file if source else None)
    location = Path(file).name if file else "Markdown"
    if line is not None:
        location += f":{line}"
    safe_excerpt = " ".join(excerpt[:200].split())
    safe_excerpt = "".join(char for char in safe_excerpt if char.isprintable())
    reporter.warn(
        "RECOVER201",
        f"Recovered {diagnostic.code}: {diagnostic.message}",
        file,
        line,
        "Correct the declaration and rerun in strict mode.",
    )
    text = f"[Conversion recovery {diagnostic.code}, {location}] {safe_excerpt}".rstrip()
    return BlockQuote(
        children=[Paragraph(children=[Text(text=text)], source=source)], source=source
    )
