from __future__ import annotations

import pytest
from lxml import etree

from mddocx.math.converter import DefaultMathConverter
from mddocx.math.normalize import normalize_equation
from mddocx.math.preflight import inspect_math
from mddocx.math.sidecar import MathJaxSidecar
from mddocx.math.validation import validate_mathml


def test_batched_mathjax_matches_individual_conversion():
    sidecar = MathJaxSidecar()
    if not sidecar.available:
        pytest.skip("optional MathJax sidecar is unavailable")
    equations = [("x^2+1", False), (r"\frac{x+1}{y}", True), ("x_i", False)]
    assert sidecar.convert_many(equations) == [sidecar.convert(*equation) for equation in equations]


def test_large_equation_batches_run_lazily_and_with_bounded_chunks(monkeypatch):
    sidecar = MathJaxSidecar()
    if not sidecar.available:
        pytest.skip("optional MathJax sidecar is unavailable")
    call = sidecar.convert_many
    sizes = []

    def capture(batch):
        sizes.append(len(batch))
        return call(batch)

    monkeypatch.setattr(sidecar, "convert_many", capture)
    converter = DefaultMathConverter(sidecar=sidecar)
    expressions = [(f"x^{{{i}}}+1", False) for i in range(140)]
    converter.prepare_batch(expressions)
    assert sizes == []
    assert all(converter.convert(*item).engine == "mathjax-sidecar" for item in expressions)
    assert sizes == [128, 12]


def test_chat_report_formulas_share_a_batch_without_changing_equations(monkeypatch):
    sidecar = MathJaxSidecar()
    if not sidecar.available:
        pytest.skip("optional MathJax sidecar is unavailable")
    expressions = [
        (r"\boxed{x_{i+1}=x_i-\frac{f(x_i)}{f'(x_i)}}", True),
        (r"\varepsilon_a\approx6.25\%\quad\text{relative error}", False),
        (r"\displaystyle\left\lvert\frac{\Delta x}{x}\right\rvert\tag{A}", True),
        (r"\lambda\sqrt{x}+\delta\qquad x\leq y", False),
    ]
    individual = [DefaultMathConverter(sidecar=sidecar).convert(*item) for item in expressions]
    requests = []
    convert_many = sidecar.convert_many

    def capture(batch):
        requests.append(batch)
        return convert_many(batch)

    monkeypatch.setattr(sidecar, "convert_many", capture)
    converter = DefaultMathConverter(sidecar=sidecar)
    converter.prepare_batch(expressions)
    batched = [converter.convert(*item) for item in expressions]

    assert requests == [[expressions[0], expressions[1], expressions[3]], [expressions[2]]]
    for before, after in zip(individual, batched, strict=True):
        assert before.engine == after.engine == "mathjax-sidecar"
        assert before.mathml == after.mathml
        assert etree.tostring(before.omml) == etree.tostring(after.omml)


def test_full_math_conversion_does_not_keep_a_second_unbounded_cache(monkeypatch):
    converter = DefaultMathConverter()
    monkeypatch.setattr(type(converter._sidecar), "available", False)
    for index in range(140):
        converter.convert(f"x_{{{index}}}")
    assert len(converter._conversions) == 128
    assert not converter._omml_cache
    first = converter.convert("x_{139}")
    first.omml.clear()
    assert len(converter.convert("x_{139}").omml)


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
    converter._external = lambda _, **kwargs: "<not-math/>"  # type: ignore[assignment]

    result = converter.convert("x+1")

    assert result.engine == "mddocx-basic"
    assert result.warnings and result.warnings[0].startswith("latex2mathml:")
    assert result.structural_valid
    assert result.semantic_fingerprint


def test_repeated_equations_share_engine_work_but_keep_separate_xml():
    converter = DefaultMathConverter()
    converter._sidecar.executable = None
    calls = []

    def engine(latex, *, display):
        calls.append(latex)
        return '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'

    converter._external = engine
    first = converter.latex_to_omml("x")
    first.set("modified", "true")
    second = converter.latex_to_omml("x")
    converter.latex_to_omml("x", display=True)

    assert calls == ["x", "x"]
    assert first is not second and second.get("modified") is None


def test_external_engine_semantic_token_loss_falls_through():
    converter = DefaultMathConverter(cache=False)
    converter._sidecar.executable = None
    converter._external = lambda _, **kwargs: (  # type: ignore[assignment]
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


def test_preflight_covers_equations_in_notes():
    report = inspect_math("Body $x^2$.[^note]\n\n[^note]: Note with $y^3$.\n")

    assert [equation.source_text for equation in report.equations] == ["x^2", "y^3"]
    assert report.native == 2
