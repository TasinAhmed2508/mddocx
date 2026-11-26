# AI-generated mathematical Markdown

mddocx accepts common mathematical Markdown copied from ChatGPT, Claude, Gemini, and other
assistants. Parsing is syntax-driven; provider names do not change document behavior and no AI
service or network request is used during conversion.

## Recognized forms

| Source form | Result |
|---|---|
| `\(x^2\)` or `\\(x^2\\)` | Inline native Word equation |
| `$x^2$` | Inline native Word equation |
| `\[ x^2 \]` or `\\[ x^2 \\]` | Display native Word equation, on one line or with delimiters on separate lines |
| `$$` ... `$$` | Display native Word equation |
| fenced `math`, `latex`, `tex`, or `mddocx-math` | Display native Word equation |

ChatGPT Markdown downloads can use the doubled-backslash forms and escape subscripts,
percent signs, and matrix row separators inside the equation. mddocx reads these forms
in the original downloaded file, including inline formulas in Markdown tables.

Inline code and non-math fenced code are never scanned for equations. Escaped dollar signs and
common currency ranges remain text. An unmatched display delimiter is preserved as source text and
does not absorb the rest of the document. Unterminated explicit display/inline delimiters and
math-labelled fences produce a source-located `MATH101` warning.

## Conversion engines and failure policy

The compiler tries bundled MathJax first, then the Python `latex2mathml` converter, then its
built-in subset parser. Every path generates editable OMML. The default install includes
the Python converter and supplies a MathJax runtime on supported platforms. Run
`mddocx doctor` to check which engines are available in your environment.

Leading `\newcommand` declarations can provide positional arguments and a default for the
first argument. Definitions apply within the equation that contains them. AMS `\genfrac`
preserves the delimiters, numerator, denominator, and zero-width rule in editable Word math.

Integrals keep their limits beside the operator by default. Sums, products, and
indexed unions and intersections use side limits inline and stacked limits in
display equations. Use
`\limits` to stack limits and `\nolimits` to put them beside the symbol. Word keeps
the operator, limits, and operand editable, and `mddocx verify` checks explicit
placement on named large operators.

Use `\phantom`, `\hphantom`, and `\vphantom` to reserve space with hidden equation
content. `\smash`, `\smash[t]`, and `\smash[b]` keep their content visible and
exclude the selected vertical dimensions from line spacing. The content remains
editable in Word, and offline verification checks the visibility and spacing flags.

LaTeX arrays support `l`, `c`, and `r` columns, bounded repetition such as
`*{2}{r}`, vertical rules, and intercolumn expressions such as `r@{.}l` for aligned
decimal points. Vertical rules stay aligned across tall cells such as fractions. Mixed
intercolumn spacing uses Word's native zero-gap columns with an em space at ordinary
column boundaries. A single `\hline` at any row boundary keeps a full-width solid
rule. Outer horizontal and vertical rules form an editable Word math frame. Dashed,
partial, or repeated horizontal rules use the math failure policy.

`\multicolumn{2}{c}{...}` centers an editable cell across two columns. Use `l` or `r`
to set its alignment to the left or right. Disjoint spans and nested spans across
different rows share column measurements. Spans work with solid `\hline` rules and
use the built-in Python engine. Shared widths reflect the cells as converted, so
edits that make a cell wider in Word can shift that row's alignment. Crossing
spans, spans combined with column rules or inserts, and row spans use the math
failure policy.

Unsupported syntax produces a `MATH201` warning and is kept as editable source text by default.
Use `--strict-math` to fail instead. Diagnostics identify the active conversion engine and the
underlying conversion error.

Use `mddocx math-check FILE.md` for a non-writing preflight. It reports the active engine, total
equation count, native conversions, and required fallbacks for the body and notes.
`--json` emits a machine-readable
equation-by-equation report plus delimiter syntax issues, and `--strict` returns exit code 3 if a
fallback or explicit delimiter issue would be encountered.

## Current regression case

The tracked ChatGPT-style sphere fixture contains 20 display equations and two inline equations,
including boxes, fractions, Greek letters, text, spacing, scripts, and multiline math. Tests verify
that the generated DOCX contains all 22 native equations, seven native boxes, two native fractions,
valid inline/display containment, no raw dollar delimiters, and no nested Office Math objects.

Structural tests are not a substitute for visual qualification in Microsoft Word. Word 365 is the
primary visual target; LibreOffice may differ in equation layout, fonts, fields, and pagination.
