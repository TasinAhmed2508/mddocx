from __future__ import annotations

import os
from pathlib import Path

import pytest

from mddocx import render
from mddocx.visual_qa import compare_visual_pages, render_docx_pages


@pytest.mark.visual
def test_visual_regression_snapshot(tmp_path: Path):
    if os.environ.get("MDDOCX_RUN_VISUAL") != "1":
        pytest.skip("set MDDOCX_RUN_VISUAL=1 to run LibreOffice page regression")
    root = Path(__file__).parents[1]
    source = root / "visual" / "visual_fixture.md"
    baseline = root / "visual" / "baseline"
    docx = tmp_path / "fixture.docx"
    render(source, docx)
    pages = tmp_path / "pages"
    render_docx_pages(docx, pages)
    report = compare_visual_pages(baseline, pages, threshold=0.995)
    assert report.ok, report.to_text()
