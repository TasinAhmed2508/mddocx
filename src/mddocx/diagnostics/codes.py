from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Severity = Literal["info", "warning", "error"]


@dataclass(slots=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    source_file: str | None = None
    line: int | None = None

    def __str__(self) -> str:
        location = ""
        if self.source_file:
            location = f" {self.source_file}"
            if self.line is not None:
                location += f":{self.line}"
        return f"{self.severity.upper()} {self.code} {self.message}{location}"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class MddocxError(RuntimeError):
    def __init__(self, diagnostic: Diagnostic):
        self.diagnostic = diagnostic
        super().__init__(str(diagnostic))
