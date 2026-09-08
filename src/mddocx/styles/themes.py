from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemeSpec:
    body_font: str
    heading_font: str
    code_font: str
    body_size_pt: float
    line_spacing: float
    heading_sizes_pt: tuple[float, float, float, float, float, float]
    paragraph_after_pt: float
    quote_indent_pt: float
    code_size_pt: float
    table_header_fill: str
    heading_color: str = "000000"


THEMES: dict[str, ThemeSpec] = {
    "default": ThemeSpec(
        body_font="Aptos",
        heading_font="Aptos Display",
        code_font="Consolas",
        body_size_pt=11,
        line_spacing=1.15,
        heading_sizes_pt=(20, 16, 14, 12, 11, 10),
        paragraph_after_pt=6,
        quote_indent_pt=18,
        code_size_pt=9,
        table_header_fill="EDEDED",
    ),
    "academic": ThemeSpec(
        body_font="Times New Roman",
        heading_font="Times New Roman",
        code_font="Consolas",
        body_size_pt=11.5,
        line_spacing=1.15,
        heading_sizes_pt=(18, 15, 13, 12, 11, 10),
        paragraph_after_pt=5,
        quote_indent_pt=20,
        code_size_pt=9,
        table_header_fill="E8E8E8",
    ),
    "modern": ThemeSpec(
        body_font="Aptos",
        heading_font="Aptos Display",
        code_font="Cascadia Mono",
        body_size_pt=10.5,
        line_spacing=1.12,
        heading_sizes_pt=(22, 17, 14, 12, 11, 10),
        paragraph_after_pt=7,
        quote_indent_pt=16,
        code_size_pt=9,
        table_header_fill="EAF0F6",
    ),
    "minimal": ThemeSpec(
        body_font="Arial",
        heading_font="Arial",
        code_font="Courier New",
        body_size_pt=10.5,
        line_spacing=1.1,
        heading_sizes_pt=(19, 15, 13, 11.5, 10.5, 10),
        paragraph_after_pt=4,
        quote_indent_pt=15,
        code_size_pt=8.5,
        table_header_fill="F4F4F4",
    ),
}


def get_theme(name: str) -> ThemeSpec:
    try:
        return THEMES[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown theme {name!r}. Available themes: {', '.join(sorted(THEMES))}"
        ) from exc
