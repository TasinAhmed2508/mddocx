from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document

from mddocx import MarkdownWord, PerformanceConfig, RenderConfig, ResourcePolicy, TableConfig, render_string
from mddocx.ast.base import Document as AstDocument, Node
from mddocx.resources import ResourceResolver
from mddocx.config import ImageConfig
from mddocx.diagnostics import MddocxError


def _zip_text(blob: bytes, name: str) -> str:
    with ZipFile(BytesIO(blob)) as z:
        return z.read(name).decode("utf-8")


def test_svg_and_webp_are_embedded_as_word_compatible_images(tmp_path: Path):
    pytest.importorskip("cairosvg")
    Image = pytest.importorskip("PIL.Image")
    svg = tmp_path / "diagram.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60"><rect width="120" height="60"/><text x="10" y="35">SVG</text></svg>', encoding="utf-8")
    webp = tmp_path / "photo.webp"
    Image.new("RGB", (40, 20), "white").save(webp, format="WEBP")
    blob = render_string("![svg](diagram.svg)\n\n![webp](photo.webp)", base_dir=tmp_path)
    Document(BytesIO(blob))
    with ZipFile(BytesIO(blob)) as z:
        media = [name for name in z.namelist() if name.startswith("word/media/")]
        assert len(media) == 2
        assert all(name.endswith((".png", ".jpg", ".jpeg")) for name in media)


def test_svg_external_references_are_rejected(tmp_path: Path):
    pytest.importorskip("cairosvg")
    svg = tmp_path / "unsafe.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>', encoding="utf-8")
    with pytest.raises(MddocxError) as exc:
        render_string("![unsafe](unsafe.svg)", base_dir=tmp_path)
    assert exc.value.diagnostic.code == "IMAGE207"


def test_remote_resource_policy_blocks_private_and_unapproved_hosts(tmp_path: Path):
    resolver = ResourceResolver(tmp_path, ResourcePolicy(allow_remote_resources=True), ImageConfig())
    try:
        with pytest.raises(MddocxError) as exc:
            resolver._validate_remote_url("https://127.0.0.1/a.png")
        assert exc.value.diagnostic.code == "RESOURCE211"
        restricted = ResourceResolver(tmp_path, ResourcePolicy(allow_remote_resources=True, allowed_domains=("example.com",)), ImageConfig())
        try:
            with pytest.raises(MddocxError) as exc2:
                restricted._validate_remote_url("https://example.org/a.png")
            assert exc2.value.diagnostic.code == "RESOURCE209"
        finally:
            restricted.close()
    finally:
        resolver.close()


def test_wide_table_can_be_isolated_in_landscape_section():
    header = "| " + " | ".join(f"Column {i}" for i in range(7)) + " |"
    sep = "|" + "|".join("---" for _ in range(7)) + "|"
    row = "| " + " | ".join("long-value-" + "x" * 20 for _ in range(7)) + " |"
    md = "# Before\n\n" + header + "\n" + sep + "\n" + row + "\n\n# After\n"
    cfg = RenderConfig(table=TableConfig(auto_landscape=True, landscape_min_columns=6))
    converter = MarkdownWord(cfg)
    blob = converter.render_string(md)
    xml = _zip_text(blob, "word/document.xml")
    assert 'w:orient="landscape"' in xml
    assert xml.count("<w:sectPr") >= 3
    assert any(d.code == "TABLE301" for d in converter.diagnostics)


class UnknownNode(Node):
    pass


def test_json_diagnostics_and_performance_stats_are_available():
    cfg = RenderConfig(performance=PerformanceConfig(enabled=True, track_memory=True))
    converter = MarkdownWord(cfg)
    blob = converter.render_ast(AstDocument(children=[UnknownNode()]))
    assert blob.startswith(b"PK")
    assert '"code": "EXT301"' in converter.diagnostics_json()
    # render_ast exposes render timing; full string compilation also populates all stages.
    converter.render_string("# Profile\n\nText $x^2$.")
    assert converter.last_stats.output_bytes > 0
    assert converter.last_stats.total_ms > 0
    assert converter.last_stats.peak_memory_bytes is not None


def test_remote_image_download_works_only_with_explicit_private_opt_in(tmp_path: Path):
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    Image = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "remote.png"
    Image.new("RGB", (20, 10), "white").save(image_path, format="PNG")

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    handler = functools.partial(QuietHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        cfg = RenderConfig(resources=ResourcePolicy(
            allow_remote_resources=True,
            allowed_schemes=("http",),
            allowed_domains=("127.0.0.1",),
            allow_private_hosts=True,
        ))
        blob = render_string(f"![remote](http://127.0.0.1:{port}/remote.png)", config=cfg)
        with ZipFile(BytesIO(blob)) as z:
            media = [name for name in z.namelist() if name.startswith("word/media/")]
        assert len(media) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
