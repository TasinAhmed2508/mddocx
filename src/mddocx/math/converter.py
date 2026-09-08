from __future__ import annotations

from copy import deepcopy
import re
from typing import Protocol
from xml.etree import ElementTree as ET

from .latex import BasicLatexToMathML, UnsupportedLatexError
from .mathml import MathMLToOMML


class MathConverter(Protocol):
    def latex_to_mathml(self, latex: str) -> str: ...
    def mathml_to_omml(self, mathml: str, display: bool): ...


class DefaultMathConverter:
    def __init__(self, cache: bool = True) -> None:
        self._fallback = BasicLatexToMathML()
        self._omml = MathMLToOMML()
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
        return "latex2mathml" if self._external is not None else "mddocx-basic"

    def latex_to_mathml(self, latex: str) -> str:
        if self._cache_enabled and latex in self._mathml_cache:
            return self._mathml_cache[latex]
        value = (
            self._external(latex) if self._external is not None else self._fallback.convert(latex)
        )
        if self._external is not None:
            self._reject_unconverted_commands(value)
        if self._cache_enabled:
            self._mathml_cache[latex] = value
        return value

    @staticmethod
    def _reject_unconverted_commands(mathml: str) -> None:
        """Do not treat literal TeX commands in external MathML as success."""
        try:
            root = ET.fromstring(mathml)
        except ET.ParseError as exc:
            raise UnsupportedLatexError(f"Math engine returned invalid MathML: {exc}") from exc
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
        return self.mathml_to_omml(self.latex_to_mathml(latex), display)
