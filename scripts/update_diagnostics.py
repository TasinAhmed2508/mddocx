"""Generate the packaged catalog of statically declared diagnostic codes."""

import ast
import json
from pathlib import Path
import re
import sys

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "mddocx"
CATALOG = PACKAGE / "diagnostic-catalog.json"
_CALLS = {"Diagnostic": 1, "warn": 0, "info": 0, "_fail": 0, "_project_error": 0, "_finding": 0}


def catalog():
    entries: dict[str, dict] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        for call in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(call, ast.Call):
                continue
            name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
            index = _CALLS.get(name)
            if index is None or len(call.args) <= index + 1:
                continue
            code = call.args[index]
            if not isinstance(code, ast.Constant) or not isinstance(code.value, str):
                continue
            if not re.fullmatch(r"[A-Z]+[0-9]{3}", code.value):
                continue
            severity = {"info": "info", "warn": "warning", "_finding": "warning"}.get(name, "error")
            if name == "Diagnostic" and isinstance(call.args[0], ast.Constant):
                severity = call.args[0].value
            entry = entries.setdefault(
                code.value, {"code": code.value, "severities": [], "remediations": []}
            )
            if severity not in entry["severities"]:
                entry["severities"].append(severity)
            remediation = next(
                (item.value for item in call.keywords if item.arg == "remediation"), None
            )
            if (
                remediation is None
                and name in {"Diagnostic", "warn", "info"}
                and len(call.args) > index + 4
            ):
                remediation = call.args[index + 4]
            if isinstance(remediation, ast.Constant) and isinstance(remediation.value, str):
                if remediation.value not in entry["remediations"]:
                    entry["remediations"].append(remediation.value)
    return [entries[code] for code in sorted(entries)]


if __name__ == "__main__":
    text = json.dumps(catalog(), indent=2, ensure_ascii=True) + "\n"
    if "--check" in sys.argv:
        if not CATALOG.is_file() or CATALOG.read_text(encoding="utf-8") != text:
            raise SystemExit("Run python scripts/update_diagnostics.py to refresh the catalog.")
    else:
        CATALOG.write_text(text, encoding="utf-8")
