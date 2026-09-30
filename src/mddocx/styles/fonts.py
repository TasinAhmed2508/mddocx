"""Effective font slots resolved from configuration and the active theme.

The rule "explicit configuration, then the configured fallback list, then the
theme's own font" is defined once here and consumed by both the Word style
builder and the renderer, so a document's styles and its runs cannot disagree
about which font a script uses.
"""

from __future__ import annotations

from dataclasses import dataclass

from mddocx.config import RenderConfig

from .themes import ThemeSpec


@dataclass(frozen=True, slots=True)
class FontSlots:
    """Fonts for one document, one value per Word font slot."""

    body: str
    headings: str
    code: str
    east_asia: str | None
    complex_script: str | None
    bengali: str | None
    # Explicit `fonts.complex_script` only: the renderer uses it as the body
    # font for right-to-left runs, while the slot above may be a fallback.
    rtl_body: str | None

    @classmethod
    def resolve(cls, config: RenderConfig, theme: ThemeSpec) -> "FontSlots":
        fonts = config.fonts
        body = fonts.body or theme.body_font
        fallback = fonts.fallback[0] if fonts.fallback else None
        return cls(
            body=body,
            headings=fonts.headings or theme.heading_font,
            code=fonts.code or theme.code_font,
            east_asia=fonts.east_asia or fallback or body,
            complex_script=fonts.complex_script or fallback or body,
            bengali=fonts.bengali,
            rtl_body=fonts.complex_script,
        )

    def for_text(self, *, rtl: bool = False, code: bool = False) -> str:
        """Return the body font for one run of text."""
        if code:
            return self.code
        if rtl and self.rtl_body:
            return self.rtl_body
        return self.body
