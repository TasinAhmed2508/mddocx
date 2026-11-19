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
write access, and whether an optional page-level rendering host (LibreOffice plus
`pdftoppm`, or Microsoft Word on Windows) is available. That last group is reported
under "Optional visual QA tools" and is never a requirement: conversion and
structural validation need no office application.

## Page-render visual regression (optional)

This section describes an optional maintainer cross-check. It is the one part of the
project that needs software mddocx does not ship, and no feature, test gate, or
normal conversion depends on it. The structural checks in `mddocx inspect`,
`mddocx accessibility` and the render-time content-model validation are the primary
verification and run anywhere Python runs.

Visual QA uses a real DOCX rendering host rather than only XML assertions:

```text
mddocx visual-qa output.docx --baseline-dir qa/baseline --update-baseline
mddocx visual-qa output.docx --baseline-dir qa/baseline
```

The command converts the DOCX to PDF with LibreOffice/soffice (or Word on Windows),
rasterizes pages with `pdftoppm`, and compares each page to a stored baseline using a
tolerant mean pixel-difference score. It catches layout regressions such as missing
markers, shifted equations, table reflow, clipping, and page-count changes. When those
tools are absent the command reports that they are unavailable rather than failing
obscurely, and the opt-in test reports *not run* rather than a pass.

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
