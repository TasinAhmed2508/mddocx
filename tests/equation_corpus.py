from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquationCase:
    family: str
    latex: str
    expected_omml: str


def build_equation_corpus() -> tuple[EquationCase, ...]:
    """Return 250 deterministic academic/AI-style equation variants."""
    cases: list[EquationCase] = []
    for index in range(1, 26):
        symbol = chr(ord("a") + (index - 1) % 20)
        cases.extend(
            (
                EquationCase("fractions", rf"\frac{{{symbol}+{index}}}{{x+1}}", "f"),
                EquationCase("nested-scripts", rf"{symbol}_{{i_{index}}}^{{n+{index}}}", "sSubSup"),
                EquationCase("roots", rf"\sqrt[{index % 5 + 2}]{{x+{index}}}", "rad"),
                EquationCase("nary-limits", rf"\sum_{{i=1}}^{{{index}}} i^2", "nary"),
                EquationCase(
                    "matrices",
                    rf"\begin{{bmatrix}}{index} & x \\ y & {index + 1}\end{{bmatrix}}",
                    "m",
                ),
                EquationCase(
                    "aligned", rf"\begin{{aligned}}x&={index} \\ y&={index + 1}\end{{aligned}}", "m"
                ),
                EquationCase("accents", rf"\widehat{{{symbol}}}+\vec{{v_{index}}}", "acc"),
                EquationCase("binomials", rf"\binom{{n+{index}}}{{2}}", "f"),
                EquationCase(
                    "piecewise", rf"\begin{{cases}}x+{index} & x>0 \\ 0 & x=0\end{{cases}}", "m"
                ),
                EquationCase(
                    "text-and-chemistry",
                    rf"\mathrm{{H}}_2\mathrm{{O}}+\text{{ sample {index}}}",
                    "r",
                ),
            )
        )
    return tuple(cases)


EQUATION_CORPUS = build_equation_corpus()
