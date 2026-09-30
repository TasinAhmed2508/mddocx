"""Guardrails for the renderer's per-surface module split.

The ownership rules live in docs/ARCHITECTURE.md; these tests keep the structure from
drifting back into one god module.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from mddocx.render import DocxRenderer

ROOT = Path(__file__).parents[1]
RENDER = ROOT / "src" / "mddocx" / "render"

SURFACE_MODULES = {
    "document_setup": ("open_document", "configure_document", "request_field_updates"),
    "sections": ("configure_section",),
    "headers_footers": ("configure_header_footer",),
    "front_matter": ("render_title_page", "render_abstract", "render_toc"),
    "text_blocks": (
        "render_heading",
        "render_paragraph",
        "render_block_quote",
        "render_callout",
        "render_definition_list",
        "render_horizontal_rule",
        "render_page_break",
        "render_section_break",
    ),
    "lists": ("render_list",),
    "tables": (
        "render_table_block",
        "render_table_with_layout",
        "render_table",
        "table_should_landscape",
        "remove_table_borders",
    ),
    "data_tables": ("resolve_data_path", "render_data_table"),
    "charts": ("render_chart", "prepare_chart_entry"),
    "figures": ("render_image_block", "add_image", "add_image_path"),
    "code_blocks": ("render_code_block", "write_fenced_code"),
    "math_blocks": ("render_math_block", "render_numbered_equation"),
    "citations": (
        "display_label",
        "render_caption",
        "render_cross_reference",
        "render_bibliography",
    ),
}

SHARED_CORE = (
    "_style",
    "_apply_planned_paragraph_layout",
    "_render_block",
    "_render_inlines",
    "_plain_inline_text",
    "_append_math",
    "_configure_run",
    "_configure_xml_run",
    "_apply_text_direction",
    "_apply_text_policy",
    "_rtl_for_text",
)


def _type_checking_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    ranges = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            ranges.append((node.lineno, node.end_lineno or node.lineno))
    return ranges


def test_renderer_stays_a_small_orchestrator():
    source = (RENDER / "renderer.py").read_text(encoding="utf-8")
    line_count = len(source.splitlines())

    assert line_count <= 700, (
        f"render/renderer.py grew to {line_count} lines; keep surfaces separate"
    )


def test_renderer_exposes_the_shared_text_and_dispatch_core():
    missing = [name for name in SHARED_CORE if not hasattr(DocxRenderer, name)]

    assert not missing, f"shared renderer entry points disappeared: {missing}"


def test_surface_modules_expose_their_documented_entry_points():
    for module_name, functions in SURFACE_MODULES.items():
        module = importlib.import_module(f"mddocx.render.{module_name}")
        missing = [name for name in functions if not callable(getattr(module, name, None))]
        assert not missing, f"{module_name} is missing surface functions: {missing}"


def test_surfaces_only_reference_the_renderer_for_typing():
    offenders = {}
    for module_name in SURFACE_MODULES:
        path = RENDER / f"{module_name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        guarded = _type_checking_ranges(tree)
        lines = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and (node.module or "").endswith("render.renderer")
            and not any(start <= node.lineno <= end for start, end in guarded)
        ]
        if lines:
            offenders[module_name] = lines

    assert not offenders, (
        f"runtime imports of renderer.py would break the acyclic split: {offenders}"
    )


def test_renderer_imports_every_surface_it_calls_directly():
    """Surfaces used only by other surfaces (sections, headers_footers) stay off this list."""
    direct = {
        "charts",
        "citations",
        "code_blocks",
        "data_tables",
        "document_setup",
        "figures",
        "front_matter",
        "lists",
        "math_blocks",
        "tables",
        "text_blocks",
    }
    source = (RENDER / "renderer.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is None:
            imported.update(alias.name for alias in node.names)

    missing = sorted(direct - imported)
    assert not missing, f"renderer.py no longer wires surface modules: {missing}"
    assert direct <= set(SURFACE_MODULES)
