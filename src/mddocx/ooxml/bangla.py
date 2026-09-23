"""Apply the preferred Bangla font at the package boundary.

Markdown and the AST remain Unicode. SutonnyMJ requires Bijoy glyph encoding,
so conversion is limited to Bangla text runs in Word XML, never source files.
"""

from copy import deepcopy
from io import BytesIO
import re
from zipfile import ZipFile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
BENGALI = re.compile(r"([\u0980-\u09ff\u200c\u200d]+)")


def apply_bangla_font(blob: bytes, font: str | None) -> bytes:
    if not font:
        return blob
    legacy = font.lower().replace(" ", "") == "sutonnymj"
    converter = None
    if legacy:
        from bijoy2unicode.converter import Unicode

        converter = Unicode()
    output = BytesIO()
    with ZipFile(BytesIO(blob)) as source, ZipFile(output, "w") as destination:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                root = etree.fromstring(data)
                changed = False
                for run in list(root.iter(f"{{{W}}}r")):
                    children = [child for child in run if child.tag != f"{{{W}}}rPr"]
                    if not any(
                        child.tag == f"{{{W}}}t" and BENGALI.search(child.text or "")
                        for child in children
                    ):
                        continue
                    parent = run.getparent()
                    position = parent.index(run)
                    original_pr = run.find(f"{{{W}}}rPr")
                    for child in children:
                        parts = (
                            BENGALI.split(child.text or "") if child.tag == f"{{{W}}}t" else [None]
                        )
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
                            unsafe_legacy = legacy and bangla and part[0] in "িেৈ"
                            original_font = (
                                fonts.get(f"{{{W}}}hAnsi") or fonts.get(f"{{{W}}}ascii") or "Aptos"
                            )
                            if original_font.lower().replace(" ", "") == "sutonnymj":
                                original_font = "Aptos"
                            selected = (
                                ("Nirmala UI" if unsafe_legacy else font)
                                if bangla
                                else original_font
                            )
                            for slot in ("ascii", "hAnsi", "cs", "eastAsia"):
                                fonts.set(f"{{{W}}}{slot}", selected)
                            for slot in ("asciiTheme", "hAnsiTheme", "cstheme", "eastAsiaTheme"):
                                fonts.attrib.pop(f"{{{W}}}{slot}", None)
                            new.append(pr)
                            content = deepcopy(child)
                            if part is not None:
                                # Padding guards the converter lookahead at word endings.
                                # Its soft-hyphen la-phala is absent from SutonnyMJ; use ø.
                                content.text = (
                                    converter.convertUnicodeToBijoy(part + "  ")[:-2].replace(
                                        "\u00ad", "\u00f8"
                                    )
                                    if bangla and legacy and not unsafe_legacy
                                    else part
                                )
                                content.set(
                                    "{http://www.w3.org/XML/1998/namespace}space", "preserve"
                                )
                            new.append(content)
                            parent.insert(position, new)
                            position += 1
                    parent.remove(run)
                    changed = True
                if changed:
                    data = etree.tostring(
                        root, xml_declaration=True, encoding="UTF-8", standalone=True
                    )
            destination.writestr(info, data)
    return output.getvalue()
