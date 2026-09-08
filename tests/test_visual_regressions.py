from pathlib import Path

import pytest

from mddocx import MarkdownWord, compare_visual_pages, render_docx_pages


@pytest.mark.visual
def test_ai_math_report_renders_repeatably_with_libreoffice(tmp_path: Path):
    """Exercise the real DOCX -> PDF -> PNG path in the Linux CI renderer."""
    markdown = r"""# Formula report

Inline math \(x^2+y^2=z^2\) remains in the paragraph.

\[
\boxed{\frac{-b \pm \sqrt{b^2-4ac}}{2a}}
\]

| Variable | Meaning | Value |
|---|---|---|
| \(a\) | quadratic coefficient | 1 |
| \(b\) | linear coefficient | -3 |
| \(c\) | constant | 2 |
"""
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    first.write_bytes(MarkdownWord().render_string(markdown))
    second.write_bytes(MarkdownWord().render_string(markdown))

    baseline_pages = render_docx_pages(first, tmp_path / "baseline", dpi=96)
    actual_pages = render_docx_pages(second, tmp_path / "actual", dpi=96)
    report = compare_visual_pages(tmp_path / "baseline", tmp_path / "actual", threshold=0.999)

    assert baseline_pages
    assert len(actual_pages) == len(baseline_pages)
    assert report.ok, report.to_text()
