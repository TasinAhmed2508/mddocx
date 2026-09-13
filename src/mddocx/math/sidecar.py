from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess


class MathJaxSidecarError(RuntimeError):
    pass


class MathJaxSidecar:
    """Bounded JSONL client for an optional, non-networked MathJax executable."""

    protocol_version = 1

    def __init__(self, executable: str | Path | None = None, timeout: float = 5.0) -> None:
        self.executable = Path(executable) if executable else discover_sidecar()
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return self.executable is not None and self.executable.is_file()

    def convert(self, latex: str, display: bool) -> str:
        if not self.available or self.executable is None:
            raise MathJaxSidecarError("MathJax sidecar is not installed")
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
                [shutil.which("node") or "node", str(self.executable)]
                if self.executable.suffix.lower() in {".js", ".mjs", ".cjs"}
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
