from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from mddocx import render_string
from mddocx.config import ValidationConfig
from mddocx.diagnostics import MddocxError
from mddocx.inspection import inspect_docx_bytes
from mddocx.validation import validate_docx_package


def _rewrite_part(blob: bytes, name: str, transform) -> bytes:
    src = ZipFile(BytesIO(blob), "r")
    out = BytesIO()
    with src, ZipFile(out, "w", ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == name:
                data = transform(data)
            dst.writestr(info.filename, data)
    return out.getvalue()


def test_inspector_counts_native_structures():
    blob = render_string("# H\n\n- a\n- [x] done\n\n$$\\int_0^1 x\\,dx$$\n")
    report = inspect_docx_bytes(blob)
    assert report.ok
    assert report.headings == 1
    assert report.native_list_paragraphs == 1
    assert report.task_checkboxes == 1
    assert report.equations >= 1
    assert report.nary_operators >= 1
    assert report.empty_nary_operands == 0


def test_inspector_and_validator_detect_suspicious_placeholder_character():
    blob = render_string("normal")
    broken = _rewrite_part(blob, "word/document.xml", lambda data: data.replace(b"normal", "normal □".encode("utf-8")))
    report = inspect_docx_bytes(broken)
    assert report.suspicious_placeholder_chars.get("□") == 1
    try:
        validate_docx_package(broken, ValidationConfig(detect_placeholder_chars=True))
    except MddocxError as exc:
        assert exc.diagnostic.code == "DOCX413"
    else:
        raise AssertionError("validator accepted suspicious placeholder output")
