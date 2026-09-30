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
    # ASCII cannot carry right-to-left characters, so the common case avoids a
    # per-character bidirectional classification.
    if value.isascii():
        return False
    rtl = 0
    ltr = 0
    for ch in value:
        bidi = unicodedata.bidirectional(ch)
        if bidi in {"R", "AL", "AN"}:
            rtl += 1
        elif bidi == "L":
            ltr += 1
    return rtl > 0 and rtl >= ltr


# Word applies the eastAsia font slot to CJK text, including extension planes
# and the compatibility forms used by Chinese, Japanese and Korean documents.
_CJK_RANGES = (
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x2E80, 0x2EFF),  # CJK radicals
    (0x3000, 0x303F),  # CJK symbols and punctuation
    (0x3040, 0x30FF),  # Hiragana and Katakana
    (0x3100, 0x312F),  # Bopomofo
    (0x3130, 0x318F),  # Hangul compatibility Jamo
    (0x3400, 0x4DBF),  # CJK unified ideographs extension A
    (0x4E00, 0x9FFF),  # CJK unified ideographs
    (0xA960, 0xA97F),  # Hangul Jamo extended-A
    (0xAC00, 0xD7AF),  # Hangul syllables
    (0xD7B0, 0xD7FF),  # Hangul Jamo extended-B
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
    (0xFF66, 0xFF9D),  # Halfwidth Katakana
    (0x20000, 0x2A6DF),  # Extension B
    (0x2A700, 0x2EBEF),  # Extensions C through F
    (0x2F800, 0x2FA1F),  # Compatibility ideographs supplement
    (0x30000, 0x3134F),  # Extension G
)

# Word selects the complex-script font slot (w:cs) and its shaping engine for
# these writing systems. Bengali additionally receives the legacy-font boundary
# pass in mddocx.ooxml.bangla, which overrides the slot for Bengali runs.
_COMPLEX_SCRIPT_RANGES = (
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0x0700, 0x074F),  # Syriac
    (0x0750, 0x077F),  # Arabic Supplement
    (0x0780, 0x07BF),  # Thaana
    (0x07C0, 0x07FF),  # NKo
    (0x0800, 0x083F),  # Samaritan
    (0x0840, 0x085F),  # Mandaic
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0x0900, 0x097F),  # Devanagari
    (0x0980, 0x09FF),  # Bengali
    (0x0A00, 0x0A7F),  # Gurmukhi
    (0x0A80, 0x0AFF),  # Gujarati
    (0x0B00, 0x0B7F),  # Oriya
    (0x0B80, 0x0BFF),  # Tamil
    (0x0C00, 0x0C7F),  # Telugu
    (0x0C80, 0x0CFF),  # Kannada
    (0x0D00, 0x0D7F),  # Malayalam
    (0x0D80, 0x0DFF),  # Sinhala
    (0x0E00, 0x0E7F),  # Thai
    (0x0E80, 0x0EFF),  # Lao
    (0x0F00, 0x0FFF),  # Tibetan
    (0x1000, 0x109F),  # Myanmar
    (0x1200, 0x137F),  # Ethiopic
    (0x1780, 0x17FF),  # Khmer
    (0x1800, 0x18AF),  # Mongolian
    (0xFB1D, 0xFB4F),  # Hebrew presentation forms
    (0xFB50, 0xFDFF),  # Arabic presentation forms-A
    (0xFE70, 0xFEFF),  # Arabic presentation forms-B
    (0x1EE00, 0x1EEFF),  # Arabic mathematical alphabetic symbols
)


def _within(value: str, ranges: tuple[tuple[int, int], ...]) -> bool:
    """Return True when any code point falls inside one of ``ranges``.

    ASCII text dominates ordinary documents, and it exits after a single
    C-level scan. Repeated code points are de-duplicated before the range scan.
    """
    if value.isascii():
        return False
    return any(
        start <= code <= end
        for code in {ord(character) for character in value}
        for start, end in ranges
    )


def has_cjk(value: str) -> bool:
    return _within(value, _CJK_RANGES)


def has_complex_script(value: str) -> bool:
    """Return True when text contains a Word complex-script code point."""
    return _within(value, _COMPLEX_SCRIPT_RANGES)


def set_xml_paragraph_rtl(paragraph_element, enabled: bool = True) -> None:
    """Set bidi paragraph direction on a raw ``w:p`` element."""
    ppr = paragraph_element.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        paragraph_element.insert(0, ppr)
    bidi = ppr.find(qn("w:bidi"))
    if enabled:
        if bidi is None:
            bidi = OxmlElement("w:bidi")
            ppr.append(bidi)
        bidi.set(qn("w:val"), "1")
    elif bidi is not None:
        ppr.remove(bidi)


def set_paragraph_rtl(paragraph, enabled: bool = True) -> None:
    set_xml_paragraph_rtl(paragraph._p, enabled)


def configure_run_properties(
    rpr, text: str, body: str, east_asia: str | None, complex_script: str | None, rtl: bool
) -> None:
    """Set the script-specific font slots and direction on a ``w:rPr`` element."""
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), body)
    rfonts.set(qn("w:hAnsi"), body)
    if east_asia and has_cjk(text):
        rfonts.set(qn("w:eastAsia"), east_asia)
    if complex_script and (rtl or has_complex_script(text)):
        rfonts.set(qn("w:cs"), complex_script)
    if rtl:
        rtl_el = rpr.find(qn("w:rtl"))
        if rtl_el is None:
            rtl_el = OxmlElement("w:rtl")
            rpr.append(rtl_el)
        rtl_el.set(qn("w:val"), "1")


def configure_run_fonts(
    run, text: str, body: str, east_asia: str | None, complex_script: str | None, rtl: bool
) -> None:
    run.font.name = body
    configure_run_properties(run._r.get_or_add_rPr(), text, body, east_asia, complex_script, rtl)


def configure_xml_run(
    run, text: str, body: str, east_asia: str | None, complex_script: str | None, rtl: bool
) -> None:
    """Configure a raw ``w:r`` element, such as a note, header or footer run."""
    rpr = run.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        run.insert(0, rpr)
    configure_run_properties(rpr, text, body, east_asia, complex_script, rtl)
