# Phase 5A — Word QA, Math Hardening, and Native Task Lists

Phase 5A is an additive post-PRD quality milestone. It does not change the stable
`render()`, `render_string()`, or `MarkdownWord` entry points.

## Native Markdown task lists

Common task-list syntax is recognized at the parser/AST boundary:

```markdown
- [x] Completed
- [ ] Pending
```

The marker is removed from paragraph text and retained as `ListItem.task_checked`.
The Word renderer emits a Word 2010+ checkbox content control (`w14:checkbox`) with
a Unicode fallback glyph. Ordinary list items in the same list continue to use
native Word numbering.

## `mddocx inspect`

Inspect a generated or third-party DOCX without opening Word:

```text
mddocx inspect report.docx
mddocx inspect report.docx --json
mddocx inspect report.docx --strict
```

The inspector reports package integrity and important Word structures, including:

- required/duplicate/invalid package parts;
- broken internal relationships;
- headings, tables, sections, images, hyperlinks, bookmarks and fields;
- native list paragraphs and checkbox content controls;
- footnote references and definitions;
- OMML equation, n-ary, radical and matrix counts;
- empty n-ary operands and malformed radical containers;
- conservative wide-table overflow candidates;
- suspicious replacement/placeholder characters.

Suspicious visible square/replacement characters are a QA warning rather than a
hard validation failure by default because a user may intentionally type such a
character. `ValidationConfig(detect_placeholder_chars=True)` can make that check
fatal in controlled pipelines.

## `mddocx doctor`

```text
mddocx doctor
mddocx doctor --json
```

This checks Python, required/optional package availability, temporary-directory
write access, and whether LibreOffice plus `pdftoppm` are available for page-level
visual QA.

## Page-render visual regression

Visual QA uses a real DOCX rendering host rather than only XML assertions:

```text
mddocx visual-qa output.docx --baseline-dir qa/baseline --update-baseline
mddocx visual-qa output.docx --baseline-dir qa/baseline
```

The command converts the DOCX to PDF with LibreOffice/soffice, rasterizes pages
with `pdftoppm`, and compares each page to a stored baseline using a tolerant mean
pixel-difference score. It catches layout regressions such as missing markers,
shifted equations, table reflow, clipping, and page-count changes.

The source test suite includes an opt-in page-render regression:

```text
MDDOCX_RUN_VISUAL=1 pytest tests/integration/test_phase5_visual_render.py
```

Visual baselines are host/version-sensitive. Projects should create/update their
own baselines on the Word-compatible renderer used in CI.

## Math regression corpus

The Phase 5A suite converts 600 deterministic LaTeX expressions through the
project-owned fallback parser and MathML → OMML renderer. The corpus covers powers,
subscripts, fractions, nested fractions, roots, n-ary operators, limits, grouped
superscripts, matrices, cases, aligned equations, accents, variants, boxes, Greek
symbols, and common operator symbols. Every n-ary object is structurally checked
for a real operand and generated text is checked for placeholder squares.

This corpus complements the real-world stress fixture; it does not make the
fallback parser a complete TeX engine.

## Stronger generated-package validation

Output validation now additionally supports:

- total uncompressed package-size limits;
- macro payload rejection in `.docx` output by default;
- duplicate package-part detection;
- broken internal-relationship detection;
- OMML n-ary/radical structure checks;
- optional suspicious-placeholder hard failure.
