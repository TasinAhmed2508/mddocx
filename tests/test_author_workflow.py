import json

from PIL import Image
import pytest

from mddocx.cli import main
from mddocx.watch import watch_file


def test_capabilities_reports_packaged_feature_and_diagnostic_catalogs(capsys):
    assert main(["capabilities", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert "verify" in report["commands"]
    assert report["features"][0]["verify"]
    diagnostics = {item["code"]: item for item in report["diagnostics"]}
    assert diagnostics["RECOVER201"]["severities"] == ["warning"]
    assert diagnostics["DOCX422"]["severities"] == ["error"]


@pytest.mark.parametrize(
    ("shell", "flag"),
    [("bash", "--recover"), ("zsh", "--strict"), ("fish", "-l recover"), ("powershell", "--jobs")],
)
def test_shell_completion_uses_cli_options(shell, flag, capsys):
    assert main(["completions", shell]) == 0
    output = capsys.readouterr().out
    assert flag in output and "mddocx-native" in output and "verify" in output


@pytest.mark.parametrize("filename", ["tile.png", "tile image.png"])
def test_single_file_watch_recovers_and_monitors_local_images(tmp_path, monkeypatch, filename):
    source = tmp_path / "doc.md"
    output = source.with_suffix(".docx")
    asset = tmp_path / filename
    Image.new("RGB", (8, 8), "red").save(asset)
    source.write_text(f"![Tile](<{filename}>)\n\n# First")
    builds = []
    errors = []

    def on_build(result):
        assert asset in result.dependencies
        builds.append(result.output_bytes)
        if len(builds) == 1:
            source.write_text("---\ntitle: [\n---\nBroken source.")
        elif len(builds) == 2:
            Image.new("RGB", (8, 8), "blue").save(asset)
        else:
            raise KeyboardInterrupt

    def on_error(exc):
        errors.append(str(exc))
        assert output.read_bytes() == builds[0]
        source.write_text(f"![Tile](<{filename}>)\n\n# Fixed")

    monkeypatch.setattr("mddocx.watch.sleep", lambda _: None)
    with pytest.raises(KeyboardInterrupt):
        watch_file(source, output, interval=0.1, once=False, on_build=on_build, on_error=on_error)
    assert len(errors) == 1 and "PARSE353" in errors[0]
    assert len(set(builds)) == 3


@pytest.mark.parametrize("filename", ["tile.png", "tile image.png"])
def test_diagnostic_output_cannot_overwrite_implicit_local_dependency(tmp_path, filename):
    source = tmp_path / "doc.md"
    resource = tmp_path / filename
    Image.new("RGB", (8, 8), "red").save(resource)
    source.write_text(f"![Tile](<{filename}>)\n\n# First")
    original = resource.read_bytes()
    assert main([str(source), "--diagnostics-json", str(resource)]) == 2
    assert resource.read_bytes() == original
    assert not source.with_suffix(".docx").exists()


@pytest.mark.parametrize("introduced_after_success", [False, True])
def test_watch_retries_when_a_new_missing_data_file_is_created(
    tmp_path, monkeypatch, introduced_after_success
):
    from docx import Document

    source = tmp_path / "report.md"
    output = source.with_suffix(".docx")
    asset = tmp_path / "readings.csv"
    declaration = "~~~data-table\nsource: readings.csv\n~~~"
    source.write_text("# Initial" if introduced_after_success else declaration, encoding="utf-8")
    output.write_bytes(b"previous output")
    builds, errors = [], []
    polls = 0

    def on_build(result):
        builds.append(result.output_bytes)
        if introduced_after_success and len(builds) == 1:
            source.write_text(declaration, encoding="utf-8")
            return
        assert asset in result.dependencies
        assert Document(output).tables[0].cell(1, 0).text == "Alpha"
        raise KeyboardInterrupt

    def on_error(exc):
        errors.append(str(exc))
        assert "DATA201" in str(exc)
        assert output.read_bytes() == (builds[0] if builds else b"previous output")
        asset.write_text("Name,Value\nAlpha,10\n", encoding="utf-8")

    def poll(_interval):
        nonlocal polls
        polls += 1
        assert polls <= 10, "Watch did not notice the new data file"

    monkeypatch.setattr("mddocx.watch.sleep", poll)
    with pytest.raises(KeyboardInterrupt):
        watch_file(source, output, interval=0.1, once=False, on_build=on_build, on_error=on_error)
    assert len(errors) == 1
    assert len(builds) == (2 if introduced_after_success else 1)
