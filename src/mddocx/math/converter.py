from __future__ import annotations

from copy import deepcopy
import re
from typing import Protocol

from .latex import BasicLatexToMathML, UnsupportedLatexError
from .mathml import MathMLToOMML
from .models import MathConversion
from .normalize import normalize_equation
from .sidecar import MathJaxSidecar
from .validation import (
    semantic_fingerprint,
    semantic_tokens_preserved,
    source_tokens_preserved,
    validate_mathml,
    validate_omml,
)


class MathConverter(Protocol):
    def latex_to_mathml(self, latex: str) -> str: ...
    def mathml_to_omml(self, mathml: str, display: bool): ...


class DefaultMathConverter:
    def __init__(self, cache: bool = True, *, sidecar: MathJaxSidecar | None = None) -> None:
        self._fallback = BasicLatexToMathML()
        self._omml = MathMLToOMML()
        self._sidecar = sidecar or MathJaxSidecar()
        self._cache_enabled = cache
        self._mathml_cache: dict[str, str] = {}
        self._omml_cache: dict[tuple[str, bool], object] = {}
        try:
            from latex2mathml.converter import convert  # type: ignore
        except ImportError:
            self._external = None
        else:
            self._external = convert

    @property
    def engine_name(self) -> str:
        if self._sidecar.available:
            return "mathjax-sidecar"
        return "latex2mathml" if self._external is not None else "mddocx-basic"

    def latex_to_mathml(self, latex: str) -> str:
        if self._cache_enabled and latex in self._mathml_cache:
            return self._mathml_cache[latex]
        value = (
            self._external(latex) if self._external is not None else self._fallback.convert(latex)
        )
        validate_mathml(value)
        if self._cache_enabled:
            self._mathml_cache[latex] = value
        return value

    @staticmethod
    def _reject_unconverted_commands(mathml: str) -> None:
        """Do not treat literal TeX commands in external MathML as success."""
        root = validate_mathml(mathml)
        literal = re.search(r"\\([A-Za-z]+)", "".join(root.itertext()))
        if literal:
            raise UnsupportedLatexError(
                f"Unsupported LaTeX command left unconverted by math engine: \\{literal.group(1)}"
            )

    def mathml_to_omml(self, mathml: str, display: bool):
        key = (mathml, display)
        if self._cache_enabled and key in self._omml_cache:
            return deepcopy(self._omml_cache[key])
        value = self._omml.convert(mathml)
        if self._cache_enabled:
            self._omml_cache[key] = deepcopy(value)
        return value

    def latex_to_omml(self, latex: str, display: bool = False):
        return self.convert(latex, display).omml

    def convert(self, latex: str, display: bool = False) -> MathConversion:
        normalized = normalize_equation(latex)
        failures: list[str] = []
        engines = []
        if self._sidecar.available:
            engines.append(
                ("mathjax-sidecar", lambda: self._sidecar.convert(normalized.text, display))
            )
        if self._external is not None:
            engines.append(("latex2mathml", lambda: self._external(normalized.text)))
        engines.append(("mddocx-basic", lambda: self._fallback.convert(normalized.text)))
        for engine, operation in engines:
            try:
                mathml = operation()
                root = validate_mathml(mathml)
                if engine != "mddocx-basic" and not source_tokens_preserved(normalized.text, root):
                    raise UnsupportedLatexError(
                        f"{engine} output lost one or more source identifier or numeral tokens"
                    )
                omml = self.mathml_to_omml(mathml, display)
                validate_omml(omml)
                fingerprint = semantic_fingerprint(root, omml)
                semantic_valid = semantic_tokens_preserved(root, omml)
                if not semantic_valid and engine != "mddocx-basic":
                    raise UnsupportedLatexError(
                        f"{engine} output lost one or more identifier or numeral tokens"
                    )
            except Exception as exc:
                failures.append(f"{engine}: {exc}")
                continue
            return MathConversion(
                source_text=latex,
                normalized_text=normalized.text,
                display=display,
                engine=engine,
                mathml=mathml,
                omml=omml,
                repairs=normalized.repairs,
                warnings=tuple(failures),
                semantic_valid=semantic_valid,
                semantic_fingerprint=fingerprint,
                label=normalized.label,
            )
        raise UnsupportedLatexError("; ".join(failures) or "No math conversion engine available")
