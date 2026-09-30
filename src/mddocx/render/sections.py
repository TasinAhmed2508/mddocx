"""Section surface: page geometry, margins, and orientation.

Sections are the only place page setup is decided, so landscape tables and
``<!-- sectionbreak -->`` directives both route through here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.section import WD_ORIENT
from docx.shared import Mm

from . import headers_footers

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def configure_section(
    renderer: DocxRenderer,
    sec,
    orientation: str | None = None,
    preserve_page: bool = False,
) -> None:
    target_orientation = orientation or renderer.config.page.orientation
    if not preserve_page:
        if renderer.config.page.size == "A4":
            width, height = Mm(210), Mm(297)
        else:
            width, height = Mm(215.9), Mm(279.4)
        sec.page_width, sec.page_height = width, height
        if target_orientation == "landscape":
            sec.orientation = WD_ORIENT.LANDSCAPE
            sec.page_width, sec.page_height = height, width
        else:
            sec.orientation = WD_ORIENT.PORTRAIT
            sec.page_width, sec.page_height = width, height
        m = renderer.config.page.margins
        sec.top_margin, sec.bottom_margin = Mm(m.top), Mm(m.bottom)
        sec.left_margin, sec.right_margin = Mm(m.left), Mm(m.right)
    elif orientation is not None:
        current_landscape = sec.page_width > sec.page_height
        want_landscape = orientation == "landscape"
        if current_landscape != want_landscape:
            sec.page_width, sec.page_height = sec.page_height, sec.page_width
        sec.orientation = WD_ORIENT.LANDSCAPE if want_landscape else WD_ORIENT.PORTRAIT
    headers_footers.configure_header_footer(renderer, sec)
