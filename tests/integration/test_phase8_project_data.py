from __future__ import annotations

from pathlib import Path
import time

from mddocx import build_project, compile_project
from mddocx.ast.block import ChartBlock, DataTableBlock


def test_project_tracks_chart_and_table_data_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "chapters").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "mddocx.yml").write_text(
        "version: 1\noutput: build/report.docx\nsources: [chapters/main.md]\n",
        encoding="utf-8",
    )
    (root / "chapters" / "main.md").write_text(
        '''# Results\n\n```chart {#fig-results caption="Results"}\ntype: line\nsource: ../data/results.csv\ncategory: Quarter\nseries_fields: [Revenue]\n```\n\n```data-table\nsource: ../data/results.csv\n```\n''',
        encoding="utf-8",
    )
    data = root / "data" / "results.csv"
    data.write_text("Quarter,Revenue\nQ1,10\nQ2,12\n", encoding="utf-8")
    compiled = compile_project(root)
    assert data.resolve() in compiled.dependencies
    chart = next(x for x in compiled.document.children if isinstance(x, ChartBlock))
    assert chart.source_path == "data/results.csv"
    table = next(x for x in compiled.document.children if isinstance(x, DataTableBlock))
    assert table.source_path == "data/results.csv"

    first = build_project(root)
    second = build_project(root)
    assert first.built and second.skipped
    time.sleep(0.01)
    data.write_text("Quarter,Revenue\nQ1,10\nQ2,15\n", encoding="utf-8")
    third = build_project(root)
    assert third.built and third.fingerprint != first.fingerprint
