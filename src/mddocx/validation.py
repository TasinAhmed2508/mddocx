from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile, ZipFile

from lxml import etree

from .config import ValidationConfig
from .diagnostics import Diagnostic, MddocxError
from .inspection import inspect_docx_bytes

_REQUIRED_PARTS = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}


def validate_docx_package(blob: bytes, config: ValidationConfig) -> None:
    if not config.validate_output:
        return
    try:
        with ZipFile(BytesIO(blob), "r") as archive:
            names = archive.namelist()
            if len(names) > config.max_package_parts:
                _fail("DOCX402", f"DOCX contains more than {config.max_package_parts} package parts.")
            missing = sorted(_REQUIRED_PARTS.difference(names))
            if missing:
                _fail("DOCX403", "DOCX is missing required package parts: " + ", ".join(missing))
            total_uncompressed = sum(info.file_size for info in archive.infolist())
            if total_uncompressed > config.max_total_uncompressed_size:
                _fail("DOCX407", f"DOCX uncompressed package size exceeds {config.max_total_uncompressed_size} bytes.")
            if not config.allow_macros and any(name.lower().endswith("vbaproject.bin") for name in names):
                _fail("DOCX408", "Macro-enabled content is not permitted in generated DOCX output.")
            for name in names:
                normalized = name.replace("\\", "/")
                if normalized.startswith("/") or ".." in normalized.split("/"):
                    _fail("DOCX404", f"Unsafe package part path: {name}")
                if not (name.endswith(".xml") or name.endswith(".rels")):
                    continue
                info = archive.getinfo(name)
                if info.file_size > config.max_xml_part_size:
                    _fail("DOCX405", f"XML package part exceeds configured limit: {name}")
                data = archive.read(name)
                parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
                try:
                    etree.fromstring(data, parser=parser)
                except (etree.XMLSyntaxError, ValueError) as exc:
                    raise MddocxError(
                        Diagnostic("error", "DOCX406", f"Invalid XML package part: {name}")
                    ) from exc

        inspection = inspect_docx_bytes(blob)
        if inspection.duplicate_parts:
            _fail("DOCX409", "DOCX contains duplicate package part names: " + ", ".join(inspection.duplicate_parts[:5]))
        if config.validate_relationships and inspection.broken_relationships:
            _fail("DOCX410", "DOCX contains broken internal relationships: " + "; ".join(inspection.broken_relationships[:3]))
        if config.validate_math_structure and inspection.empty_nary_operands:
            _fail("DOCX411", f"DOCX contains {inspection.empty_nary_operands} n-ary math operators with empty operands.")
        if config.validate_math_structure and inspection.radicals_missing_degree:
            _fail("DOCX412", f"DOCX contains {inspection.radicals_missing_degree} malformed radical structures.")
        if config.detect_placeholder_chars and inspection.suspicious_placeholder_chars:
            _fail("DOCX413", "DOCX contains suspicious replacement/placeholder characters.")
        if config.validate_relationships and inspection.dangling_internal_hyperlinks:
            _fail("DOCX414", f"DOCX contains {inspection.dangling_internal_hyperlinks} dangling internal hyperlinks.")
        if config.validate_relationships and inspection.dangling_ref_fields:
            _fail("DOCX415", f"DOCX contains {inspection.dangling_ref_fields} REF fields targeting missing bookmarks.")
        if inspection.duplicate_bookmark_names:
            _fail("DOCX416", f"DOCX contains {inspection.duplicate_bookmark_names} duplicate bookmark names.")
        if inspection.comment_references != inspection.comment_definitions:
            _fail("DOCX417", "DOCX comment references and definitions are inconsistent.")
        if inspection.duplicate_relationship_ids:
            _fail("DOCX418", f"DOCX contains {inspection.duplicate_relationship_ids} duplicate relationship IDs.")
        if inspection.duplicate_drawing_ids:
            _fail("DOCX419", f"DOCX contains {inspection.duplicate_drawing_ids} duplicate drawing object IDs.")
        if inspection.duplicate_note_ids:
            _fail("DOCX420", f"DOCX contains {inspection.duplicate_note_ids} duplicate footnote/endnote IDs.")
        if inspection.chart_relationship_issues:
            _fail("DOCX421", f"DOCX contains {inspection.chart_relationship_issues} invalid chart/workbook relationship sets.")
    except MddocxError:
        raise
    except (BadZipFile, OSError, ValueError) as exc:
        raise MddocxError(Diagnostic("error", "DOCX401", "Generated output is not a valid DOCX ZIP package.")) from exc


def _fail(code: str, message: str) -> None:
    raise MddocxError(Diagnostic("error", code, message))
