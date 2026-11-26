from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from mddocx.interactive import history
from mddocx.interactive.history import ShellPreferences
from mddocx.interactive.shell import InteractiveConsole
from mddocx.cli import _config_from_args, build_parser
from mddocx.resources import network, resolver


def test_shell_preferences_default_to_allow_and_round_trip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path)

    initial = history.load_shell_preferences()
    assert initial.initialized is False
    assert initial.allow_remote_resources is True

    history.save_shell_preferences(ShellPreferences(initialized=True, allow_remote_resources=False))
    saved = history.load_shell_preferences()
    assert saved.initialized is True
    assert saved.allow_remote_resources is False


def test_first_shell_launch_enables_images_without_prompt(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path / "state")
    answers = iter(["exit"])
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
    assert any("allowed by default" in line for line in output)


def test_saved_shell_blocking_preference_is_preserved(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path / "state")
    history.save_shell_preferences(ShellPreferences(initialized=True, allow_remote_resources=False))
    answers = iter(["exit"])
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


def test_shell_uses_markdown_image_hosts_for_download_policy(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path / "state")
    source = tmp_path / "report.md"
    source.write_text(
        "![Map](https://figures.example/map.png)\n\n"
        "[Overlay](http://overlays.example/scene.png) {width=35%}\n\n"
        "Guide: [reference](https://docs.example/show.png).\n\n"
        "```md\n![Example](https://unused.example/chart.png)\n```\n",
        encoding="utf-8",
    )
    png = BytesIO()
    Image.new("RGB", (16, 8), "#4472C4").save(png, format="PNG")
    requested = []

    class Response(BytesIO):
        def __init__(self, url):
            super().__init__(png.getvalue())
            self.url = url

        def geturl(self):
            return self.url

    class Opener:
        def open(self, request, *, timeout):
            requested.append(urlparse(request.full_url).hostname)
            return Response(request.full_url)

    def build_opener(handler):
        assert handler.resolver.policy.allowed_domains == ("figures.example", "overlays.example")
        return Opener()

    monkeypatch.setattr(resolver, "build_opener", build_opener)
    monkeypatch.setattr(
        network.socket,
        "getaddrinfo",
        lambda *args, **kw: [(None, None, None, "", ("93.184.216.34", 443))],
    )
    shell = InteractiveConsole(tmp_path, writer=lambda _: None)
    assert shell.cmd_render([str(source)]) == 0
    assert requested == ["figures.example", "overlays.example"]
    assert not any(item["code"].startswith("RESOURCE") for item in shell.last_diagnostics)

    assert shell.cmd_render([str(source), "--block-remote-resources"]) == 0
    assert requested == ["figures.example", "overlays.example"]
    assert [
        item["code"] for item in shell.last_diagnostics if item["code"].startswith("RESOURCE")
    ] == ["RESOURCE201", "RESOURCE201"]
