# AI-generated mathematical Markdown

mddocx accepts common mathematical Markdown copied from ChatGPT, Claude, Gemini, and other
assistants. Parsing is syntax-driven; provider names do not change document behavior and no AI
service or network request is used during conversion.

## Recognized forms

| Source form | Result |
|---|---|
| `\\(x^2\\)` | Inline native Word equation |
| `$x^2$` | Inline native Word equation |
| `\\[` ... `\\]` | Display native Word equation |
| `$$` ... `$$` | Display native Word equation |
| fenced `math`, `latex`, `tex`, or `mddocx-math` | Display native Word equation |

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

LaTeX arrays support `l`, `c`, and `r` columns, bounded repetition such as
`*{2}{r}`, vertical rules, and intercolumn expressions such as `r@{.}l` for aligned
decimal points. Vertical rules stay aligned across tall cells such as fractions. Mixed
intercolumn spacing uses Word's native zero-gap columns with an em space at ordinary
column boundaries. Horizontal rules, array frames, and `\multicolumn` use the math
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
