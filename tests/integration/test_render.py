from io import BytesIO
from zipfile import ZipFile
from docx import Document
from mddocx import render_string


def test_docx_contains_native_structures():
    md = """# Report\n\nA [link](https://example.com) and $E=mc^2$.\n\n- Alpha\n- Beta\n\n| Model | Score |\n|---|---:|\n| A | 94 |\n\n```python\nprint('editable')\n```\n\n$$\n\\frac{x}{y}\n$$\n"""
    blob = render_string(md)
    Document(BytesIO(blob))  # package can be reopened by python-docx
    with ZipFile(BytesIO(blob)) as z:
        names = set(z.namelist())
        assert "word/document.xml" in names
        xml = z.read("word/document.xml").decode("utf-8")
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        numbering = z.read("word/numbering.xml").decode("utf-8")
        assert "<m:oMath" in xml
        assert "<w:tbl" in xml
        assert "<w:numPr" in xml
        assert "hyperlink" in rels.lower()
        assert "abstractNum" in numbering
        assert "editable" in xml
