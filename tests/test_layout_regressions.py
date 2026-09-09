from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from lxml import etree

from mddocx import Compiler, MarkdownWord, RenderConfig, TableConfig, inspect_docx_bytes


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _document_xml(blob: bytes):
    with ZipFile(BytesIO(blob)) as package:
        return etree.fromstring(package.read("word/document.xml"))


def test_wide_table_enters_landscape_and_restores_portrait():
    markdown = """# Before

| A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|
| one | two | three | four | five | six | seven | eight |

# After

Portrait content continues.
"""
    config = RenderConfig(
        table=TableConfig(
            auto_landscape=True,
            landscape_min_columns=6,
            restore_portrait_after_landscape=True,
        )
    )
    compiler = MarkdownWord(config)
    blob = compiler.render_string(markdown)
    inspection = inspect_docx_bytes(blob)

    assert inspection.sections == 3
    assert inspection.landscape_sections == 1
    assert [item.code for item in compiler.diagnostics] == ["TABLE301"]


def test_layout_plan_exposes_the_reason_before_ooxml_rendering():
    markdown = """| A | B | C | D | E | F |
|---|---|---|---|---|---|
| one | two | three | four | five | six |
"""
    config = RenderConfig(table=TableConfig(auto_landscape=True, landscape_min_columns=6))

    result = Compiler(config).compile_string(markdown)
    decision = result.layout_plan.tables[0]

    assert decision.orientation == "landscape"
    assert decision.reason == "column threshold"
    assert decision.columns == 6
    assert decision.available_width_mm > 0
    assert len(decision.column_widths_mm) == 6
    assert sum(decision.column_widths_mm) <= decision.available_width_mm + 0.01
    assert result.stats.plan_ms >= 0


def test_table_header_repeats_and_rows_cannot_split():
    markdown = """| Header A | Header B |
|---|---|
| First | Row |
| Second | Row |
"""
    root = _document_xml(MarkdownWord().render_string(markdown))
    rows = root.xpath(".//w:tbl/w:tr", namespaces=NS)

    assert rows[0].xpath("./w:trPr/w:tblHeader[@w:val='true']", namespaces=NS)
    assert all(row.xpath("./w:trPr/w:cantSplit", namespaces=NS) for row in rows)


def test_layout_plan_covers_heading_code_caption_and_break_intent():
    markdown = """# Heading

```python
print('short')
```

$$x^2$$
{caption="Equation caption"}

<!-- pagebreak -->
"""
    parsed = Compiler().parse_string(markdown)
    normalized = Compiler().normalize(parsed.document)
    planned = Compiler().plan(normalized.document)
    decisions = {item.treatment: item for item in planned.layout_plan.blocks}

    assert decisions["heading"].keep_with_next
    assert decisions["keep"].keep_together
    assert decisions["native-equation"].keep_together
    assert decisions["page-break"].page_break_before
