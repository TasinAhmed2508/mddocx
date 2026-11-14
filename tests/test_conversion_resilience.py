"""Regression tests for the conversion-robustness contract.

Every case here was a real defect: an internal exception type reaching the user,
a raw traceback from the CLI, a silently swallowed accessibility failure, or a
diagnostic emitted under a code that documents something else. Each test fails
against the behaviour it was written to pin down.
"""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest

from mddocx import MarkdownWord, RenderConfig
from mddocx.cli import main
from mddocx.config import AccessibilityConfig
from mddocx.diagnostics import MddocxError

ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _document_xml(blob: bytes) -> str:
    with ZipFile(BytesIO(blob)) as package:
        assert package.testzip() is None
        return package.read("word/document.xml").decode("utf-8")


def test_malformed_front_matter_reports_a_diagnostic_not_a_yaml_traceback():
    config = RenderConfig()
    markdown = "---\ntitle: [unclosed\n  bad: : indent\n---\n\n# Title\n"

    with pytest.raises(MddocxError) as error:
        MarkdownWord(config).render_string(markdown)

    assert error.value.diagnostic.code == "PARSE353"
    assert type(error.value).__name__ == "MddocxError"


def test_front_matter_diagnostic_names_the_source_file_and_line():
    config = RenderConfig()
    parser = MarkdownWord(config).parser

    with pytest.raises(MddocxError) as error:
        parser.parse(
            "---\ntitle: [unclosed\n  bad: : indent\n---\n\nbody\n", source_file="report.md"
        )

    diagnostic = error.value.diagnostic
    assert diagnostic.code == "PARSE353"
    assert diagnostic.source_file == "report.md"
    # The offending token is on file line 3, not in the document body below.
    assert diagnostic.line == 3
    assert diagnostic.remediation


def test_lone_surrogate_input_compiles_and_drops_the_invalid_code_point():
    config = RenderConfig()
    markdown = "before \ud800 after\n"

    blob = MarkdownWord(config).render_string(markdown)

    assert "before" in _document_xml(blob)
    assert "after" in _document_xml(blob)


def test_missing_image_alt_text_uses_the_image_diagnostic_code():
    config = RenderConfig(accessibility=AccessibilityConfig(image_alt_required=True))
    markdown = f"![](data:image/png;base64,{ONE_PIXEL_PNG})\n"

    compiler = MarkdownWord(config)
    compiler.render_string(markdown)

    codes = [item.code for item in compiler.diagnostics]
    assert "A11Y101" in codes
    # A11Y201 documents a missing table header row, not a missing image alt text.
    assert "A11Y201" not in codes


def test_cli_reports_an_internal_defect_without_a_raw_traceback(tmp_path, monkeypatch, capsys):
    source = tmp_path / "document.md"
    source.write_text("# Title\n\nBody text.\n", encoding="utf-8")

    def explode(*args, **kwargs):
        raise RuntimeError("simulated internal defect")

    monkeypatch.setattr("mddocx.compiler.Compiler.compile_file", explode)

    status = main([str(source), "-o", str(tmp_path / "out.docx")])
    captured = capsys.readouterr()

    assert status == 2
    assert "INTERNAL500" in captured.err
    assert "Traceback" not in captured.err
    assert "simulated internal defect" in captured.err


def test_cli_traceback_flag_exposes_the_internal_stack(tmp_path, monkeypatch, capsys):
    source = tmp_path / "document.md"
    source.write_text("# Title\n\nBody text.\n", encoding="utf-8")

    def explode(*args, **kwargs):
        raise RuntimeError("simulated internal defect")

    monkeypatch.setattr("mddocx.compiler.Compiler.compile_file", explode)

    status = main([str(source), "-o", str(tmp_path / "out.docx"), "--traceback"])
    captured = capsys.readouterr()

    assert status == 2
    assert "Traceback" in captured.err
