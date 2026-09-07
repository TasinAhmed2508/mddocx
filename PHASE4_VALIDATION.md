# Phase 4 Validation — mddocx 0.4.0

Validation date: 2026-08-07

## Release scope

Phase 4 is an additive post-PRD operational-maturity release. It preserves the established
Markdown → canonical AST → normalizer → DOCX renderer architecture and stable Phase 1–3 APIs.

## Automated tests

- Source test suite: **35 passed, 0 failed, 0 skipped**
- `python -m compileall -q src tests`: passed
- Existing 25 Phase 1–3 tests continue to pass unchanged
- Added Phase 4 coverage for:
  - reproducible DOCX packages;
  - input/AST compilation limits;
  - persistent normalized-AST cache;
  - malformed output-package rejection;
  - SARIF diagnostics;
  - explicit-only entry-point plugins;
  - deterministic batch conversion;
  - Phase 4 CLI behavior.

## Packaging

- Wheel: `dist/mddocx-0.4.0-py3-none-any.whl`
- Wheel SHA-256: `3b9f5b83be8fbb016b83cb3bf85001a7cde4a1a3efdeda3fa4b5d8673533d456`
- Wheel built with `pip wheel --no-deps --no-build-isolation`
- Wheel installed into a clean target directory and smoke-tested successfully
- Installed package reports version `0.4.0`
- Installed wheel generated a valid DOCX containing native OMML and fixed reproducible ZIP timestamps

## Phase 4 showcase artifact

- Markdown: `examples/phase4_demo.md`
- DOCX: `examples/phase4_demo.docx`
- DOCX SHA-256: `3a0aba8936916b935e716fc6ec70867c0315012a213db7704281e817dd3e8369`
- SARIF: `examples/phase4_diagnostics.sarif`

The showcase validates:

- native editable OMML equations;
- native Word table markup;
- native bidi/RTL paragraph properties;
- TOC/PAGE field infrastructure and field-update request;
- SVG input converted through the safe image path and embedded as Word media;
- portrait → landscape → portrait section sequence for a wide table;
- Word reopening through `python-docx`.

Package inspection results:

- 24 ZIP package parts;
- all XML and `.rels` parts parsed with a defensive lxml parser;
- 6 OMML `<m:oMath...>` occurrences;
- 1 bidi paragraph property;
- 1 Word table;
- 3 section-property blocks;
- 1 TOC field instruction;
- 1 embedded media part;
- all ZIP entries use timestamp `1980-01-01 00:00:00`;
- package parts are lexicographically ordered.

## Reproducibility and AST-cache validation

The Phase 4 showcase was rendered twice. The second run loaded the normalized AST from the persistent
cache and reported `ast_cache_hit=true`. Both generated DOCX files were byte-for-byte identical and
shared the SHA-256 shown above.

The same showcase was then rendered through the isolated installed wheel. Its bytes and SHA-256 were
again identical to the source-tree render.

## Stress render

A generated stress fixture containing 60 headings/sections, Unicode/RTL text, inline OMML, and 60
7-column tables with automatic landscape handling completed successfully.

Observed in this sandbox with Python allocation tracing enabled:

- output bytes: 39,453;
- elapsed wall time: approximately 3.94 s;
- parse: approximately 122 ms;
- normalize/transform: approximately 15 ms;
- render/finalize: approximately 3.80 s;
- peak traced Python allocations: approximately 3.66 MB;
- output SHA-256: `d044cb1634d0ea0b037b687954e736dc4b0666e0b3726a94ac74b671c82be68d`.

These timings describe this sandbox only and are not performance guarantees.

## Static-analysis tooling note

Ruff and mypy are declared in the project `dev` extra, but neither executable is preinstalled in this
sandbox and the configured package index returned no distributions for either package. Their installation
was attempted and could not be completed. Compilation, the complete test suite, wheel build/install,
OOXML/XML structural checks, reproducibility checks, and isolated-wheel smoke tests were used as the
available executable release gates.

The host environment's global `pip check` also reports an unrelated pre-existing `moviepy`/Pillow version
conflict. `mddocx` does not require Pillow in its core dependency set; Pillow is optional under the image extra.

## Result

**PASS** for the declared mddocx 0.4.0 Phase 4 scope.
