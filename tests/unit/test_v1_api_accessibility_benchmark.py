from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree

import mddocx
from mddocx import RenderConfig, audit_docx_accessibility_bytes, get_public_api_manifest, render_string, run_performance_gate
from mddocx.inspection import inspect_docx_bytes
from mddocx.validation import validate_docx_package
from mddocx.config import ValidationConfig
from mddocx.diagnostics import MddocxError


def test_v1_public_api_manifest_is_frozen_and_resolvable():
    manifest = get_public_api_manifest()
    assert manifest.api_version == "1"
    assert manifest.package_version == mddocx.__version__
    assert "render" in manifest.names
    assert "RenderConfig" in manifest.names
    for name in manifest.names:
        assert hasattr(mddocx, name), name


def test_accessibility_audit_reports_missing_metadata_and_heading_jump():
    blob = render_string("# One\n\n### Three\n\n| A | B |\n|---|---|\n| 1 | 2 |")
    report = audit_docx_accessibility_bytes(blob)
    assert report.heading_level_jumps == 1
    assert not report.document_title_present
    assert any(f.code == "A11Y301" for f in report.findings)
    assert any(f.code == "A11Y501" for f in report.findings)


def test_accessibility_audit_passes_good_semantic_document():
    blob = render_string(
        "# Report\n\n## Results\n\n| Metric | Value |\n|---|---:|\n| A | 1 |",
        config=RenderConfig(title="Accessible report"),
    )
    report = audit_docx_accessibility_bytes(blob)
    assert report.images_missing_alt == 0
    assert report.tables_missing_header == 0
    assert report.heading_level_jumps == 0
    assert report.document_title_present
    assert report.passes("medium")


def test_small_performance_gate_runs_and_inspects_output():
    report = run_performance_gate(sections=3, max_seconds=30.0, max_peak_memory_bytes=256 * 1024 * 1024)
    assert report.ok
    assert report.equations >= 3
    assert report.tables >= 3
    assert len(report.sha256) == 64


def test_inspection_detects_duplicate_relationship_ids():
    blob = render_string("# Test\n\n[link](https://example.com)")
    with ZipFile(BytesIO(blob), "r") as zin:
        parts = {n: zin.read(n) for n in zin.namelist()}
    root = etree.fromstring(parts["word/_rels/document.xml.rels"])
    rels = list(root)
    duplicate = etree.fromstring(etree.tostring(rels[0]))
    root.append(duplicate)
    parts["word/_rels/document.xml.rels"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            zout.writestr(name, data)
    broken = out.getvalue()
    report = inspect_docx_bytes(broken)
    assert report.duplicate_relationship_ids == 1
    try:
        validate_docx_package(broken, ValidationConfig())
    except MddocxError as exc:
        assert "DOCX418" in str(exc)
    else:
        raise AssertionError("duplicate relationship IDs should fail validation")
