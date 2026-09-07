from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from lxml import etree

from mddocx import render_string
from mddocx.ast.block import BulletList, Paragraph
from mddocx.ast.inline import Text
from mddocx.inspection import inspect_docx_bytes
from mddocx.parser import MarkdownParser

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"


def test_task_markers_become_ast_state_and_are_removed_from_text():
    doc = MarkdownParser().parse("- [x] Done\n- [ ] Pending\n- normal\n")
    block = doc.children[0]
    assert isinstance(block, BulletList)
    assert [item.task_checked for item in block.items] == [True, False, None]
    first_para = block.items[0].children[0]
    assert isinstance(first_para, Paragraph)
    assert isinstance(first_para.children[0], Text)
    assert first_para.children[0].text == "Done"


def test_task_lists_render_as_native_word_checkbox_content_controls():
    blob = render_string("- [x] Done\n- [ ] Pending\n- normal\n")
    report = inspect_docx_bytes(blob)
    assert report.task_checkboxes == 2
    # Only the ordinary list item should retain a native numbering marker.
    assert report.native_list_paragraphs == 1
    with ZipFile(BytesIO(blob)) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    ns = {"w": W, "w14": W14}
    checked = root.xpath(".//w14:checkbox/w14:checked/@w14:val", namespaces=ns)
    assert checked == ["1", "0"]
    text = "".join(root.xpath(".//w:t/text()", namespaces=ns))
    assert "[x]" not in text and "[ ]" not in text
