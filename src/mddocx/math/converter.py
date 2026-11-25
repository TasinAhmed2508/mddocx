from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Protocol

from lxml import etree

from .chemistry import attach_chemistry_scripts
from .latex import (
    NARY,
    INTEGRAL_SYMBOLS,
    BasicLatexToMathML,
    UnsupportedLatexError,
    array_preambles,
    array_span_preambles,
)
from .mathml import NARY_CHARS, MathMLToOMML
from .models import MathConversion
from .normalize import normalize_equation
from .sidecar import MathJaxSidecar, MathJaxSidecarError
from .validation import (
    MATHML_NS,
    explicit_nary_limits_preserved,
    semantic_fingerprint,
    semantic_tokens_preserved,
    source_matrices_preserved,
    source_tokens_preserved,
    validate_mathml,
    validate_omml,
)

_BATCH_COMMANDS = {
    *NARY,
    "%",
    ",",
    "approx",
    "boxed",
    "cdot",
    "cdots",
    "ce",
    "delta",
    "Delta",
    "displaystyle",
    "varepsilon",
    "frac",
    "ge",
    "lambda",
    "le",
    "left",
    "leftarrow",
    "leq",
    "limits",
    "lvert",
    "nolimits",
    "partial",
    "pu",
    "quad",
    "qquad",
    "right",
    "rvert",
    "sqrt",
    "text",
    "times",
    "xi",
}
_BATCH_SIZE = 128
_MATHJAX_TEXT_AMPERSAND = re.compile(r"(?<!\\)\\&")
_MOVABLE_OPERATORS = NARY_CHARS - INTEGRAL_SYMBOLS
_NARY_SOURCE = re.compile(
    rf"(?<!\\)\\({'|'.join(NARY)})(?![A-Za-z])(?:\s*\\(limits|nolimits)(?![A-Za-z]))?"
)


def _mark_movable_operators(root: etree._Element, explicit_source: str | None = None) -> bool:
    operators = [
        operator for operator in root.iter(f"{{{MATHML_NS}}}mo") if operator.text in NARY_CHARS
    ]
    if explicit_source is not None:
        source = _NARY_SOURCE.findall(explicit_source)
        if [NARY[command] for command, _ in source] != [op.text for op in operators]:
            return False
        operators = [op for op, (_, mode) in zip(operators, source, strict=True) if not mode]
    changed = False
    for operator in operators:
        if operator.text in _MOVABLE_OPERATORS and "movablelimits" not in operator.attrib:
            operator.set("movablelimits", "true")
            changed = True
    return changed


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
        self._batches: dict[tuple[str, bool], list[tuple[tuple[str, bool], str]]] = {}
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

    def mathml_to_omml(self, mathml: str, display: bool, *, root=None):
        if root is not None:
            # The full conversion path already keeps a bounded cache of native equations.
            return self._omml.convert_root(root)
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
        """Group equations with stateless commands for bounded conversion by the bundled sidecar."""
        bundled = Path(__file__).with_name("bin") / "mddocx-mathjax.mjs"
        if (
            not self._cache_enabled
            or not self._sidecar.available
            or self._sidecar.executable != bundled
        ):
            return
        self._batches.clear()
        self._prefetched.clear()
        # shortcut: keep commands that can affect later equations out of shared processes.
        eligible = {}
        for latex, display in dict.fromkeys(expressions):
            if len(latex) > 4096:
                continue
            try:
                normalized = normalize_equation(latex).text
            except UnsupportedLatexError:
                continue
            if (
                len(normalized) <= 4096
                and set(re.findall(r"\\([A-Za-z]+|.)", normalized)) <= _BATCH_COMMANDS
            ):
                eligible[latex, display] = normalized
        items = list(eligible.items())
        for start in range(0, len(items), _BATCH_SIZE):
            batch = items[start : start + _BATCH_SIZE]
            if len(batch) > 1:
                self._batches.update((key, batch) for key, _ in batch)

    def _convert_sidecar(self, key: tuple[str, bool], normalized: str) -> str:
        batch = self._batches.get(key)
        if batch is not None:
            # Keep at most one batch of expanded MathML in memory.
            self._prefetched.clear()
            for batch_key, _ in batch:
                self._batches.pop(batch_key)
            try:
                replies = self._sidecar.convert_many(
                    [(tex, display) for (_, display), tex in batch]
                )
            except MathJaxSidecarError:
                pass  # Fall back to the usual single-expression request.
            else:
                self._prefetched.update(zip((item[0] for item in batch), replies, strict=True))
        if key not in self._prefetched:
            return self._sidecar.convert(normalized, key[1])
        result = self._prefetched.pop(key)
        if isinstance(result, MathJaxSidecarError):
            raise result
        return result

    def convert(self, latex: str, display: bool = False) -> MathConversion:
        key = (latex, display)
        if key in self._conversions:
            return deepcopy(self._conversions[key])
        normalized = normalize_equation(latex)
        try:
            spanning = next(array_span_preambles(normalized.text), None) is not None
            decorated_array = any(
                any(kind in {"@", "|"} for kind, _ in columns)
                or "*" in normalized.text[start:end]
                or any(tag in normalized.text for tag in (r"\hline", r"\hdashline", r"\cline"))
                for start, end, columns in array_preambles(normalized.text)
            )
        except ValueError as exc:
            raise UnsupportedLatexError(f"array ({exc})") from exc
        failures: list[str] = []
        engines = []
        sidecar_ready = self._sidecar.available
        # The bundled MathJax engine does not recognize LaTeX's multicolumn command.
        if sidecar_ready and not spanning:
            engines.append(("mathjax-sidecar", lambda: self._convert_sidecar(key, normalized.text)))
        if self._external is not None and not (decorated_array or spanning):
            external_display = "block" if display else "inline"
            engines.append(
                ("latex2mathml", lambda: self._external(normalized.text, display=external_display))
            )
        engines.append(
            ("mddocx-basic", lambda: self._fallback.convert(normalized.text, display=display))
        )
        for engine, operation in engines:
            try:
                mathml = operation()
                root = validate_mathml(mathml)
                changed = False
                if engine == "mathjax-sidecar":
                    changed = r"\ce" in normalized.text and attach_chemistry_scripts(root)
                    if r"\&" in normalized.text:
                        for token in root.iter(f"{{{MATHML_NS}}}mtext"):
                            text = token.text or ""
                            rendered = _MATHJAX_TEXT_AMPERSAND.sub("&", text)
                            if rendered != text:
                                token.text = rendered
                                changed = True
                    # MathJax leaves implicit dictionary values out of its serialization.
                    changed = _mark_movable_operators(root) or changed
                elif engine == "latex2mathml":
                    has_modifier = r"\limits" in normalized.text or r"\nolimits" in normalized.text
                    changed = _mark_movable_operators(
                        root, normalized.text if has_modifier else None
                    )
                if changed:
                    mathml = etree.tostring(root, encoding="unicode")
                if engine != "mddocx-basic" and not source_tokens_preserved(normalized.text, root):
                    raise UnsupportedLatexError(
                        f"{engine} output lost one or more source identifier or numeral tokens"
                    )
                omml = self.mathml_to_omml(mathml, display, root=root)
                validate_omml(omml)
                if not explicit_nary_limits_preserved(normalized.text, omml):
                    raise UnsupportedLatexError(f"{engine} changed an explicit limit placement")
                if not source_matrices_preserved(normalized.text, omml):
                    raise UnsupportedLatexError(
                        f"{engine} output lost an alignment or matrix layout"
                    )
                fingerprint = semantic_fingerprint(root)
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
            # A sidecar failure can be transient, while the local Python fallback is deterministic.
            if self._cache_enabled and (not failures or not sidecar_ready):
                if len(self._conversions) == 128:
                    del self._conversions[next(iter(self._conversions))]
                self._conversions[key] = deepcopy(result)
            return result
        raise UnsupportedLatexError("; ".join(failures) or "No math conversion engine available")
