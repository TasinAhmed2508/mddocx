from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path
from time import perf_counter
import tracemalloc
from typing import Any

from .ast.base import Document
from .cache import AstCache
from .config import RenderConfig
from .config_validation import validate_render_config
from .diagnostics import Diagnostic, DiagnosticReporter, MddocxError
from .extensions.base import call_transform_document
from .extensions.discovery import load_entrypoint_extensions
from .limits import enforce_ast_limits, enforce_input_limit
from .layout import LayoutPlan, LayoutPlanner
from .metadata import (
    MetadataSanitizationReport,
    sanitize_markdown_metadata,
    scrub_generated_docx_core_properties,
)
from .normalize import Normalizer
from .parser import MarkdownParser
from .parser.compatibility import find_math_syntax_issues
from .profiling import RenderStats
from .render import DocxRenderer
from .reproducibility import make_reproducible_docx
from .validation import validate_docx_package


class MarkdownWord:
    def __init__(self, config: RenderConfig | None = None):
        self.config = validate_render_config(
            deepcopy(config) if config is not None else RenderConfig()
        )
        self._config_was_provided = config is not None
        if self.config.plugins.names:
            discovered = load_entrypoint_extensions(
                self.config.plugins.names, self.config.plugins.entrypoint_group
            )
            self.config.extensions = tuple(self.config.extensions) + discovered
        self.reporter = DiagnosticReporter()
        self.parser = MarkdownParser(self.config.extensions, self.config.metadata)
        self.normalizer = Normalizer(self.reporter)
        self.last_stats = RenderStats()
        self.last_layout_plan = LayoutPlan()

    @property
    def diagnostics(self):
        return tuple(self.reporter.diagnostics)

    def diagnostics_json(self, indent: int | None = 2) -> str:
        return self.reporter.to_json(indent=indent)

    def diagnostics_sarif(self, indent: int | None = 2) -> str:
        return self.reporter.to_sarif(indent=indent)

    def render_file(self, input_path: str | Path, output_path: str | Path) -> None:
        input_path = Path(input_path)
        output_path = Path(output_path)
        try:
            if input_path.stat().st_size > self.config.limits.max_input_bytes:
                raise _input_limit_error(self.config.limits.max_input_bytes)
            markdown = input_path.read_text(encoding="utf-8-sig")
            blob = self._compile(markdown, input_path.parent, source_file=str(input_path))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(blob)
        except MddocxError as exc:
            self._record_error(exc)
            raise

    def render_string(self, markdown: str, base_dir: str | Path | None = None) -> bytes:
        return self._compile(
            markdown,
            Path(base_dir) if base_dir is not None else Path("."),
            source_file=None,
        )

    def render_ast(self, document: Document, base_dir: str | Path | None = None) -> bytes:
        self.reporter.diagnostics.clear()
        base = Path(base_dir) if base_dir is not None else Path(".")
        cfg = self._config_for_document(base, document.metadata)
        started = perf_counter()
        try:
            transformed = call_transform_document(
                cfg.extensions, self.normalizer.normalize(document)
            )
            enforce_ast_limits(transformed, cfg.limits)
            plan_start = perf_counter()
            self.last_layout_plan = LayoutPlanner(cfg).plan(transformed)
            plan_ms = (perf_counter() - plan_start) * 1000
            renderer = DocxRenderer(self.reporter)
            blob = renderer.render(transformed, cfg, self.last_layout_plan)
            blob = self._finalize_output(blob, cfg)
        except MddocxError as exc:
            self._record_error(exc)
            raise
        elapsed = (perf_counter() - started) * 1000
        self.last_stats = RenderStats(
            render_ms=elapsed,
            total_ms=elapsed,
            plan_ms=plan_ms,
            output_bytes=len(blob),
            output_sha256=hashlib.sha256(blob).hexdigest(),
        )
        return blob

    def check_file(self, input_path: str | Path) -> None:
        self.reporter.diagnostics.clear()
        input_path = Path(input_path)
        try:
            if input_path.stat().st_size > self.config.limits.max_input_bytes:
                raise _input_limit_error(self.config.limits.max_input_bytes)
            markdown = input_path.read_text(encoding="utf-8-sig")
            enforce_input_limit(markdown, self.config.limits)
            sanitized = sanitize_markdown_metadata(markdown, self.config.metadata)
            self._report_metadata_sanitization(sanitized.report, str(input_path))
            self._report_math_syntax_issues(sanitized.markdown, str(input_path))
            ast = self.normalizer.normalize(
                self.parser.parse(
                    sanitized.markdown, source_file=str(input_path), sanitize_metadata=False
                )
            )
            cfg = self._config_for_document(input_path.parent, ast.metadata)
            ast = call_transform_document(cfg.extensions, ast)
            enforce_ast_limits(ast, cfg.limits)
        except MddocxError as exc:
            self._record_error(exc)
            raise

    def _compile(self, markdown: str, base_dir: Path, source_file: str | None) -> bytes:
        self.reporter.diagnostics.clear()
        cfg_for_memory = self.config.performance
        started_tracemalloc = cfg_for_memory.track_memory and not tracemalloc.is_tracing()
        if started_tracemalloc:
            tracemalloc.start()
        total_start = perf_counter()
        cache_hit = False
        try:
            enforce_input_limit(markdown, self.config.limits)
            sanitized = sanitize_markdown_metadata(markdown, self.config.metadata)
            self._report_metadata_sanitization(sanitized.report, source_file)
            markdown = sanitized.markdown
            self._report_math_syntax_issues(markdown, source_file)
            ast: Document | None = None
            cache: AstCache | None = None
            cache_key: str | None = None
            if self.config.cache.ast_enabled:
                if self.config.extensions:
                    self.reporter.info(
                        "CACHE402",
                        "Persistent AST cache is disabled when extensions are active.",
                        source_file,
                    )
                else:
                    cache = AstCache(self.config.cache, base_dir)
                    cache_key = cache.key(markdown, source_file)
                    ast = cache.load(cache_key)
                    cache_hit = ast is not None
                    if cache_hit:
                        self.reporter.info(
                            "CACHE401", "Loaded normalized AST from persistent cache.", source_file
                        )

            parse_ms = 0.0
            normalize_ms = 0.0
            if ast is None:
                parse_start = perf_counter()
                ast = self.parser.parse(markdown, source_file=source_file, sanitize_metadata=False)
                parse_ms = (perf_counter() - parse_start) * 1000

                normalize_start = perf_counter()
                ast = self.normalizer.normalize(ast)
                normalize_ms = (perf_counter() - normalize_start) * 1000
                if cache is not None and cache_key is not None:
                    try:
                        cache.save(cache_key, ast)
                    except (OSError, TypeError, ValueError) as exc:
                        self.reporter.warn(
                            "CACHE403",
                            f"Unable to write persistent AST cache: {type(exc).__name__}",
                            source_file,
                        )

            cfg = self._config_for_document(base_dir, ast.metadata)
            transform_start = perf_counter()
            ast = call_transform_document(cfg.extensions, ast)
            enforce_ast_limits(ast, cfg.limits)
            normalize_ms += (perf_counter() - transform_start) * 1000

            plan_start = perf_counter()
            self.last_layout_plan = LayoutPlanner(cfg).plan(ast)
            plan_ms = (perf_counter() - plan_start) * 1000
            render_start = perf_counter()
            renderer = DocxRenderer(self.reporter)
            blob = renderer.render(ast, cfg, self.last_layout_plan)
            blob = self._finalize_output(blob, cfg)
            render_ms = (perf_counter() - render_start) * 1000
            total_ms = (perf_counter() - total_start) * 1000

            peak = None
            if cfg_for_memory.track_memory and tracemalloc.is_tracing():
                _, peak = tracemalloc.get_traced_memory()
            self.last_stats = RenderStats(
                parse_ms=parse_ms,
                normalize_ms=normalize_ms,
                plan_ms=plan_ms,
                render_ms=render_ms,
                total_ms=total_ms,
                peak_memory_bytes=peak,
                output_bytes=len(blob),
                output_sha256=hashlib.sha256(blob).hexdigest(),
                ast_cache_hit=cache_hit,
            )
            return blob
        except MddocxError as exc:
            self._record_error(exc)
            raise
        finally:
            if started_tracemalloc and tracemalloc.is_tracing():
                tracemalloc.stop()

    @staticmethod
    def _finalize_output(blob: bytes, cfg: RenderConfig) -> bytes:
        blob = scrub_generated_docx_core_properties(
            blob,
            cfg.metadata,
            template_used=cfg.template is not None,
            explicit={
                "title": cfg.title is not None,
                "author": cfg.author is not None,
                "subject": cfg.subject is not None,
                "keywords": cfg.keywords is not None,
                "comments": cfg.comments is not None,
                "created_at": cfg.created_at is not None,
                "modified_at": False,
            },
        )
        blob = make_reproducible_docx(blob, cfg.reproducibility)
        validate_docx_package(blob, cfg.validation)
        return blob

    def _report_metadata_sanitization(
        self, report: MetadataSanitizationReport, source_file: str | None
    ) -> None:
        if report.changed:
            parts = []
            if report.removed_lines:
                parts.append(f"{report.removed_lines} source line(s)")
            if report.removed_front_matter_keys:
                parts.append(f"{len(report.removed_front_matter_keys)} front-matter field(s)")
            detail = " and ".join(parts) or "metadata"
            self.reporter.info(
                "META101", f"Removed AI/chat export metadata: {detail}.", source_file
            )
        elif report.detected_export_metadata and report.policy == "keep":
            self.reporter.info(
                "META102",
                "AI/chat export metadata was detected and preserved by configuration.",
                source_file,
            )

    def _report_math_syntax_issues(self, markdown: str, source_file: str | None) -> None:
        for issue in find_math_syntax_issues(markdown):
            self.reporter.warn("MATH101", issue.message, source_file, issue.line)

    def _record_error(self, exc: MddocxError) -> None:
        if not self.reporter.diagnostics or self.reporter.diagnostics[-1] != exc.diagnostic:
            self.reporter.diagnostics.append(exc.diagnostic)

    def _config_for_document(self, base_dir: Path, metadata: dict[str, Any]) -> RenderConfig:
        cfg = deepcopy(self.config)
        if cfg.base_dir is None:
            cfg.base_dir = base_dir
        return validate_render_config(_apply_front_matter(cfg, metadata, self._config_was_provided))


def _input_limit_error(max_bytes: int) -> MddocxError:
    return MddocxError(
        Diagnostic("error", "LIMIT401", f"Markdown input exceeds {max_bytes} bytes.")
    )


def _apply_front_matter(
    cfg: RenderConfig, metadata: dict[str, Any], explicit_config: bool
) -> RenderConfig:
    if not metadata:
        return cfg
    defaults = RenderConfig()

    def can_use(current: Any, default: Any) -> bool:
        return not explicit_config or current == default

    scalar_fields = ("title", "author", "subject", "comments")
    for name in scalar_fields:
        if metadata.get(name) is not None and can_use(getattr(cfg, name), getattr(defaults, name)):
            setattr(cfg, name, str(metadata[name]))
    if metadata.get("keywords") is not None and can_use(cfg.keywords, defaults.keywords):
        value = metadata["keywords"]
        cfg.keywords = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
    if metadata.get("theme") is not None and can_use(cfg.theme, defaults.theme):
        cfg.theme = str(metadata["theme"])
    if metadata.get("page_size") in {"A4", "Letter"} and can_use(cfg.page.size, defaults.page.size):
        cfg.page.size = metadata["page_size"]
    if metadata.get("orientation") in {"portrait", "landscape"} and can_use(
        cfg.page.orientation, defaults.page.orientation
    ):
        cfg.page.orientation = metadata["orientation"]
    if metadata.get("rtl") in {"off", "auto", "force"} and can_use(cfg.rtl, defaults.rtl):
        cfg.rtl = metadata["rtl"]
    if metadata.get("toc") is not None and can_use(cfg.toc.enabled, defaults.toc.enabled):
        cfg.toc.enabled = bool(metadata["toc"])
    if metadata.get("page_numbers") is not None and can_use(
        cfg.footer.page_number, defaults.footer.page_number
    ):
        cfg.footer.page_number = bool(metadata["page_numbers"])
        cfg.footer.enabled = cfg.footer.enabled or cfg.footer.page_number
    if metadata.get("auto_landscape_tables") is not None and can_use(
        cfg.table.auto_landscape, defaults.table.auto_landscape
    ):
        cfg.table.auto_landscape = bool(metadata["auto_landscape_tables"])
    if metadata.get("header") is not None and can_use(cfg.header.text, defaults.header.text):
        cfg.header.text = str(metadata["header"])
        cfg.header.enabled = True
    if metadata.get("footer") is not None and can_use(cfg.footer.text, defaults.footer.text):
        cfg.footer.text = str(metadata["footer"])
        cfg.footer.enabled = True
    if metadata.get("notes") in {"footnote", "endnote"} and can_use(
        cfg.notes.style, defaults.notes.style
    ):
        cfg.notes.style = str(metadata["notes"])
    if metadata.get("bibliography") is not None and can_use(
        cfg.citations.bibliography, defaults.citations.bibliography
    ):
        cfg.citations.bibliography = Path(str(metadata["bibliography"]))
    if metadata.get("citation_style") in {"author-year", "apa", "ieee", "numeric"} and can_use(
        cfg.citations.style, defaults.citations.style
    ):
        cfg.citations.style = str(metadata["citation_style"])
    if metadata.get("auto_bibliography") is not None and can_use(
        cfg.citations.auto_bibliography, defaults.citations.auto_bibliography
    ):
        cfg.citations.auto_bibliography = bool(metadata["auto_bibliography"])
    if metadata.get("title_page") is not None and can_use(
        cfg.title_page.enabled, defaults.title_page.enabled
    ):
        cfg.title_page.enabled = bool(metadata["title_page"])
    if metadata.get("subtitle") is not None and can_use(
        cfg.title_page.subtitle, defaults.title_page.subtitle
    ):
        cfg.title_page.subtitle = str(metadata["subtitle"])
        cfg.title_page.enabled = True
    if metadata.get("organization") is not None and can_use(
        cfg.title_page.organization, defaults.title_page.organization
    ):
        cfg.title_page.organization = str(metadata["organization"])
        cfg.title_page.enabled = True
    if metadata.get("title_date") is not None and can_use(
        cfg.title_page.date, defaults.title_page.date
    ):
        cfg.title_page.date = str(metadata["title_date"])
    if metadata.get("abstract") is not None and can_use(cfg.abstract.text, defaults.abstract.text):
        cfg.abstract.text = str(metadata["abstract"])
    if metadata.get("abstract_title") is not None and can_use(
        cfg.abstract.title, defaults.abstract.title
    ):
        cfg.abstract.title = str(metadata["abstract_title"])
    if metadata.get("keywords") is not None and not cfg.abstract.keywords:
        value = metadata["keywords"]
        cfg.abstract.keywords = (
            tuple(map(str, value))
            if isinstance(value, list)
            else tuple(x.strip() for x in str(value).split(",") if x.strip())
        )
    if metadata.get("heading_numbering") is not None and can_use(
        cfg.heading_numbering.enabled, defaults.heading_numbering.enabled
    ):
        cfg.heading_numbering.enabled = bool(metadata["heading_numbering"])
    if metadata.get("heading_numbering_depth") is not None and can_use(
        cfg.heading_numbering.max_level, defaults.heading_numbering.max_level
    ):
        try:
            cfg.heading_numbering.max_level = max(
                1, min(6, int(metadata["heading_numbering_depth"]))
            )
        except (TypeError, ValueError):
            pass
    if metadata.get("equation_numbering") in {"document", "section"} and can_use(
        cfg.references.equation_number_format, defaults.references.equation_number_format
    ):
        cfg.references.equation_number_format = str(metadata["equation_numbering"])
    if metadata.get("caption_numbering") in {"document", "section"} and can_use(
        cfg.references.caption_number_format, defaults.references.caption_number_format
    ):
        cfg.references.caption_number_format = str(metadata["caption_numbering"])
    if metadata.get("code_line_numbers") is not None and can_use(
        cfg.code.line_numbers, defaults.code.line_numbers
    ):
        cfg.code.line_numbers = bool(metadata["code_line_numbers"])
    if metadata.get("syntax_highlighting") is not None and can_use(
        cfg.code.syntax_highlighting, defaults.code.syntax_highlighting
    ):
        cfg.code.syntax_highlighting = bool(metadata["syntax_highlighting"])
    if metadata.get("page_x_of_y") is not None and can_use(
        cfg.footer.page_x_of_y, defaults.footer.page_x_of_y
    ):
        cfg.footer.page_x_of_y = bool(metadata["page_x_of_y"])
        cfg.footer.enabled = cfg.footer.enabled or cfg.footer.page_x_of_y
    if metadata.get("created_at") is not None and can_use(cfg.created_at, defaults.created_at):
        try:
            cfg.created_at = datetime.fromisoformat(
                str(metadata["created_at"]).replace("Z", "+00:00")
            )
        except ValueError:
            pass
    return cfg


def _config_with_template(
    config: RenderConfig | None, template: str | Path | None
) -> RenderConfig | None:
    if template is None:
        return config
    cfg = deepcopy(config) if config is not None else RenderConfig()
    cfg.template = Path(template)
    return cfg


def render(
    input_path: str | Path,
    output_path: str | Path,
    config: RenderConfig | None = None,
    *,
    template: str | Path | None = None,
) -> None:
    MarkdownWord(_config_with_template(config, template)).render_file(input_path, output_path)


def render_string(
    markdown: str,
    config: RenderConfig | None = None,
    base_dir: str | Path | None = None,
    *,
    template: str | Path | None = None,
) -> bytes:
    return MarkdownWord(_config_with_template(config, template)).render_string(
        markdown, base_dir=base_dir
    )
