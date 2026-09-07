from __future__ import annotations

from pathlib import Path

from mddocx import render_string
from mddocx.cli import main


def test_cli_doctor(capsys):
    assert main(["doctor", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"python"' in out
    assert '"dependencies"' in out


def test_cli_inspect(tmp_path: Path, capsys):
    path = tmp_path / "sample.docx"
    path.write_bytes(render_string("# Heading\n\n- [x] task\n"))
    assert main(["inspect", str(path), "--strict", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"task_checkboxes": 1' in out
    assert '"headings": 1' in out
