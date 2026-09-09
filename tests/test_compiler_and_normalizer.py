from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from mddocx import Compiler, LayoutStageResult
from mddocx.ast.base import Document, SourcePosition
from mddocx.ast.block import Heading, MathBlock, Paragraph, Table, TableCell, TableRow
from mddocx.ast.inline import Text
from mddocx.ast.codec import document_from_json, document_to_json
from mddocx.diagnostics import DiagnosticReporter, MddocxError
from mddocx.normalize import Normalizer


def test_normalizer_coalesces_text_and_normalizes_math_sources():
    document = Document(
        children=[
            Paragraph(children=[Text(text="one"), Text(text=""), Text(text=" two")]),
            MathBlock(source_text="  x\r\n+ y  "),
        ]
    )

    normalized = Normalizer().normalize(document)

    assert normalized.children[0].children == [Text(text="one two")]
    assert normalized.children[1].source_text == "x\n+ y"


def test_normalizer_assigns_unique_stable_heading_identifiers():
    document = Document(
        children=[
            Heading(level=1, children=[Text(text="Repeated Heading")]),
            Heading(level=2, children=[Text(text="Repeated Heading")]),
        ]
    )

    normalized = Normalizer().normalize(document)

    assert [node.identifier for node in normalized.children] == [
        "repeated-heading",
        "repeated-heading-2",
    ]


def test_normalizer_reports_duplicate_ids_and_irregular_tables():
    reporter = DiagnosticReporter()
    source = SourcePosition(file="input.md", line=3, column=1)
    document = Document(
        children=[
            Heading(level=1, children=[Text(text="A")], identifier="same", source=source),
            Heading(level=2, children=[Text(text="B")], identifier="same", source=source),
            Table(
                rows=[
                    TableRow(cells=[TableCell(), TableCell()]),
                    TableRow(cells=[TableCell()]),
                ],
                source=source,
            ),
        ]
    )

    Normalizer(reporter).normalize(document)

    assert {item.code for item in reporter.diagnostics} == {"NORM201", "NORM202"}


def test_normalizer_rejects_invalid_heading_level():
    document = Document(children=[Heading(level=7, children=[Text(text="Invalid")])])

    with pytest.raises(MddocxError, match="Heading level"):
        Normalizer().normalize(document)


def test_compiler_returns_typed_success_result():
    result = Compiler().compile_string("# Report\n\nInline \\(x^2\\).")

    assert result.success
    assert not result.completed_with_fallbacks
    assert result.output_bytes.startswith(b"PK")
    assert result.stats.output_bytes == len(result.output_bytes)
    with ZipFile(BytesIO(result.output_bytes)) as package:
        assert package.testzip() is None


def test_compiler_exposes_parse_normalize_plan_and_render_stages():
    compiler = Compiler()
    parsed = compiler.parse_string(r"# Stage" "\n\n" r"Text \(x^2\).", source_file="stage.md")
    normalized = compiler.normalize(parsed.document)
    planned = compiler.plan(normalized.document)
    rendered = compiler.render(planned.document)
    checked = compiler.check_string("# Check\n\nValid.")

    assert parsed.document.children[0].source.file == "stage.md"
    assert normalized.success
    assert normalized.semantic_index is not None
    assert normalized.semantic_index.heading_ids == ("stage",)
    assert isinstance(planned, LayoutStageResult)
    assert planned.success
    assert rendered.success and rendered.output_bytes.startswith(b"PK")
    assert checked.success


def test_semantic_index_records_targets_citations_notes_and_unresolved_references():
    markdown = """# Target {#sec-target}

See @sec-target and @sec-missing [@source]. A note.[^known] Missing.[^absent]

[^known]: Defined.
"""
    result = Compiler().check_string(markdown)
    index = result.semantic_index

    assert index is not None
    assert index.heading_ids == ("sec-target",)
    assert index.citation_keys == ("source",)
    assert index.note_labels == ("known",)
    assert index.unresolved_crossrefs == ("sec-missing",)
    assert index.unresolved_notes == ("absent",)


def test_compiler_file_result_includes_output_path(tmp_path: Path):
    source = tmp_path / "source.md"
    output = tmp_path / "output.docx"
    source.write_text("$$\\unknownprovidercommand{x}$$", encoding="utf-8")

    result = Compiler().compile_file(source, output)

    assert result.success
    assert result.completed_with_fallbacks
    assert result.output_path == output
    assert result.output_bytes == output.read_bytes()
    assert result.diagnostics[0].code == "MATH201"

    checked = Compiler().check_file(source)
    assert checked.success
    assert checked.document.source.file == str(source)
    acquired = Compiler().acquire_file(source)
    assert acquired.source_file == str(source)
    assert acquired.base_dir == tmp_path


def test_ast_serialization_is_versioned_and_rejects_incompatible_cache():
    document = Document(children=[Paragraph(children=[Text(text="cached")])])
    encoded = document_to_json(document)

    assert document_from_json(encoded) == document
    with pytest.raises(ValueError, match="schema version"):
        document_from_json(encoded.replace('"version":2', '"version":999'))
    with pytest.raises(ValueError, match="schema identifier"):
        document_from_json('{"__node__":"Document","children":[]}')
