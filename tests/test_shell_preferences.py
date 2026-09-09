from pathlib import Path

from mddocx.interactive import history
from mddocx.interactive.history import ShellPreferences
from mddocx.interactive.shell import InteractiveConsole
from mddocx.cli import _config_from_args, build_parser


def test_shell_preferences_default_to_allow_and_round_trip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path)

    initial = history.load_shell_preferences()
    assert initial.initialized is False
    assert initial.allow_remote_resources is True

    history.save_shell_preferences(ShellPreferences(initialized=True, allow_remote_resources=False))
    saved = history.load_shell_preferences()
    assert saved.initialized is True
    assert saved.allow_remote_resources is False


def test_first_shell_launch_asks_with_allow_as_default(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path / "state")
    answers = iter(["", "exit"])
    output: list[str] = []

    def read(prompt: str) -> str:
        output.append(prompt)
        return next(answers)

    console = InteractiveConsole(
        tmp_path,
        reader=read,
        writer=output.append,
    )

    assert console.run(show_menu=False) == 0
    saved = history.load_shell_preferences()
    assert saved.initialized is True
    assert saved.allow_remote_resources is True
    assert any("RESOURCE201" in line for line in output)


def test_first_shell_launch_can_persist_blocking(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path / "state")
    answers = iter(["yes", "exit"])
    console = InteractiveConsole(
        tmp_path,
        reader=lambda _prompt: next(answers),
        writer=lambda _line: None,
    )

    assert console.run(show_menu=False) == 0
    assert history.load_shell_preferences().allow_remote_resources is False


def test_noninteractive_cli_allows_remote_by_default_and_can_block():
    parser = build_parser()

    default_config = _config_from_args(parser.parse_args(["input.md"]))
    blocked_config = _config_from_args(parser.parse_args(["input.md", "--block-remote-resources"]))

    assert default_config.resources.allow_remote_resources is True
    assert blocked_config.resources.allow_remote_resources is False
