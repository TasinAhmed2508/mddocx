from __future__ import annotations

import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from threading import Thread
from zipfile import ZipFile

import pytest
from docx import Document
from docx.oxml.ns import qn
from lxml import etree
from PIL import Image

from mddocx import Compiler, MarkdownWord, NotesConfig, RenderConfig, audit_docx_accessibility_bytes
from mddocx.config import ImageConfig, ResourcePolicy
from mddocx.diagnostics import MddocxError
from mddocx.ooxml.package import read_parts
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


def test_direct_image_links_embed_and_other_links_do_not_fetch(tmp_path):
    image = BytesIO()
    Image.new("RGB", (64, 34), "#315c91").save(image, format="JPEG")
    cfg = RenderConfig(
        resources=ResourcePolicy(allow_private_hosts=True),
        images=ImageConfig(allow_upscale=True),
    )
    with _server({"/plate.JPG?raw=1": (200, "image/jpeg", image.getvalue())}) as (origin, counts):
        url = f"{origin}/plate.JPG?raw=1"
        source = (
            f'[Inspection plate]({url}) {{#fig:plate width=35% caption="Inspection results"}}\n\n'
            f"{url} {{width=55%}}\n\n"
            f"[Prose link]({origin}/do-not-fetch.png) with notes {{width=35%}}\n\n"
            f"Ordinary link: [Documentation]({origin}/guide).\n\n"
            f"![First]({url}) ![Second]({url})"
        )
        compiler = Compiler(cfg)
        md = tmp_path / "report.md"
        md.write_text(source, encoding="utf-8")
        output = compiler.compile_file(md, tmp_path / "report.docx").output_bytes
        assert compiler.verify(md, output).ok
    assert counts == {"/plate.JPG?raw=1": 1}
    document = Document(BytesIO(output))
    section = document.sections[0]
    text_width = section.page_width - section.left_margin - section.right_margin
    assert [picture.width for picture in document.inline_shapes][:2] == [
        int(text_width * percent) for percent in (0.35, 0.55)
    ]
    with ZipFile(BytesIO(output)) as package:
        xml = package.read("word/document.xml")
        assert xml.count(b"<w:drawing>") == 4
        assert b'descr="Inspection plate"' in xml
        assert b"Inspection results" in xml
        assert b"with notes {width=35%}" in xml
        assert any(
            package.read(name) == image.getvalue()
            for name in package.namelist()
            if "/media/" in name
        )
        assert f"{origin}/guide".encode() in package.read("word/_rels/document.xml.rels")


@pytest.mark.parametrize("style", ["footnote", "endnote"])
def test_standalone_image_links_embed_in_cells_and_notes(tmp_path, style):
    asset = BytesIO()
    Image.new("RGB", (640, 100), "#315c91").save(asset, format="JPEG")
    path = "/inspection.JPG?raw=1"
    config = RenderConfig(
        resources=ResourcePolicy(allow_private_hosts=True),
        notes=NotesConfig(style=style),
    )
    compiler = Compiler(config)
    source = tmp_path / "inspection.md"
    with _server({path: (200, "image/jpeg", asset.getvalue())}) as (origin, counts):
        url = origin + path
        guide = origin + "/guide"
        source.write_text(
            f"| Image | Reference |\n| --- | --- |\n"
            f'| [**Sensor** plot]({url} "Inspection") | [Instructions]({guide}) |\n'
            f"| {url} | See [raw file]({origin}/as-text.jpg) for the original. |\n\n"
            f'<table>\n<tr><td> <a href="{url}" title="Thermal plot">Thermal</a> </td></tr>\n'
            "</table>\n\n"
            f"Evidence is available.[^plate]\n\n[^plate]: [Detail]({url})\n",
            encoding="utf-8",
        )
        output = compiler.compile_file(source, source.with_suffix(".docx"))
        assert compiler.verify(source, output.output_bytes).ok
    assert counts == {path: 1}

    parts = read_parts(output.output_bytes)
    body = etree.fromstring(parts["word/document.xml"])
    notes = etree.fromstring(parts[f"word/{style}s.xml"])
    for container, descriptions in [(body, ["Sensor plot", None, "Thermal"]), (notes, ["Detail"])]:
        pictures = list(container.iter(qn("wp:docPr")))
        assert [picture.get("descr") for picture in pictures] == descriptions
        assert all(
            next(picture.iterancestors(qn("w:hyperlink")), None) is not None for picture in pictures
        )
    for part in ("document", f"{style}s"):
        links = etree.fromstring(parts[f"word/_rels/{part}.xml.rels"])
        assert any(rel.get("Target") == url for rel in links)
    assert guide.encode() in parts["word/_rels/document.xml.rels"]
    assert b"for the original." in parts["word/document.xml"]
    assert b'w:tooltip="Thermal plot"' in parts["word/document.xml"]
    document = Document(BytesIO(output.output_bytes))
    first_cell = document.tables[0].cell(1, 0)
    assert int(next(body.iter(qn("wp:extent"))).get("cx")) < first_cell.width


@pytest.mark.parametrize("allow_remote", [False, True])
def test_unavailable_image_link_in_cell_keeps_clickable_label(tmp_path, allow_remote):
    policy = ResourcePolicy(
        allow_remote_resources=allow_remote,
        allow_private_hosts=True,
    )
    compiler = Compiler(RenderConfig(resources=policy))
    with _server({"/not-an-image.jpg": (200, "text/html", b"<p>A web page</p>")}) as (
        origin,
        counts,
    ):
        url = f"{origin}/not-an-image.jpg"
        source = f"| Inspection |\n| --- |\n| [Original page]({url}) |\n"
        result = compiler.compile_string(source, base_dir=tmp_path)
    assert counts == ({"/not-an-image.jpg": 1} if allow_remote else {})
    assert [finding.code for finding in result.diagnostics] == [
        "RESOURCE206" if allow_remote else "RESOURCE201"
    ]
    parts = read_parts(result.output_bytes)
    body = etree.fromstring(parts["word/document.xml"])
    (link,) = body.iter(qn("w:hyperlink"))
    assert "".join(link.itertext()) == "Original page"
    assert url.encode() in parts["word/_rels/document.xml.rels"]
    assert not list(body.iter(qn("w:drawing")))


def test_literal_math_characters_in_image_links_survive_conversion(tmp_path):
    jpg = BytesIO()
    Image.new("RGB", (12, 8), "navy").save(jpg, format="JPEG")
    path = "/plate.JPG?raw=$version$"
    config = RenderConfig(resources=ResourcePolicy(allow_private_hosts=True))
    compiler = Compiler(config)
    source = tmp_path / "assets.md"
    (tmp_path / "$local$.jpg").write_bytes(jpg.getvalue())
    with _server({path: (200, "image/jpeg", jpg.getvalue())}) as (origin, counts):
        url = origin + path
        other = f"{origin}/documentation?topic=$topic$"
        currency_link = f"{origin}/documentation?format=$"
        source.write_text(
            f'![Direct](<{url}> "$caption$")\n\n{url}\n\n'
            f'![Reference][plate]\n\n<img src="{url}" alt="HTML plate">\n\n'
            f"[Read the guide]({other}). Budget $5. [See the price]({currency_link}) with $x^2$.\n\n"
            f"![Local]($local$.jpg)\n\n[plate]: {url}\n",
            encoding="utf-8",
        )
        output = compiler.compile_file(source, source.with_suffix(".docx"))
        assert compiler.verify(source, output.output_bytes).ok
    assert counts == {path: 1}
    parts = read_parts(output.output_bytes)
    root = etree.fromstring(parts["word/document.xml"])
    assert len(list(root.iter(qn("w:drawing")))) == 5
    assert len(list(root.iter(qn("m:oMath")))) == 1
    assert other.encode() in parts["word/_rels/document.xml.rels"]
    assert currency_link.encode() in parts["word/_rels/document.xml.rels"]


def test_direct_image_links_obey_block_remote_flag(tmp_path):
    cfg = RenderConfig(resources=ResourcePolicy(allow_remote_resources=False))
    compiler = Compiler(cfg)
    with _server({}) as (origin, counts):
        result = compiler.compile_string(f"[Plate]({origin}/plate.jpg)", base_dir=tmp_path)
    assert counts == {}
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RESOURCE201"]
    with ZipFile(BytesIO(result.output_bytes)) as package:
        assert b"/plate.jpg" in package.read("word/_rels/document.xml.rels")


def test_image_descriptions_use_label_text_and_keep_requested_click_targets(tmp_path):
    jpg = BytesIO()
    Image.new("RGB", (12, 8), "navy").save(jpg, format="JPEG")
    config = RenderConfig(resources=ResourcePolicy(allow_private_hosts=True))
    compiler = Compiler(config)
    source = tmp_path / "descriptions.md"
    with _server({"/plot.jpg": (200, "image/jpeg", jpg.getvalue())}) as (origin, counts):
        url = f"{origin}/plot.jpg"
        click_target = f"{origin}/original.jpg"
        source.write_text(
            rf"![**Area** for $r^2$ and `gain`<br>\$draft\$ \[^literal] "
            rf"![nested $x$\(y\)](unused.png)]({url})"
            "\n\n"
            rf"[**Measured** `area` at \(r=2\)]({url})"
            "\n\n"
            rf"[![*বাংলা* and $x$]({url})]({click_target})"
            "\n\nA note.[^picture]\n\n"
            rf"[^picture]: ![**Plate** for `study`]({url})"
            "\n",
            encoding="utf-8",
        )
        output = compiler.compile_file(source, source.with_suffix(".docx"))
        assert not output.diagnostics
        assert compiler.verify(source, output.output_bytes).ok
    assert counts == {"/plot.jpg": 1}
    parts = read_parts(output.output_bytes)
    document = etree.fromstring(parts["word/document.xml"])
    notes = etree.fromstring(parts["word/footnotes.xml"])
    assert [node.get("descr") for node in document.iter(qn("wp:docPr"))] == [
        "Area for r^2 and gain $draft$ [^literal] nested xy",
        "Measured area at r=2",
        "বাংলা and x",
    ]
    assert [node.get("descr") for node in notes.iter(qn("wp:docPr"))] == ["Plate for study"]
    assert click_target.encode() in parts["word/_rels/document.xml.rels"]
    assert not list(document.iter(qn("m:oMath")))


@pytest.mark.parametrize(
    "template",
    [
        '[See ![Diagram]({image}) for details]({target} "Open manual")',
        '<a href="{target}" title="Open manual">See <img src="{image}" alt="Diagram"> for details</a>',
        '<a href="{target}">\nSee <img src="{image}" alt="Diagram"> for details\n</a>',
        '<table><tr><td><a href="{target}">See <img src="{image}" alt="Diagram"> for details</a></td></tr></table>',
    ],
)
def test_clickable_images_are_embedded_and_only_the_image_is_fetched(tmp_path, template):
    image = BytesIO()
    Image.new("RGB", (80, 40), "#315c91").save(image, format="JPEG")
    config = RenderConfig(resources=ResourcePolicy(allow_private_hosts=True))
    compiler = Compiler(config)
    source = tmp_path / "report.md"
    with _server({"/diagram.jpg": (200, "image/jpeg", image.getvalue())}) as (origin, requests):
        target = f"{origin}/manual.html"
        source.write_text(
            template.format(image=f"{origin}/diagram.jpg", target=target), encoding="utf-8"
        )
        result = compiler.compile_file(source, source.with_suffix(".docx"))
        assert not result.diagnostics
        assert compiler.verify(source, result.output_bytes).ok
        assert requests == {"/diagram.jpg": 1}

    parts = read_parts(result.output_bytes)
    main = etree.fromstring(parts["word/document.xml"])
    (link,) = main.iter(qn("w:hyperlink"))
    (drawing,) = link.iter(qn("w:drawing"))
    runs = list(link)
    picture_run = drawing.getparent()
    before = runs[: runs.index(picture_run)]
    after = runs[runs.index(picture_run) + 1 :]
    assert (
        "".join(text.text or "" for run in before for text in run.iter(qn("w:t"))).strip() == "See"
    )
    assert (
        "".join(text.text or "" for run in after for text in run.iter(qn("w:t"))).strip()
        == "for details"
    )
    assert next(drawing.iter(qn("wp:docPr"))).get("descr") == "Diagram"
    rels = etree.fromstring(parts["word/_rels/document.xml.rels"])
    link_id = link.get(qn("r:id"))
    embed_id = next(drawing.iter(qn("a:blip"))).get(qn("r:embed"))
    destinations = {item.get("Id"): item.get("Target") for item in rels}
    assert destinations[link_id] == target
    assert parts[f"word/{destinations[embed_id]}"] == image.getvalue()


def test_blocked_clickable_image_keeps_the_authored_destination(tmp_path):
    config = RenderConfig(resources=ResourcePolicy(allow_remote_resources=False))
    compiler = Compiler(config)
    with _server({}) as (origin, requests):
        result = compiler.compile_string(
            f"[![Diagram]({origin}/missing.png)]({origin}/manual.html)", base_dir=tmp_path
        )
    assert requests == {}
    assert [item.code for item in result.diagnostics] == ["RESOURCE201"]
    document = Document(BytesIO(result.output_bytes))
    (link,) = document.paragraphs[0].hyperlinks
    assert (link.text, link.address) == ("Diagram", f"{origin}/manual.html")


@pytest.mark.parametrize("style", ["footnote", "endnote"])
def test_note_pictures_share_the_image_resource_and_keep_their_own_links(tmp_path, style):
    image = BytesIO()
    Image.new("RGB", (80, 40), "#315c91").save(image, format="JPEG")
    config = RenderConfig(
        resources=ResourcePolicy(allow_private_hosts=True), notes=NotesConfig(style=style)
    )
    compiler = Compiler(config)
    source = tmp_path / "report.md"
    with _server({"/diagram.jpg": (200, "image/jpeg", image.getvalue())}) as (origin, requests):
        manual = f"{origin}/manual.html"
        asset = f"{origin}/diagram.jpg"
        source.write_text(
            "# Summary {#summary}\n\n"
            f"![Overview]({asset})\n\n"
            "Review.[^trace]\n\n"
            f"[^trace]: [![Diagram]({asset})]({manual}) and [Summary](#summary).\n",
            encoding="utf-8",
        )
        result = compiler.compile_file(source, source.with_suffix(".docx"))
        assert compiler.verify(source, result.output_bytes).ok
        assert requests == {"/diagram.jpg": 1}
    parts = read_parts(result.output_bytes)
    notes = etree.fromstring(parts[f"word/{style}s.xml"])
    links = list(notes.iter(qn("w:hyperlink")))
    (blip,) = links[0].iter(qn("a:blip"))
    rid = blip.get(qn("r:embed"))
    rels = etree.fromstring(parts[f"word/_rels/{style}s.xml.rels"])
    by_id = {rel.get("Id"): rel.get("Target") for rel in rels}
    assert by_id[links[0].get(qn("r:id"))] == manual
    assert links[1].get(qn("w:anchor")) == "summary"
    assert [name for name in parts if name.startswith("word/media/")] == [f"word/{by_id[rid]}"]
    assert parts[f"word/{by_id[rid]}"] == image.getvalue()
    audit = audit_docx_accessibility_bytes(result.output_bytes)
    assert (audit.images, audit.images_missing_alt, audit.empty_hyperlinks) == (2, 0, 0)


def test_blocked_note_image_has_the_definition_source_line(tmp_path):
    compiler = Compiler(RenderConfig(resources=ResourcePolicy(allow_remote_resources=False)))
    source = tmp_path / "report.md"
    with _server({}) as (origin, requests):
        source.write_text(
            f"Review.[^trace]\n\n[^trace]: ![Diagram]({origin}/diagram.jpg)\n",
            encoding="utf-8",
        )
        result = compiler.compile_file(source, source.with_suffix(".docx"))
    assert not requests
    (diagnostic,) = result.diagnostics
    assert (diagnostic.code, diagnostic.line, diagnostic.source_file) == (
        "RESOURCE201",
        3,
        str(source),
    )


@pytest.mark.parametrize(
    "source",
    [
        "![Plate](https://example.com:invalid/plate.jpg)",
        '<img alt="Plate" src="https://[bad/plate.jpg">',
    ],
)
def test_invalid_remote_image_url_is_reported_without_a_request(tmp_path, source):
    compiler = Compiler()
    md = tmp_path / "report.md"
    md.write_text(source, encoding="utf-8")
    result = compiler.compile_file(md, md.with_suffix(".docx"))
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RESOURCE208"]


@pytest.mark.parametrize("keep", [True, False])
def test_caption_stays_with_figure_only_when_requested(tmp_path, keep):
    from docx import Document

    (tmp_path / "plot.gif").write_bytes(_gif_bytes(1))
    config = RenderConfig()
    config.figures.caption_keep_with_figure = keep
    config.references.figure_caption_position = "below"
    result = Compiler(config).compile_string(
        '![Plot](plot.gif) {caption="Plot results"}\n\nFollowing paragraph.',
        base_dir=tmp_path,
    )
    figure, caption, following = Document(BytesIO(result.output_bytes)).paragraphs
    assert figure.paragraph_format.keep_with_next is keep
    assert caption.paragraph_format.keep_with_next is False
    assert following.text == "Following paragraph."


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
