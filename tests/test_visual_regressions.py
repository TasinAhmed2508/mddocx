import os
from pathlib import Path
import shutil

import pytest

from mddocx import MarkdownWord, compare_visual_pages, render_docx_pages
from mddocx import RenderConfig


def require_visual_tools() -> None:
    """Skip with a reason when no office renderer is installed.

    Visual QA is an optional cross-check for layout, not how mddocx proves its
    output is correct: page rendering needs LibreOffice/soffice plus pdftoppm, or
    Microsoft Word on Windows. A machine without them reports *not run* rather
    than either a pass or an unexplained failure. The CI visual job asserts
    ``visual_qa_ready`` first, so this skip cannot hide a broken runner.
    """
    office = shutil.which("libreoffice") or shutil.which("soffice")
    word = os.name == "nt" and (shutil.which("powershell") or shutil.which("pwsh"))
    if shutil.which("pdftoppm") and (office or word):
        return
    pytest.skip(
        "visual QA needs LibreOffice/soffice plus pdftoppm, or Microsoft Word on Windows; "
        "document conversion does not need any of them"
    )


@pytest.mark.visual
def test_ai_math_report_renders_repeatably_with_libreoffice(tmp_path: Path):
    """Exercise the real DOCX -> PDF -> PNG path in the Linux CI renderer."""
    require_visual_tools()
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


@pytest.mark.visual
def test_multipage_table_repeats_header_and_restores_orientation(tmp_path: Path):
    import subprocess

    from PIL import Image
    from mddocx.visual_qa import _convert_to_pdf

    require_visual_tools()
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        pytest.skip("pdftotext is required for checking the repeated header")
    config = RenderConfig()
    config.table.auto_landscape = True
    config.table.landscape_min_columns = 2
    rows = "\n".join(f"| Row {index} | Note for row {index} |" for index in range(104))
    markdown = (
        "# Before the table\n\n| RepeatedHeader | Notes |\n| --- | --- |\n"
        + rows
        + "\n\n# After the table\n"
    )
    docx = tmp_path / "table.docx"
    docx.write_bytes(MarkdownWord(config).render_string(markdown))
    pdf = tmp_path / "table.pdf"
    office = shutil.which("libreoffice") or shutil.which("soffice")
    _convert_to_pdf(docx, pdf, tmp_path, office)
    pages = subprocess.check_output([pdftotext, str(pdf), "-"], text=True).split("\f")
    assert sum("RepeatedHeader" in page for page in pages) >= 2
    assert "After the table" in pages[-2]
    prefix = tmp_path / "table-layout"
    subprocess.run(
        [shutil.which("pdftoppm"), "-png", "-r", "36", str(pdf), str(prefix)], check=True
    )
    sizes = []
    for page in sorted(tmp_path.glob("table-layout-*.png")):
        with Image.open(page) as image:
            sizes.append(image.size)
    assert sizes[0][0] < sizes[0][1] and sizes[-1][0] < sizes[-1][1]
    assert any(width > height for width, height in sizes)
