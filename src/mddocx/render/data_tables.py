"""Data surfaces: base-directory containment and imported data tables."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mddocx.ast.block import DataTableBlock
from mddocx.data import load_data_table
from mddocx.diagnostics import MddocxError
from mddocx.recovery import recovery_block

from . import tables, text_blocks

if TYPE_CHECKING:
    from mddocx.render.renderer import DocxRenderer


def render_data_table(renderer: DocxRenderer, node: DataTableBlock) -> None:
    try:
        table = load_data_table(node, renderer.config)
    except MddocxError as exc:
        if not renderer.config.recover or exc.diagnostic.code != "DATA208":
            raise
        placeholder = recovery_block(
            renderer.reporter, exc.diagnostic, ", ".join(node.columns), node.source
        )
        text_blocks.render_block_quote(renderer, placeholder)
        return
    tables.render_table_block(renderer, table)
    renderer.reporter.info(
        "DATA100",
        f"Rendered {max(0, len(table.rows) - 1)} rows from {Path(node.source_path).name} as a native Word table.",
        getattr(node.source, "file", None),
        getattr(node.source, "line", None),
    )
