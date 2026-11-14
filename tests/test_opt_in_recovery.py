from io import BytesIO

from docx import Document
import pytest

from mddocx import Compiler, RenderConfig, build_project, inspect_docx_bytes, render_many
from mddocx.cli import main
from mddocx.diagnostics import MddocxError


@pytest.mark.parametrize(
    ("declaration", "code"),
    [
        ("~~~chart\nseries: [\n~~~", "PARSE350"),
        ("~~~chart\nseries: wrong\n~~~", "PARSE351"),
        ("~~~chart\nwidth_mm: wrong\n~~~", "PARSE354"),
        ("~~~chart\nseries: []\n~~~", "CHART203"),
        ("~~~data-table\ncolumns: [Item]\n~~~", "PARSE352"),
        ("~~~mermaid\nunknown type\n~~~", "DIAGRAM201"),
    ],
)
def test_opt_in_recovery_preserves_surrounding_content(declaration, code):
    markdown = f"Before.\n\n{declaration}\n\nAfter."
    strict = RenderConfig()
    strict.mermaid.fallback = "error"
    with pytest.raises(MddocxError, match=code):
        Compiler(strict).compile_string(markdown)
    recovered = Compiler(RenderConfig(recover=True)).compile_string(markdown)
    assert recovered.recovered and recovered.completed_with_fallbacks
    assert inspect_docx_bytes(recovered.output_bytes).ok
    before, placeholder, after = Document(BytesIO(recovered.output_bytes)).paragraphs
    assert before.text == "Before." and after.text == "After."
    assert code in placeholder.text and "Markdown:3" in placeholder.text
    assert placeholder.style.name == "MD Quote"


def test_project_recovery_does_not_become_strict_cache_hit(tmp_path, capsys):
    source = tmp_path / "main.md"
    manifest = tmp_path / "mddocx.yml"
    manifest.write_text("version: 1\nsources: [main.md]\n")
    source.write_text("~~~chart\nseries: broken\n~~~")
    result = build_project(manifest, RenderConfig(recover=True))
    assert result.recovered and result.diagnostics[0].line == 1
    assert not (tmp_path / ".mddocx" / "build-state.json").exists()
    previous = result.output_path.read_bytes()
    assert main(["build", str(manifest)]) == 2
    assert "Previous output left in place" in capsys.readouterr().err
    assert result.output_path.read_bytes() == previous
    assert main(["build", str(manifest), "--recover"]) == 3


def test_batch_status_prioritizes_hard_failures(tmp_path):
    recoverable = tmp_path / "recoverable.md"
    recoverable.write_text("~~~chart\nseries: broken\n~~~")
    fatal = tmp_path / "fatal.md"
    fatal.write_text("---\ntitle: [\n---\n\nBody.")
    output = tmp_path / "output"
    assert main([str(recoverable), "--output-dir", str(output), "--recover"]) == 3
    assert main([str(recoverable), str(fatal), "--output-dir", str(output), "--recover"]) == 2
    reports = render_many([recoverable, fatal], output, RenderConfig(recover=True), jobs=2)
    assert [(item.ok, item.recovered) for item in reports] == [(False, False), (True, True)]


@pytest.mark.parametrize("expanded", [False, True])
def test_project_byte_budget_counts_expansion(tmp_path, expanded):
    manifest = tmp_path / "mddocx.yml"
    manifest.write_text("version: 1\nsources: [main.md]\nvariables:\n  word: " + "x" * 75)
    source = tmp_path / "main.md"
    (tmp_path / "part.md").write_text("a" * 75)
    source.write_text(
        "{{ word }} {{ word }}" if expanded else "@include part.md\n\n@include part.md"
    )
    config = RenderConfig(recover=True)
    config.limits.max_input_bytes = 120
    with pytest.raises(MddocxError, match="LIMIT401"):
        build_project(manifest, config)


def test_parallel_batch_matches_serial_with_duplicate_stems_and_bad_cache(tmp_path):
    files = []
    for name in ("a", "b"):
        folder = tmp_path / name
        folder.mkdir()
        path = folder / "same.md"
        path.write_text(f"# Document {name}")
        files.append(path)
    config = RenderConfig(title="Explicit title")
    config.cache.ast_enabled = True
    config.cache.directory = tmp_path / "cache"
    serial = render_many(files, tmp_path / "serial", config)
    cache_path = next(config.cache.directory.rglob("*.json"))
    cache_path.write_text("invalid JSON")
    parallel = render_many(files, tmp_path / "parallel", config, jobs=2)
    assert [item.input_path for item in serial] == [item.input_path for item in parallel]
    for before, after in zip(serial, parallel, strict=True):
        assert before.ok and after.ok
        assert before.output_path.name == after.output_path.name
        assert before.output_path.read_bytes() == after.output_path.read_bytes()


def test_recovery_does_not_publish_past_resource_policy_failure(tmp_path):
    source = tmp_path / "report.md"
    output = source.with_suffix(".docx")
    output.write_bytes(b"existing")
    source.write_text("~~~chart\nseries: broken\n~~~\n\n![Outside](../outside.png)")
    with pytest.raises(MddocxError, match="RESOURCE203"):
        Compiler(RenderConfig(recover=True)).compile_file(source, output)
    assert output.read_bytes() == b"existing"


def test_recovery_does_not_bypass_diagram_limits():
    config = RenderConfig(recover=True)
    config.mermaid.max_source_chars = 10
    with pytest.raises(MddocxError, match="DIAGRAM201"):
        Compiler(config).compile_string("~~~mermaid\nflowchart TD\nA --> B\n~~~")
