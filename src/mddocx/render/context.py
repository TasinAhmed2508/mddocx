from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mddocx.config import RenderConfig
from mddocx.diagnostics import DiagnosticReporter
from mddocx.math import DefaultMathConverter


@dataclass(slots=True)
class RenderContext:
    """Shared typed services and registries for focused render components."""

    word_document: Any
    config: RenderConfig
    reporter: DiagnosticReporter
    math: DefaultMathConverter
    numbering: Any
    references: Any
    resolver: Any
