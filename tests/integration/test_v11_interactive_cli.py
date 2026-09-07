from __future__ import annotations

from pathlib import Path

import yaml

from mddocx.cli import main
from mddocx.interactive.history import load_recent
from mddocx.interactive.shell import InteractiveConsole
from mddocx.interactive.tokenize import split_command
from mddocx.project import init_project


def test_windows_paths_are_not_destroyed_by_shell_tokenizer():
    assert split_command(r'render D:\Project\report.md -o "D:\My Files\report.docx"') == [
        "render", r"D:\Project\report.md", "-o", r"D:\My Files\report.docx"
    ]


def test_interactive_direct_render_and_recent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    source = tmp_path / "report.md"
    source.write_text("# Report\n\n- one\n- two\n\n$$E=mc^2$$\n", encoding="utf-8")
    lines: list[str] = []
    opened: list[Path] = []
    console = InteractiveConsole(tmp_path, writer=lines.append, opener=lambda p: opened.append(Path(p)))

    result = console.execute_line("render report.md -o result.docx")
    assert result.exit_code == 0
    assert (tmp_path / "result.docx").exists()
    assert any("Equations:" in line for line in lines)
    recent = load_recent()
    assert recent and recent[0].source.endswith("report.md")
    assert recent[0].output.endswith("result.docx")
    assert opened == []


def test_interactive_guided_render_from_menu(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    (tmp_path / "a.md").write_text("# Hello\n\nWorld", encoding="utf-8")
    answers = iter(["1", "", "", "n"])
    output: list[str] = []
    console = InteractiveConsole(tmp_path, reader=lambda prompt: next(answers), writer=output.append, opener=lambda p: None)
    result = console.execute_line("1")
    assert result.exit_code == 0
    assert (tmp_path / "a.docx").exists()
    assert any("DOCX generated" in line for line in output)


def test_interactive_project_config_set(tmp_path: Path):
    manifest = init_project(tmp_path)
    console = InteractiveConsole(tmp_path, writer=lambda text: None)
    result = console.execute_line("config set render.theme academic")
    assert result.exit_code == 0
    loaded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert loaded["render"]["theme"] == "academic"


def test_cli_shell_dispatch(monkeypatch, tmp_path: Path):
    called: list[tuple[Path, bool]] = []

    def fake_run(workspace, *, show_menu=True):
        called.append((Path(workspace), show_menu))
        return 0

    monkeypatch.setattr("mddocx.cli.run_shell", fake_run)
    assert main(["shell", str(tmp_path), "--no-menu"]) == 0
    assert called == [(tmp_path, False)]


def test_top_level_recent_command(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    src = tmp_path / "x.md"
    dst = tmp_path / "x.docx"
    src.write_text("# X", encoding="utf-8")
    assert main([str(src), "-o", str(dst)]) == 0
    capsys.readouterr()
    assert main(["recent", "--limit", "1"]) == 0
    out = capsys.readouterr().out
    assert "x.md" in out and "x.docx" in out


def test_remote_host_detection_only_considers_images(tmp_path: Path):
    from mddocx.interactive.shell import _remote_hosts
    source = tmp_path / "remote.md"
    source.write_text(
        "[ordinary link](https://example.com/page)\n\n"
        "![remote image](https://images.example.net/a.png)\n",
        encoding="utf-8",
    )
    assert _remote_hosts(source) == ["images.example.net"]


def test_shell_has_no_generic_shell_escape(tmp_path: Path):
    output: list[str] = []
    console = InteractiveConsole(tmp_path, writer=output.append)
    result = console.execute_line("! whoami")
    assert result.exit_code == 2
    assert any("Unknown command" in line for line in output)
