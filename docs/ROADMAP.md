# Roadmap: usability, performance, and defect prevention

This plan covers two things that belong together: features that make mddocx easier and
faster for users, and the engineering work that keeps defects out. Priorities are P1
(next milestone), P2 (following), P3 (later). Sizes are rough: **S** ≈ a day, **M** ≈ a
week, **L** ≈ a multi-week program.

Every item lists an acceptance criterion, because a roadmap without a definition of done
is a wish list.

## Part 1 — Usability and performance for users

| # | Item | Priority | Size | Acceptance criterion |
|---|---|---|---|---|
| U1 | `python -m mddocx` parity with the console script | done | S | `python -m mddocx --version` and every subcommand work; guarded by `tests/test_release_contract.py` |
| U2 | Shell completions: `mddocx completions bash\|zsh\|fish\|powershell` | P1 | S | Generated scripts complete subcommands and flags; one test per shell |
| U3 | Single-file watch mode: `mddocx watch document.md` | P1 | M | Rebuild on change in under one second for a 100-section document, debounced, reusing `mddocx cache` and project fingerprints |
| U4 | Word-native change report: `mddocx diff old.docx new.docx` | P1 | M | Structural report of headings, tables, equations, notes, images, references, and chapters added/removed/changed, built on `inspection.py`; supports `--json` |
| U5 | Machine-readable catalog: `mddocx capabilities --json` | P1 | S | Emits the feature matrix, every diagnostic code with severity and remediation, and supported config keys, generated from source so it cannot drift |
| U6 | Parallel batch conversion: `--jobs N` for `render_many` | P2 | M | 4× throughput on a 20-document project with byte-identical output to serial rendering |
| U7 | Incremental math cache across runs | P2 | M | LaTeX→OMML results cached on disk and reused between invocations; `doctor` reports cache health |
| U8 | Markdown dialect profiles: `--profile gfm\|commonmark\|ai\|academic` | P2 | M | One flag reproduces the documented config bundles; profiles are covered by fixtures |
| U9 | Accessibility assistant: alt-text suggestions + missing-alt report | P2 | M | `mddocx accessibility --suggest` proposes alt text from caption/title/context and lists every image missing it |
| U10 | Chart coverage: stacked, area, combo, secondary axes for bar and line | P2 | L | New types render editable ChartML with embedded workbook and pass the chart conformance corpus |
| U11 | Tagged PDF export path | P3 | L | Documented, tested LibreOffice pipeline that preserves heading structure and image alt text |
| U12 | Block-surface plugin API v2 | P3 | L | Third-party surfaces receive a typed host contract instead of the raw renderer; documented in `EXTENSIONS.md` |
| U13 | Rename the internal `mddocx/render` package | P3 | M | Removes the name collision with the public `render()` function (see Known warts), with a compatibility shim for one release |

## Part 2 — Defect prevention

Today's bug hunt (section-scoped caption counters, bookmark placement, the missing
`__main__`) found three defects that no test covered. The items below convert each class
of defect into a build failure rather than a user report.

| # | Item | Priority | Size | Acceptance criterion |
|---|---|---|---|---|
| Q1 | OOXML schema-order validation in `validation.py` | P1 | M | `--strict` rejects `w:pPr` that is not first, bookmarks that straddle paragraph boundaries, and out-of-sequence `w:r` children; regression tests reproduce today's two fixed bugs |
| Q2 | Field-code lint with an allow-list | P1 | S | A test fails if any emitted `w:instrText` uses an unknown switch or a control character; the allow-list lives next to `ooxml/fields.py` |
| Q3 | Golden render corpus in CI | P1 | M | `tests/fixtures/golden/` stores hashes for the 18-document corpus, with `--update-goldens`; the suite fails on unintended output changes |
| Q4 | Differential refactor harness in `scripts/` | P1 | S | `scripts/differential_render.py` renders the corpus with the checked-out and the previous revision and reports differences; CI runs it when `src/mddocx/render/**` changes |
| Q5 | Fuzz and property tests (Hypothesis) | P2 | M | Generated documents always render, always pass `validate_docx_package`, and render byte-identically twice; no unexpected exception in 10k cases |
| Q6 | Type-completeness ratchet | P2 | L | `DocxRenderer` state is typed, surfaces take a `RendererHost` protocol, `mddocx.render` joins the mypy subset, and the package-wide error count is recorded in a budget file that may only shrink |
| Q7 | Coverage gate and mutation testing | P2 | M | Branch coverage ≥ 90% for `mddocx/ooxml` and `mddocx/render`; mutation score ≥ 80% for `fields.py`, `tables.py`, `notes.py` |
| Q8 | Generated diagnostics catalog | P2 | S | `docs/DIAGNOSTICS.md` is generated from source; a test fails on a duplicated or undocumented code |
| Q9 | Error-path matrix | P2 | M | One test per diagnostic code asserting code, severity, and remediation text; a coverage report lists codes without a test |
| U14 | Pre-commit hooks and nightly stress | P2 | S | Hooks run ruff, ruff-format, the mypy subset, and the fast tests; a nightly job renders a 500-section, 5 MB document within the benchmark budget |
| Q10 | Visual regression expansion | P3 | L | Nightly Word 365 and LibreOffice visual diffs on the corpus with documented tolerances, plus a curated layout corpus |
| Q11 | Security fuzz for the resource resolver | P3 | M | Property tests for path traversal, redirect chains, MIME mismatches, decompression bombs, and size limits |

## Part 3 — Known warts and deferred work

Recorded so they are decisions rather than surprises. Only W1 and W2 are defects; the
rest are structural debts.

| # | Item | Status |
|---|---|---|
| W1 | Section-scoped figure/table/listing reset fields carried a carriage return instead of the Word `\r` switch, so counters never restarted | fixed |
| W2 | Heading and caption bookmarks were written before `w:pPr`, violating the `CT_P` sequence | fixed |
| W3 | `figures.add_image_path` swallows every exception while attaching alt text, so an accessibility failure can pass silently | planned (Q9): emit a diagnostic instead of `pass` |
| W4 | `mddocx.render` as an attribute is the public `render()` function, shadowing the internal subpackage; `import mddocx.render` therefore surprises tooling | planned (U13) |
| W5 | Package-wide mypy reports 321 errors; CI checks only an 11-file subset | planned (Q6) |
| W6 | `RenderConfig` values set through front matter are assigned without validation of literal types (`api.py`, `project.py`) | planned (Q6) |
| W7 | Reserved: `docs/FIDELITY_FIRST_V2_PLAN.md` remains the source of truth for the staged 2.x program | tracked there |

## Milestones

1. **1.5.0 — defect prevention first.** Ship today's fixes with Q1–Q4: schema-order
   validation, field-code lint, the golden corpus, and the differential harness. This is
   the release that makes the 1.4.x fidelity guarantees self-checking.
2. **1.6.0 — author experience.** U2, U3, U4, U5: completions, single-file watch, the
   native change report, and the machine-readable catalog.
3. **1.7.0 — scale and quality ratchet.** U6, U7, U9, Q5–Q9: parallel and incremental
   builds, accessibility assistance, fuzzing, typed surfaces, coverage and mutation gates.
4. **2.x — platform work.** U10–U13 and Q10–Q11: chart breadth, tagged PDF, the typed
   plugin boundary, the subpackage rename, and visual/security hardening.

## How to use this document

- Each PR addresses one row and states its acceptance criterion in the description.
- New rows go in the table rather than into issue text, so the plan stays readable and
  reviewable in the repository.
- When an item ships, move the row into `CHANGELOG.md` and delete it here; this file is a
  plan, not a history.
