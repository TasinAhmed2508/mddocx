from __future__ import annotations

from .config import RenderConfig
from .diagnostics import Diagnostic, MddocxError


def validate_render_config(config: RenderConfig) -> RenderConfig:
    """Validate cross-field invariants at the compiler boundary."""

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "CONFIG401",
                    message,
                    remediation="Correct the invalid configuration value before compiling.",
                )
            )

    require(config.page.size in {"A4", "Letter"}, "Page size must be A4 or Letter.")
    require(
        config.page.orientation in {"portrait", "landscape"},
        "Page orientation must be portrait or landscape.",
    )
    require(config.rtl in {"off", "auto", "force"}, "RTL mode must be off, auto, or force.")
    require(
        config.math_failure.mode in {"error", "plain_text", "warning"},
        "Math failure mode must be error, plain_text, or warning.",
    )
    require(
        config.notes.style in {"footnote", "endnote"},
        "Notes style must be footnote or endnote.",
    )
    require(
        config.style_map.missing in {"error", "warning"},
        "Missing mapped-style policy must be error or warning.",
    )
    require(
        config.references.figure_caption_position in {"above", "below"}
        and config.references.table_caption_position in {"above", "below"}
        and config.references.listing_caption_position in {"above", "below"},
        "Caption positions must be above or below.",
    )
    page_width = 210.0 if config.page.size == "A4" else 215.9
    page_height = 297.0 if config.page.size == "A4" else 279.4
    margins = config.page.margins
    require(
        all(value >= 0 for value in (margins.top, margins.bottom, margins.left, margins.right)),
        "Page margins must be non-negative.",
    )
    require(
        margins.left + margins.right < page_width,
        "Left and right margins must leave a positive page content width.",
    )
    require(
        margins.top + margins.bottom < page_height,
        "Top and bottom margins must leave a positive page content height.",
    )
    require(config.table.min_column_width_mm > 0, "Minimum table column width must be positive.")
    require(
        config.table.max_column_width_mm >= config.table.min_column_width_mm,
        "Maximum table column width must be greater than or equal to the minimum.",
    )
    require(config.table.landscape_min_columns >= 1, "Landscape column threshold must be positive.")
    require(config.table.landscape_width_ratio > 0, "Landscape width ratio must be positive.")
    require(config.figures.default_width_percent > 0, "Default figure width must be positive.")
    require(config.images.max_width_percent > 0, "Maximum image width must be positive.")
    require(
        config.charts.default_width_mm > 0 and config.charts.default_height_mm > 0,
        "Default chart dimensions must be positive.",
    )
    require(
        config.charts.max_series > 0 and config.charts.max_points > 0,
        "Chart series and point limits must be positive.",
    )
    require(
        config.data.max_rows > 0 and config.data.max_columns > 0,
        "Data row and column limits must be positive.",
    )
    limits = config.limits
    require(
        all(
            value > 0
            for value in (
                limits.max_input_bytes,
                limits.max_ast_nodes,
                limits.max_nesting_depth,
                limits.max_table_cells,
                limits.max_images,
                limits.max_equations,
            )
        ),
        "Compilation limits must all be positive.",
    )
    require(config.resources.max_resource_size > 0, "Maximum resource size must be positive.")
    require(config.resources.timeout_seconds > 0, "Resource timeout must be positive.")
    require(config.resources.max_redirects >= 0, "Maximum redirects cannot be negative.")
    require(
        all(scheme in {"http", "https"} for scheme in config.resources.allowed_schemes),
        "Remote resource schemes are limited to HTTP and HTTPS.",
    )
    require(
        all(
            isinstance(canonical, str)
            and bool(canonical.strip())
            and isinstance(target, str)
            and bool(target.strip())
            for canonical, target in config.style_map.mapping.items()
        ),
        "Style-map names must be non-empty strings.",
    )
    return config
