"""Chart surface: queue native ChartML entries for package injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH

from mddocx.ast.block import ChartBlock
from mddocx.chart_data import prepare_chart_entry
from mddocx.diagnostics import MddocxError
from mddocx.recovery import recovery_block

from . import citations, text_blocks

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def render_chart(renderer: DocxRenderer, node: ChartBlock) -> None:
    if not renderer.config.charts.enabled:
        renderer.reporter.warn(
            "CHART101",
            "Chart rendering is disabled; source was omitted.",
            getattr(node.source, "file", None),
            getattr(node.source, "line", None),
        )
        return
    try:
        entry = prepare_chart_entry(node, renderer.config, renderer.reporter)
    except MddocxError as exc:
        recoverable = exc.diagnostic.code == "CHART205" or (
            exc.diagnostic.code == "CHART203" and not node.source_path
        )
        if not renderer.config.recover or not recoverable:
            raise
        placeholder = recovery_block(renderer.reporter, exc.diagnostic, node.title, node.source)
        text_blocks.render_block_quote(renderer, placeholder)
        return
    caption = (
        (node.caption or node.title or ("Chart" if node.identifier else None))
        if renderer.config.references.captions
        else None
    )
    if caption and renderer.config.references.figure_caption_position == "above":
        citations.render_caption(renderer, "Figure", caption, node.identifier)
    token = f"MDDOCX_CHART_{len(renderer._chart_entries) + 1}_PLACEHOLDER"
    entry.token = token
    renderer._chart_entries.append(entry)
    p = renderer._add_paragraph("MD Normal")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_together = True
    if caption and renderer.config.references.figure_caption_position == "below":
        p.paragraph_format.keep_with_next = True
    p.add_run(token)
    if caption and renderer.config.references.figure_caption_position == "below":
        citations.render_caption(renderer, "Figure", caption, node.identifier)
    renderer.reporter.info(
        "CHART100",
        f"Queued native editable {node.chart_type} chart.",
        getattr(node.source, "file", None),
        getattr(node.source, "line", None),
    )
