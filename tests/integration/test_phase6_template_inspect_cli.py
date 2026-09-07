from pathlib import Path
from docx import Document
from mddocx.cli import main
from mddocx.template_inspection import inspect_template


def test_template_inspector_and_cli(tmp_path: Path, capsys):
    path = tmp_path / "template.docx"
    doc = Document()
    doc.core_properties.title = "Corporate Template"
    doc.sections[0].header.paragraphs[0].text = "Header"
    doc.save(path)
    report = inspect_template(path)
    assert report.sections == 1
    assert report.title == "Corporate Template"
    assert "Header" in report.header_text[0]
    assert main(["template", "inspect", str(path), "--json"]) == 0
    assert '"sections": 1' in capsys.readouterr().out
