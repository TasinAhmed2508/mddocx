from __future__ import annotations

import unicodedata

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


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


def is_rtl_text(value: str) -> bool:
    rtl = 0
    ltr = 0
    for ch in value:
        bidi = unicodedata.bidirectional(ch)
        if bidi in {"R", "AL", "AN"}:
            rtl += 1
        elif bidi == "L":
            ltr += 1
    return rtl > 0 and rtl >= ltr


def has_cjk(value: str) -> bool:
    for ch in value:
        code = ord(ch)
        if (
            0x3400 <= code <= 0x4DBF
            or 0x4E00 <= code <= 0x9FFF
            or 0x3040 <= code <= 0x30FF
            or 0xAC00 <= code <= 0xD7AF
        ):
            return True
    return False


def set_paragraph_rtl(paragraph, enabled: bool = True) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    bidi = ppr.find(qn("w:bidi"))
    if enabled:
        if bidi is None:
            bidi = OxmlElement("w:bidi")
            ppr.append(bidi)
        bidi.set(qn("w:val"), "1")
    elif bidi is not None:
        ppr.remove(bidi)


def configure_run_fonts(run, text: str, body: str, east_asia: str | None, complex_script: str | None, rtl: bool) -> None:
    run.font.name = body
    rpr = run._r.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), body)
    rfonts.set(qn("w:hAnsi"), body)
    if east_asia and has_cjk(text):
        rfonts.set(qn("w:eastAsia"), east_asia)
    if complex_script and rtl:
        rfonts.set(qn("w:cs"), complex_script)
        rtl_el = rpr.find(qn("w:rtl"))
        if rtl_el is None:
            rtl_el = OxmlElement("w:rtl")
            rpr.append(rtl_el)
        rtl_el.set(qn("w:val"), "1")
