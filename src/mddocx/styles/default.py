from __future__ import annotations

from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from mddocx.config import RenderConfig
from .themes import get_theme


def _outline(style, level: int) -> None:
    ppr = style.element.get_or_add_pPr()
    existing = ppr.find(qn("w:outlineLvl"))
    if existing is None:
        existing = OxmlElement("w:outlineLvl")
        ppr.append(existing)
    existing.set(qn("w:val"), str(level))


def _set_font(
    style, latin: str, east_asia: str | None = None, complex_script: str | None = None
) -> None:
    style.font.name = latin
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    if east_asia:
        rfonts.set(qn("w:eastAsia"), east_asia)
    if complex_script:
        rfonts.set(qn("w:cs"), complex_script)


def ensure_styles(document, config: RenderConfig) -> None:
    styles = document.styles
    theme = get_theme(config.theme)
    body_font = config.fonts.body or theme.body_font
    heading_font = config.fonts.headings or theme.heading_font
    code_font = config.fonts.code or theme.code_font
    east_asia = config.fonts.east_asia or (
        config.fonts.fallback[0] if config.fonts.fallback else body_font
    )
    complex_script = config.fonts.complex_script or (
        config.fonts.fallback[0] if config.fonts.fallback else body_font
    )
    preserve = bool(config.template and config.preserve_template_styles)

    if "MD Normal" not in styles:
        s = styles.add_style("MD Normal", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["Normal"]
        _set_font(s, body_font, east_asia, complex_script)
        s.font.size = Pt(theme.body_size_pt)
        s.paragraph_format.line_spacing = theme.line_spacing
        s.paragraph_format.space_after = Pt(theme.paragraph_after_pt)
        s.paragraph_format.widow_control = True
    elif not preserve:
        s = styles["MD Normal"]
        _set_font(s, body_font, east_asia, complex_script)
        s.font.size = Pt(theme.body_size_pt)
        s.paragraph_format.line_spacing = theme.line_spacing
        s.paragraph_format.space_after = Pt(theme.paragraph_after_pt)
        s.paragraph_format.widow_control = True

    for level in range(1, 7):
        name = f"MD Heading {level}"
        created = name not in styles
        if created:
            s = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            base_name = f"Heading {level}" if f"Heading {level}" in styles else "MD Normal"
            s.base_style = styles[base_name]
        else:
            s = styles[name]
        if created or not preserve:
            _set_font(s, heading_font, east_asia, complex_script)
            s.font.size = Pt(theme.heading_sizes_pt[level - 1])
            s.font.color.rgb = RGBColor.from_string(theme.heading_color)
            s.paragraph_format.keep_with_next = True
            s.paragraph_format.keep_together = True
            if level == 1:
                s.paragraph_format.page_break_before = config.h1_page_break_before
            _outline(s, level - 1)

    if "MD Quote" not in styles:
        s = styles.add_style("MD Quote", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["Quote"] if "Quote" in styles else styles["MD Normal"]
        _set_font(s, body_font, east_asia, complex_script)
        s.paragraph_format.left_indent = Pt(theme.quote_indent_pt)
        s.paragraph_format.keep_together = True
    elif not preserve:
        s = styles["MD Quote"]
        _set_font(s, body_font, east_asia, complex_script)
        s.paragraph_format.left_indent = Pt(theme.quote_indent_pt)

    if "MD Code" not in styles:
        s = styles.add_style("MD Code", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        _set_font(s, code_font, code_font, code_font)
        s.font.size = Pt(theme.code_size_pt)
        s.paragraph_format.keep_together = True
        s.paragraph_format.space_before = Pt(4)
        s.paragraph_format.space_after = Pt(4)
    elif not preserve:
        s = styles["MD Code"]
        _set_font(s, code_font, code_font, code_font)
        s.font.size = Pt(theme.code_size_pt)

    if "MD Equation" not in styles:
        s = styles.add_style("MD Equation", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        s.paragraph_format.keep_together = True
    if "MD Caption" not in styles:
        s = styles.add_style("MD Caption", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        _set_font(s, body_font, east_asia, complex_script)
        s.font.size = Pt(max(8.5, theme.body_size_pt - 1.0))
        s.font.italic = True
        s.font.color.rgb = RGBColor.from_string("000000")

    if "Footnote Text" not in styles:
        s = styles.add_style("Footnote Text", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        _set_font(s, body_font, east_asia, complex_script)
        s.font.size = Pt(max(8.0, theme.body_size_pt - 2.0))
        s.paragraph_format.space_after = Pt(0)
    if "Footnote Reference" not in styles:
        s = styles.add_style("Footnote Reference", WD_STYLE_TYPE.CHARACTER)
        _set_font(s, body_font, east_asia, complex_script)
        rpr = s.element.get_or_add_rPr()
        va = rpr.find(qn("w:vertAlign"))
        if va is None:
            va = OxmlElement("w:vertAlign")
            rpr.append(va)
        va.set(qn("w:val"), "superscript")

    ensure_professional_styles(document, config)


def _set_paragraph_shading(style, fill: str) -> None:
    ppr = style.element.get_or_add_pPr()
    shd = ppr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        ppr.append(shd)
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)


def ensure_professional_styles(document, config: RenderConfig) -> None:
    styles = document.styles
    theme = get_theme(config.theme)
    body_font = config.fonts.body or theme.body_font
    heading_font = config.fonts.headings or theme.heading_font
    east_asia = config.fonts.east_asia or body_font
    complex_script = config.fonts.complex_script or body_font

    if "MD Title" not in styles:
        s = styles.add_style("MD Title", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        _set_font(s, heading_font, east_asia, complex_script)
        s.font.size = Pt(28)
        s.font.bold = True
        s.font.color.rgb = RGBColor(0, 0, 0)
        s.paragraph_format.space_after = Pt(12)
    if "MD Subtitle" not in styles:
        s = styles.add_style("MD Subtitle", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        _set_font(s, body_font, east_asia, complex_script)
        s.font.size = Pt(16)
        s.font.color.rgb = RGBColor(0, 0, 0)
        s.paragraph_format.space_after = Pt(10)
    if "MD Abstract" not in styles:
        s = styles.add_style("MD Abstract", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        _set_font(s, body_font, east_asia, complex_script)
        s.paragraph_format.left_indent = Pt(18)
        s.paragraph_format.right_indent = Pt(18)
        s.paragraph_format.keep_together = True
    if "MD Code Label" not in styles:
        s = styles.add_style("MD Code Label", WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        _set_font(s, config.fonts.code or theme.code_font, None, None)
        s.font.size = Pt(max(8.0, theme.code_size_pt - 0.5))
        s.font.bold = True
        s.paragraph_format.space_after = Pt(0)
        s.paragraph_format.keep_with_next = True
    callout_fills = {
        "Note": "F2F2F2",
        "Tip": "EEF7EE",
        "Important": "EEF3FA",
        "Warning": "FFF4E5",
        "Caution": "FDECEC",
        "Example": "F5F0FA",
    }
    for kind, fill in callout_fills.items():
        name = f"MD Callout {kind}"
        if name in styles:
            continue
        s = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles["MD Normal"]
        _set_font(s, body_font, east_asia, complex_script)
        s.paragraph_format.left_indent = Pt(12)
        s.paragraph_format.right_indent = Pt(6)
        s.paragraph_format.space_before = Pt(4)
        s.paragraph_format.space_after = Pt(4)
        s.paragraph_format.keep_together = True
        _set_paragraph_shading(s, fill)
