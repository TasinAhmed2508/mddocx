from __future__ import annotations

from dataclasses import dataclass, field
import json
from .codes import Diagnostic, MddocxError


@dataclass
class DiagnosticReporter:
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def emit(self, diagnostic: Diagnostic) -> None:
        self.diagnostics.append(diagnostic)
        if diagnostic.severity == "error":
            raise MddocxError(diagnostic)

    def warn(
        self, code: str, message: str, source_file: str | None = None, line: int | None = None
    ) -> None:
        self.diagnostics.append(Diagnostic("warning", code, message, source_file, line))

    def info(
        self, code: str, message: str, source_file: str | None = None, line: int | None = None
    ) -> None:
        self.diagnostics.append(Diagnostic("info", code, message, source_file, line))

    def summary(self) -> dict[str, int]:
        counts = {"error": 0, "warning": 0, "info": 0}
        for diagnostic in self.diagnostics:
            counts[diagnostic.severity] += 1
        counts["total"] = len(self.diagnostics)
        return counts

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(
            [d.to_dict() for d in self.diagnostics], ensure_ascii=False, indent=indent
        )

    def to_sarif(self, indent: int | None = 2, tool_version: str = "0.8.0") -> str:
        results = []
        rules: dict[str, dict[str, object]] = {}
        level_map = {"error": "error", "warning": "warning", "info": "note"}
        for diagnostic in self.diagnostics:
            rules.setdefault(
                diagnostic.code,
                {"id": diagnostic.code, "shortDescription": {"text": diagnostic.code}},
            )
            result: dict[str, object] = {
                "ruleId": diagnostic.code,
                "level": level_map[diagnostic.severity],
                "message": {"text": diagnostic.message},
            }
            if diagnostic.source_file:
                region: dict[str, int] = {}
                if diagnostic.line is not None:
                    region["startLine"] = diagnostic.line
                location: dict[str, object] = {
                    "physicalLocation": {
                        "artifactLocation": {"uri": diagnostic.source_file},
                    }
                }
                if region:
                    location["physicalLocation"]["region"] = region  # type: ignore[index]
                result["locations"] = [location]
            results.append(result)
        payload = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "mddocx",
                            "version": tool_version,
                            "informationUri": "https://pypi.org/project/mddocx/",
                            "rules": list(rules.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=indent)
