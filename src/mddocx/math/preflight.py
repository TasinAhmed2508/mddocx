from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Literal

from mddocx.ast.block import MathBlock
from mddocx.ast.inline import InlineMath
from mddocx.config import MetadataConfig
from mddocx.parser import MarkdownParser
from mddocx.parser.compatibility import MathSyntaxIssue, find_math_syntax_issues

from .converter import DefaultMathConverter


@dataclass(slots=True)
class EquationCheck:
    mode: Literal["inline", "display"]
    source: str
    status: Literal["native", "fallback"]
    source_file: str | None = None
    line: int | None = None
    error: str | None = None


@dataclass(slots=True)
class MathPreflightReport:
    engine: str
    source_file: str | None = None
    equations: list[EquationCheck] = field(default_factory=list)
    syntax_issues: list[MathSyntaxIssue] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.equations)

    @property
    def native(self) -> int:
        return sum(item.status == "native" for item in self.equations)

    @property
    def fallbacks(self) -> int:
        return sum(item.status == "fallback" for item in self.equations)

    @property
    def ok(self) -> bool:
        return self.fallbacks == 0 and not self.syntax_issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "source_file": self.source_file,
            "total": self.total,
            "native": self.native,
            "fallbacks": self.fallbacks,
            "syntax_issues": [asdict(item) for item in self.syntax_issues],
            "ok": self.ok,
            "equations": [asdict(item) for item in self.equations],
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_text(self) -> str:
        lines = [
            "Math preflight",
            f"Engine: {self.engine}",
            f"Equations: {self.total}",
            f"Native: {self.native}",
            f"Fallbacks: {self.fallbacks}",
            f"Syntax issues: {len(self.syntax_issues)}",
        ]
        for issue in self.syntax_issues:
            location = self.source_file or "<string>"
            lines.append(f"WARNING {location}:{issue.line}: {issue.message}")
        for item in self.equations:
            if item.status == "native":
                continue
            location = item.source_file or "<string>"
            if item.line is not None:
                location += f":{item.line}"
            lines.append(f"WARNING {location}: {item.error}")
        return "\n".join(lines)


def inspect_math(
    markdown: str,
    *,
    source_file: str | None = None,
    metadata_config: MetadataConfig | None = None,
) -> MathPreflightReport:
    parser = MarkdownParser(metadata_config=metadata_config)
    document = parser.parse(markdown, source_file=source_file)
    converter = DefaultMathConverter()
    report = MathPreflightReport(
        engine=converter.engine_name,
        source_file=source_file,
        syntax_issues=find_math_syntax_issues(markdown),
    )
    for node in _walk(document.children):
        if not isinstance(node, (InlineMath, MathBlock)):
            continue
        display = isinstance(node, MathBlock)
        source = getattr(node, "source", None)
        error: str | None
        try:
            converter.latex_to_omml(node.source_text, display)
        except Exception as exc:
            status: Literal["native", "fallback"] = "fallback"
            error = str(exc)
        else:
            status = "native"
            error = None
        report.equations.append(
            EquationCheck(
                mode="display" if display else "inline",
                source=node.source_text,
                status=status,
                source_file=getattr(source, "file", source_file),
                line=getattr(source, "line", None),
                error=error,
            )
        )
    return report


def inspect_math_file(path: str | Path) -> MathPreflightReport:
    source = Path(path)
    return inspect_math(source.read_text(encoding="utf-8-sig"), source_file=str(source))


def _walk(value):
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk(item)
        return
    yield value
    for name in ("children", "items", "rows", "cells", "term", "definition"):
        child = getattr(value, name, None)
        if child:
            yield from _walk(child)
