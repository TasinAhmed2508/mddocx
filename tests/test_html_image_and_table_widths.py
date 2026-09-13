import base64
from io import BytesIO
from zipfile import ZipFile

from PIL import Image

from mddocx import MarkdownWord, RenderConfig, TableConfig


def _png_data_uri() -> str:
    stream = BytesIO()
    Image.new("RGB", (20, 12), "#4472C4").save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def test_html_data_uri_images_render_in_blocks_and_inline_quotes():
    uri = _png_data_uri()
    markdown = (
        f'<img alt="page" src="{uri}" />\n\n'
        f'> <img alt="icon" src="{uri}" /> **Finding:** supported.\n'
    )
    result = MarkdownWord().render_string(markdown)
    with ZipFile(BytesIO(result)) as package:
        document = package.read("word/document.xml")
    assert document.count(b"<a:blip") == 2
    assert b"<img" not in result


def test_details_wrapper_is_ignored_but_embedded_image_is_rendered():
    uri = _png_data_uri()
    markdown = (
        f'<details>\n<summary>Facsimiles</summary>\n\n<img alt="page" src="{uri}" />\n</details>'
    )
    result = MarkdownWord().render_string(markdown)
    with ZipFile(BytesIO(result)) as package:
        document = package.read("word/document.xml")
    assert document.count(b"<a:blip") == 1


def test_table_writes_fixed_grid_and_cell_widths():
    markdown = "| Narrative column | 2025 | Status |\n|---|---:|:---:|\n| Long explanatory text | 42 | OK |"
    config = RenderConfig(table=TableConfig(auto_landscape=True))
    result = MarkdownWord(config).render_string(markdown)
    with ZipFile(BytesIO(result)) as package:
        document = package.read("word/document.xml")
    assert b'w:tblLayout w:type="fixed"' in document
    assert b"<w:gridCol w:w=" in document
    assert b"<w:tcW" in document and b'w:type="dxa"' in document
