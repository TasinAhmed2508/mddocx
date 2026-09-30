"""Figure surface: image resolution, DrawingML embedding, and figure captions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from docx.enum.text import WD_ALIGN_PARAGRAPH
from lxml import etree

from mddocx.ast.block import ImageBlock
from mddocx.ooxml.fields import add_hyperlink
from mddocx.ooxml.text import clean_xml_text
from mddocx.resources import ResourceFallback, ResourceRequest

from . import citations

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def render_image_block(renderer: DocxRenderer, node: ImageBlock) -> None:
    caption = (
        (
            node.caption
            or (node.title if renderer.config.image_captions_from_title else None)
            or (node.alt if node.identifier else None)
        )
        if renderer.config.references.captions
        else None
    )
    if caption and renderer.config.references.figure_caption_position == "above":
        citations.render_caption(renderer, "Figure", caption, node.identifier)
    p = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
    renderer._apply_planned_paragraph_layout(p, node)
    p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT, "right": WD_ALIGN_PARAGRAPH.RIGHT}.get(
        node.align or renderer.config.figures.default_align, WD_ALIGN_PARAGRAPH.CENTER
    )
    add_image(
        renderer,
        p,
        node.src,
        node.alt,
        title=node.title,
        width_percent=node.width_percent,
        decorative=node.decorative,
        source=node.source,
    )
    if caption and renderer.config.references.figure_caption_position == "below":
        citations.render_caption(renderer, "Figure", caption, node.identifier)


def add_image(
    renderer: DocxRenderer,
    paragraph,
    src: str,
    alt: str,
    title: str | None = None,
    width_percent: float | None = None,
    decorative: bool = False,
    source=None,
):
    result = renderer.resolver.resolve_image(
        ResourceRequest(
            source=src,
            source_file=getattr(source, "file", None),
            line=getattr(source, "line", None),
            alt_text=alt,
            title=title,
        )
    )
    if isinstance(result, ResourceFallback):
        renderer.reporter.emit(result.diagnostic)
        label = alt or title or src
        if getattr(renderer.config.resources, "image_failure", "clickable_fallback") == "literal":
            paragraph.add_run(clean_xml_text(label))
        elif urlparse(src).scheme.lower() in {"http", "https"}:
            add_hyperlink(paragraph, clean_xml_text(label), src)
        else:
            paragraph.add_run(clean_xml_text(label))
        return
    if result.format == "gif" and result.frame_count > 1:
        renderer.reporter.info(
            "IMAGE211",
            f"Animated GIF preserved ({result.frame_count} frames); playback depends on Word client.",
            getattr(source, "file", None),
            getattr(source, "line", None),
        )
    add_image_path(
        renderer,
        paragraph,
        result.path,
        alt,
        title=title,
        width_percent=width_percent,
        decorative=decorative,
    )


def add_image_path(
    renderer: DocxRenderer,
    paragraph,
    path: Path,
    alt: str,
    title: str | None = None,
    width_percent: float | None = None,
    decorative: bool = False,
):
    run = paragraph.add_run()
    shape = run.add_picture(str(path))
    sec = renderer.document.sections[-1]
    usable = sec.page_width - sec.left_margin - sec.right_margin
    requested_percent = (
        width_percent
        if width_percent is not None
        else renderer.config.figures.default_width_percent
    )
    requested_percent = min(requested_percent, renderer.config.images.max_width_percent)
    max_width = int(usable * max(0.05, min(1.0, requested_percent / 100.0)))
    if shape.width > max_width or (
        renderer.config.images.allow_upscale and shape.width < max_width
    ):
        ratio = max_width / shape.width
        shape.width = max_width
        shape.height = int(shape.height * ratio)
    try:
        docpr = shape._inline.docPr
        if decorative and renderer.config.accessibility.mark_decorative_images:
            docpr.set("descr", "")
            docpr.set("title", "Decorative")
            a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
            adec_ns = "http://schemas.microsoft.com/office/drawing/2017/decorative"
            ext_lst = docpr.find(f"{{{a_ns}}}extLst")
            if ext_lst is None:
                ext_lst = etree.SubElement(docpr, f"{{{a_ns}}}extLst")
            ext = etree.SubElement(ext_lst, f"{{{a_ns}}}ext")
            ext.set("uri", "{C183D7F6-B498-43B3-948B-1728B52AA6E}")
            dec = etree.SubElement(ext, f"{{{adec_ns}}}decorative", nsmap={"adec": adec_ns})
            dec.set("val", "1")
        else:
            if alt:
                docpr.set("descr", clean_xml_text(alt))
            if title:
                docpr.set("title", clean_xml_text(title))
            if renderer.config.accessibility.image_alt_required and not alt:
                renderer.reporter.warn("A11Y201", f"Image has no alt text: {path.name}")
    except Exception:
        pass
