from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


@dataclass(slots=True)
class Margins:
    top: float = 20.0
    bottom: float = 20.0
    left: float = 22.0
    right: float = 22.0


@dataclass(slots=True)
class PageConfig:
    size: Literal["A4", "Letter"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    margins: Margins = field(default_factory=Margins)




@dataclass(slots=True)
class MetadataConfig:
    """Controls removal of AI/chat export metadata before Markdown parsing.

    auto: conservatively remove high-confidence export metadata (default).
    strip: remove recognized metadata/provenance even without a strong export marker.
    keep: preserve source metadata exactly as supplied.
    """
    ai_export: Literal["auto", "strip", "keep"] = "auto"
    strip_front_matter_provenance: bool = True
    strip_boundary_metadata: bool = True
    strip_html_metadata_comments: bool = True
    strip_role_timestamps: bool = True
    scrub_generated_docx_properties: bool = True


@dataclass(slots=True)
class ResourcePolicy:
    allow_remote_resources: bool = False
    allowed_schemes: tuple[str, ...] = ("https",)
    allowed_domains: tuple[str, ...] | None = None
    allow_private_hosts: bool = False
    max_resource_size: int = 10_000_000
    timeout_seconds: float = 10.0
    max_redirects: int = 3
    validate_mime: bool = True
    cache_remote_resources: bool = True
    cache_directory: Path | None = None


@dataclass(slots=True)
class MathFailurePolicy:
    mode: Literal["error", "plain_text", "warning"] = "error"


@dataclass(slots=True)
class HeaderConfig:
    enabled: bool = False
    text: str | None = None
    document_title: bool = False
    section_title: bool = False
    different_first_page: bool = False
    different_odd_even: bool = False
    first_page_text: str | None = None
    even_page_text: str | None = None


@dataclass(slots=True)
class FooterConfig:
    enabled: bool = False
    text: str | None = None
    page_number: bool = False
    num_pages: bool = False
    page_x_of_y: bool = False
    different_first_page: bool = False
    different_odd_even: bool = False
    first_page_text: str | None = None
    even_page_text: str | None = None




@dataclass(slots=True)
class HeadingNumberingConfig:
    enabled: bool = False
    max_level: int = 3
    separator: str = "."
    suffix: str = " "


@dataclass(slots=True)
class TitlePageConfig:
    enabled: bool = False
    subtitle: str | None = None
    organization: str | None = None
    date: str | None = None
    page_break_after: bool = True


@dataclass(slots=True)
class AbstractConfig:
    text: str | None = None
    title: str = "Abstract"
    keywords: tuple[str, ...] = ()
    keywords_label: str = "Keywords"


@dataclass(slots=True)
class CodeConfig:
    syntax_highlighting: bool = True
    line_numbers: bool = False
    show_language_label: bool = False
    wrap: bool = True
    highlight_lines: tuple[int, ...] = ()


@dataclass(slots=True)
class CalloutConfig:
    enabled: bool = True
    labels: dict[str, str] = field(default_factory=lambda: {
        "note": "Note", "tip": "Tip", "important": "Important",
        "warning": "Warning", "caution": "Caution", "example": "Example",
    })


@dataclass(slots=True)
class CommentConfig:
    enabled: bool = True
    author: str = "mddocx"
    initials: str = "MD"


@dataclass(slots=True)
class FieldConfig:
    update_on_open: bool = True


@dataclass(slots=True)
class TOCConfig:
    enabled: bool = False
    min_level: int = 1
    max_level: int = 3
    title: str | None = "Contents"


@dataclass(slots=True)
class ListConfig:
    bullet_glyphs: tuple[str, ...] = ("•", "◦", "▪")
    bullet_font: str = "Arial"
    number_font: str | None = None
    indent_twips_per_level: int = 360
    hanging_twips: int = 180
    tab_twips_offset: int = 0


@dataclass(slots=True)
class TableConfig:
    repeat_header: bool = True
    header_shading: str = "EDEDED"
    cell_padding_twips: int = 90
    min_column_width_mm: float = 16.0
    max_column_width_mm: float = 85.0
    short_row_character_limit: int = 400
    auto_landscape: bool = False
    landscape_min_columns: int = 6
    landscape_width_ratio: float = 1.22
    restore_portrait_after_landscape: bool = True


@dataclass(slots=True)
class FontConfig:
    body: str | None = None
    headings: str | None = None
    code: str | None = None
    east_asia: str | None = None
    complex_script: str | None = None
    fallback: tuple[str, ...] = ("Aptos", "Arial", "Noto Sans")


@dataclass(slots=True)
class ImageConfig:
    max_width_percent: float = 100.0
    allow_upscale: bool = False
    webp_conversion: bool = True
    svg_conversion: bool = True
    svg_dpi: int = 144
    jpeg_quality: int = 92


@dataclass(slots=True)
class MermaidConfig:
    enabled: bool = True
    fallback: Literal["code", "error"] = "code"
    max_source_chars: int = 100_000
    max_nodes: int = 500
    max_edges: int = 1_000



@dataclass(slots=True)
class ChartConfig:
    enabled: bool = True
    default_width_mm: float = 150.0
    default_height_mm: float = 85.0
    max_series: int = 20
    max_points: int = 10_000


@dataclass(slots=True)
class DataConfig:
    max_rows: int = 10_000
    max_columns: int = 100


@dataclass(slots=True)
class PerformanceConfig:
    enabled: bool = False
    track_memory: bool = False
    cache_math: bool = True


@dataclass(slots=True)
class CompilationLimits:
    max_input_bytes: int = 20_000_000
    max_ast_nodes: int = 100_000
    max_nesting_depth: int = 64
    max_table_cells: int = 100_000
    max_images: int = 5_000
    max_equations: int = 10_000


@dataclass(slots=True)
class ReproducibilityConfig:
    enabled: bool = True
    zip_timestamp: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)
    sort_package_parts: bool = True


@dataclass(slots=True)
class ValidationConfig:
    validate_output: bool = True
    max_package_parts: int = 5_000
    max_xml_part_size: int = 20_000_000
    max_total_uncompressed_size: int = 100_000_000
    validate_relationships: bool = True
    validate_math_structure: bool = True
    detect_placeholder_chars: bool = False
    allow_macros: bool = False


@dataclass(slots=True)
class CacheConfig:
    ast_enabled: bool = False
    directory: Path | None = None
    max_entry_bytes: int = 20_000_000


@dataclass(slots=True)
class PluginConfig:
    names: tuple[str, ...] = ()
    entrypoint_group: str = "mddocx.extensions"



@dataclass(slots=True)
class ReferenceConfig:
    enabled: bool = True
    captions: bool = True
    equation_numbering: bool = True
    listing_numbering: bool = True
    include_prefix_in_crossrefs: bool = True
    figure_caption_position: Literal["above", "below"] = "below"
    table_caption_position: Literal["above", "below"] = "above"
    listing_caption_position: Literal["above", "below"] = "above"
    equation_number_format: Literal["document", "section"] = "document"
    caption_number_format: Literal["document", "section"] = "document"
    figure_label: str = "Figure"
    table_label: str = "Table"
    equation_label: str = "Equation"
    listing_label: str = "Listing"


@dataclass(slots=True)
class NotesConfig:
    style: Literal["footnote", "endnote"] = "footnote"


@dataclass(slots=True)
class CitationConfig:
    bibliography: Path | None = None
    style: Literal["author-year", "apa", "ieee", "numeric"] = "author-year"
    auto_bibliography: bool = False
    bibliography_title: str = "References"


@dataclass(slots=True)
class AccessibilityConfig:
    image_alt_required: bool = True
    mark_decorative_images: bool = True


@dataclass(slots=True)
class FigureConfig:
    default_align: Literal["left", "center", "right"] = "center"
    default_width_percent: float = 100.0
    caption_keep_with_figure: bool = True

@dataclass(slots=True)
class RenderConfig:
    theme: str = "default"
    page: PageConfig = field(default_factory=PageConfig)
    resources: ResourcePolicy = field(default_factory=ResourcePolicy)
    metadata: MetadataConfig = field(default_factory=MetadataConfig)
    math_failure: MathFailurePolicy = field(default_factory=MathFailurePolicy)
    header: HeaderConfig = field(default_factory=HeaderConfig)
    footer: FooterConfig = field(default_factory=FooterConfig)
    toc: TOCConfig = field(default_factory=TOCConfig)
    table: TableConfig = field(default_factory=TableConfig)
    lists: ListConfig = field(default_factory=ListConfig)
    fonts: FontConfig = field(default_factory=FontConfig)
    images: ImageConfig = field(default_factory=ImageConfig)
    mermaid: MermaidConfig = field(default_factory=MermaidConfig)
    charts: ChartConfig = field(default_factory=ChartConfig)
    data: DataConfig = field(default_factory=DataConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    limits: CompilationLimits = field(default_factory=CompilationLimits)
    reproducibility: ReproducibilityConfig = field(default_factory=ReproducibilityConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    references: ReferenceConfig = field(default_factory=ReferenceConfig)
    notes: NotesConfig = field(default_factory=NotesConfig)
    citations: CitationConfig = field(default_factory=CitationConfig)
    accessibility: AccessibilityConfig = field(default_factory=AccessibilityConfig)
    figures: FigureConfig = field(default_factory=FigureConfig)
    heading_numbering: HeadingNumberingConfig = field(default_factory=HeadingNumberingConfig)
    title_page: TitlePageConfig = field(default_factory=TitlePageConfig)
    abstract: AbstractConfig = field(default_factory=AbstractConfig)
    code: CodeConfig = field(default_factory=CodeConfig)
    callouts: CalloutConfig = field(default_factory=CalloutConfig)
    native_comments: CommentConfig = field(default_factory=CommentConfig)
    fields: FieldConfig = field(default_factory=FieldConfig)
    base_dir: Path | None = None
    template: Path | None = None
    preserve_template_page_setup: bool = True
    preserve_template_styles: bool = True
    rtl: Literal["off", "auto", "force"] = "auto"
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    comments: str | None = None
    created_at: datetime | None = None
    h1_page_break_before: bool = False
    heading_bookmarks: bool = True
    image_captions_from_title: bool = True
    extensions: tuple[Any, ...] = ()
