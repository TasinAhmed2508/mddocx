"""Native footnote and endnote parts with their own image and link relationships."""

from __future__ import annotations

from dataclasses import dataclass

from docx.opc.packuri import PackURI
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.parts.story import StoryPart
from docx.text.paragraph import Paragraph


@dataclass(frozen=True, slots=True)
class NoteSpec:
    kind: str
    style_id: str

    @property
    def relationship_type(self) -> str:
        return f"http://schemas.openxmlformats.org/officeDocument/2006/relationships/{self.kind}s"


FOOTNOTE = NoteSpec("footnote", "FootnoteText")
ENDNOTE = NoteSpec("endnote", "EndnoteText")


def open_note_part(document_part, spec: NoteSpec) -> StoryPart:
    """Attach a writable note part, retaining existing note IDs and relationships."""
    edge = next(
        (rel for rel in document_part.rels.values() if rel.reltype == spec.relationship_type),
        None,
    )
    package = document_part.package
    if edge is not None:
        old = edge.target_part
        part = StoryPart.load(old.partname, old.content_type, old.blob, package)
        for rel in old.rels.values():
            target = rel.target_ref if rel.is_external else rel.target_part
            part.load_rel(rel.reltype, target, rel.rId, rel.is_external)
        document_part.load_rel(edge.reltype, part, edge.rId)
        return part

    root = OxmlElement(f"w:{spec.kind}s")
    root.extend(
        [
            _separator(spec, -1, "separator"),
            _separator(spec, 0, "continuationSeparator"),
        ]
    )
    part = StoryPart(
        PackURI(f"/word/{spec.kind}s.xml"),
        f"application/vnd.openxmlformats-officedocument.wordprocessingml.{spec.kind}s+xml",
        root,
        package,
    )
    document_part.relate_to(part, spec.relationship_type)
    return part


def next_note_id(part: StoryPart, spec: NoteSpec) -> int:
    maximum = 0
    for note in part.element.iterchildren(qn(f"w:{spec.kind}")):
        try:
            maximum = max(maximum, int(note.get(qn("w:id"), "")))
        except ValueError:
            continue
    return maximum + 1


def append_note_reference(paragraph, note_id: int, spec: NoteSpec) -> None:
    ref = OxmlElement(f"w:{spec.kind}Reference")
    ref.set(qn("w:id"), str(note_id))
    paragraph._p.append(_reference_run(ref))


def append_note(part: StoryPart, note_id: int, spec: NoteSpec) -> Paragraph:
    note = OxmlElement(f"w:{spec.kind}")
    note.set(qn("w:id"), str(note_id))
    part.element.append(note)
    paragraph = Paragraph(OxmlElement("w:p"), part)
    paragraph._p.style = spec.style_id
    paragraph._p.append(_reference_run(OxmlElement(f"w:{spec.kind}Ref")))
    note.append(paragraph._p)
    return paragraph


def _reference_run(ref):
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "FootnoteReference")
    properties.append(style)
    run.extend([properties, ref])
    return run


def _separator(spec: NoteSpec, note_id: int, kind: str):
    note = OxmlElement(f"w:{spec.kind}")
    note.set(qn("w:type"), kind)
    note.set(qn("w:id"), str(note_id))
    paragraph = OxmlElement("w:p")
    run = OxmlElement("w:r")
    run.append(OxmlElement(f"w:{kind}"))
    paragraph.append(run)
    note.append(paragraph)
    return note
