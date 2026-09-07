from __future__ import annotations

from pathlib import Path

from mddocx.cli import main


def test_project_init_build_info_and_watch_once(tmp_path: Path, capsys) -> None:
    root = tmp_path / "project"
    assert main(["project", "init", str(root)]) == 0
    assert (root / "mddocx.yml").is_file()

    assert main(["project", "info", str(root), "--json"]) == 0
    info_out = capsys.readouterr().out
    assert '"source_count": 1' in info_out

    assert main(["build", str(root), "--json"]) == 0
    build_out = capsys.readouterr().out
    assert '"built": true' in build_out.lower()
    assert (root / "build" / "document.docx").is_file()

    assert main(["build", str(root)]) == 0
    assert "UP-TO-DATE" in capsys.readouterr().out

    assert main(["watch", str(root), "--once"]) == 0
    assert "UP-TO-DATE" in capsys.readouterr().out


def test_project_build_check_reports_dependencies(tmp_path: Path, capsys) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "mddocx.yml").write_text(
        "version: 1\nsources: [main.md]\n", encoding="utf-8"
    )
    (root / "main.md").write_text("# A\n\n@include part.md\n", encoding="utf-8")
    (root / "part.md").write_text("Text.\n", encoding="utf-8")
    assert main(["build", str(root), "--check"]) == 0
    out = capsys.readouterr().out
    assert "Sources: 1" in out
    assert "Includes: 1" in out
