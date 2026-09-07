# Phase 3 Validation

Validation date: 2026-08-07

## Automated checks

- `pytest`: 25 passed, 0 failed in the release environment.
- `compileall`: passed for `src/` and `tests/`.
- Phase 3 demo DOCX reopened with `python-docx`.
- Every XML part in the Phase 3 demo and stress DOCX parsed successfully with network/entity resolution disabled.
- Demo package contains native OMML, native tables, RTL/bidi markup, TOC/PAGE fields, converted SVG media, and portrait → landscape → portrait sections.
- Safe remote-image fetching was tested end-to-end against a local HTTP fixture with explicit scheme/domain/private-host opt-in.

## Stress render

A generated 40-section technical document contained repeated native equations, nested lists,
Unicode text, and ten 7-column tables using automatic landscape sections.

Observed in this sandbox:

- parse: ~51 ms
- normalize/configure: <1 ms
- render: ~1468 ms
- total: ~1520 ms
- peak traced Python allocations: ~2.58 MB
- output size: 55,975 bytes
- diagnostics: 10 informational `TABLE301` landscape-section notices, no errors/warnings

These figures are environment-specific and are not performance guarantees.

## Packaging

- Version: 0.3.0
- Wheel built with setuptools using `--no-build-isolation`.
- Wheel installed into an isolated target and smoke-rendered successfully.
- Source release is delivered as `mddocx_phase3.zip`.

## Tooling note

The PRD requests Ruff and mypy/Pyright in the development loop. Neither Ruff nor mypy was
preinstalled, and the sandbox package index returned no available distributions when installation
was attempted. Syntax compilation and the full automated test suite were run successfully; the
project retains Ruff/mypy in the `dev` optional dependency set for environments where those tools
are available.
