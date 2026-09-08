from __future__ import annotations

from pathlib import Path

import pytest

from mddocx import RenderConfig, build_project, compile_project, init_project, load_project
from mddocx.diagnostics import MddocxError
from mddocx.project import ProjectCompiler


def test_project_build_is_reproducible_and_skips_unchanged_input(tmp_path: Path):
    project_file = init_project(tmp_path / "report")
    manifest = load_project(project_file)

    first = build_project(manifest)
    second = build_project(manifest)

    assert first.built and not first.skipped
    assert second.skipped and not second.built
    assert first.output_sha256 == second.output_sha256
    assert manifest.output.is_file()


def test_project_includes_are_combined_and_tracked(tmp_path: Path):
    root = tmp_path / "book"
    root.mkdir()
    (root / "main.md").write_text(
        "# Main\n\n@include chapters/math.md\n\nEnd {{ audience }}.", encoding="utf-8"
    )
    (root / "chapters").mkdir()
    (root / "chapters" / "math.md").write_text("## Math\n\n$$x^2$$", encoding="utf-8")
    (root / "mddocx.yml").write_text(
        """version: 1
output: build/book.docx
sources: [main.md]
variables:
  audience: readers
""",
        encoding="utf-8",
    )

    compiled = compile_project(root)

    assert compiled.source_count == 1
    assert compiled.include_count == 1
    assert {path.name for path in compiled.dependencies} == {
        "mddocx.yml",
        "main.md",
        "math.md",
    }


def test_project_rejects_source_and_include_path_traversal(tmp_path: Path):
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    root = tmp_path / "project"
    root.mkdir()
    manifest = root / "mddocx.yml"
    manifest.write_text(
        "version: 1\noutput: build/out.docx\nsources: [../outside.md]\n",
        encoding="utf-8",
    )

    with pytest.raises(MddocxError, match="escapes the project root"):
        load_project(manifest)

    (root / "main.md").write_text("@include ../outside.md", encoding="utf-8")
    manifest.write_text(
        "version: 1\noutput: build/out.docx\nsources: [main.md]\n",
        encoding="utf-8",
    )
    with pytest.raises(MddocxError, match="escapes the project root"):
        compile_project(manifest)


def test_project_detects_include_cycles(tmp_path: Path):
    root = tmp_path / "cycle"
    root.mkdir()
    (root / "a.md").write_text("@include b.md", encoding="utf-8")
    (root / "b.md").write_text("@include a.md", encoding="utf-8")
    (root / "mddocx.yml").write_text(
        "version: 1\noutput: build/out.docx\nsources: [a.md]\n",
        encoding="utf-8",
    )

    with pytest.raises(MddocxError, match="Include cycle"):
        compile_project(root)


def test_explicit_project_config_overrides_manifest_render_values(tmp_path: Path):
    project_file = init_project(tmp_path / "precedence")
    manifest = load_project(project_file)
    explicit = RenderConfig(title="Caller title", theme="academic")

    compiler = ProjectCompiler(manifest, explicit)

    assert compiler.config.title == "Caller title"
    assert compiler.config.theme == "academic"
