from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from PIL import Image

from mddocx import Compiler, MarkdownWord, RenderConfig
from mddocx.diagrams import MermaidRenderer
from mddocx.interactive import history
from mddocx.interactive.shell import InteractiveConsole
from mddocx.ooxml import bangla


def test_flowchart_keeps_labeled_edges_and_node_text():
    lines = [
        "flowchart TD",
        "Start([Reader's start]) -->|5/5 points| Choice{Choose route}",
        "Choice-->|yes|Result[First result]-->End([Finished])",
        "Choice -->|no|Other[Other result]",
    ]

    direction, nodes, edges = MermaidRenderer()._parse_flow(lines)

    assert direction == "TD"
    assert nodes["Start"].label == "Reader's start"
    assert nodes["Choice"].shape == "diamond"
    assert [(edge.src, edge.dst, edge.label) for edge in edges] == [
        ("Start", "Choice", "5/5 points"),
        ("Choice", "Result", "yes"),
        ("Result", "End", ""),
        ("Choice", "Other", "no"),
    ]


def test_long_flowchart_is_readable_across_pages_and_keeps_conditions():
    edges = [
        f"N{index}[Step {index}] -->|condition {index}| N{index + 1}[Step {index + 1}]"
        for index in range(15)
    ]
    source = "```mermaid\nflowchart TD\n" + "\n".join(edges) + "\n```\n"

    result = Compiler().compile_string(source)
    document = Document(BytesIO(result.output_bytes))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert len(document.inline_shapes) >= 3
    assert "Flowchart conditions" in text
    assert all(f"condition {index}" in text for index in range(15))
    section = document.sections[0]
    available_width = section.page_width - section.left_margin - section.right_margin
    available_height = section.page_height - section.top_margin - section.bottom_margin
    assert all(shape.width <= available_width for shape in document.inline_shapes)
    assert all(shape.height <= available_height for shape in document.inline_shapes)
    assert not any(item.code == "DIAGRAM201" for item in result.diagnostics)


def test_paginated_flowcharts_do_not_cut_connections_at_page_edges(tmp_path: Path):
    source = "flowchart TD\n" + "\n".join(f"N{i} --> N{i + 1}" for i in range(15))
    paths, _, _ = MermaidRenderer().render_pages(
        source, tmp_path, width_inches=6.5, height_inches=10
    )

    assert len(paths) >= 3
    for path in paths:
        with Image.open(path).convert("RGB") as image:
            assert all(image.getpixel((x, 0)) == (255, 255, 255) for x in range(image.width))
            assert all(
                image.getpixel((x, image.height - 1)) == (255, 255, 255) for x in range(image.width)
            )


def test_multilingual_flowchart_labels_remain_editable_in_word(monkeypatch):
    monkeypatch.setattr(bangla, "installed_font_stems", lambda: frozenset({"nirmala"}))
    source = "```mermaid\nflowchart TD\nA[বাংলা ভাষা] -->|अगला| B[中文 日本語]\n```"

    result = Compiler().compile_string(source)
    document = Document(BytesIO(result.output_bytes))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert len(document.inline_shapes) == 1
    assert "Node 1: বাংলা ভাষা" in text
    assert "Node 2: 中文 日本語" in text
    assert "अगला" in text


def test_table_header_is_kept_with_its_first_data_row():
    source = "| Heading A | Heading B |\n| --- | --- |\n| First | Row |\n| Second | Row |\n"
    table = Document(BytesIO(MarkdownWord().render_string(source))).tables[0]

    assert all(
        p.paragraph_format.keep_with_next for cell in table.rows[0].cells for p in cell.paragraphs
    )
    assert all(
        p.paragraph_format.keep_with_next is None
        for cell in table.rows[1].cells
        for p in cell.paragraphs
    )
    assert [cell.text for cell in table.rows[1].cells] == ["First", "Row"]


def test_default_font_automatically_falls_back_and_preserves_other_script_slots(monkeypatch):
    monkeypatch.setattr(bangla, "installed_font_stems", lambda: frozenset({"nirmala"}))
    config = RenderConfig()
    config.fonts.east_asia = "Microsoft YaHei"
    config.fonts.complex_script = "Nirmala UI"

    result = Compiler(config).compile_string("বাংলা 中文 العربية हिन्दी English")
    paragraph = Document(BytesIO(result.output_bytes)).paragraphs[0]
    bengali = next(run for run in paragraph.runs if "বাংলা" in run.text)
    other = next(run for run in paragraph.runs if "English" in run.text)

    assert bengali.font.name == "Nirmala UI"
    assert "বাংলা 中文 العربية हिन्दी English" == paragraph.text
    assert other._r.rPr.rFonts.get(qn("w:ascii")) == "Aptos"
    assert other._r.rPr.rFonts.get(qn("w:eastAsia")) == "Microsoft YaHei"
    assert other._r.rPr.rFonts.get(qn("w:cs")) == "Nirmala UI"
    assert not any(item.code == "FONT301" for item in result.diagnostics)


def test_legacy_bangla_preserves_other_scripts_and_their_joiners(monkeypatch):
    monkeypatch.setattr(bangla, "installed_font_stems", lambda: frozenset({"sutonnymjregular"}))
    config = RenderConfig()
    config.fonts.east_asia = "Microsoft YaHei"
    config.fonts.complex_script = "Nirmala UI"
    source = "বাংলা क्\u200dष العربية 中文 English"

    document = Document(BytesIO(MarkdownWord(config).render_string(source)))
    paragraph = document.paragraphs[0]
    other = next(run for run in paragraph.runs if "क्\u200dष" in run.text)

    assert paragraph.runs[0].font.name == "SutonnyMJ"
    assert "العربية 中文 English" in other.text
    assert other._r.rPr.rFonts.get(qn("w:eastAsia")) == "Microsoft YaHei"
    assert other._r.rPr.rFonts.get(qn("w:cs")) == "Nirmala UI"


def test_guided_theme_menu_hides_the_separate_bangla_theme(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path / "state")
    source = tmp_path / "report.md"
    source.write_text("# Report\n", encoding="utf-8")
    console = InteractiveConsole(tmp_path, writer=lambda text: None)
    monkeypatch.setattr(console, "choose_file", lambda *args: source)
    monkeypatch.setattr(console, "ask", lambda *args: str(tmp_path / "output.docx"))
    monkeypatch.setattr(console, "confirm", lambda *args, **kwargs: False)
    offered: list[list[str]] = []

    def choose(title, options, default=1):
        offered.append(list(options))
        return options.index("default") + 1

    monkeypatch.setattr(console, "choose", choose)
    assert console.cmd_render([]) == 0
    assert offered == [["academic", "default", "minimal", "modern"]]
