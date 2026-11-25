from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
import pytest

from mddocx import MarkdownWord, MathFailurePolicy, NotesConfig, RenderConfig
from mddocx.ast.block import CodeBlock, MathBlock
from mddocx.ast.inline import Emphasis, InlineCode, InlineMath
from mddocx.parser import MarkdownParser
from mddocx.math.preflight import inspect_math
from mddocx.math.converter import DefaultMathConverter


FIXTURE = Path(__file__).parent / "fixtures" / "ai_markdown" / "chatgpt_sphere_equations.md"
NS = {
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


def _walk(value):
    if isinstance(value, list):
        for item in value:
            yield from _walk(item)
        return
    yield value
    for name in ("children", "items", "rows", "cells", "term", "definition"):
        child = getattr(value, name, None)
        if child:
            yield from _walk(child)


def _document_xml(blob: bytes):
    with ZipFile(BytesIO(blob)) as package:
        assert package.testzip() is None
        return etree.fromstring(package.read("word/document.xml"))


def test_chatgpt_equation_fixture_preserves_all_math_as_native_omml():
    markdown = FIXTURE.read_text(encoding="utf-8")
    config = RenderConfig()
    ast = MarkdownParser(metadata_config=config.metadata).parse(markdown, source_file=str(FIXTURE))
    nodes = list(_walk(ast.children))

    assert sum(isinstance(node, MathBlock) for node in nodes) == 20
    assert sum(isinstance(node, InlineMath) for node in nodes) == 2

    compiler = MarkdownWord(config)
    blob = compiler.render_string(markdown, base_dir=FIXTURE.parent)
    root = _document_xml(blob)

    assert compiler.diagnostics == ()
    assert len(root.xpath(".//m:oMathPara", namespaces=NS)) == 20
    assert len(root.xpath(".//m:oMath", namespaces=NS)) == 22
    assert len(root.xpath(".//m:borderBox", namespaces=NS)) == 7
    assert len(root.xpath(".//m:f", namespaces=NS)) == 2
    write_runs = root.xpath(".//m:r[m:t[contains(., 'Write')]]", namespaces=NS)
    assert len(write_runs) == 1
    assert write_runs[0].xpath("./m:rPr/m:sty[@m:val='p']", namespaces=NS)
    assert not root.xpath(".//m:oMath//m:oMath", namespaces=NS)
    assert not root.xpath("/w:document/w:body/m:oMath", namespaces=NS)
    assert not root.xpath("/w:document/w:body/m:oMathPara", namespaces=NS)
    assert all("$" not in text for text in root.xpath(".//w:t/text()", namespaces=NS))


def test_math_scanner_supports_ai_delimiters_and_math_fences():
    markdown = """Inline \\(x^2\\) and $y_1$.

\\[
\\frac{1}{2}
\\]

~~~latex
\\boxed{z}
~~~
"""
    ast = MarkdownParser().parse(markdown)
    nodes = list(_walk(ast.children))

    assert sum(isinstance(node, MathBlock) for node in nodes) == 2
    assert [node.source_text for node in nodes if isinstance(node, InlineMath)] == ["x^2", "y_1"]


def test_math_scanner_does_not_convert_code_or_currency():
    markdown = """Price range: $5 to $10. Inline code: `$x$`.

```python
formula = "$$not_math$$"
```
"""
    ast = MarkdownParser().parse(markdown)
    nodes = list(_walk(ast.children))
    assert not any(isinstance(node, (MathBlock, InlineMath)) for node in nodes)
    assert [node.code for node in nodes if isinstance(node, InlineCode)] == ["$x$"]
    assert [node.code for node in nodes if isinstance(node, CodeBlock)] == [
        'formula = "$$not_math$$"'
    ]


def test_wrapped_code_spans_and_literal_backticks_preserve_neighboring_equations():
    markdown = r"""Example ``show
$x^2$ and \(an open delimiter
as-is``, then $y^2$.

Escaped \` and formula $z^2$.

Unmatched ` and formula $q^2$.
"""
    nodes = list(_walk(MarkdownParser().parse(markdown).children))
    assert [node.code for node in nodes if isinstance(node, InlineCode)] == [
        r"show $x^2$ and \(an open delimiter as-is"
    ]
    report = inspect_math(markdown)
    assert report.ok
    assert [equation.source for equation in report.equations] == ["y^2", "z^2", "q^2"]


def test_code_blocks_and_display_math_respect_markdown_containers():
    markdown = r"""    show $x^2$ in code
    $$x+1$$
    \(incomplete delimiter

> ~~~text
> show $y^2$ and \(
> ~~~
>
> $$y^2$$

- Example

  ~~~text
  $z^2$
  ~~~

  $$
  \frac{1}{2}
  $$ {#eq:half}

  ~~~~latex
  \boxed{w}
  ~~~~

# After the equations
"""
    ast = MarkdownParser().parse(markdown)
    nodes = list(_walk(ast.children))
    assert [node.code for node in nodes if isinstance(node, CodeBlock)] == [
        "show $x^2$ in code\n$$x+1$$\n\\(incomplete delimiter",
        r"show $y^2$ and \(",
        "$z^2$",
    ]
    display_math = [node for node in nodes if isinstance(node, MathBlock)]
    assert [node.source_text for node in display_math] == ["y^2", r"\frac{1}{2}", r"\boxed{w}"]
    assert display_math[1].identifier == "eq:half"
    assert ast.children[-1].source.line == 25
    report = inspect_math(markdown)
    assert report.ok
    assert report.native == 3


def test_chat_export_escaped_math_stays_editable_in_text_and_tables():
    markdown = r"""# Revision notes

\\[ \boxed{x\_{i+1}=6.25\\%} \\] {#eq:percentage}

| Method | Formula |
| ------ | ------- |
| Matrix | \\(\begin{bmatrix} 4&1\\\ 12&13 \end{bmatrix}\\) |

\\[
\frac{x\_{i+1}}{2}
\\]

Inline \\(x^2\\). Literal: `\\(x^2\\)`.

```text
\\[ x^2 \\]
```

# Still here
"""
    ast = MarkdownParser().parse(markdown)
    nodes = list(_walk(ast.children))
    display = [node for node in nodes if isinstance(node, MathBlock)]
    assert [node.source_text for node in display] == [
        r"\boxed{x_{i+1}=6.25\%}",
        r"\frac{x_{i+1}}{2}",
    ]
    assert display[0].identifier == "eq:percentage"
    assert [node.source.line for node in display] == [3, 9]
    assert ast.children[-1].source.line == 19
    assert [node.source_text for node in nodes if isinstance(node, InlineMath)] == [
        r"\begin{bmatrix} 4&1\\ 12&13 \end{bmatrix}",
        "x^2",
    ]

    compiler = MarkdownWord(RenderConfig(math_failure=MathFailurePolicy(mode="error")))
    root = _document_xml(compiler.render_string(markdown))
    assert compiler.diagnostics == ()
    assert len(root.xpath(".//m:oMath", namespaces=NS)) == 4
    assert len(root.xpath(".//m:oMathPara", namespaces=NS)) == 2
    assert len(root.xpath(".//w:tc//m:m/m:mr", namespaces=NS)) == 2
    assert root.xpath(".//m:sSub", namespaces=NS)
    assert "%" in "".join(root.xpath(".//m:t/text()", namespaces=NS))


@pytest.mark.parametrize("note_style", ["footnote", "endnote"])
def test_math_fragments_keep_equations_and_escaped_dollars_distinct(note_style):
    markdown = r"""Body \$literal\$ and $a^2$.[^example]

| Cell |
| --- |
| \$cell\$ a\|b &amp; c |

Sequence \(r_{i+1}\)
: Exported \\(s\_{i+1}\\) and \$definition\$.

[^example]: Note \(x_{i+1}+y_{i-1}\) and \\(\frac{x\_{i}}{2}\\).
    Keep \$note\$, `$code$`, and the [guide].

[guide]: https://example.org/guide
"""
    report = inspect_math(markdown)
    assert report.ok
    assert [equation.source for equation in report.equations] == [
        "a^2",
        "r_{i+1}",
        "s_{i+1}",
        "x_{i+1}+y_{i-1}",
        r"\frac{x_{i}}{2}",
    ]

    config = RenderConfig(
        notes=NotesConfig(style=note_style), math_failure=MathFailurePolicy(mode="error")
    )
    compiler = MarkdownWord(config)
    with ZipFile(BytesIO(compiler.render_string(markdown))) as package:
        document = etree.fromstring(package.read("word/document.xml"))
        notes = etree.fromstring(package.read(f"word/{note_style}s.xml"))

    assert compiler.diagnostics == ()
    assert len(document.xpath(".//m:oMath", namespaces=NS)) == 3
    assert len(notes.xpath(".//m:oMath", namespaces=NS)) == 2
    assert notes.xpath(".//m:f", namespaces=NS)
    assert notes.xpath(".//w:hyperlink[.//w:t='guide']", namespaces=NS)
    body_text = "".join(document.xpath(".//w:t/text()", namespaces=NS))
    assert all(value in body_text for value in ("$literal$", "$cell$ a|b & c", "$definition$"))
    note_text = "".join(notes.xpath(".//w:t/text()", namespaces=NS))
    assert "$note$" in note_text and "$code$" in note_text


def test_invalid_math_markers_remain_text_next_to_valid_math():
    markdown = "Literal MDDOCXMATHaZ:ENDMATH and MDDOCXMATH_aZ:ENDMATH; $0$ then $x^2$."

    ast = MarkdownParser().parse(markdown)
    nodes = list(_walk(ast.children))

    assert [node.source_text for node in nodes if isinstance(node, InlineMath)] == ["0", "x^2"]
    text = "".join(getattr(node, "text", "") for node in nodes)
    assert "MDDOCXMATHaZ:ENDMATH" in text
    assert "MDDOCXMATH_aZ:ENDMATH" in text


def test_adjacent_inline_equations_keep_their_boundaries_inside_emphasis():
    ast = MarkdownParser().parse(r"_Equations $x$\(y\) and \(ab?\)_")
    (span,) = ast.children[0].children
    assert isinstance(span, Emphasis)
    assert [node.source_text for node in span.children if isinstance(node, InlineMath)] == [
        "x",
        "y",
        "ab?",
    ]


def test_unclosed_display_delimiter_does_not_consume_document_tail():
    markdown = "Before\n\n$$\nx+1\n\n# Still present"
    ast = MarkdownParser().parse(markdown)
    nodes = list(_walk(ast.children))

    assert not any(isinstance(node, MathBlock) for node in nodes)
    assert any(getattr(node, "level", None) == 1 for node in nodes)

    compiler = MarkdownWord()
    compiler.render_string(markdown)
    assert compiler.diagnostics[0].code == "MATH101"
    assert compiler.diagnostics[0].line == 3
    assert "Unterminated" in compiler.diagnostics[0].message
    assert compiler.diagnostics[0].remediation

    report = inspect_math(markdown, source_file="broken.md")
    assert not report.ok
    assert report.syntax_issues[0].line == 3
    assert "broken.md:3" in report.to_text()


def test_malformed_math_warning_retains_original_line_with_ast_cache(tmp_path):
    markdown = "---\ntitle: Report\n---\n\n$$x^2$$\n\nText with \\(an open delimiter.\n"
    config = RenderConfig()
    config.cache.ast_enabled = True
    config.cache.directory = tmp_path / "ast-cache"
    compiler = MarkdownWord(config)

    for _ in range(2):
        compiler.render_string(markdown, base_dir=tmp_path)
        (finding,) = compiler.diagnostics
        assert (finding.code, finding.line) == ("MATH101", 7)


def test_math_syntax_diagnostics_ignore_code_fences():
    markdown = """```text
$$
\\(
```

~~~latex
x + 1
"""
    report = inspect_math(markdown)

    assert len(report.syntax_issues) == 1
    assert report.syntax_issues[0].line == 6
    assert "fenced" in report.syntax_issues[0].message


def test_unsupported_ai_macro_preserves_document_and_reports_reason():
    compiler = MarkdownWord()
    blob = compiler.render_string("Before\n\n$$\\inventedmacro{x}$$\n\nAfter")
    root = _document_xml(blob)

    body_text = root.xpath("string(.//w:body)", namespaces=NS)
    assert "Before" in body_text
    assert "After" in body_text
    assert "\\inventedmacro{x}" in body_text
    assert len(compiler.diagnostics) == 1
    assert compiler.diagnostics[0].code == "MATH201"
    assert "inventedmacro" in compiler.diagnostics[0].message
    assert "math-check" in (compiler.diagnostics[0].remediation or "")


def test_strict_math_rejects_unsupported_ai_macro():
    config = RenderConfig(math_failure=MathFailurePolicy(mode="error"))
    compiler = MarkdownWord(config)

    try:
        compiler.render_string("$$\\inventedmacro{x}$$")
    except Exception as exc:
        assert "inventedmacro" in str(exc)
    else:
        raise AssertionError("strict math mode did not reject an unsupported command")


def test_math_preflight_reports_engine_counts_and_fallbacks():
    report = inspect_math(FIXTURE.read_text(encoding="utf-8"), source_file=str(FIXTURE))

    assert report.total == 22
    assert report.native == 22
    assert report.fallbacks == 0
    assert report.ok
    assert report.engine in {"mathjax-sidecar", "mddocx-basic", "latex2mathml"}

    failed = inspect_math("$$\\inventedmacro{x}$$")
    assert failed.total == 1
    assert failed.fallbacks == 1
    assert not failed.ok
    assert "inventedmacro" in (failed.equations[0].error or "")


def test_common_claude_and_gemini_latex_variants_are_native():
    markdown = r"""
\[
\begin{align*}
x &= \dfrac{1}{2} \\
y &= \binom{n}{2}
\end{align*}
\]

```tex
\begin{gathered}
a=b \\
c=d
\end{gathered}
```

Inline $x \pmod{n}$ and \(\textnormal{done}\).
"""
    report = inspect_math(markdown)

    assert report.total == 4
    assert report.native == 4
    assert report.ok

    root = _document_xml(MarkdownWord().render_string(markdown))
    assert root.xpath(".//m:m", namespaces=NS)
    assert root.xpath(".//m:f[m:fPr/m:type[@m:val='noBar']]", namespaces=NS)


def test_ai_equation_tags_checks_and_vector_arrows_are_native():
    markdown = r"""
$$\boxed{2u+d=-1}\tag{1}$$

$$6=6\quad\checkmark$$

$$\overrightarrow{ON}=\text{normal}$$
"""
    report = inspect_math(markdown)

    assert report.total == 3
    assert report.native == 3
    assert report.fallbacks == 0
    assert report.ok

    root = _document_xml(MarkdownWord().render_string(markdown))
    equation_text = "".join(root.xpath(".//m:t/text()", namespaces=NS))
    assert "✓" in equation_text
    assert root.xpath(".//m:accPr/m:chr[@m:val='⃗']", namespaces=NS)
    assert "1" in equation_text


def test_external_math_engine_cannot_hide_unconverted_commands():
    converter = DefaultMathConverter(cache=False)
    converter._external = lambda _: (  # type: ignore[assignment]
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>\\invented</mi></math>'
    )

    try:
        converter.latex_to_mathml(r"\invented{x}")
    except Exception as exc:
        assert "invented" in str(exc)
    else:
        raise AssertionError("literal TeX command was accepted as converted MathML")
