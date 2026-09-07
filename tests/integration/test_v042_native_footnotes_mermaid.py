from io import BytesIO
from zipfile import ZipFile

from docx import Document
from lxml import etree

from mddocx import render_string

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}


def test_native_footnotes_and_mermaid_are_packaged():
    markdown = r'''# Test
A footnote.[^a]

```mermaid
flowchart TD
A[Start] --> B[Done]
```

[^a]: Note with $e^{i\pi}+1=0$.
'''
    blob = render_string(markdown)
    Document(BytesIO(blob))  # package remains readable by python-docx
    with ZipFile(BytesIO(blob)) as z:
        names = set(z.namelist())
        assert "word/footnotes.xml" in names
        assert any(name.startswith("word/media/") for name in names)
        doc = etree.fromstring(z.read("word/document.xml"))
        foot = etree.fromstring(z.read("word/footnotes.xml"))
        assert int(doc.xpath("count(.//w:footnoteReference)", namespaces=NS)) == 1
        assert int(foot.xpath("count(.//w:footnote[@w:id='1'])", namespaces=NS)) == 1
        assert int(foot.xpath("count(.//m:oMath)", namespaces=NS)) >= 1


def test_supported_mermaid_replaces_source_code_with_diagram():
    blob = render_string("```mermaid\ngraph LR\nA((A)) --> B((B))\n```\n")
    with ZipFile(BytesIO(blob)) as z:
        doc = etree.fromstring(z.read("word/document.xml"))
        text = "".join(doc.xpath(".//w:t/text()", namespaces=NS))
        assert "graph LR" not in text
        assert int(doc.xpath("count(.//w:drawing)", namespaces=NS)) >= 1
