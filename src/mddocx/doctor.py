from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib.util
from importlib import metadata
import json
import platform
import shutil
import sys
import tempfile

# The package-name conflict and its explanation live in the launcher module,
# which stays importable even when another distribution has overwritten the
# mddocx package. Re-exported here because the doctor is where users look.
from mddocx_launcher import conflicting_distributions, install_conflict_message

__all__ = ["DoctorReport", "conflicting_distributions", "install_conflict_message", "run_doctor"]


def svg_support_status() -> str:
    """Report whether SVG conversion can actually run.

    CairoSVG installs as a pure-Python package but needs a native cairo library
    at import time, which is the one optional feature that can be installed and
    still fail, so it is probed rather than reported by version alone.
    """
    try:
        import cairosvg  # noqa: F401
    except ImportError:
        return "not installed; install the images extra for SVG sources"
    except OSError as exc:
        first_line = str(exc).splitlines()[0] if str(exc) else "unknown error"
        return f"unavailable: the native cairo library was not found ({first_line})"
    return "ready"


def math_engine_probe(latex: str = "x^2 + 1") -> tuple[str | None, str | None]:
    """Convert one trivial equation and report the engine that actually ran.

    Engine names are advisory unless they have been exercised, so the doctor
    proves the math pipeline instead of reporting that a file exists.
    """
    try:
        from .math import DefaultMathConverter

        conversion = DefaultMathConverter(cache=False).convert(latex, False)
    except Exception as exc:  # noqa: BLE001 - the report carries the reason
        return None, f"{type(exc).__name__}: {exc}"
    return conversion.engine, None


@dataclass(slots=True)
class DoctorReport:
    python: str
    platform: str
    machine: str
    mddocx_version: str
    dependencies: dict[str, str] = field(default_factory=dict)
    executables: dict[str, str | None] = field(default_factory=dict)
    temp_directory_writable: bool = False
    mathjax_sidecar: str | None = None
    mathjax_protocol: int = 1
    javascript_runtime: str | None = None
    math_engine: str | None = None
    math_engine_error: str | None = None
    install_conflict: tuple[str, ...] = ()
    svg_support: str = "unknown"

    @property
    def mathjax_ready(self) -> bool:
        return self.math_engine == "mathjax-sidecar"

    @property
    def visual_qa_ready(self) -> bool:
        return bool(
            (self.executables.get("libreoffice") or self.executables.get("soffice"))
            and self.executables.get("pdftoppm")
        )

    @property
    def ok(self) -> bool:
        required = (
            "markdown-it-py",
            "python-docx",
            "lxml",
            "Pillow",
            "Pygments",
            "PyYAML",
            "latex2mathml",
            "openpyxl",
            "prompt-toolkit",
        )
        return (
            sys.version_info >= (3, 11)
            and self.temp_directory_writable
            and self.math_engine is not None
            and not self.install_conflict
            and all(self.dependencies.get(name) not in {None, "missing"} for name in required)
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["visual_qa_ready"] = self.visual_qa_ready
        payload["mathjax_ready"] = self.mathjax_ready
        payload["ok"] = self.ok
        return payload

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)

    def to_text(self) -> str:
        lines = [f"mddocx doctor: {'PASS' if self.ok else 'ISSUES'}"]
        if self.install_conflict:
            lines.append("Install conflict detected:")
            lines.extend(
                f"  {line}" for line in install_conflict_message(self.install_conflict).splitlines()
            )
        lines.extend(
            [
                f"mddocx: {self.mddocx_version}",
                f"Python: {self.python}",
                f"Platform: {self.platform} ({self.machine})",
                f"Temporary directory writable: {'yes' if self.temp_directory_writable else 'no'}",
                f"MathJax sidecar: {self.mathjax_sidecar or 'not found'}",
                f"JavaScript runtime: {self.javascript_runtime or 'not found; optional, needed for the MathJax engine'}",
                "Math engine in use: "
                + (
                    self.math_engine
                    if self.math_engine
                    else f"unavailable ({self.math_engine_error or 'no engine available'})"
                ),
                f"MathJax protocol: {self.mathjax_protocol}",
                f"SVG conversion: {self.svg_support}",
                "Dependencies:",
            ]
        )
        for name, value in self.dependencies.items():
            lines.append(f"  {name}: {value}")
        lines.append("External QA tools:")
        for name, value in self.executables.items():
            lines.append(f"  {name}: {value or 'not found'}")
        lines.append(f"Visual DOCX regression ready: {'yes' if self.visual_qa_ready else 'no'}")
        if not self.visual_qa_ready:
            lines.append(
                "  Visual QA needs LibreOffice/soffice plus pdftoppm; document conversion itself does not."
            )
        return "\n".join(lines)


def run_doctor() -> DoctorReport:
    from .math.sidecar import MathJaxSidecar

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
            deps[label] = (
                "available (version unknown)"
                if importlib.util.find_spec(module_name)
                else "missing"
            )

    try:
        from . import __version__ as mddocx_version
    except (ImportError, AttributeError):
        try:
            mddocx_version = metadata.version("mddocx-native")
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

    sidecar = MathJaxSidecar()
    math_engine, math_engine_error = math_engine_probe()
    return DoctorReport(
        python=platform.python_version(),
        platform=f"{platform.system()} {platform.release()}",
        machine=platform.machine(),
        mddocx_version=mddocx_version,
        dependencies=deps,
        executables={name: shutil.which(name) for name in ("libreoffice", "soffice", "pdftoppm")},
        temp_directory_writable=temp_ok,
        mathjax_sidecar=(
            str(sidecar.executable)
            if sidecar.executable is not None and sidecar.executable.is_file()
            else None
        ),
        mathjax_protocol=sidecar.protocol_version,
        javascript_runtime=sidecar.runtime,
        math_engine=math_engine,
        math_engine_error=math_engine_error,
        install_conflict=conflicting_distributions(),
        svg_support=svg_support_status(),
    )
