"""Word XML text handling: sanitation, run font slots, and paragraph direction.

Script classification is owned by :mod:`mddocx.scripts`, and the fonts for each
slot are resolved by :mod:`mddocx.styles.fonts`. This module only knows how to
write those decisions into WordprocessingML.
"""

from __future__ import annotations

from docx.oxml.ns import qn

from mddocx.ooxml.sequence import get_or_add
from mddocx.scripts import has_cjk, has_complex_script

_XML_ALLOWED_CONTROLS = {"\t", "\n", "\r"}


def clean_xml_text(value: str) -> str:
    """Remove XML 1.0-invalid code points while preserving valid Unicode text."""
    out: list[str] = []
    for ch in value:
        code = ord(ch)
        if (
            ch in _XML_ALLOWED_CONTROLS
            or 0x20 <= code <= 0xD7FF
            or 0xE000 <= code <= 0xFFFD
            or 0x10000 <= code <= 0x10FFFF
        ):
            out.append(ch)
    return "".join(out)


def configure_xml_run(
    run,
    text: str,
    body: str,
    east_asia: str | None,
    complex_script: str | None,
    rtl: bool = False,
) -> None:
    """Write script-specific font slots and direction onto a raw ``w:r`` element.

    Accepts any run element, whether it belongs to a python-docx document, a
    header, or a note part, so every text surface is configured the same way.
    """
    rpr = get_or_add(run, "w:rPr")
    rfonts = get_or_add(rpr, "w:rFonts")
    rfonts.set(qn("w:ascii"), body)
    rfonts.set(qn("w:hAnsi"), body)
    if east_asia and has_cjk(text):
        rfonts.set(qn("w:eastAsia"), east_asia)
    if complex_script and (rtl or has_complex_script(text)):
        rfonts.set(qn("w:cs"), complex_script)
    if rtl:
        get_or_add(rpr, "w:rtl").set(qn("w:val"), "1")


def set_xml_paragraph_rtl(paragraph_element, enabled: bool = True) -> None:
    """Set or clear bidi paragraph direction on a raw ``w:p`` element."""
    ppr = get_or_add(paragraph_element, "w:pPr")
    bidi = ppr.find(qn("w:bidi"))
    if enabled:
        get_or_add(ppr, "w:bidi").set(qn("w:val"), "1")
    elif bidi is not None:
        ppr.remove(bidi)
