from __future__ import annotations

from collections import Counter
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZipFile

from docx import Document
from lxml import etree
import pytest

from mddocx import MarkdownWord, RenderConfig
from mddocx.inspection import NS, inspect_docx_bytes
from mddocx.ooxml.package import read_parts, write_parts

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "golden" / "structure.json"
CASES = ("report", "multilingual", "table", "mermaid", "math", "lists", "template")
STRUCTURES = {
    "paragraphs": ".//w:p",
    "tables": ".//w:tbl",
    "rows": ".//w:tr",
    "cells": ".//w:tc",
    "equations": ".//m:oMath",
    "list_items": ".//w:p[w:pPr/w:numPr]",
    "images": ".//w:drawing",
    "links": ".//w:hyperlink",
    "bookmarks": ".//w:bookmarkStart",
    "header_rows": ".//w:tblHeader",
    "landscape_sections": ".//w:pgSz[@w:orient='landscape']",
}


def render_case(name: str, directory: Path) -> bytes:
    config = RenderConfig()
    config.fonts.bengali = None
    base = FIXTURES
    match name:
        case "report" | "multilingual" | "math":
            source = (
                FIXTURES
                / {
                    "report": "technical_report/report.md",
                    "multilingual": "multilingual/polyglot.md",
                    "math": "ai_markdown/chatgpt_sphere_equations.md",
                }[name]
            )
            markdown = source.read_text(encoding="utf-8")
            base = source.parent
        case "table":
            rows = [
                ["Column " + str(i) for i in range(12)],
                ["---"] * 12,
                *[[f"Data {row}-{col}" for col in range(12)] for row in range(45)],
            ]
            markdown = "# Wide table\n\n" + "\n".join("|" + "|".join(row) + "|" for row in rows)
        case "mermaid":
            edges = [f"N{i}[Step {i}] -->|branch {i}| N{i + 1}[Step {i + 1}]" for i in range(15)]
            fence = chr(96) * 3
            markdown = (
                f"# Flowchart\n\n{fence}mermaid\nflowchart TD\n" + "\n".join(edges) + f"\n{fence}"
            )
        case "lists":
            markdown = "# Lists\n\n4. First\n   - Inner\n5. Next\n\nParagraph.\n\n8. Restarted"
        case "template":
            template = Document()
            template.sections[0].header.paragraphs[0].text = "Template header"
            template.sections[0].footer.paragraphs[0].text = "Template footer"
            config.template = directory / "template.docx"
            template.save(str(config.template))
            markdown = "# Template report\n\nBody."
        case _:
            raise ValueError(name)
    return MarkdownWord(config).render_string(markdown, base_dir=base)


def snapshot(blob: bytes) -> dict[str, object]:
    result: dict[str, object] = {}
    with ZipFile(BytesIO(blob)) as archive:
        for name in sorted(archive.namelist()):
            is_content = name == "word/document.xml" or re.fullmatch(
                r"word/(?:header\d+|footer\d+|footnotes|endnotes)\.xml", name
            )
            if is_content:
                root = etree.fromstring(archive.read(name))
                counts = {
                    construct: len(root.xpath(query, namespaces=NS))
                    for construct, query in STRUCTURES.items()
                }
                instructions = [
                    item.text or "" for item in root.xpath(".//w:instrText", namespaces=NS)
                ]
                # Math engine-specific token grouping and run boundaries vary by host.
                result[name] = {
                    "counts": {key: count for key, count in counts.items() if count},
                    "text": [
                        text
                        for p in root.xpath(".//w:p", namespaces=NS)
                        if (text := "".join(p.xpath(".//w:t/text()", namespaces=NS)).strip())
                    ],
                    "fields": [" ".join(item.split()) for item in instructions],
                }
            if name.endswith(".rels") and name.startswith("word/"):
                root = etree.fromstring(archive.read(name))
                result[name] = dict(Counter(child.get("Type", "").split("/")[-1] for child in root))
            if name.startswith(("word/charts/", "word/embeddings/")) and "/_rels/" not in name:
                result[name] = "present"
    return result


@pytest.mark.parametrize("name", CASES)
def test_structural_golden(name, tmp_path):
    from mddocx.ooxml.fields import field_instruction_issue

    actual = render_case(name, tmp_path)
    assert inspect_docx_bytes(actual).ok
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))[name]
    observed = snapshot(actual)
    assert observed == expected
    for part in observed.values():
        if isinstance(part, dict):
            for instruction in part.get("fields", []):
                assert field_instruction_issue(instruction) is None, instruction
    assert actual == render_case(name, tmp_path)


@pytest.mark.parametrize(
    ("query", "construct"), [(".//w:tc", "cells"), (".//m:oMath", "equations")]
)
def test_snapshot_detects_missing_native_content(query, construct):
    original = MarkdownWord().render_string("## Report\n\n$x^2$\n\n| A |\n| --- |\n| B |")
    parts = read_parts(original)
    root = etree.fromstring(parts["word/document.xml"])
    element = root.xpath(query, namespaces=NS)[0]
    element.getparent().remove(element)
    parts["word/document.xml"] = etree.tostring(root)
    before = snapshot(original)["word/document.xml"]["counts"]
    after = snapshot(write_parts(parts))["word/document.xml"]["counts"]
    assert after.get(construct, 0) == before[construct] - 1


def test_corpus_rejects_broken_relationship(tmp_path):
    parts = read_parts(render_case("report", tmp_path))
    del parts["word/footnotes.xml"]
    assert not inspect_docx_bytes(write_parts(parts)).ok


if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        report = {name: snapshot(render_case(name, Path(directory))) for name in CASES}
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
