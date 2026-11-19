from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Protocol

from .latex import BasicLatexToMathML, UnsupportedLatexError
from .mathml import MathMLToOMML
from .models import MathConversion
from .normalize import normalize_equation
from .sidecar import MathJaxSidecar, MathJaxSidecarError
from .validation import (
    semantic_fingerprint,
    semantic_tokens_preserved,
    source_tokens_preserved,
    validate_mathml,
    validate_omml,
)

_BATCH_COMMANDS = {"frac", "sum", "sqrt", "left", "right", "cdot", "times", "le", "ge"}


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
        self._conversions: dict[tuple[str, bool], MathConversion] = {}
        self._omml_cache: dict[tuple[str, bool], object] = {}
        self._prefetched: dict[tuple[str, bool], str | MathJaxSidecarError] = {}
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

    def prepare_batch(self, expressions: list[tuple[str, bool]]) -> None:
        """Prefetch simple math through the bundled sidecar, with normal fallback."""
        bundled = Path(__file__).with_name("bin") / "mddocx-mathjax.mjs"
        if (
            not self._cache_enabled
            or not self._sidecar.available
            or self._sidecar.executable != bundled
        ):
            return
        # shortcut: batch only small expressions using known commands, until the sidecar isolates user macros.
        eligible = {}
        for latex, display in dict.fromkeys(expressions):
            if len(latex) > 4096:
                continue
            normalized = normalize_equation(latex).text
            if set(re.findall(r"\\([A-Za-z]+|.)", normalized)) <= _BATCH_COMMANDS:
                eligible[latex, display] = normalized
        if len(eligible) < 2 or len(eligible) > 128:
            return
        try:
            replies = self._sidecar.convert_many(
                [(normalized, display) for (_, display), normalized in eligible.items()]
            )
        except MathJaxSidecarError:
            return
        self._prefetched.update(zip(eligible, replies, strict=True))

    def _convert_sidecar(self, key: tuple[str, bool], normalized: str) -> str:
        if key not in self._prefetched:
            return self._sidecar.convert(normalized, key[1])
        result = self._prefetched[key]
        if isinstance(result, MathJaxSidecarError):
            raise result
        return result

    def convert(self, latex: str, display: bool = False) -> MathConversion:
        key = (latex, display)
        if key in self._conversions:
            return deepcopy(self._conversions[key])
        normalized = normalize_equation(latex)
        failures: list[str] = []
        engines = []
        if self._sidecar.available:
            engines.append(("mathjax-sidecar", lambda: self._convert_sidecar(key, normalized.text)))
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
            result = MathConversion(
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
            if self._cache_enabled and not failures:
                if len(self._conversions) == 128:
                    del self._conversions[next(iter(self._conversions))]
                self._conversions[key] = deepcopy(result)
            return result
        raise UnsupportedLatexError("; ".join(failures) or "No math conversion engine available")
