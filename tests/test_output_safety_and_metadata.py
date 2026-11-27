from __future__ import annotations

import os
import json
from pathlib import Path

from docx import Document
from PIL import Image
import pytest

from mddocx import Compiler, MarkdownWord, RenderConfig, build_project, render_many
from mddocx.cli import main
from mddocx.diagnostics import MddocxError
from mddocx.interactive import history
from mddocx.interactive.shell import InteractiveConsole
from mddocx.output import write_docx


@pytest.mark.parametrize("value", ["[wrong]", "{wrong: value}"])
def test_invalid_front_matter_value_types_do_not_crash_conversion(value: str):
    fields = (
        "page_size",
        "orientation",
        "rtl",
        "notes",
        "citation_style",
        "equation_numbering",
        "caption_numbering",
    )
    front_matter = "\n".join(f"{field}: {value}" for field in fields)

    blob = MarkdownWord().render_string(f"---\n{front_matter}\n---\n\n# Preserved body\n")

    from io import BytesIO

    assert "Preserved body" in "\n".join(p.text for p in Document(BytesIO(blob)).paragraphs)


def test_project_ignores_invalid_enum_types_in_render_settings(tmp_path: Path):
    (tmp_path / "chapter.md").write_text("# Chapter\n", encoding="utf-8")
    (tmp_path / "mddocx.yml").write_text(
        "version: 1\noutput: result.docx\nsources: [chapter.md]\n"
        "render:\n  page_size: [A4]\n  ai_metadata: {mode: auto}\n",
        encoding="utf-8",
    )

    result = build_project(tmp_path)

    assert result.built
    assert (tmp_path / "result.docx").read_bytes().startswith(b"PK")


@pytest.mark.parametrize("field", ["size", "orientation"])
def test_invalid_api_config_types_report_a_diagnostic(field: str):
    config = RenderConfig()
    setattr(config.page, field, [])

    with pytest.raises(MddocxError, match="CONFIG401"):
        MarkdownWord(config)


def test_same_input_and_output_are_rejected_by_api_and_cli(tmp_path: Path, capsys):
    source = tmp_path / "report.md"
    original = "# Do not overwrite\n"
    source.write_text(original, encoding="utf-8")

    with pytest.raises(MddocxError, match="OUTPUT401"):
        MarkdownWord().render_file(source, source)
    assert source.read_text(encoding="utf-8") == original

    assert main([str(source), "-o", str(source)]) == 2
    assert "OUTPUT401" in capsys.readouterr().err
    assert source.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("diagnostics_target", ["source", "output", "same-report"])
def test_diagnostics_cannot_overwrite_documents_or_each_other(
    tmp_path: Path, capsys, diagnostics_target: str
):
    source = tmp_path / "report.md"
    source.write_text("# Original\n", encoding="utf-8")
    output = tmp_path / "result.docx"
    output.write_bytes(b"previous document")
    target = {"source": source, "output": output, "same-report": tmp_path / "report.json"}[
        diagnostics_target
    ]
    args = [str(source), "-o", str(output), "--diagnostics-json", str(target)]
    if diagnostics_target == "same-report":
        args += ["--diagnostics-sarif", str(target)]

    assert main(args) == 2
    assert "OUTPUT401" in capsys.readouterr().err
    assert source.read_text(encoding="utf-8") == "# Original\n"
    assert output.read_bytes() == b"previous document"


def test_batch_reports_fallback_warnings(tmp_path: Path, capsys):
    first = tmp_path / "first.md"
    first.write_text("Before.\n\n$$\\unknownprovidercommand{x}$$\n\nAfter.\n", encoding="utf-8")
    second = tmp_path / "second.md"
    second.write_text("# Second\n", encoding="utf-8")
    output_dir = tmp_path / "output"

    assert main([str(first), str(second), "--output-dir", str(output_dir)]) == 0
    captured = capsys.readouterr()
    assert "MATH201" in captured.err
    assert (output_dir / "first.docx").is_file()
    assert (output_dir / "second.docx").is_file()


def test_batch_does_not_overwrite_inputs(tmp_path: Path):
    source = tmp_path / "report.md"
    source.write_text("# Source\n", encoding="utf-8")
    other_source = tmp_path / "report.docx"
    other_source.write_text("# Other source\n", encoding="utf-8")

    results = render_many([source, other_source], tmp_path)

    assert any(not result.ok and "OUTPUT401" in result.error for result in results)
    assert source.read_text(encoding="utf-8") == "# Source\n"
    assert other_source.read_text(encoding="utf-8") == "# Other source\n"


@pytest.mark.parametrize("jobs", [1, 2])
@pytest.mark.parametrize("reference_first", [False, True])
def test_batch_does_not_overwrite_another_documents_image(tmp_path, jobs, reference_first):
    asset = tmp_path / "middle.docx"
    Image.new("RGB", (12, 8), "navy").save(asset, format="PNG")
    original = asset.read_bytes()
    producer = tmp_path / "middle.md"
    producer.write_text("# Report\n\nText.", encoding="utf-8")
    consumer = tmp_path / ("a.md" if reference_first else "z.md")
    consumer.write_text("![Keep the image](middle.docx)", encoding="utf-8")
    results = render_many([producer, consumer], tmp_path, jobs=jobs)
    by_input = {item.input_path: item for item in results}
    assert not by_input[producer].ok
    assert [item.code for item in by_input[producer].diagnostics] == ["OUTPUT401"]
    assert asset.read_bytes() == original
    assert by_input[consumer].ok and not by_input[consumer].diagnostics
    assert len(Document(by_input[consumer].output_path).inline_shapes) == 1


@pytest.mark.parametrize("jobs", [1, 2])
def test_batch_protects_dependencies_added_by_document_transforms(tmp_path, jobs):
    from mddocx.ast.block import ImageBlock

    class AddImage:
        def transform_document(self, document):
            if document.children[0].children[0].text == "Consumer":
                document.children.append(ImageBlock(src="a.docx", alt="Protected image"))

    asset = tmp_path / "a.docx"
    Image.new("RGB", (12, 8), "navy").save(asset, format="PNG")
    original = asset.read_bytes()
    producer, consumer = tmp_path / "a.md", tmp_path / "b.md"
    producer.write_text("# Producer", encoding="utf-8")
    consumer.write_text("# Consumer", encoding="utf-8")
    results = render_many(
        [producer, consumer], tmp_path, RenderConfig(extensions=(AddImage(),)), jobs=jobs
    )
    assert not results[0].ok and results[0].diagnostics[0].code == "OUTPUT401"
    assert results[1].ok
    assert asset.read_bytes() == original
    assert len(Document(results[1].output_path).inline_shapes) == 1


def test_batch_fail_fast_checks_future_assets_before_rendering(tmp_path):
    asset = tmp_path / "a.docx"
    Image.new("RGB", (12, 8), "navy").save(asset, format="PNG")
    original = asset.read_bytes()
    producer, consumer = tmp_path / "a.md", tmp_path / "b.md"
    producer.write_text("# Producer", encoding="utf-8")
    consumer.write_text("![Protected](a.docx)", encoding="utf-8")
    results = render_many([producer, consumer], tmp_path, fail_fast=True, jobs=4)
    assert len(results) == 1 and not results[0].ok
    assert results[0].diagnostics[0].code == "OUTPUT401"
    assert asset.read_bytes() == original
    assert not consumer.with_suffix(".docx").exists()


def test_batch_reports_invalid_configuration_per_file(tmp_path):
    source = tmp_path / "report.md"
    source.write_text("# Report", encoding="utf-8")
    config = RenderConfig()
    config.page.orientation = "invalid"
    results = render_many([source], tmp_path, config)
    assert len(results) == 1 and not results[0].ok
    assert results[0].diagnostics[0].code == "CONFIG401"


def test_cli_parallel_batch_protects_encoded_image_paths(tmp_path, capsys):
    asset = tmp_path / "a report.docx"
    Image.new("RGB", (12, 8), "navy").save(asset, format="PNG")
    original = asset.read_bytes()
    producer, consumer = tmp_path / "a report.md", tmp_path / "b.md"
    producer.write_text("# Producer", encoding="utf-8")
    consumer.write_text("![Protected](a%20report.docx)", encoding="utf-8")
    assert (
        main([str(producer), str(consumer), "--output-dir", str(tmp_path), "--jobs", "2", "--json"])
        == 2
    )
    report = json.loads(capsys.readouterr().out)
    assert [item["status"] for item in report["results"]] == ["failed", "ok"]
    assert report["results"][0]["diagnostics"][0]["code"] == "OUTPUT401"
    assert asset.read_bytes() == original
    assert len(Document(consumer.with_suffix(".docx")).inline_shapes) == 1


@pytest.mark.parametrize("alias", ["hardlink", "symlink"])
def test_batch_protects_output_aliases_of_another_documents_image(tmp_path, alias):
    asset = tmp_path / "photo.png"
    Image.new("RGB", (12, 8), "navy").save(asset)
    original = asset.read_bytes()
    target = tmp_path / "a.docx"
    try:
        if alias == "hardlink":
            os.link(asset, target)
        else:
            target.symlink_to(asset)
    except OSError:
        pytest.skip(f"{alias} is not available on this filesystem")
    producer, consumer = tmp_path / "a.md", tmp_path / "b.md"
    producer.write_text("# Producer", encoding="utf-8")
    consumer.write_text("![Protected](photo.png)", encoding="utf-8")
    results = render_many([producer, consumer], tmp_path, jobs=2)
    assert not results[0].ok and results[0].diagnostics[0].code == "OUTPUT401"
    assert results[1].ok
    assert asset.read_bytes() == original
    assert target.samefile(asset)


def test_interactive_render_reports_fallback_warnings(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "state_directory", lambda: tmp_path / "state")
    source = tmp_path / "report.md"
    source.write_text("Before.\n\n$$\\unknownprovidercommand{x}$$\n\nAfter.\n", encoding="utf-8")
    messages: list[str] = []
    console = InteractiveConsole(tmp_path, writer=messages.append)

    assert console.cmd_render([str(source), "-o", str(tmp_path / "report.docx")]) == 0

    assert any("MATH201" in message for message in messages)
    assert any(item.get("code") == "MATH201" for item in console.last_diagnostics)


def test_hardlinked_output_does_not_replace_input(tmp_path: Path):
    source = tmp_path / "report.md"
    alias = tmp_path / "output.docx"
    source.write_text("# Original\n", encoding="utf-8")
    try:
        os.link(source, alias)
    except OSError as exc:
        pytest.skip(f"Hard links unavailable: {exc}")

    with pytest.raises(MddocxError, match="OUTPUT401"):
        MarkdownWord().render_file(source, alias)

    assert source.read_text(encoding="utf-8") == "# Original\n"


def test_template_is_not_overwritten(tmp_path: Path):
    template = tmp_path / "template.docx"
    Document().save(template)
    original = template.read_bytes()
    source = tmp_path / "report.md"
    source.write_text("# Report\n", encoding="utf-8")

    with pytest.raises(MddocxError, match="OUTPUT401"):
        MarkdownWord(RenderConfig(template=template)).render_file(source, template)

    assert template.read_bytes() == original


def test_diagnostics_do_not_overwrite_template(tmp_path: Path, capsys):
    template = tmp_path / "template.docx"
    Document().save(template)
    original = template.read_bytes()
    source = tmp_path / "report.md"
    source.write_text("# Report\n", encoding="utf-8")

    assert (
        main([str(source), "--template", str(template), "--diagnostics-json", str(template)]) == 2
    )
    assert "OUTPUT401" in capsys.readouterr().err
    assert template.read_bytes() == original


def test_project_cannot_overwrite_relative_template(tmp_path: Path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.md").write_text("# Report\n", encoding="utf-8")
    (root / "mddocx.yml").write_text(
        "version: 1\noutput: result.docx\nsources: [main.md]\n", encoding="utf-8"
    )
    template = tmp_path / "template.docx"
    Document().save(template)
    original = template.read_bytes()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(MddocxError, match="OUTPUT401"):
        build_project(root, RenderConfig(template=Path("template.docx")), output=template)

    assert template.read_bytes() == original


@pytest.mark.parametrize("name", ["main.md", "include.md", "mddocx.yml"])
def test_project_output_cannot_overwrite_project_inputs(tmp_path: Path, name: str):
    (tmp_path / "main.md").write_text("# Main\n\n@include include.md\n", encoding="utf-8")
    (tmp_path / "include.md").write_text("# Include\n", encoding="utf-8")
    (tmp_path / "mddocx.yml").write_text(
        "version: 1\noutput: result.docx\nsources: [main.md]\n", encoding="utf-8"
    )
    target = tmp_path / name
    original = target.read_bytes()

    with pytest.raises(MddocxError, match="OUTPUT401"):
        build_project(tmp_path, output=target, force=True)

    assert target.read_bytes() == original


def test_failed_replacement_preserves_existing_output(tmp_path: Path, monkeypatch):
    target = tmp_path / "output.docx"
    target.write_bytes(b"previous document")

    def fail_replace(self, target):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replacement failure"):
        write_docx(target, b"new document")

    assert target.read_bytes() == b"previous document"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["output.docx"]


def test_failed_write_preserves_existing_output(tmp_path: Path, monkeypatch):
    target = tmp_path / "output.docx"
    target.write_bytes(b"previous document")
    original_open = Path.open

    class IncompleteWrite:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, data):
            self.stream.write(data[:3])
            raise OSError("simulated disk failure")

    def fail_during_write(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return IncompleteWrite(stream) if path.name.endswith(".tmp") else stream

    monkeypatch.setattr(Path, "open", fail_during_write)
    with pytest.raises(OSError, match="simulated disk failure"):
        write_docx(target, b"new document")

    assert target.read_bytes() == b"previous document"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["output.docx"]


def test_strict_note_math_preserves_existing_output(tmp_path):
    source = tmp_path / "report.md"
    source.write_text(
        "Review.[^note]\n\n[^note]: An unknown command $\\missingnotecommand{x}$.\n",
        encoding="utf-8",
    )
    target = source.with_suffix(".docx")
    target.write_bytes(b"previous document")
    config = RenderConfig()
    config.math_failure.mode = "error"

    with pytest.raises(MddocxError) as caught:
        Compiler(config).compile_file(source, target)

    diagnostic = caught.value.diagnostic
    assert (diagnostic.code, diagnostic.line, diagnostic.source_file) == ("MATH201", 3, str(source))
    assert target.read_bytes() == b"previous document"
