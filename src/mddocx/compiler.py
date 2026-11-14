from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .api import MarkdownWord, _apply_front_matter
from .ast.base import Document
from .config import RenderConfig
from .config_validation import validate_render_config
from .diagnostics import Diagnostic, DiagnosticReporter
from .extensions.base import call_transform_document, call_transform_layout
from .layout import LayoutPlan
from .limits import enforce_ast_limits, enforce_input_limit
from .metadata import sanitize_markdown_metadata
from .normalize import Normalizer, SemanticIndex, build_semantic_index
from .parser.compatibility import find_math_syntax_issues
from .profiling import RenderStats
from .source import SourceDocument, acquire_markdown_source
from .validation import validated_docx_parts
from .verification import VerificationResult, compare_document


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """Typed output, diagnostics, and timing for one compilation."""

    output_bytes: bytes
    diagnostics: tuple[Diagnostic, ...]
    stats: RenderStats
    output_path: Path | None = None
    layout_plan: LayoutPlan = LayoutPlan()
    dependencies: tuple[Path, ...] = ()

    @property
    def success(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)

    @property
    def completed_with_fallbacks(self) -> bool:
        return self.recovered or any(item.code == "MATH201" for item in self.diagnostics)

    @property
    def recovered(self) -> bool:
        return any(item.code == "RECOVER201" for item in self.diagnostics)

    def diagnostics_json(self, indent: int | None = 2) -> str:
        reporter = DiagnosticReporter(list(self.diagnostics))
        return reporter.to_json(indent)

    def diagnostics_sarif(self, indent: int | None = 2) -> str:
        reporter = DiagnosticReporter(list(self.diagnostics))
        return reporter.to_sarif(indent)


@dataclass(frozen=True, slots=True)
class DocumentStageResult:
    """Canonical AST plus diagnostics from a parse or normalization stage."""

    document: Document
    diagnostics: tuple[Diagnostic, ...] = ()
    semantic_index: SemanticIndex | None = None

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
    """Parse, normalize, plan, render, verify, and compile Markdown documents."""

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
        return self._parse(markdown, MarkdownWord(self.config), source_file)

    def _parse(
        self, markdown: str, service: MarkdownWord, source_file: str | None
    ) -> DocumentStageResult:
        enforce_input_limit(markdown, service.config.limits)
        sanitized = sanitize_markdown_metadata(markdown, service.config.metadata)
        parser = service.parser
        document = parser.parse(
            sanitized.markdown,
            source_file=source_file,
            sanitize_metadata=False,
        )
        diagnostics = list(service.reporter.diagnostics)
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
            Diagnostic(
                "warning",
                "MATH101",
                issue.message,
                source_file,
                issue.line,
                "Close the explicit math delimiter/fence or escape it when literal text is intended.",
            )
            for issue in find_math_syntax_issues(sanitized.markdown)
        )
        return DocumentStageResult(document, tuple(diagnostics))

    def parse_file(self, input_path: str | Path) -> DocumentStageResult:
        source = self.acquire_file(input_path)
        return self.parse_string(
            source.text,
            source_file=source.source_file,
        )

    def acquire_file(self, input_path: str | Path) -> SourceDocument:
        return acquire_markdown_source(input_path, self.config.limits.max_input_bytes)

    def normalize(self, document: Document) -> DocumentStageResult:
        """Normalize and validate a parsed AST without rendering it."""
        service = MarkdownWord(self.config)
        config = service._config_for_document(Path("."), document.metadata)
        normalizer = Normalizer(service.reporter)
        normalized = normalizer.normalize(deepcopy(document))
        normalized = call_transform_document(config.extensions, normalized)
        enforce_ast_limits(normalized, config.limits)
        return DocumentStageResult(
            normalized,
            service.diagnostics,
            build_semantic_index(normalized),
        )

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

        layout_plan = call_transform_layout(
            cfg.extensions, document, LayoutPlanner(cfg).plan(document)
        )
        return LayoutStageResult(document, layout_plan, service.diagnostics)

    def render(
        self,
        document: Document,
        *,
        base_dir: str | Path | None = None,
        diagnostics: tuple[Diagnostic, ...] = (),
    ) -> CompilationResult:
        """Render a canonical AST and finalize a validated DOCX package."""
        return self._render(document, base_dir, diagnostics)

    def _render(
        self,
        document: Document,
        base_dir: str | Path | None,
        diagnostics: tuple[Diagnostic, ...],
        *,
        effective_config: bool = False,
    ) -> CompilationResult:
        service = MarkdownWord(self.config)
        output = service._render_ast(
            deepcopy(document), base_dir, diagnostics, effective_config=effective_config
        )
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
            normalized.semantic_index,
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
        *,
        report_paths: tuple[Path, ...] = (),
    ) -> CompilationResult:
        source = Path(input_path)
        target = Path(output_path)
        compiler = MarkdownWord(self.config)
        output = compiler._render_file(source, target, report_paths=report_paths)
        return CompilationResult(
            output,
            compiler.diagnostics,
            compiler.last_stats,
            target,
            compiler.last_layout_plan,
            tuple(sorted(compiler._dependencies)),
        )

    def check_file(self, input_path: str | Path) -> DocumentStageResult:
        parsed = self.parse_file(input_path)
        normalized = self.normalize(parsed.document)
        return DocumentStageResult(
            normalized.document,
            parsed.diagnostics + normalized.diagnostics,
            normalized.semantic_index,
        )

    def verify(self, source_path: str | Path, output: str | Path | bytes) -> VerificationResult:
        """Compare normalized source constructs with a DOCX, entirely in-process."""
        source = Path(source_path)
        parser_config = deepcopy(self.config)
        parser_config.extensions = ()
        parser_config.plugins.names = ()
        parser_config.recover = False
        source_text = self.acquire_file(source)
        parsed = self._parse(source_text.text, MarkdownWord(parser_config), source_text.source_file)
        # Extension hooks are not called by the offline verifier.
        reporter = DiagnosticReporter()
        normalized = Normalizer(reporter).normalize(parsed.document)
        config = validate_render_config(
            _apply_front_matter(deepcopy(self.config), normalized.metadata, True)
        )
        enforce_ast_limits(normalized, config.limits)
        blob = output if isinstance(output, bytes) else Path(output).read_bytes()
        roots = validated_docx_parts(blob, config.validation)
        result = compare_document(normalized, roots, config)
        return VerificationResult(
            result.checked_units, result.findings, parsed.diagnostics + tuple(reporter.diagnostics)
        )
