from __future__ import annotations

from lxml import etree
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .validation import validate_mathml

NARY_CHARS = {"∑", "∏", "∫", "∬", "∭", "∮"}
GROUP_CHARS = {"⏞", "⏟", "⏜", "⏝", "⎴", "⎵", "↔"}
ENCLOSURE_EDGES = {"top": "hideTop", "bottom": "hideBot", "left": "hideLeft", "right": "hideRight"}
ENCLOSURE_STRIKES = {
    "horizontalstrike": "strikeH",
    "verticalstrike": "strikeV",
    "updiagonalstrike": "strikeBLTR",
    "downdiagonalstrike": "strikeTLBR",
}
ACCENT_CHARS = {
    "^": "\u0302",
    "ˆ": "\u0302",
    "̂": "\u0302",
    "¯": "\u0305",
    "‾": "\u0305",
    "̅": "\u0305",
    "→": "\u20d7",
    "⃗": "\u20d7",
    "~": "\u0303",
    "˜": "\u0303",
    "̃": "\u0303",
    "˙": "\u0307",
    "̇": "\u0307",
    "¨": "\u0308",
    "̈": "\u0308",
}
SCRIPT_VARIANTS = {
    "double-struck": "double-struck",
    "fraktur": "fraktur",
    "script": "script",
    "sans-serif": "sans-serif",
    "monospace": "monospace",
}
STYLE_VARIANTS = {
    "normal": "p",
    "bold": "b",
    "italic": "i",
    "bold-italic": "bi",
    "bold-script": "b",
    "bold-fraktur": "b",
    "sans-serif-bold": "b",
    "sans-serif-italic": "i",
    "sans-serif-bold-italic": "bi",
}


class MathMLToOMML:
    """Convert Presentation MathML to native Word OMML.

    The converter intentionally owns the Word-specific mapping rather than relying on
    a stale third-party MathML→OMML package.  It accepts MathML from both the internal
    parser and common external converters such as latex2mathml.
    """

    def convert(self, mathml: str):
        return self.convert_root(validate_mathml(mathml))

    def convert_root(self, root):
        omath = OxmlElement("m:oMath")
        self._append_children(omath, root)
        return omath

    @staticmethod
    def _local(node) -> str:
        return etree.QName(node).localname

    @staticmethod
    def _text(node) -> str:
        return "".join(node.itertext())

    def _append_children(self, parent, node, inherited_variant: str | None = None) -> None:
        tag = self._local(node)
        variant = node.get("mathvariant") or inherited_variant

        if tag in {"math", "mrow"}:
            children = list(node)
            if not self._append_fenced_row(parent, children, variant):
                self._append_row(parent, children, variant)
            return
        if tag == "semantics":
            for child in node:
                if self._local(child) not in {"annotation", "annotation-xml"}:
                    self._append_children(parent, child, variant)
                    break
            return
        if tag in {"annotation", "annotation-xml"}:
            return
        if tag == "mstyle":
            for child in node:
                self._append_children(parent, child, variant)
            return
        if tag == "mphantom":
            phantom = OxmlElement("m:phant")
            props = OxmlElement("m:phantPr")
            show = OxmlElement("m:show")
            show.set(qn("m:val"), "0")
            props.append(show)
            phantom.extend([props, self._argument("m:e", node, variant, contents=True)])
            parent.append(phantom)
            return
        if tag in {"mi", "mn", "mo", "mtext", "ms"}:
            value = node.text or ""
            # ASCII vertical bar is inconsistently shaped in Word/LibreOffice math fonts.
            # MathML uses it as an operator/delimiter, so normalize it to the Unicode
            # mathematical divides/vertical-line glyph for reliable equation rendering.
            if tag == "mo" and value == "|":
                value = "∣"
            # TeX ``\\text{...}`` and MathML string literals are prose, not
            # mathematical identifiers. Word otherwise applies math italic to
            # them, which visibly breaks AI-generated explanatory boxes.
            token_variant = "normal" if tag in {"mtext", "ms"} and variant is None else variant
            self._run(parent, value, variant=token_variant)
            return
        if tag == "mspace":
            if node.get("width") not in {None, "0em", "0ex", "0px"}:
                self._run(parent, " ", variant="normal")
            return
        if tag == "mfrac":
            if len(node) < 2:
                self._run(parent, "\u200b", variant="normal")
                return
            f = OxmlElement("m:f")
            if node.get("linethickness") in {"0", "0px", "0pt", "0em"}:
                f_pr = OxmlElement("m:fPr")
                fraction_type = OxmlElement("m:type")
                fraction_type.set(qn("m:val"), "noBar")
                f_pr.append(fraction_type)
                f.append(f_pr)
            num = OxmlElement("m:num")
            den = OxmlElement("m:den")
            self._append_children(num, node[0], variant)
            self._append_children(den, node[1], variant)
            f.extend([num, den])
            parent.append(f)
            return
        if tag in {"msqrt", "mroot"}:
            rad = OxmlElement("m:rad")
            rad_pr = OxmlElement("m:radPr")
            deg = OxmlElement("m:deg")
            if tag == "msqrt":
                hide = OxmlElement("m:degHide")
                hide.set(qn("m:val"), "1")
                rad_pr.append(hide)
            elif len(node) >= 2:
                self._append_children(deg, node[1], variant)
            rad.append(rad_pr)
            # CT_Rad requires the degree element even when the degree is hidden.
            rad.append(deg)
            e = OxmlElement("m:e")
            if tag == "msqrt":
                for child in node:
                    self._append_children(e, child, variant)
            elif len(node):
                self._append_children(e, node[0], variant)
            if len(e) == 0:
                self._run(e, "\u200b", variant="normal")
            rad.append(e)
            parent.append(rad)
            return
        if tag in {"msup", "msub", "msubsup"}:
            if self._is_nary_script(node):
                parent.append(self._make_nary(node, inherited_variant=variant))
                return
            if self._is_limit_script(node):
                self._append_limit(parent, node, variant)
                return
            mapped = {"msup": "m:sSup", "msub": "m:sSub", "msubsup": "m:sSubSup"}[tag]
            names = {
                "msup": ["m:e", "m:sup"],
                "msub": ["m:e", "m:sub"],
                "msubsup": ["m:e", "m:sub", "m:sup"],
            }[tag]
            wrap = OxmlElement(mapped)
            for index, name in enumerate(names):
                wrap.append(
                    self._argument(name, node[index] if index < len(node) else None, variant)
                )
            parent.append(wrap)
            return
        if tag == "mmultiscripts" and len(node):
            self._append_multiscripts(parent, node, variant)
            return
        if tag in {"munder", "mover"} and len(node) == 2 and self._local(node[1]) == "mo":
            mark = self._text(node[1])
            if mark == "―" or mark in GROUP_CHARS:
                name = "bar" if mark == "―" else "groupChr"
                wrapper = OxmlElement(f"m:{name}")
                props = OxmlElement(f"m:{name}Pr")
                above = tag == "mover"
                if name == "groupChr":
                    character = OxmlElement("m:chr")
                    character.set(qn("m:val"), mark)
                    props.append(character)
                position = OxmlElement("m:pos")
                position.set(qn("m:val"), "top" if above else "bot")
                props.append(position)
                if name == "groupChr":
                    alignment = OxmlElement("m:vertJc")
                    alignment.set(qn("m:val"), "bot" if above else "top")
                    props.append(alignment)
                wrapper.extend([props, self._argument("m:e", node[0], variant)])
                parent.append(wrapper)
                return
        if tag == "mover" and self._is_accent_mover(node):
            self._append_accent(parent, node, variant)
            return
        if tag in {"munder", "mover", "munderover"}:
            self._append_generic_limits(parent, node, tag, variant)
            return
        if tag == "mfenced":
            self._append_delimiter(
                parent,
                list(node),
                variant,
                node.get("open", "("),
                node.get("close", ")"),
                separators="".join(node.get("separators", ",").split()),
            )
            return
        if tag == "menclose":
            self._append_enclosure(parent, node, variant)
            return
        if tag == "mtable":
            self._append_matrix(parent, node, variant)
            return

        if len(node):
            for child in node:
                self._append_children(parent, child, variant)
        elif node.text:
            self._run(parent, node.text, variant=variant)

    def _append_enclosure(self, parent, node, variant):
        notations = set((node.get("notation") or "box").split())
        unsupported = notations - ({"box"} | ENCLOSURE_EDGES.keys() | ENCLOSURE_STRIKES.keys())
        if unsupported:
            raise ValueError(
                f"Word math enclosure is unsupported: {', '.join(sorted(unsupported))}"
            )
        box = OxmlElement("m:borderBox")
        props = OxmlElement("m:borderBoxPr")
        for direction, name in ENCLOSURE_EDGES.items():
            if "box" not in notations and direction not in notations:
                flag = OxmlElement(f"m:{name}")
                flag.set(qn("m:val"), "1")
                props.append(flag)
        for notation, name in ENCLOSURE_STRIKES.items():
            if notation in notations:
                flag = OxmlElement(f"m:{name}")
                flag.set(qn("m:val"), "1")
                props.append(flag)
        if len(props):
            box.append(props)
        box.append(self._argument("m:e", node, variant, contents=True))
        parent.append(box)

    def _append_fenced_row(self, parent, children, variant):
        if len(children) < 2:
            return False
        first, last = children[0], children[-1]

        def fence(node, mathjax_class, form, plain, matrix):
            return (
                self._local(node) == "mo"
                and node.get("stretchy") != "false"
                and (
                    node.get("data-mjx-texclass") == mathjax_class
                    or (node.get("fence") == "true" and node.get("form") == form)
                    or (matrix and bool(node.text) and node.text in plain)
                )
            )

        left = fence(first, "OPEN", "prefix", "([{⟨|‖", self._local(children[1]) == "mtable")
        right = fence(last, "CLOSE", "postfix", ")]}⟩|‖", self._local(children[-2]) == "mtable")
        interior = children[int(left) : len(children) - int(right)]
        if not interior or not (
            (left and right)
            or ((left or right) and len(interior) == 1 and self._local(interior[0]) == "mtable")
        ):
            return False
        self._append_delimiter(
            parent,
            interior,
            variant,
            (first.text or "") if left else "",
            (last.text or "") if right else "",
        )
        return True

    def _append_delimiter(self, parent, children, variant, opening, closing, *, separators=""):
        delimiter = OxmlElement("m:d")
        props = OxmlElement("m:dPr")
        for name, value in (("begChr", opening), ("endChr", closing), ("grow", "1")):
            prop = OxmlElement("m:" + name)
            prop.set(qn("m:val"), value)
            props.append(prop)
        argument = OxmlElement("m:e")
        if separators:
            for index, child in enumerate(children):
                if index:
                    self._run(argument, separators[min(index - 1, len(separators) - 1)])
                self._append_children(argument, child, variant)
        else:
            self._append_row(argument, children, variant)
        if not len(argument):
            self._run(argument, "\u200b", variant="normal")
        delimiter.extend([props, argument])
        parent.append(delimiter)

    def _argument(self, tag, node, variant, *, contents=False):
        argument = OxmlElement(tag)
        if contents:
            self._append_row(argument, list(node), variant)
        elif node is not None and self._local(node) not in {"none", "mprescripts"}:
            self._append_children(argument, node, variant)
        if not len(argument):
            self._run(argument, "\u200b", variant="normal")
        return argument

    def _append_multiscripts(self, parent, node, variant):
        base = self._argument("m:e", node[0], variant)
        scripts = list(node)[1:]
        boundary = next(
            (i for i, child in enumerate(scripts) if self._local(child) == "mprescripts"),
            len(scripts),
        )
        for sequence, left in ((scripts[:boundary], False), (scripts[boundary + 1 :], True)):
            for offset in range(0, len(sequence), 2):
                sub = self._argument("m:sub", sequence[offset], variant)
                sup = self._argument(
                    "m:sup", sequence[offset + 1] if offset + 1 < len(sequence) else None, variant
                )
                wrapper = OxmlElement("m:sPre" if left else "m:sSubSup")
                wrapper.extend((sub, sup, base) if left else (base, sub, sup))
                base = OxmlElement("m:e")
                base.append(wrapper)
        parent.extend(base)

    def _append_matrix(self, parent, node, variant):
        rows = []
        for row in node:
            tag = self._local(row)
            if tag not in {"mtr", "mlabeledtr"}:
                continue
            cells = [cell for cell in row if self._local(cell) == "mtd"]
            rows.append(cells[1:] + cells[:1] if tag == "mlabeledtr" else cells)
        width = max(map(len, rows), default=0)
        if not width:
            return
        if width > 64:
            # Word limits native matrices to 64 columns (MS-OI29500 §22.1.2.67).
            raise ValueError("Word supports up to 64 columns in a native equation matrix.")
        matrix = OxmlElement("m:m")
        alignments = node.get("columnalign", "").split()
        if not alignments:
            alignments = [cell.get("columnalign", "center") for cell in rows[0]]
        if any(alignment in {"left", "right"} for alignment in alignments):
            properties = OxmlElement("m:mPr")
            columns = OxmlElement("m:mcs")
            for index in range(width):
                alignment = alignments[min(index, len(alignments) - 1)]
                column = OxmlElement("m:mc")
                column_properties = OxmlElement("m:mcPr")
                justification = OxmlElement("m:mcJc")
                justification.set(
                    qn("m:val"), alignment if alignment in {"left", "right"} else "center"
                )
                column_properties.append(justification)
                column.append(column_properties)
                columns.append(column)
            properties.append(columns)
            matrix.append(properties)
        for row in rows:
            mr = OxmlElement("m:mr")
            for index in range(width):
                mr.append(self._argument("m:e", row[index] if index < len(row) else None, variant))
            matrix.append(mr)
        parent.append(matrix)

    def _append_row(self, parent, children: list, variant: str | None) -> None:
        i = 0
        while i < len(children):
            child = children[i]
            tag = self._local(child)
            if (
                tag in {"msubsup", "msub", "msup"}
                and len(child) >= 2
                and self._local(child[0]) == "mrow"
                and not len(child[0])
                and i + 1 < len(children)
                and self._is_reasonable_operand(children[i + 1])
            ):
                sub = child[1] if tag != "msup" else None
                sup = child[-1] if tag != "msub" else None
                pre = OxmlElement("m:sPre")
                pre.extend(
                    [
                        self._argument("m:sub", sub, variant),
                        self._argument("m:sup", sup, variant),
                        self._argument("m:e", children[i + 1], variant),
                    ]
                )
                parent.append(pre)
                i += 2
                continue
            if self._is_nary_node(child):
                # Consecutive integral/sum/product nodes need to nest around a real operand.
                # Treating only the next operator as the operand creates an empty inner m:e,
                # which Word exposes as a dotted square placeholder.
                chain = [child]
                j = i + 1
                while j < len(children) and self._is_ignorable_space(children[j]):
                    j += 1
                while j < len(children) and self._is_nary_node(children[j]):
                    chain.append(children[j])
                    j += 1
                    while j < len(children) and self._is_ignorable_space(children[j]):
                        j += 1

                operand = None
                consume_operand = False
                if j < len(children) and self._is_reasonable_operand(children[j]):
                    operand = children[j]
                    consume_operand = True

                built = self._make_nary(chain[-1], operand=operand, inherited_variant=variant)
                for nary_node in reversed(chain[:-1]):
                    built = self._make_nary(
                        nary_node, operand_omml=built, inherited_variant=variant
                    )
                parent.append(built)
                i = j + (1 if consume_operand else 0)
                continue
            self._append_children(parent, child, variant)
            i += 1

    def _run(self, parent, value: str, variant: str | None = None) -> None:
        run = OxmlElement("m:r")
        if variant:
            rpr = OxmlElement("m:rPr")
            base_variant = variant
            style = STYLE_VARIANTS.get(base_variant)
            script = SCRIPT_VARIANTS.get(base_variant)
            if base_variant.startswith("bold-") and script is None:
                script = SCRIPT_VARIANTS.get(base_variant.removeprefix("bold-"))
            if style:
                sty = OxmlElement("m:sty")
                sty.set(qn("m:val"), style)
                rpr.append(sty)
            if script:
                scr = OxmlElement("m:scr")
                scr.set(qn("m:val"), script)
                rpr.append(scr)
            if len(rpr):
                run.append(rpr)
        text = OxmlElement("m:t")
        text.set(qn("xml:space"), "preserve")
        text.text = value
        run.append(text)
        parent.append(run)

    def _is_nary_node(self, node) -> bool:
        tag = self._local(node)
        if tag == "mo":
            return self._text(node) in NARY_CHARS
        if tag in {"msup", "msub", "msubsup"}:
            return self._is_nary_script(node)
        if tag in {"munder", "mover", "munderover"} and len(node):
            return self._local(node[0]) == "mo" and self._text(node[0]) in NARY_CHARS
        return False

    def _is_nary_script(self, node) -> bool:
        return len(node) >= 2 and self._local(node[0]) == "mo" and self._text(node[0]) in NARY_CHARS

    def _is_ignorable_space(self, node) -> bool:
        return self._local(node) == "mspace" and (node.get("width") in {None, "0em", "0ex", "0px"})

    def _is_reasonable_operand(self, node) -> bool:
        if self._local(node) == "mo" and self._text(node) in {"=", ",", ";", ".", ":"}:
            return False
        return True

    def _make_nary(
        self, node, operand=None, operand_omml=None, inherited_variant: str | None = None
    ):
        tag = self._local(node)
        base = node
        sub_node = sup_node = None
        if tag in {"msub", "msup", "msubsup"}:
            base = node[0]
            if tag == "msub":
                sub_node = node[1]
            elif tag == "msup":
                sup_node = node[1]
            else:
                sub_node, sup_node = node[1], node[2]
        elif tag in {"munder", "mover", "munderover"}:
            base = node[0]
            if tag == "munder":
                sub_node = node[1]
            elif tag == "mover":
                sup_node = node[1]
            else:
                sub_node, sup_node = node[1], node[2]

        nary = OxmlElement("m:nary")
        pr = OxmlElement("m:naryPr")
        chr_el = OxmlElement("m:chr")
        chr_el.set(qn("m:val"), self._text(base))
        pr.append(chr_el)
        lim = OxmlElement("m:limLoc")
        lim.set(qn("m:val"), "undOvr")
        pr.append(lim)
        if sub_node is None:
            hide = OxmlElement("m:subHide")
            hide.set(qn("m:val"), "1")
            pr.append(hide)
        if sup_node is None:
            hide = OxmlElement("m:supHide")
            hide.set(qn("m:val"), "1")
            pr.append(hide)
        nary.append(pr)

        sub = OxmlElement("m:sub")
        sup = OxmlElement("m:sup")
        if sub_node is not None:
            self._append_children(sub, sub_node, inherited_variant)
        if sup_node is not None:
            self._append_children(sup, sup_node, inherited_variant)
        nary.extend([sub, sup])

        e = OxmlElement("m:e")
        if operand_omml is not None:
            e.append(operand_omml)
        elif operand is not None:
            self._append_children(e, operand, inherited_variant)
        if len(e) == 0:
            # A syntactically empty n-ary body is rendered by Word as a visible
            # placeholder square. A zero-width body preserves native n-ary structure
            # without leaking an editor placeholder into the final document.
            self._run(e, "\u200b", variant="normal")
        nary.append(e)
        return nary

    def _is_limit_script(self, node) -> bool:
        return (
            len(node) >= 2
            and self._local(node[0]) in {"mi", "mtext"}
            and self._text(node[0]) == "lim"
        )

    def _append_limit(self, parent, node, variant: str | None = None) -> None:
        tag = self._local(node)
        if tag == "msub":
            wrap = OxmlElement("m:limLow")
            e = OxmlElement("m:e")
            self._append_children(e, node[0], variant)
            wrap.append(e)
            lim = OxmlElement("m:lim")
            self._append_children(lim, node[1], variant)
            wrap.append(lim)
            parent.append(wrap)
            return
        if tag == "msup":
            wrap = OxmlElement("m:limUpp")
            e = OxmlElement("m:e")
            self._append_children(e, node[0], variant)
            wrap.append(e)
            lim = OxmlElement("m:lim")
            self._append_children(lim, node[1], variant)
            wrap.append(lim)
            parent.append(wrap)
            return
        upper = OxmlElement("m:limUpp")
        lower = OxmlElement("m:limLow")
        e = OxmlElement("m:e")
        self._append_children(e, node[0], variant)
        lower.append(e)
        low = OxmlElement("m:lim")
        self._append_children(low, node[1], variant)
        lower.append(low)
        upper_e = OxmlElement("m:e")
        upper_e.append(lower)
        upper.append(upper_e)
        high = OxmlElement("m:lim")
        self._append_children(high, node[2], variant)
        upper.append(high)
        parent.append(upper)

    def _is_accent_mover(self, node) -> bool:
        if len(node) < 2 or self._local(node) != "mover":
            return False
        mark = self._text(node[1]).strip()
        explicit = str(node.get("accent", "")).lower() in {"true", "1"}
        child_explicit = str(node[1].get("accent", "")).lower() in {"true", "1"}
        return explicit or child_explicit or mark in ACCENT_CHARS

    def _append_accent(self, parent, node, variant: str | None = None) -> None:
        acc = OxmlElement("m:acc")
        pr = OxmlElement("m:accPr")
        mark = self._text(node[1]).strip() or "^"
        chr_el = OxmlElement("m:chr")
        chr_el.set(qn("m:val"), ACCENT_CHARS.get(mark, mark))
        pr.append(chr_el)
        acc.append(pr)
        e = OxmlElement("m:e")
        self._append_children(e, node[0], variant)
        if len(e) == 0:
            self._run(e, "\u200b", variant="normal")
        acc.append(e)
        parent.append(acc)

    def _append_generic_limits(self, parent, node, tag: str, variant: str | None = None) -> None:
        if tag == "munder":
            wrap = OxmlElement("m:limLow")
            e = OxmlElement("m:e")
            self._append_children(e, node[0], variant)
            wrap.append(e)
            lim = OxmlElement("m:lim")
            self._append_children(lim, node[1], variant)
            wrap.append(lim)
            parent.append(wrap)
            return
        if tag == "mover":
            wrap = OxmlElement("m:limUpp")
            e = OxmlElement("m:e")
            self._append_children(e, node[0], variant)
            wrap.append(e)
            lim = OxmlElement("m:lim")
            self._append_children(lim, node[1], variant)
            wrap.append(lim)
            parent.append(wrap)
            return
        upper = OxmlElement("m:limUpp")
        lower = OxmlElement("m:limLow")
        e = OxmlElement("m:e")
        self._append_children(e, node[0], variant)
        lower.append(e)
        low = OxmlElement("m:lim")
        self._append_children(low, node[1], variant)
        lower.append(low)
        ue = OxmlElement("m:e")
        ue.append(lower)
        upper.append(ue)
        high = OxmlElement("m:lim")
        self._append_children(high, node[2], variant)
        upper.append(high)
        parent.append(upper)
