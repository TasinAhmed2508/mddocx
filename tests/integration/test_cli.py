from pathlib import Path
from mddocx.cli import main


def test_cli_writes_output(tmp_path: Path):
    src = tmp_path / "a.md"; dst = tmp_path / "a.docx"
    src.write_text("# Hello\n\nWorld", encoding="utf-8")
    assert main([str(src), "-o", str(dst)]) == 0
    assert dst.exists() and dst.stat().st_size > 1000
    assert main([str(src), "--check"]) == 0
