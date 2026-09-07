from __future__ import annotations

from pathlib import Path

from docx import Document

from mddocx.batch import render_many
from mddocx.cli import main


def test_render_many_converts_directory_deterministically(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "b.md").write_text("# B\n", encoding="utf-8")
    (source / "a.md").write_text("# A\n", encoding="utf-8")
    out = tmp_path / "out"
    results = render_many([source], out)
    assert [r.input_path.name for r in results] == ["a.md", "b.md"]
    assert all(r.ok for r in results)
    assert [p.name for p in sorted(out.glob("*.docx"))] == ["a.docx", "b.docx"]
    assert Document(out / "a.docx").paragraphs[0].text == "A"


def test_cli_batch_and_sarif(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("# A\n", encoding="utf-8")
    b.write_text("# B\n", encoding="utf-8")
    out = tmp_path / "out"
    assert main([str(a), str(b), "--output-dir", str(out)]) == 0
    assert (out / "a.docx").is_file()
    assert (out / "b.docx").is_file()

    sarif = tmp_path / "diagnostics.sarif"
    one = tmp_path / "one.docx"
    assert main([str(a), "-o", str(one), "--diagnostics-sarif", str(sarif)]) == 0
    assert '"version": "2.1.0"' in sarif.read_text(encoding="utf-8")
