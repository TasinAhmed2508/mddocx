from __future__ import annotations

from pathlib import Path
import time
import zipfile

import pytest
from PIL import Image as PILImage

from mddocx import build_project, compile_project, load_project
from mddocx.diagnostics import MddocxError
from mddocx.ast.block import Heading, ImageBlock


def _write_project(root: Path, manifest: str, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "mddocx.yml").write_text(manifest, encoding="utf-8")
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_project_load_compile_includes_variables_and_source_locations(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _write_project(
        root,
        """version: 1
output: build/book.docx
sources:
  - main.md
variables:
  book_name: Compiler Handbook
render:
  heading_numbering: true
""",
        {
            "main.md": "---\ntitle: Project Title\n---\n# {{ book_name }}\n\n@include chapters/intro.md\n",
            "chapters/intro.md": "## Introduction\n\nText from include.\n",
        },
    )
    manifest = load_project(root)
    compiled = compile_project(manifest)
    assert compiled.source_count == 1
    assert compiled.include_count == 1
    assert len(compiled.dependencies) >= 3  # manifest + main + include
    headings = [node for node in compiled.document.children if isinstance(node, Heading)]
    assert ["".join(x.text for x in h.children if hasattr(x, "text")) for h in headings] == [
        "Compiler Handbook",
        "Introduction",
    ]
    assert headings[0].source is not None and headings[0].source.line == 4
    assert headings[1].source is not None and headings[1].source.line == 1
    assert compiled.document.metadata["title"] == "Project Title"


def test_project_include_inside_fence_is_not_expanded(tmp_path: Path) -> None:
    root = tmp_path / "p"
    _write_project(
        root,
        "version: 1\nsources: [main.md]\n",
        {
            "main.md": "```text\n@include missing.md\n```\n\n# End\n",
        },
    )
    compiled = compile_project(root)
    assert compiled.include_count == 0
    assert any(isinstance(x, Heading) for x in compiled.document.children)


def test_project_rejects_include_traversal_and_cycles(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    root = tmp_path / "p"
    _write_project(
        root,
        "version: 1\nsources: [main.md]\n",
        {"main.md": "@include ../outside.md\n"},
    )
    with pytest.raises(MddocxError) as exc:
        compile_project(root)
    assert exc.value.diagnostic.code == "PROJECT802"

    (root / "main.md").write_text("@include a.md\n", encoding="utf-8")
    (root / "a.md").write_text("@include main.md\n", encoding="utf-8")
    with pytest.raises(MddocxError) as exc2:
        compile_project(root)
    assert exc2.value.diagnostic.code == "PROJECT805"


def test_project_variable_policies(tmp_path: Path) -> None:
    root = tmp_path / "p"
    _write_project(
        root,
        "version: 1\nsources: [main.md]\n",
        {"main.md": "# {{ missing }}\n"},
    )
    with pytest.raises(MddocxError) as exc:
        compile_project(root)
    assert exc.value.diagnostic.code == "PROJECT808"

    (root / "mddocx.yml").write_text(
        "version: 1\nsources: [main.md]\nproject:\n  undefined_variables: keep\n",
        encoding="utf-8",
    )
    compiled = compile_project(root)
    heading = next(x for x in compiled.document.children if isinstance(x, Heading))
    text = "".join(x.text for x in heading.children if hasattr(x, "text"))
    assert text == "{{ missing }}"


def test_project_rewrites_chapter_relative_images_and_tracks_dependency(tmp_path: Path) -> None:
    root = tmp_path / "p"
    _write_project(
        root,
        "version: 1\nsources: [chapters/a.md]\n",
        {"chapters/a.md": "# A\n\n![Plot](../images/plot.png)\n"},
    )
    image = root / "images" / "plot.png"
    image.parent.mkdir(parents=True)
    PILImage.new("RGB", (32, 20), "white").save(image)
    compiled = compile_project(root)
    image_node = next(x for x in compiled.document.children if isinstance(x, ImageBlock))
    assert image_node.src == "images/plot.png"
    assert image.resolve() in compiled.dependencies


def test_project_incremental_build_skips_and_rebuilds_on_dependency_change(tmp_path: Path) -> None:
    root = tmp_path / "p"
    _write_project(
        root,
        """version: 1
output: build/report.docx
sources: [main.md]
variables:
  value: one
render:
  title: Incremental Project
""",
        {"main.md": "# Report\n\nValue: {{ value }}\n\n@include part.md\n", "part.md": "First.\n"},
    )
    first = build_project(root)
    assert first.built and not first.skipped and first.output_path.is_file()
    second = build_project(root)
    assert second.skipped and not second.built
    assert second.fingerprint == first.fingerprint

    time.sleep(0.01)
    (root / "part.md").write_text("Second.\n", encoding="utf-8")
    third = build_project(root)
    assert third.built and not third.skipped
    assert third.fingerprint != first.fingerprint
    with zipfile.ZipFile(third.output_path) as zf:
        document_xml = zf.read("word/document.xml")
    assert b"Second." in document_xml


def test_project_manifest_validation_rejects_source_and_output_escape(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    (root / "mddocx.yml").write_text("version: 1\nsources: [../x.md]\n", encoding="utf-8")
    with pytest.raises(MddocxError) as exc:
        load_project(root)
    assert exc.value.diagnostic.code == "PROJECT814"

    (root / "main.md").write_text("# A\n", encoding="utf-8")
    (root / "mddocx.yml").write_text(
        "version: 1\nsources: [main.md]\noutput: ../escape.docx\n", encoding="utf-8"
    )
    with pytest.raises(MddocxError) as exc2:
        load_project(root)
    assert exc2.value.diagnostic.code == "PROJECT816"


def test_project_source_globs_expand_deterministically(tmp_path: Path) -> None:
    root = tmp_path / "p"
    _write_project(
        root,
        "version: 1\nsources:\n  - chapters/*.md\n",
        {
            "chapters/02-second.md": "# Second\n",
            "chapters/01-first.md": "# First\n",
        },
    )
    manifest = load_project(root)
    assert [p.name for p in manifest.sources] == ["01-first.md", "02-second.md"]
    compiled = compile_project(manifest)
    headings = [x for x in compiled.document.children if isinstance(x, Heading)]
    assert ["".join(y.text for y in x.children if hasattr(y, "text")) for x in headings] == ["First", "Second"]


def test_incremental_build_rebuilds_if_output_was_modified(tmp_path: Path) -> None:
    root = tmp_path / "p"
    _write_project(
        root,
        "version: 1\noutput: build/report.docx\nsources: [main.md]\n",
        {"main.md": "# Report\n"},
    )
    first = build_project(root)
    first.output_path.write_bytes(b"not-a-docx")
    rebuilt = build_project(root)
    assert rebuilt.built and not rebuilt.skipped
    assert rebuilt.output_sha256 == first.output_sha256
