from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib.util
from importlib import metadata
import json
import os
import platform
import shutil
import sys
import tempfile


@dataclass(slots=True)
class DoctorReport:
    python: str
    platform: str
    machine: str
    mddocx_version: str
    dependencies: dict[str, str] = field(default_factory=dict)
    executables: dict[str, str | None] = field(default_factory=dict)
    temp_directory_writable: bool = False

    @property
    def visual_qa_ready(self) -> bool:
        return bool((self.executables.get("libreoffice") or self.executables.get("soffice")) and self.executables.get("pdftoppm"))

    @property
    def ok(self) -> bool:
        required = ("markdown-it-py", "python-docx", "lxml", "Pillow", "Pygments", "PyYAML", "openpyxl", "prompt-toolkit")
        return sys.version_info >= (3, 11) and self.temp_directory_writable and all(self.dependencies.get(name) not in {None, "missing"} for name in required)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["visual_qa_ready"] = self.visual_qa_ready
        payload["ok"] = self.ok
        return payload

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)

    def to_text(self) -> str:
        lines = [
            f"mddocx doctor: {'PASS' if self.ok else 'ISSUES'}",
            f"mddocx: {self.mddocx_version}",
            f"Python: {self.python}",
            f"Platform: {self.platform} ({self.machine})",
            f"Temporary directory writable: {'yes' if self.temp_directory_writable else 'no'}",
            "Dependencies:",
        ]
        for name, value in self.dependencies.items():
            lines.append(f"  {name}: {value}")
        lines.append("External QA tools:")
        for name, value in self.executables.items():
            lines.append(f"  {name}: {value or 'not found'}")
        lines.append(f"Visual DOCX regression ready: {'yes' if self.visual_qa_ready else 'no'}")
        if not self.visual_qa_ready:
            lines.append("  Visual QA needs LibreOffice/soffice plus pdftoppm; document conversion itself does not.")
        return "\n".join(lines)


def run_doctor() -> DoctorReport:
    dependency_packages = {
        "markdown-it-py": "markdown-it-py",
        "python-docx": "python-docx",
        "lxml": "lxml",
        "Pillow": "Pillow",
        "Pygments": "Pygments",
        "CairoSVG": "CairoSVG",
        "PyYAML": "PyYAML",
        "latex2mathml": "latex2mathml",
        "openpyxl": "openpyxl",
        "prompt-toolkit": "prompt-toolkit",
    }
    deps: dict[str, str] = {}
    for label, dist in dependency_packages.items():
        try:
            deps[label] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            # Some development/source environments can import a package without
            # dist metadata being visible, so distinguish that from truly missing.
            module_name = {
                "markdown-it-py": "markdown_it",
                "python-docx": "docx",
                "Pillow": "PIL",
                "Pygments": "pygments",
                "CairoSVG": "cairosvg",
                "PyYAML": "yaml",
                "prompt-toolkit": "prompt_toolkit",
            }.get(label, label)
            deps[label] = "available (version unknown)" if importlib.util.find_spec(module_name) else "missing"

    try:
        from . import __version__ as mddocx_version
    except (ImportError, AttributeError):
        try:
            mddocx_version = metadata.version("mddocx")
        except metadata.PackageNotFoundError:
            mddocx_version = "source checkout"

    temp_ok = False
    try:
        with tempfile.NamedTemporaryFile(prefix="mddocx-doctor-", delete=True) as handle:
            handle.write(b"ok")
            handle.flush()
        temp_ok = True
    except OSError:
        temp_ok = False

    return DoctorReport(
        python=platform.python_version(),
        platform=f"{platform.system()} {platform.release()}",
        machine=platform.machine(),
        mddocx_version=mddocx_version,
        dependencies=deps,
        executables={name: shutil.which(name) for name in ("libreoffice", "soffice", "pdftoppm")},
        temp_directory_writable=temp_ok,
    )
