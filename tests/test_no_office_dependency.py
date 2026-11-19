"""Conversion must never require an office suite.

mddocx generates OOXML directly, so every feature that matters to a user has to
work on a machine with nothing installed but Python and the declared
dependencies. The only parts that may need LibreOffice/soffice or Word are the
opt-in visual-regression helpers, and they must say so clearly instead of
failing obscurely or, worse, being treated as requirement.

These tests hide every office tool from ``shutil.which`` and then check that the
conversion path is untouched, that ``doctor`` still passes, and that the visual
helper reports its own absence as a clean, catchable error.
"""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from mddocx import RenderConfig, render_string
from mddocx.config import FooterConfig, TOCConfig
from mddocx.doctor import run_doctor
from mddocx.visual_qa import VisualQAUnavailable, render_docx_pages

# Tools mddocx must never need, plus the shells the Word fallback would use.
ABSENT_TOOLS = frozenset({"libreoffice", "soffice", "pdftoppm", "powershell", "pwsh"})


@pytest.fixture
def no_office_tools(monkeypatch):
    real_which = shutil.which

    def without_office(command, *args, **kwargs):
        if Path(str(command)).name in ABSENT_TOOLS:
            return None
        return real_which(command, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", without_office)
    return without_office


def test_the_fixture_actually_hides_the_tools(no_office_tools):
    # Without this, every test below could pass for the wrong reason.
    assert no_office_tools("soffice") is None
    assert no_office_tools("pdftoppm") is None


def test_conversion_works_with_no_office_suite(no_office_tools, tmp_path):
    markdown = (
        "# Report\n\n"
        "Text with **bold**, `code`, and an equation \\(x^2\\).\n\n"
        "| Metric | Value |\n| --- | ---: |\n| Growth | 18% |\n\n"
        "1. First\n2. Second\n\n"
        "![Pixel](data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=)\n\n"
        "> [!NOTE]\n> A callout.\n"
    )
    config = RenderConfig(
        toc=TOCConfig(enabled=True),
        footer=FooterConfig(enabled=True, page_number=True),
    )

    blob = render_string(markdown, config=config, base_dir=tmp_path)

    assert blob[:2] == b"PK"
    assert len(blob) > 10_000


def test_doctor_passes_and_reports_visual_qa_as_optional(no_office_tools):
    report = run_doctor()

    assert report.ok is True
    assert report.visual_qa_ready is False
    text = report.to_text()
    assert "Visual DOCX regression ready: no" in text
    # The report must not imply that conversion needs an office suite.
    assert "document conversion itself does not" in text


def test_visual_regression_reports_not_run_rather_than_passing(no_office_tools):
    """A visual check that cannot run must never read as a pass."""
    import importlib

    visual_regressions = importlib.import_module("test_visual_regressions")

    with pytest.raises(pytest.skip.Exception) as skipped:
        visual_regressions.require_visual_tools()

    assert "document conversion does not need" in str(skipped.value)


def test_visual_qa_reports_the_missing_tool_instead_of_hanging_or_passing(
    no_office_tools, tmp_path
):
    docx = tmp_path / "document.docx"
    docx.write_bytes(render_string("# Title\n\nBody.\n", config=RenderConfig()))

    with pytest.raises(VisualQAUnavailable) as error:
        render_docx_pages(docx, tmp_path / "pages")

    assert "pdftoppm" in str(error.value)
