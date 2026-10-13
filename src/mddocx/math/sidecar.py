from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

NODE_ENV_VAR = "MDDOCX_NODE"
_SCRIPT_SUFFIXES = frozenset({".js", ".mjs", ".cjs"})


class MathJaxSidecarError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def node_executable() -> str | None:
    """Locate the JavaScript runtime the bundled MathJax sidecar needs.

    ``MDDOCX_NODE`` wins so a self-managed runtime can be selected explicitly.
    Otherwise the interpreter that owns mddocx is checked first, which is how an
    environment-installed ``nodejs-wheel`` dependency is found even when the
    environment's script directory is not on ``PATH``.

    The result is cached for the process; call ``node_executable.cache_clear()``
    after changing ``PATH`` or ``MDDOCX_NODE``.
    """
    configured = os.environ.get(NODE_ENV_VAR)
    if configured:
        return shutil.which(configured) or (configured if Path(configured).is_file() else None)
    suffix = ".exe" if os.name == "nt" else ""
    local = Path(sys.executable).with_name(f"node{suffix}")
    if local.is_file():
        return str(local)
    return shutil.which("node") or shutil.which("nodejs")


class MathJaxSidecar:
    """Bounded JSONL client for an optional, non-networked MathJax executable."""

    protocol_version = 1

    def __init__(self, executable: str | Path | None = None, timeout: float = 5.0) -> None:
        self.executable = Path(executable) if executable else discover_sidecar()
        self.timeout = timeout

    @property
    def is_script(self) -> bool:
        return self.executable is not None and self.executable.suffix.lower() in _SCRIPT_SUFFIXES

    @property
    def runtime(self) -> str | None:
        """JavaScript runtime for a script sidecar, or None when none is needed."""
        return node_executable() if self.is_script else None

    @property
    def available(self) -> bool:
        """True only when the sidecar can actually run, not merely when it exists."""
        if self.executable is None or not self.executable.is_file():
            return False
        return self.runtime is not None if self.is_script else True

    def unavailable_reason(self) -> str | None:
        """Explain why :attr:`available` is False, for actionable diagnostics."""
        if self.executable is None:
            return "the MathJax sidecar file was not found"
        if not self.executable.is_file():
            return f"the MathJax sidecar file is missing: {self.executable}"
        if self.is_script and self.runtime is None:
            return (
                "the MathJax sidecar needs a JavaScript runtime; install Node.js, "
                f"install the mddocx[mathjax] extra, or set {NODE_ENV_VAR}"
            )
        return None

    def convert(self, latex: str, display: bool) -> str:
        if not self.available or self.executable is None:
            raise MathJaxSidecarError(
                f"MathJax sidecar is not usable: {self.unavailable_reason() or 'unknown reason'}"
            )
        request = {
            "protocol": self.protocol_version,
            "tex": latex,
            "display": display,
            "packages": "mddocx-safe",
            "timeout_ms": int(self.timeout * 1000),
            "max_expression_chars": 100_000,
        }
        try:
            command = (
                [self.runtime or "node", str(self.executable)]
                if self.is_script
                else [str(self.executable)]
            )
            completed = subprocess.run(
                command,
                input=json.dumps(request) + "\n",
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MathJaxSidecarError(f"MathJax sidecar failed: {exc}") from exc
        line = completed.stdout.splitlines()[0] if completed.stdout.strip() else ""
        if completed.returncode or not line:
            detail = completed.stderr.strip() or f"exit status {completed.returncode}"
            raise MathJaxSidecarError(f"MathJax sidecar failed: {detail}")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MathJaxSidecarError("MathJax sidecar returned invalid JSON") from exc
        if response.get("protocol", self.protocol_version) != self.protocol_version:
            raise MathJaxSidecarError("MathJax sidecar protocol is incompatible")
        if response.get("error"):
            raise MathJaxSidecarError(str(response["error"]))
        mathml = response.get("mathml")
        if not isinstance(mathml, str) or not mathml.strip():
            raise MathJaxSidecarError("MathJax sidecar returned no MathML")
        return mathml


def discover_sidecar() -> Path | None:
    configured = os.environ.get("MDDOCX_MATHJAX_SIDECAR")
    if configured:
        return Path(configured)
    directory = Path(__file__).with_name("bin")
    suffix = ".exe" if os.name == "nt" else ""
    candidates = (directory / f"mddocx-mathjax{suffix}", directory / "mddocx-mathjax.mjs")
    return next((candidate for candidate in candidates if candidate.is_file()), None)
