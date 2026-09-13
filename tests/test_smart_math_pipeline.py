from __future__ import annotations

import pytest

from mddocx.math.converter import DefaultMathConverter
from mddocx.math.normalize import normalize_equation
from mddocx.math.preflight import inspect_math
from mddocx.math.validation import validate_mathml


def test_normalization_is_conservative_and_records_repairs():
    result = normalize_equation(" $$\\dfrac{1}{2−x\u200b}$$ ")

    assert result.text == r"\frac{1}{2-x}"
    assert result.repairs == (
        "stripped outer math delimiter",
        "normalized Unicode minus",
        "removed invisible formatting characters",
        r"normalized \dfrac to \frac",
    )


def test_normalization_balances_only_small_missing_closing_brace_counts():
    assert normalize_equation(r"\frac{1{x").text.endswith("}}")
    assert normalize_equation("{{{{x").text == "{{{{x"
    assert normalize_equation("x}}").text == "x}}"


def test_mathml_validator_rejects_foreign_and_active_content():
    with pytest.raises(Exception, match="foreign"):
        validate_mathml('<math xmlns="http://www.w3.org/1998/Math/MathML"><script/></math>')
    with pytest.raises(Exception, match="Unsafe"):
        validate_mathml(
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi href="x">x</mi></math>'
        )


def test_engine_failure_falls_through_and_is_observable():
    converter = DefaultMathConverter(cache=False)
    converter._sidecar.executable = None
    converter._external = lambda _: "<not-math/>"  # type: ignore[assignment]

    result = converter.convert("x+1")

    assert result.engine == "mddocx-basic"
    assert result.warnings and result.warnings[0].startswith("latex2mathml:")
    assert result.structural_valid
    assert result.semantic_fingerprint


def test_external_engine_semantic_token_loss_falls_through():
    converter = DefaultMathConverter(cache=False)
    converter._sidecar.executable = None
    converter._external = lambda _: (  # type: ignore[assignment]
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
    )

    result = converter.convert("x+7")

    assert result.engine == "mddocx-basic"
    assert "lost one or more" in result.warnings[0]
    assert result.semantic_valid


def test_preflight_reports_normalization_engine_and_validation():
    report = inspect_math(r"Inline $\dfrac{1}{2}$.")
    equation = report.equations[0]

    assert equation.status == "repaired"
    assert equation.normalized_text == r"\frac{1}{2}"
    assert equation.engine in {"mathjax-sidecar", "latex2mathml", "mddocx-basic"}
    assert equation.structural_valid
    assert equation.semantic_fingerprint
