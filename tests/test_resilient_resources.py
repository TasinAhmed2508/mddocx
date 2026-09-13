from __future__ import annotations

import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from threading import Thread
from zipfile import ZipFile

import pytest
from PIL import Image

from mddocx import MarkdownWord, RenderConfig
from mddocx.config import ImageConfig, ResourcePolicy
from mddocx.diagnostics import MddocxError
from mddocx.resources import ResourceFallback, ResourceRequest, ResourceResolver, ResolvedImage


def _gif_bytes(frames: int = 2) -> bytes:
    images = [Image.new("RGBA", (3, 2), (index * 80, 20, 30, 255)) for index in range(frames)]
    stream = BytesIO()
    images[0].save(stream, format="GIF", save_all=True, append_images=images[1:], duration=50)
    return stream.getvalue()


@contextmanager
def _server(routes):
    counts = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            counts[self.path] = counts.get(self.path, 0) + 1
            status, content_type, body = routes.get(self.path, (404, "text/plain", b"missing"))
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", counts
    finally:
        httpd.shutdown()
        thread.join()


def test_content_detection_ignores_misleading_local_extension(tmp_path):
    image = tmp_path / "figure.download"
    image.write_bytes(_gif_bytes())
    resolver = ResourceResolver(tmp_path, ResourcePolicy(), ImageConfig())
    result = resolver.resolve_image(ResourceRequest("figure.download", line=7))
    assert isinstance(result, ResolvedImage)
    assert (result.format, result.media_type, result.width_px, result.height_px) == (
        "gif",
        "image/gif",
        3,
        2,
    )
    assert result.frame_count == 2


def test_invalid_image_returns_source_located_fallback(tmp_path):
    (tmp_path / "fake.png").write_text("<html>not an image</html>", encoding="utf-8")
    resolver = ResourceResolver(tmp_path, ResourcePolicy(), ImageConfig())
    result = resolver.resolve_image(
        ResourceRequest("fake.png", source_file="paper.md", line=12, alt_text="plot")
    )
    assert isinstance(result, ResourceFallback)
    assert result.reason == "not_image"
    assert result.diagnostic.severity == "warning"
    assert (result.diagnostic.source_file, result.diagnostic.line) == ("paper.md", 12)


def test_compatibility_resolve_remains_strict(tmp_path):
    resolver = ResourceResolver(tmp_path, ResourcePolicy(), ImageConfig())
    with pytest.raises(MddocxError) as caught:
        resolver.resolve("missing.png")
    assert caught.value.diagnostic.code == "RESOURCE204"


def test_data_gif_preserves_original_animation(tmp_path):
    data = _gif_bytes(3)
    uri = "data:image/gif;base64," + base64.b64encode(data).decode("ascii")
    resolver = ResourceResolver(tmp_path, ResourcePolicy(), ImageConfig())
    result = resolver.resolve_image(ResourceRequest(uri))
    assert isinstance(result, ResolvedImage)
    assert result.frame_count == 3
    assert result.path.read_bytes() == data


@pytest.mark.parametrize("status", [404, 403, 500])
def test_http_error_is_nonfatal_and_does_not_poison_cache(tmp_path, status):
    cache = tmp_path / "cache"
    policy = ResourcePolicy(allow_private_hosts=True, cache_directory=cache)
    with _server({"/broken.png": (status, "image/png", b"failure")}) as (origin, _):
        resolver = ResourceResolver(tmp_path, policy, ImageConfig())
        result = resolver.resolve_image(ResourceRequest(f"{origin}/broken.png"))
    assert isinstance(result, ResourceFallback)
    assert result.reason == "http_error"
    assert not list(cache.iterdir())


def test_extensionless_mislabeled_image_is_validated_and_cached(tmp_path):
    data = _gif_bytes()
    policy = ResourcePolicy(
        allow_private_hosts=True, cache_directory=tmp_path / "cache", validate_mime=True
    )
    with _server({"/asset": (200, "text/plain", data)}) as (origin, counts):
        resolver = ResourceResolver(tmp_path, policy, ImageConfig())
        first = resolver.resolve_image(ResourceRequest(f"{origin}/asset"))
        second = resolver.resolve_image(ResourceRequest(f"{origin}/asset"))
    assert isinstance(first, ResolvedImage) and first.format == "gif"
    assert isinstance(second, ResolvedImage) and second.from_cache
    assert counts["/asset"] == 1


def test_animated_gif_is_preserved_in_docx_package(tmp_path):
    data = _gif_bytes(3)
    (tmp_path / "motion.gif").write_bytes(data)
    blob = MarkdownWord().render_string("![Motion](motion.gif)", base_dir=tmp_path)
    with ZipFile(BytesIO(blob)) as package:
        media = [name for name in package.namelist() if name.startswith("word/media/")]
        assert any(package.read(name) == data for name in media)
        assert 'Extension="gif" ContentType="image/gif"' in package.read(
            "[Content_Types].xml"
        ).decode("utf-8")


def test_block_figure_fallback_keeps_caption_and_numbering(tmp_path):
    config = RenderConfig(resources=ResourcePolicy(image_failure="clickable_fallback"))
    markdown = '![Unavailable](https://invalid.invalid/missing.png "Missing figure"){#fig:missing}'
    blob = MarkdownWord(config).render_string(markdown, base_dir=tmp_path)
    with ZipFile(BytesIO(blob)) as package:
        xml = package.read("word/document.xml").decode("utf-8")
        relationships = package.read("word/_rels/document.xml.rels").decode("utf-8")
    assert "Unavailable" in xml
    assert "Missing figure" in xml
    assert "SEQ Figure" in xml
    assert "https://invalid.invalid/missing.png" in relationships
