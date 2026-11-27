from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from zipfile import ZipFile

from PIL import Image
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


def test_project_cache_does_not_reuse_explicit_config_output(tmp_path: Path):
    manifest = load_project(init_project(tmp_path / "report"))
    default = build_project(manifest)
    custom = build_project(manifest, config=RenderConfig(title="Caller title"))
    restored = build_project(manifest)

    assert custom.built and custom.output_sha256 != default.output_sha256
    assert restored.built
    assert build_project(manifest).skipped


def test_project_rebuilds_cache_from_before_decoded_image_paths(tmp_path, monkeypatch):
    import mddocx.project as project

    manifest = load_project(init_project(tmp_path / "report"))
    with monkeypatch.context() as legacy:
        legacy.setattr(project, "_PROJECT_ENGINE_VERSION", "mddocx-project-v24")
        old = build_project(manifest)
        assert build_project(manifest).skipped
    updated = build_project(manifest)
    assert updated.built and updated.fingerprint != old.fingerprint
    assert build_project(manifest).skipped


def test_project_rebuilds_when_cache_state_is_not_a_mapping(tmp_path: Path):
    manifest = load_project(init_project(tmp_path / "report"))
    build_project(manifest)
    state_path = manifest.root / ".mddocx" / "build-state.json"
    state_path.write_text("[]", encoding="utf-8")

    assert build_project(manifest).built


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


@pytest.mark.parametrize("filename", ["chart example.png", "বাংলা %20 ছবি.png"])
def test_project_includes_rebase_encoded_images_and_rebuild_when_they_change(tmp_path, filename):
    chapter = tmp_path / "chapters"
    chapter.mkdir()
    asset = chapter / filename
    Image.new("RGB", (12, 8), "navy").save(asset)
    (chapter / "part.md").write_text(f"![Chart]({quote(filename)})", encoding="utf-8")
    (tmp_path / "main.md").write_text("@include chapters/part.md", encoding="utf-8")
    (tmp_path / "mddocx.yml").write_text("version: 1\nsources: [main.md]\n", encoding="utf-8")
    compiled = compile_project(tmp_path)
    assert compiled.document.children[0].src == quote("chapters/" + filename)
    assert asset in compiled.dependencies
    first = build_project(tmp_path)
    assert first.built and not first.diagnostics
    with ZipFile(first.output_path) as package:
        media = [name for name in package.namelist() if name.startswith("word/media/")]
        assert len(media) == 1
        assert package.read(media[0]) == asset.read_bytes()
    assert build_project(tmp_path).skipped
    Image.new("RGB", (12, 8), "red").save(asset)
    updated = build_project(tmp_path)
    assert updated.built and updated.output_sha256 != first.output_sha256
    assert asset in updated.dependencies
    assert build_project(tmp_path).skipped


def test_project_rejects_invalid_decoded_image_paths_without_replacing_output(tmp_path):
    source = tmp_path / "main.md"
    source.write_text("Before.\n\n![Bad](bad%00.png)", encoding="utf-8")
    (tmp_path / "mddocx.yml").write_text(
        "version: 1\nsources: [main.md]\noutput: previous.docx\n", encoding="utf-8"
    )
    output = tmp_path / "previous.docx"
    output.write_bytes(b"previous document")
    with pytest.raises(MddocxError) as caught:
        build_project(tmp_path)
    assert caught.value.diagnostic.code == "PROJECT806"
    assert caught.value.diagnostic.source_file == str(source)
    assert caught.value.diagnostic.line == 3
    assert output.read_bytes() == b"previous document"


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


def test_project_includes_use_the_markdown_input_limit(tmp_path: Path):
    (tmp_path / "main.md").write_text("@include chapter.md", encoding="utf-8")
    (tmp_path / "chapter.md").write_text("x" * 257, encoding="utf-8")
    (tmp_path / "mddocx.yml").write_text("version: 1\nsources: [main.md]\n", encoding="utf-8")
    config = RenderConfig()
    config.limits.max_input_bytes = 256

    with pytest.raises(MddocxError, match="LIMIT401"):
        compile_project(tmp_path, config=config)


def test_explicit_project_config_overrides_manifest_render_values(tmp_path: Path):
    project_file = init_project(tmp_path / "precedence")
    manifest = load_project(project_file)
    explicit = RenderConfig(title="Caller title", theme="academic")

    compiler = ProjectCompiler(manifest, explicit)

    assert compiler.config.title == "Caller title"
    assert compiler.config.theme == "academic"


def test_project_render_precedence_and_recovery_preserve_manifest_context(tmp_path: Path):
    from docx import Document

    source = tmp_path / "main.md"
    source.write_text("---\ntitle: From source\n---\n\nBody.", encoding="utf-8")
    manifest = tmp_path / "mddocx.yml"
    manifest.write_text(
        "version: 1\nsources: [main.md]\nrender:\n  title: From manifest\n  header: Common header\n",
        encoding="utf-8",
    )
    result = build_project(manifest, recover=True)
    output = Document(result.output_path)
    assert output.core_properties.title == "From source"
    assert output.sections[0].header.paragraphs[0].text == "Common header"
    result = build_project(manifest, RenderConfig(title="From caller"))
    output = Document(result.output_path)
    assert output.core_properties.title == "From caller"
    assert output.sections[0].header.paragraphs[0].text == "Common header"


@pytest.mark.parametrize(
    ("setting", "code"),
    [
        ("project:\n  max_include_depth: [invalid]", "PROJECT828"),
        ("watch:\n  interval: [invalid]", "PROJECT829"),
        ("watch:\n  interval: .inf", "PROJECT829"),
        ("watch:\n  interval: .nan", "PROJECT829"),
    ],
)
def test_invalid_numeric_project_settings_have_a_clear_diagnostic(
    tmp_path: Path, setting: str, code: str
):
    (tmp_path / "main.md").write_text("# Report\n", encoding="utf-8")
    (tmp_path / "mddocx.yml").write_text(
        f"version: 1\nsources: [main.md]\n{setting}\n", encoding="utf-8"
    )

    with pytest.raises(MddocxError, match=code):
        load_project(tmp_path)
