"""List surface: bullets, ordered lists, nested levels, and task items."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mddocx.ast.block import BulletList, OrderedList, Paragraph
from mddocx.ooxml.tasks import append_checkbox, set_task_indent

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def render_list(renderer: DocxRenderer, node, level: int = 0) -> None:
    kind = "bullet" if isinstance(node, BulletList) else "decimal"
    num_id = renderer.numbering.create(kind, getattr(node, "start", 1))
    for item in node.items:
        numbered = False
        for child in item.children:
            if isinstance(child, Paragraph) and not numbered:
                p = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
                if item.task_checked is None:
                    renderer.numbering.apply(p, num_id, level)
                else:
                    set_task_indent(
                        p,
                        level,
                        renderer.config.lists.indent_twips_per_level,
                        renderer.config.lists.hanging_twips,
                    )
                    append_checkbox(p, item.task_checked, renderer._task_control_id)
                    renderer._task_control_id += 1
                    spacer = p.add_run(" ")
                    renderer._configure_run(spacer, spacer.text)
                renderer._render_inlines(p, child.children)
                renderer._apply_text_direction(p._p, renderer._plain_inline_text(child.children))
                numbered = True
            elif isinstance(child, (BulletList, OrderedList)):
                render_list(renderer, child, level + 1)
            else:
                renderer._render_block(child, list_level=level)
        if not numbered:
            p = renderer.document.add_paragraph(style=renderer._style("MD Normal"))
            if item.task_checked is None:
                renderer.numbering.apply(p, num_id, level)
            else:
                set_task_indent(
                    p,
                    level,
                    renderer.config.lists.indent_twips_per_level,
                    renderer.config.lists.hanging_twips,
                )
                append_checkbox(p, item.task_checked, renderer._task_control_id)
                renderer._task_control_id += 1
