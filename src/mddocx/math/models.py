from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class NormalizedEquation:
    source: str
    text: str
    repairs: tuple[str, ...] = ()
    label: str | None = None


@dataclass(frozen=True, slots=True)
class MathConversion:
    source_text: str
    normalized_text: str
    display: bool
    engine: str
    mathml: str
    omml: object
    repairs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    structural_valid: bool = True
    semantic_valid: bool = True
    semantic_fingerprint: str = ""
    label: str | None = None


EquationStatus = Literal["native", "repaired", "fallback", "error"]
