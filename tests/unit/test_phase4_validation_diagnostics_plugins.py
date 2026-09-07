from __future__ import annotations

import json

import pytest

from mddocx import MarkdownWord, PluginConfig, RenderConfig, validate_docx_package
from mddocx.config import ValidationConfig
from mddocx.diagnostics import Diagnostic, DiagnosticReporter, MddocxError
from mddocx.extensions.discovery import load_entrypoint_extensions


def test_validator_rejects_non_docx_bytes():
    with pytest.raises(MddocxError) as exc:
        validate_docx_package(b"not a zip", ValidationConfig())
    assert exc.value.diagnostic.code == "DOCX401"


def test_sarif_diagnostics_are_structured():
    reporter = DiagnosticReporter()
    reporter.warn("TEST401", "Example warning", "sample.md", 7)
    data = json.loads(reporter.to_sarif())
    assert data["version"] == "2.1.0"
    result = data["runs"][0]["results"][0]
    assert result["ruleId"] == "TEST401"
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 7


def test_missing_explicit_plugin_fails_without_importing_random_plugins():
    with pytest.raises(MddocxError) as exc:
        load_entrypoint_extensions(("definitely-not-installed-mddocx-plugin",))
    assert exc.value.diagnostic.code == "PLUGIN401"


def test_plugin_config_is_opt_in():
    converter = MarkdownWord(RenderConfig(plugins=PluginConfig()))
    blob = converter.render_string("# No plugins\n")
    assert blob.startswith(b"PK")
