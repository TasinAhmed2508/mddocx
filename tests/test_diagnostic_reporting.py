import json

from mddocx import __version__
from mddocx.diagnostics import DiagnosticReporter


def test_sarif_identifies_the_current_distribution_and_preserves_version_overrides():
    reporter = DiagnosticReporter()
    reporter.warn("NORM201", "Example warning", "report.md", 3)
    report = json.loads(reporter.to_sarif())
    driver = report["runs"][0]["tool"]["driver"]
    assert driver["version"] == __version__
    assert driver["informationUri"] == "https://pypi.org/project/mddocx-native/"
    override = json.loads(reporter.to_sarif(tool_version="custom-build"))
    assert override["runs"][0]["tool"]["driver"]["version"] == "custom-build"
