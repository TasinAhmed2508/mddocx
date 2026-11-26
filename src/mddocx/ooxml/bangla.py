"""Apply the preferred Bangla font at the package boundary.

Markdown and the AST remain Unicode. SutonnyMJ requires Bijoy glyph encoding,
so conversion is limited to Bangla text runs in Word XML, never source files.

Two things are checked before any part is rewritten:

* whether the package contains Bangla text runs, so documents without them skip
  the XML rewrite entirely, and
* whether the configured font is installed, because Bijoy-encoded runs are
  unreadable on a machine that lacks SutonnyMJ. ``fonts.bengali = "auto"`` lets
  the renderer pick an installed Unicode Bangla font instead.
"""

from copy import deepcopy
from io import BytesIO
from functools import lru_cache
import re
from typing import Any, Callable
from zipfile import ZipFile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
BENGALI = re.compile(r"([\u0980-\u09ff]+(?:[\u200c\u200d][\u0980-\u09ff]+)*[\u200c\u200d]?)")
_CONSONANT = r"[ক-হড়ঢ়য়ৎ]\u09bc?"
_CONJUNCT = rf"{_CONSONANT}(?:\u09cd{_CONSONANT})*"
_REPH_MARKER = "\uffff"
_REPH_SOURCE = re.compile(rf"(?<![\u09cd\u200c\u200d])র্({_CONJUNCT})([িেৈোৌ]?)")
_REPH_DECODED = re.compile(rf"({_CONJUNCT})([িেৈ]?){_REPH_MARKER}([াৗ]?)")
_SPLIT_VOWELS = {"ো": ("ে", "া"), "ৌ": ("ে", "ৗ")}
_JOINED_VOWELS = {marks: vowel for vowel, marks in _SPLIT_VOWELS.items()}

#: Font the legacy Bijoy-encoded output pass is written for.
LEGACY_BANGLA_FONT = "SutonnyMJ"

#: Font value that selects the legacy font when installed and a Unicode font otherwise.
AUTO_BANGLA_FONT = "auto"

#: Unicode Bangla fonts tried in order when a legacy font is unavailable.
UNICODE_BANGLA_FONTS: tuple[str, ...] = (
    "Nirmala UI",
    "Noto Sans Bengali",
    "Noto Serif Bengali",
    "Vrinda",
    "Kalpurush",
    "SolaimanLipi",
    "Siyam Rupali",
)

_FONT_SUFFIXES = frozenset({".ttf", ".otf", ".ttc", ".otc"})
_MIN_COMPARABLE_NAME = 4

# Bengali code points are U+0980-U+09FF, which UTF-8 encodes with these leads.
# Skip XML parsing for parts without these bytes.
_BENGALI_UTF8_LEADS = (b"\xe0\xa6", b"\xe0\xa7")

FontReport = Callable[[str], None]


def _normalize_font_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _is_legacy_font(font: str) -> bool:
    return _normalize_font_name(font) == _normalize_font_name(LEGACY_BANGLA_FONT)


@lru_cache(maxsize=1)
def installed_font_stems() -> frozenset[str]:
    """Normalized file names of the fonts installed on this machine.

    Cached for the process; call ``installed_font_stems.cache_clear()`` when the
    font set changes, as tests do.
    """
    from mddocx.interactive.fonts import font_directories

    stems: set[str] = set()
    for directory in font_directories():
        try:
            for path in directory.rglob("*"):
                if path.suffix.lower() in _FONT_SUFFIXES:
                    stems.add(_normalize_font_name(path.stem))
        except OSError:
            continue
    return frozenset(stems)


def is_font_installed(family: str) -> bool:
    """Best-effort check that a font family is installed locally.

    File names carry style suffixes (``SutonnyMJ-Regular``) and drop family
    qualifiers (the ``Nirmala UI`` family ships as ``Nirmala.ttc``), so a prefix
    match in either direction is used. Names too short to identify a family are
    assumed present rather than reported missing.
    """
    target = _normalize_font_name(family)
    if not target:
        return False
    if len(target) < _MIN_COMPARABLE_NAME:
        return True
    for stem in installed_font_stems():
        if len(stem) < _MIN_COMPARABLE_NAME:
            continue
        if stem == target or stem.startswith(target) or target.startswith(stem):
            return True
    return False


def resolve_bangla_font(font: str | None) -> tuple[str | None, str | None]:
    """Return ``(font to apply, warning)`` for the Bangla output pass.

    The configured font is kept when installed. ``auto`` selects the legacy font
    when available and otherwise falls back to an installed Unicode Bangla font,
    skipping Bijoy encoding so the text stays readable. A missing font never
    changes the output silently: the warning explains what to do instead.
    """
    if not font:
        return None, None
    if font.strip().casefold() == AUTO_BANGLA_FONT:
        if is_font_installed(LEGACY_BANGLA_FONT):
            return LEGACY_BANGLA_FONT, None
        for candidate in UNICODE_BANGLA_FONTS:
            if is_font_installed(candidate):
                return candidate, None
        return None, (
            f"{LEGACY_BANGLA_FONT} is not installed and no Unicode Bangla font was found; "
            "keeping Bangla text Unicode without a Bangla font override."
        )
    if is_font_installed(font):
        return font, None
    if _is_legacy_font(font):
        return font, (
            f"{font} is not installed, so the Bijoy-encoded Bangla runs will not display "
            "correctly. Install the font, use '--bengali-font auto' to let mddocx choose an "
            "installed Unicode Bangla font, or use '--bengali-font none' for Unicode output."
        )
    return font, f"{font} is not installed; Word will substitute another font for Bangla runs."


def _contains_bangla_runs(blob: bytes) -> bool:
    with ZipFile(BytesIO(blob)) as source:
        for info in source.infolist():
            if not (info.filename.startswith("word/") and info.filename.endswith(".xml")):
                continue
            data = source.read(info.filename)
            if not any(lead in data for lead in _BENGALI_UTF8_LEADS):
                continue
            root = etree.fromstring(data)
            if any(
                BENGALI.search(text.text or "") for text in root.iterfind(f".//{{{W}}}r/{{{W}}}t")
            ):
                return True
    return False


def _encode_bijoy(text: str, converter: Any) -> str:
    # bijoy2unicode moves reph past subsequent syllables and the lookahead padding.
    # Mark the position after the consonant cluster and before any post-base vowel.
    def place_reph(match: re.Match[str]) -> str:
        pre, post = _SPLIT_VOWELS.get(match[2], (match[2], ""))
        return match[1] + pre + _REPH_MARKER + post

    text = _REPH_SOURCE.sub(place_reph, text)
    # Padding guards the converter's lookahead. SutonnyMJ uses ø for la-phala.
    return (
        converter.convertUnicodeToBijoy(text + "  ")[:-2]
        .replace(_REPH_MARKER, "\u00a9")
        .replace("\u00ad", "\u00f8")
    )


def decode_bijoy(text: str) -> str:
    """Read SutonnyMJ text while retaining reph at the owning syllable."""
    from bijoy2unicode.converter import Unicode

    # Shield reph from the dependency's reorder pass in both directions.
    marked = text.replace("\u00f8", "\u00ad").replace("\u00a9", _REPH_MARKER)
    decoded = Unicode().convertBijoyToUnicode(marked)
    if _REPH_MARKER not in decoded:
        return decoded

    def restore_reph(match: re.Match[str]) -> str:
        vowel = _JOINED_VOWELS.get((match[2], match[3]), match[2] + match[3])
        return "র্" + match[1] + vowel

    return _REPH_DECODED.sub(restore_reph, decoded).replace(_REPH_MARKER, "র্")


def _rewrite_part(data: bytes, font: str, legacy: bool, converter: Any) -> tuple[bytes, bool]:
    root = etree.fromstring(data)
    changed = False
    for run in list(root.iter(f"{{{W}}}r")):
        children = [child for child in run if child.tag != f"{{{W}}}rPr"]
        if not any(
            child.tag == f"{{{W}}}t" and BENGALI.search(child.text or "") for child in children
        ):
            continue
        parent = run.getparent()
        position = parent.index(run)
        original_pr = run.find(f"{{{W}}}rPr")
        for child in children:
            parts = BENGALI.split(child.text or "") if child.tag == f"{{{W}}}t" else [None]
            for part in parts:
                if part == "":
                    continue
                new = etree.Element(f"{{{W}}}r", attrib=dict(run.attrib))
                pr = (
                    deepcopy(original_pr)
                    if original_pr is not None
                    else etree.Element(f"{{{W}}}rPr")
                )
                fonts = pr.find(f"{{{W}}}rFonts")
                if fonts is None:
                    fonts = etree.SubElement(pr, f"{{{W}}}rFonts")
                bangla = part is not None and BENGALI.fullmatch(part) is not None
                # bijoy2unicode loops indefinitely on a leading pre-kar (OCR can
                # leave one after a character from another script).
                unsafe_legacy = legacy and part is not None and bangla and part[0] in "িেৈ"
                if bangla:
                    selected = "Nirmala UI" if unsafe_legacy else font
                    for slot in ("ascii", "hAnsi", "cs", "eastAsia"):
                        fonts.set(f"{{{W}}}{slot}", selected)
                    for slot in ("asciiTheme", "hAnsiTheme", "cstheme", "eastAsiaTheme"):
                        fonts.attrib.pop(f"{{{W}}}{slot}", None)
                else:
                    for slot in ("ascii", "hAnsi"):
                        if _is_legacy_font(fonts.get(f"{{{W}}}{slot}", "")):
                            fonts.set(f"{{{W}}}{slot}", "Aptos")
                new.append(pr)
                content = deepcopy(child)
                if part is not None:
                    content.text = (
                        _encode_bijoy(part, converter)
                        if bangla and legacy and not unsafe_legacy
                        else part
                    )
                    content.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                new.append(content)
                parent.insert(position, new)
                position += 1
        parent.remove(run)
        changed = True
    if not changed:
        return data, False
    return (
        etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True),
        True,
    )


def apply_bangla_font(blob: bytes, font: str | None, *, report: FontReport | None = None) -> bytes:
    """Apply the Bangla font policy to a DOCX package.

    ``report`` receives one human-readable warning when the configured font is
    missing, so the CLI and API surfaces can surface it as a diagnostic.
    """
    if not font:
        return blob
    if not _contains_bangla_runs(blob):
        return blob
    font, warning = resolve_bangla_font(font)
    if warning and report is not None:
        report(warning)
    if not font:
        return blob
    legacy = _is_legacy_font(font)
    converter = None
    if legacy:
        from bijoy2unicode.converter import Unicode

        converter = Unicode()
    output = BytesIO()
    changed_any = False
    with ZipFile(BytesIO(blob)) as source, ZipFile(output, "w") as destination:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                data, changed = _rewrite_part(data, font, legacy, converter)
                changed_any = changed_any or changed
            destination.writestr(info, data)
    return output.getvalue() if changed_any else blob
