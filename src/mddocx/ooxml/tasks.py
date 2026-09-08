from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def append_checkbox(
    paragraph, checked: bool, control_id: int, font: str = "Segoe UI Symbol"
) -> None:
    """Append a native Word checkbox content control (SDT) to *paragraph*.

    Word 2010+ represents checkbox controls with ``w14:checkbox``.  The visible
    Unicode character is also included in ``w:sdtContent`` so other OOXML hosts
    have a deterministic fallback instead of a missing-glyph box.
    """
    sdt = OxmlElement("w:sdt")
    props = OxmlElement("w:sdtPr")

    sid = OxmlElement("w:id")
    sid.set(qn("w:val"), str(control_id))
    props.append(sid)

    alias = OxmlElement("w:alias")
    alias.set(qn("w:val"), "Task checkbox")
    props.append(alias)

    tag = OxmlElement("w:tag")
    tag.set(qn("w:val"), "mddocx.task")
    props.append(tag)

    checkbox = OxmlElement("w14:checkbox")
    checked_el = OxmlElement("w14:checked")
    checked_el.set(qn("w14:val"), "1" if checked else "0")
    checkbox.append(checked_el)

    checked_state = OxmlElement("w14:checkedState")
    checked_state.set(qn("w14:val"), "2612")  # ☒
    checked_state.set(qn("w14:font"), font)
    checkbox.append(checked_state)

    unchecked_state = OxmlElement("w14:uncheckedState")
    unchecked_state.set(qn("w14:val"), "2610")  # ☐
    unchecked_state.set(qn("w14:font"), font)
    checkbox.append(unchecked_state)
    props.append(checkbox)
    sdt.append(props)

    content = OxmlElement("w:sdtContent")
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(attr), font)
    rpr.append(fonts)
    run.append(rpr)
    text = OxmlElement("w:t")
    text.text = "☒" if checked else "☐"
    run.append(text)
    content.append(run)
    sdt.append(content)
    paragraph._p.append(sdt)


def set_task_indent(paragraph, level: int, indent_twips_per_level: int, hanging_twips: int) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    ind = ppr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        ppr.append(ind)
    # Put the checkbox at approximately the same marker position as a native list
    # marker while keeping the task text aligned with neighbouring list content.
    left = max(180, indent_twips_per_level * (level + 1) - hanging_twips)
    ind.set(qn("w:left"), str(left))
