from pathlib import Path

from mddocx.cli import main


def test_data_inspect_cli(tmp_path: Path, capsys) -> None:
    path = tmp_path / "data.csv"
    path.write_text("A,B\nx,1\ny,2\n", encoding="utf-8")
    assert main(["data", "inspect", str(path), "--json"]) == 0
    out = capsys.readouterr().out
    assert '"rows": 2' in out
    assert '"A"' in out and '"B"' in out
