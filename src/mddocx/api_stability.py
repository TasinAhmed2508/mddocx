from __future__ import annotations

from dataclasses import dataclass
import json

PUBLIC_API_VERSION = "1"

# v1.0 public names are intentionally explicit. New names may be added in compatible
# minor releases; removal or incompatible signature changes require a major release.
FROZEN_PUBLIC_NAMES = (
    "MarkdownWord", "RenderConfig", "Margins", "ListConfig", "PageConfig",
    "ResourcePolicy", "MathFailurePolicy", "MermaidConfig", "ChartConfig", "DataConfig",
    "HeaderConfig", "FooterConfig", "TOCConfig", "TableConfig", "FontConfig", "ImageConfig",
    "PerformanceConfig", "CompilationLimits", "ReproducibilityConfig", "ValidationConfig",
    "CacheConfig", "PluginConfig", "ReferenceConfig", "NotesConfig", "CitationConfig",
    "AccessibilityConfig", "FigureConfig", "HeadingNumberingConfig", "TitlePageConfig",
    "AbstractConfig", "CodeConfig", "CalloutConfig", "CommentConfig", "FieldConfig",
    "MetadataConfig", "MetadataSanitizationReport", "SanitizedMarkdown", "sanitize_markdown_metadata",
    "RenderStats", "MddocxExtension", "load_entrypoint_extensions", "BatchResult",
    "collect_markdown_inputs", "render_many", "validate_docx_package", "DocxInspection",
    "inspect_docx", "inspect_docx_bytes", "VisualQAReport", "compare_visual_pages",
    "render_docx_pages", "render", "render_string", "ProjectManifest", "ProjectCompilation",
    "ProjectBuildResult", "ProjectWatchEvent", "load_project", "compile_project",
    "build_project", "watch_project", "init_project", "project_info",
    "AccessibilityFinding", "AccessibilityReport", "audit_docx_accessibility",
    "audit_docx_accessibility_bytes", "BenchmarkReport", "run_performance_gate",
    "PUBLIC_API_VERSION", "get_public_api_manifest",
)


@dataclass(frozen=True, slots=True)
class PublicApiManifest:
    api_version: str
    package_version: str
    names: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"api_version": self.api_version, "package_version": self.package_version, "names": list(self.names)}

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)


def get_public_api_manifest() -> PublicApiManifest:
    from . import __version__
    return PublicApiManifest(PUBLIC_API_VERSION, __version__, FROZEN_PUBLIC_NAMES)
