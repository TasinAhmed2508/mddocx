from pathlib import Path
from zipfile import ZipFile

from mddocx.cli import main


def test_cli_phase2_word_options(tmp_path: Path):
    src = tmp_path / "phase2.md"
    dst = tmp_path / "phase2.docx"
    src.write_text("# Heading\n\nText", encoding="utf-8")
    assert main([
        str(src), "-o", str(dst), "--toc", "--page-numbers",
        "--header", "Header", "--footer", "Footer", "--title", "CLI Title",
    ]) == 0
    with ZipFile(dst) as z:
        document = z.read("word/document.xml").decode("utf-8")
        headers = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/header"))
        footers = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/footer"))
    assert "TOC" in document
    assert "Header" in headers
    assert "Footer" in footers and "PAGE" in footers
