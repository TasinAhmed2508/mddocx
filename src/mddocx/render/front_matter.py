"""Front-matter surfaces: title page, abstract, and table of contents.

These surfaces live outside block rendering, so they inherit fonts and direction by
calling ``renderer._apply_text_policy`` (the rule recorded in docs/ARCHITECTURE.md).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm

from mddocx.ooxml.fields import add_toc, render_field_template
from mddocx.ooxml.text import clean_xml_text

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def render_title_page(renderer: DocxRenderer) -> None:
    cfg = renderer.config.title_page
    if not renderer.config.title and not cfg.subtitle and not cfg.organization:
        return
    p = renderer.document.add_paragraph(style=renderer._style("MD Title"))
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Mm(42)
    p.add_run(clean_xml_text(renderer.config.title or "Untitled Document"))
    renderer._apply_text_policy(p, renderer.config.title or "Untitled Document")
    if cfg.subtitle:
        sp = renderer.document.add_paragraph(style=renderer._style("MD Subtitle"))
        sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sp.add_run(clean_xml_text(cfg.subtitle))
        renderer._apply_text_policy(sp, cfg.subtitle)
    if renderer.config.author:
        ap = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
        ap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ap.add_run(clean_xml_text(renderer.config.author))
        renderer._apply_text_policy(ap, renderer.config.author)
    if cfg.organization:
        op = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
        op.alignment = WD_ALIGN_PARAGRAPH.CENTER
        op.add_run(clean_xml_text(cfg.organization))
        renderer._apply_text_policy(op, cfg.organization)
    dp = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
    dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if cfg.date:
        render_field_template(dp, cfg.date, {"AUTHOR": renderer.config.author or ""})
        renderer._apply_text_policy(dp, cfg.date)
    else:
        render_field_template(dp, "{DATE}")
        renderer._apply_text_policy(dp)
    if cfg.page_break_after:
        renderer.document.add_page_break()


def render_abstract(renderer: DocxRenderer) -> None:
    cfg = renderer.config.abstract
    if cfg.text:
        hp = renderer.document.add_paragraph(style=renderer._style("MD Heading 1"))
        hp.add_run(clean_xml_text(cfg.title))
        renderer._apply_text_policy(hp, cfg.title)
        bp = renderer.document.add_paragraph(style=renderer._style("MD Abstract"))
        bp.add_run(clean_xml_text(cfg.text))
        renderer._apply_text_policy(bp, cfg.text)
    if cfg.keywords:
        keyword_text = ", ".join(cfg.keywords)
        kp = renderer.document.add_paragraph(style=renderer._style("MD Abstract"))
        r = kp.add_run(clean_xml_text(cfg.keywords_label) + ": ")
        r.bold = True
        kp.add_run(clean_xml_text(keyword_text))
        renderer._apply_text_policy(kp, keyword_text)


def render_toc(renderer: DocxRenderer) -> None:
    if renderer.config.toc.title:
        p = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
        r = p.add_run(clean_xml_text(renderer.config.toc.title))
        r.bold = True
        r.font.size = Mm(5.5)
        p.paragraph_format.keep_with_next = True
        renderer._apply_text_policy(p, renderer.config.toc.title)
    p = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
    add_toc(p, renderer.config.toc.min_level, renderer.config.toc.max_level)
    renderer.document.add_paragraph(style=renderer._style("MD Normal"))
