from __future__ import annotations

from pathlib import Path

from mddocx import MarkdownWord, RenderConfig, inspect_docx_bytes


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "technical_report"
REPORT = FIXTURE_DIR / "report.md"


def test_technical_report_uses_native_editable_word_structures():
    compiler = MarkdownWord(RenderConfig())
    blob = compiler.render_string(REPORT.read_text(encoding="utf-8"), base_dir=FIXTURE_DIR)
    inspection = inspect_docx_bytes(blob)

    assert all(item.severity == "info" for item in compiler.diagnostics)
    assert [item.code for item in compiler.diagnostics] == ["CHART100"]
    assert inspection.ok
    assert inspection.headings >= 3
    assert inspection.equations == 2
    assert (
        inspection.tables >= 2
    )  # Markdown table plus chart layout/package table where applicable.
    assert inspection.native_list_paragraphs >= 2
    assert inspection.task_checkboxes == 2
    assert inspection.footnote_references == 1
    assert inspection.footnote_definitions == 1
    assert inspection.native_charts == 1
    assert inspection.embedded_workbooks == 1
    assert inspection.bookmarks >= 4
    assert inspection.fields >= 4
    assert inspection.seq_fields >= 3
    assert inspection.ref_fields >= 3
    assert inspection.dangling_ref_fields == 0
    assert inspection.duplicate_bookmark_names == 0
    assert inspection.broken_relationships == []
    assert inspection.chart_relationship_issues == 0


def test_technical_report_is_deterministic():
    markdown = REPORT.read_text(encoding="utf-8")

    first = MarkdownWord().render_string(markdown, base_dir=FIXTURE_DIR)
    second = MarkdownWord().render_string(markdown, base_dir=FIXTURE_DIR)

    assert first == second
