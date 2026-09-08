from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .api import MarkdownWord
from .ast.base import Document
from .config import RenderConfig
from .config_validation import validate_render_config
from .diagnostics import Diagnostic, MddocxError
from .extensions.base import call_transform_document
from .layout import LayoutPlan
from .limits import enforce_ast_limits, enforce_input_limit
from .metadata import sanitize_markdown_metadata
from .normalize import Normalizer
from .parser import MarkdownParser
from .parser.compatibility import find_math_syntax_issues
from .profiling import RenderStats


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """Typed output, diagnostics, and timing for one compilation."""

    output_bytes: bytes
    diagnostics: tuple[Diagnostic, ...]
    stats: RenderStats
    output_path: Path | None = None
    layout_plan: LayoutPlan = LayoutPlan()

    @property
    def success(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)

    @property
    def completed_with_fallbacks(self) -> bool:
        return any(item.code == "MATH201" for item in self.diagnostics)


@dataclass(frozen=True, slots=True)
class DocumentStageResult:
    """Canonical AST plus diagnostics from a parse or normalization stage."""

    document: Document
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def success(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)


@dataclass(frozen=True, slots=True)
class LayoutStageResult:
    """Normalized AST and its pre-render layout decisions."""

    document: Document
    layout_plan: LayoutPlan
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def success(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)


class Compiler:
    """Staged-v2 compiler service backed by the stable v1 pipeline."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = validate_render_config(
            deepcopy(config) if config is not None else RenderConfig()
        )

    def parse_string(
        self,
        markdown: str,
        *,
        source_file: str | None = None,
    ) -> DocumentStageResult:
        """Acquire, sanitize, and parse Markdown into the canonical AST."""
        enforce_input_limit(markdown, self.config.limits)
        sanitized = sanitize_markdown_metadata(markdown, self.config.metadata)
        parser = MarkdownParser(self.config.extensions, self.config.metadata)
        document = parser.parse(
            sanitized.markdown,
            source_file=source_file,
            sanitize_metadata=False,
        )
        diagnostics: list[Diagnostic] = []
        if sanitized.report.changed:
            diagnostics.append(
                Diagnostic(
                    "info",
                    "META101",
                    "Removed AI/chat export metadata before parsing.",
                    source_file,
                )
            )
        diagnostics.extend(
            Diagnostic("warning", "MATH101", issue.message, source_file, issue.line)
            for issue in find_math_syntax_issues(sanitized.markdown)
        )
        return DocumentStageResult(document, tuple(diagnostics))

    def parse_file(self, input_path: str | Path) -> DocumentStageResult:
        source = Path(input_path)
        if source.stat().st_size > self.config.limits.max_input_bytes:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "LIMIT401",
                    f"Markdown input exceeds {self.config.limits.max_input_bytes} bytes.",
                    str(source),
                )
            )
        return self.parse_string(
            source.read_text(encoding="utf-8-sig"),
            source_file=str(source),
        )

    def normalize(self, document: Document) -> DocumentStageResult:
        """Normalize and validate a parsed AST without rendering it."""
        service = MarkdownWord(self.config)
        normalized = Normalizer(service.reporter).normalize(deepcopy(document))
        normalized = call_transform_document(service.config.extensions, normalized)
        enforce_ast_limits(normalized, self.config.limits)
        return DocumentStageResult(normalized, service.diagnostics)

    def plan(
        self,
        document: Document,
        *,
        base_dir: str | Path | None = None,
    ) -> LayoutStageResult:
        """Compute page-sensitive decisions without creating Word objects."""
        service = MarkdownWord(self.config)
        base = Path(base_dir) if base_dir is not None else Path(".")
        cfg = service._config_for_document(base, document.metadata)
        from .layout import LayoutPlanner

        layout_plan = LayoutPlanner(cfg).plan(document)
        return LayoutStageResult(document, layout_plan, service.diagnostics)

    def render(
        self,
        document: Document,
        *,
        base_dir: str | Path | None = None,
    ) -> CompilationResult:
        """Render a canonical AST and finalize a validated DOCX package."""
        service = MarkdownWord(self.config)
        output = service.render_ast(deepcopy(document), base_dir=base_dir)
        return CompilationResult(
            output,
            service.diagnostics,
            service.last_stats,
            layout_plan=service.last_layout_plan,
        )

    def check_string(
        self,
        markdown: str,
        *,
        source_file: str | None = None,
    ) -> DocumentStageResult:
        """Parse and normalize input without writing or rendering a DOCX."""
        parsed = self.parse_string(markdown, source_file=source_file)
        normalized = self.normalize(parsed.document)
        return DocumentStageResult(
            normalized.document,
            parsed.diagnostics + normalized.diagnostics,
        )

    def compile_string(
        self,
        markdown: str,
        *,
        base_dir: str | Path | None = None,
    ) -> CompilationResult:
        compiler = MarkdownWord(self.config)
        output = compiler.render_string(markdown, base_dir=base_dir)
        return CompilationResult(
            output,
            compiler.diagnostics,
            compiler.last_stats,
            layout_plan=compiler.last_layout_plan,
        )

    def compile_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> CompilationResult:
        source = Path(input_path)
        target = Path(output_path)
        compiler = MarkdownWord(self.config)
        compiler.render_file(source, target)
        return CompilationResult(
            target.read_bytes(),
            compiler.diagnostics,
            compiler.last_stats,
            target,
            compiler.last_layout_plan,
        )

    def check_file(self, input_path: str | Path) -> DocumentStageResult:
        parsed = self.parse_file(input_path)
        normalized = self.normalize(parsed.document)
        return DocumentStageResult(
            normalized.document,
            parsed.diagnostics + normalized.diagnostics,
        )
