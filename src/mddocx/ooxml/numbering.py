from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from mddocx.config import ListConfig


class NumberingEngine:
    def __init__(self, document, config: ListConfig | None = None, body_font: str = "Aptos"):
        self.document = document
        self.config = config or ListConfig()
        self.body_font = body_font
        self.root = document.part.numbering_part.element
        self._next_abstract = self._max_id("w:abstractNum", "w:abstractNumId") + 1
        self._next_num = self._max_id("w:num", "w:numId") + 1

    def _max_id(self, tag: str, attr: str) -> int:
        vals = []
        for el in self.root.findall(qn(tag)):
            val = el.get(qn(attr))
            if val and val.isdigit():
                vals.append(int(val))
        return max(vals, default=0)

    def create(self, kind: str, start: int = 1) -> int:
        abstract_id = self._next_abstract
        self._next_abstract += 1
        abstract = OxmlElement("w:abstractNum")
        abstract.set(qn("w:abstractNumId"), str(abstract_id))
        multi = OxmlElement("w:multiLevelType")
        multi.set(qn("w:val"), "multilevel")
        abstract.append(multi)

        glyphs = self.config.bullet_glyphs or ("•",)
        for level in range(9):
            lvl = OxmlElement("w:lvl")
            lvl.set(qn("w:ilvl"), str(level))

            start_el = OxmlElement("w:start")
            start_el.set(qn("w:val"), str(start if level == 0 else 1))
            lvl.append(start_el)

            num_fmt = OxmlElement("w:numFmt")
            num_fmt.set(qn("w:val"), "bullet" if kind == "bullet" else "decimal")
            lvl.append(num_fmt)

            lvl_text = OxmlElement("w:lvlText")
            if kind == "bullet":
                lvl_text.set(qn("w:val"), glyphs[level % len(glyphs)])
            else:
                lvl_text.set(qn("w:val"), f"%{level + 1}.")
            lvl.append(lvl_text)

            lvl_jc = OxmlElement("w:lvlJc")
            lvl_jc.set(qn("w:val"), "left")
            lvl.append(lvl_jc)

            suff = OxmlElement("w:suff")
            suff.set(qn("w:val"), "space")
            lvl.append(suff)

            left = max(180, self.config.indent_twips_per_level * (level + 1))
            hanging = max(90, min(self.config.hanging_twips, left))
            tab_pos = left + max(0, self.config.tab_twips_offset)
            ppr = OxmlElement("w:pPr")
            tabs = OxmlElement("w:tabs")
            tab = OxmlElement("w:tab")
            tab.set(qn("w:val"), "num")
            tab.set(qn("w:pos"), str(tab_pos))
            tabs.append(tab)
            ppr.append(tabs)
            ind = OxmlElement("w:ind")
            ind.set(qn("w:left"), str(left))
            ind.set(qn("w:hanging"), str(hanging))
            ppr.append(ind)
            lvl.append(ppr)

            # Explicitly assign a Unicode-capable font to *all* list markers.
            # Word can otherwise inherit the preceding Symbol/Wingdings font and
            # render perfectly valid Unicode bullets or decimal markers as boxes.
            marker_font = (
                self.config.bullet_font
                if kind == "bullet"
                else (self.config.number_font or self.body_font)
            )
            rpr = OxmlElement("w:rPr")
            fonts = OxmlElement("w:rFonts")
            for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                fonts.set(qn(attr), marker_font)
            rpr.append(fonts)
            lvl.append(rpr)
            abstract.append(lvl)

        self.root.append(abstract)
        num_id = self._next_num
        self._next_num += 1
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(num_id))
        abs_id = OxmlElement("w:abstractNumId")
        abs_id.set(qn("w:val"), str(abstract_id))
        num.append(abs_id)
        self.root.append(num)
        return num_id

    def create_heading_scheme(
        self, max_level: int = 3, separator: str = ".", suffix: str = " "
    ) -> int:
        """Create a native multilevel outline numbering definition for headings."""
        abstract_id = self._next_abstract
        self._next_abstract += 1
        abstract = OxmlElement("w:abstractNum")
        abstract.set(qn("w:abstractNumId"), str(abstract_id))
        multi = OxmlElement("w:multiLevelType")
        multi.set(qn("w:val"), "multilevel")
        abstract.append(multi)
        max_level = max(1, min(9, int(max_level)))
        for level in range(9):
            lvl = OxmlElement("w:lvl")
            lvl.set(qn("w:ilvl"), str(level))
            start = OxmlElement("w:start")
            start.set(qn("w:val"), "1")
            lvl.append(start)
            num_fmt = OxmlElement("w:numFmt")
            num_fmt.set(qn("w:val"), "decimal")
            lvl.append(num_fmt)
            lvl_text = OxmlElement("w:lvlText")
            if level < max_level:
                pieces = [f"%{i + 1}" for i in range(level + 1)]
                lvl_text.set(qn("w:val"), separator.join(pieces) + suffix)
            else:
                lvl_text.set(qn("w:val"), "")
            lvl.append(lvl_text)
            suff = OxmlElement("w:suff")
            suff.set(qn("w:val"), "space")
            lvl.append(suff)
            ppr = OxmlElement("w:pPr")
            ind = OxmlElement("w:ind")
            ind.set(qn("w:left"), "0")
            ind.set(qn("w:hanging"), "0")
            ppr.append(ind)
            lvl.append(ppr)
            abstract.append(lvl)
        self.root.append(abstract)
        num_id = self._next_num
        self._next_num += 1
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(num_id))
        abs_id = OxmlElement("w:abstractNumId")
        abs_id.set(qn("w:val"), str(abstract_id))
        num.append(abs_id)
        self.root.append(num)
        return num_id

    @staticmethod
    def apply(paragraph, num_id: int, level: int) -> None:
        ppr = paragraph._p.get_or_add_pPr()
        numpr = ppr.find(qn("w:numPr"))
        if numpr is None:
            numpr = OxmlElement("w:numPr")
            ppr.append(numpr)
        else:
            for child in list(numpr):
                if child.tag in {qn("w:ilvl"), qn("w:numId")}:
                    numpr.remove(child)
        ilvl = OxmlElement("w:ilvl")
        ilvl.set(qn("w:val"), str(min(level, 8)))
        numid = OxmlElement("w:numId")
        numid.set(qn("w:val"), str(num_id))
        numpr.extend([ilvl, numid])
