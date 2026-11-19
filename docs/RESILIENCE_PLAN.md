# Conversion resilience plan: always produce a Word document

This plan covers one guarantee and the defects that stand in its way:

> **A conversion request should end with a DOCX on disk, or with a diagnostic that
> explains why it could not be written. It should never end with nothing and no
> reason, and it should never end with an internal exception.**

Today mddocx satisfies the first half of that sentence most of the time. What it does not do
is survive *one* broken element: a single malformed chart, one missing data source, or one
unexpected exception aborts the whole run and writes no file at all, even when ninety-nine
percent of the document was already rendered.

Part 1 records the audit that produced this plan. Part 2 is the design. Part 3 is the work
list with acceptance criteria. Part 4 is how each item is verified. Part 5 lists the
decisions that belong to the maintainer rather than to this document.

## What is already right

Three properties worth stating before the defects, because the plan builds on them rather than
replacing them:

- **A corrupt file is never written.** `_finalize_output` runs `validate_docx_package` on the
  finished bytes (`api.py:244`) and only then does `render_file` write them (`api.py:69`).
  Package validation, relationship validation, math-structure validation and the new
  content-model (`DOCX422`) checks all gate the write. Resilience must preserve this ordering.
- **Two failure classes already degrade instead of aborting**, and they are the model for
  everything below: math falls back to editable plain text under
  `MathFailurePolicy.mode` (`math_failure.mode`, default `warning`, diagnostic `MATH201`),
  and an unreachable image becomes a clickable caption under `ResourcePolicy.image_failure`
  (`RESOURCE2xx`). The pattern is proven. It is simply not applied to the rest of the
  document.
- **A conversion needs nothing but Python and the declared dependencies.** mddocx writes
  OOXML directly; it does not shell out to an office suite, a Java runtime, a browser or a
  network service, and `doctor` deliberately keeps an office suite out of its required set
  (`DoctorReport.ok` does not consider `visual_qa_ready`). That is the property the design
  below has to preserve, and it is why every check this plan adds has to work in-process.

One consequence deserves stating plainly, because it shapes Part 4. **The quality gate must
not depend on LibreOffice or Word.** Most people who install the package will not have
either, and the visual-regression helpers are the only part of the project that can use them
at all: `visual_qa.render_docx_pages` needs LibreOffice/soffice plus `pdftoppm`, or Word on
Windows through a PowerShell COM call. Treating that path as the way mddocx proves its output
is correct would mean the project's fidelity guarantee is unavailable on exactly the machines
most of its users run. Office rendering stays a secondary, opt-in cross-check; the primary
guarantee is that mddocx can audit its own output.

## Part 1 — Audit

Audit method: the pre-existing suite (492 tests, all passing) and the project's own linters,
then an 89-case adversarial conversion harness covering malformed structures, invalid Unicode,
pathological nesting, broken resources, and hostile YAML. The harness became
`tests/test_adversarial_inputs.py` and the suite stands at 597 tests. A second pass asked what
the project depends on outside Python (D11, D12); the claim that conversion needs no office
suite is now pinned by `tests/test_no_office_dependency.py`. Everything below is a real
observation, not a reading of the code.

### Defects found

| # | Defect | Evidence | Status |
|---|---|---|---|
| D1 | A malformed YAML front-matter block escaped as a raw PyYAML traceback with **exit code 1**, bypassing the diagnostic system entirely. Every other YAML site in the project wraps its parser (`PARSE350` for chart/data-table blocks, `PROJECT810` for manifests); the front matter did not. | `yaml.safe_load` at `parser/frontmatter.py:32`; reproduced with `---\ntitle: [unclosed\n  bad: : indent\n---` | **fixed** |
| D2 | A lone surrogate in the Markdown raised an uncaught `UnicodeEncodeError` from the byte-size limit check, so `render_string` leaked a non-`MddocxError` exception type that the public API does not document. | `len(markdown.encode("utf-8"))` at `limits.py:14` | **fixed** |
| D3 | `figures.add_image_path` swallowed every accessibility failure with a bare `pass`, so an image could ship without alt text and nothing reported it. Already recorded as wart W3 in `docs/ROADMAP.md`; it is a defect, not a debt. | `except Exception: pass` at `render/figures.py:148` | **fixed** |
| D4 | The missing-alt-text warning was emitted as `A11Y201`, which documents a missing table header row; the image code is `A11Y101`. Any tool grouping findings by code misreports both. | `render/figures.py:147` vs `accessibility.py:159` | **fixed** |
| D5 | The CLI caught only `MddocxError`, `OSError` and `ValueError`. Any other exception type reached the terminal as a Python traceback and exit code 1. D1 was one instance; the class of failure remained open behind it. | `cli.py` `main()` except-clauses | **fixed** |
| D6 | **One broken element aborts the entire conversion and writes no file.** A document of eleven good blocks plus one malformed chart produced an error message and no DOCX. The partial document was fully rendered and then thrown away. | `mddocx bad_chart.md -o out.docx` → exit 2, `out.docx` missing | open |
| D7 | Document-level limits (`LIMIT401`–`LIMIT406`) abort with no output, including "input too large", where a partially rendered or text-only document is both possible and useful. | `deep_emphasis` harness case → `LIMIT403`, no output | open |
| D8 | Front matter is settings, but a syntax error in it is fatal to the body. The document can be perfectly well-formed and still produce nothing because a metadata key was mistyped. | D1 after the crash fix: clean diagnostic, still no output | open, decision needed |
| D9 | A failed conversion leaves any pre-existing file at the output path untouched, so the caller can open a stale document and read it as the result of the run that just failed. | `api.py:69` writes only on success; nothing invalidates the old file | open |
| D10 | The output is written non-atomically. A crash or a full disk during a direct write could leave a truncated DOCX. | Shared atomic writer since 1.4.3 | fixed |
| D11 | `doctor` reported visual QA as unavailable on a Windows machine where it demonstrably works, because `visual_qa_ready` only looked for LibreOffice/soffice and ignored the Word COM route that `render_docx_pages` actually accepts. A diagnostic whose stated purpose is to prove a capability was returning a false negative. | `doctor.py` `visual_qa_ready` vs `visual_qa.py` `_convert_to_pdf`; observed on this machine: `doctor` said no while `pytest -m visual` passed through Word | **fixed** |
| D12 | Running the visual regression test on a machine without the office tools produced an unexplained `VisualQAUnavailable` failure rather than a clear *not run*, and nothing stopped a CI runner that had lost the tools from skipping every visual test and reporting green. | `tests/test_visual_regressions.py` called `render_docx_pages` directly; `pytest -m visual` required the tools with no probe | **fixed** |

### Failure taxonomy

Grouping the defects above, because the right response differs by group:

- **Class A — the input cannot be converted.** Unreadable source (`SOURCE401`/`SOURCE402`),
  invalid configuration (`CONFIG3xx`), a template that is not a DOCX (`DOCX301`). Aborting is
  correct. The only requirement is that the reason is a diagnostic, which it already is.
- **Class B — one element cannot be rendered.** A malformed chart, a missing CSV, an
  unsupported Mermaid diagram, a broken image, an unrenderable equation. The document is
  otherwise fine. **Aborting here is wrong**, and it is what D6, D7 and D8 all are. Math and
  images already behave correctly; everything else does not.
- **Class C — an internal defect.** A `TypeError` from an unanticipated node shape, an
  `lxml` error building an element, a `KeyError` from an unexpected config value. D1, D2 and
  D5 are instances. A converter cannot eliminate these by definition, which is precisely why
  the guarantee must be structural: the pipeline must be built so that **Class C cannot
  destroy the document**, only degrade it.

Class C is the reason this plan exists. Class B is the reason it is worth doing.

## Part 2 — Design

### The ladder

Four levels. Each level is attempted only when the previous one fails, and every transition
down a level emits a diagnostic. The mode is configurable and defaults to the level that
always produces output.

| Level | Name | Behaviour | Writes a file |
|---|---|---|---|
| 0 | `strict` | First error aborts. Today's behaviour, for CI and QA. | no |
| 1 | `balanced` | Per-element isolation: the failing element is replaced by a visible placeholder and the run continues. | yes, on any element failure |
| 2 | `recovery` | If the pipeline still fails outside the block loop, rebuild the document as plain text from the source. | yes, always |
| 3 | `failed` | Even level 2 could not run (disk, permissions, no writer). Diagnostics only; file removed if a partial one exists. | no |

**Level 1 — per-element isolation.** `DocxRenderer._render_block` (`renderer.py:263`) is the
single dispatch point for every block node in the document, which makes it the natural and
the only place this belongs. The change:

1. Checkpoint the document before the block: the body's child count, the numbering and
   relationship parts, and any package parts appended since the last checkpoint.
2. Dispatch the block inside a `try`.
3. On failure, roll the checkpoint back, record the diagnostic **as an error without
   raising**, and render a placeholder paragraph in a dedicated style carrying the source
   text and the diagnostic code.
4. Continue with the next block.

Two prerequisites make this work rather than merely move the problem:

- `DiagnosticReporter.emit` currently *raises* whenever severity is `error`
  (`diagnostics/reporter.py:15`) and roughly twenty-eight modules raise `MddocxError`
  directly. A non-raising `record()` is needed so the boundary can downgrade a fatal
  diagnostic into a reported one.
- Rollback must cover more than the body XML. A chart appends an embedded workbook part, a
  table may add numbering, an image appends media. Truncating the body leaves those parts
  orphaned. Orphaned parts are harmless to Word but they are not harmless to
  `validate_docx_package`, so the checkpoint has to be defined precisely, and the level-1
  output has to pass validation before it is accepted. If it does not, fall through to
  level 2. This is the expensive half of the item and where its estimate comes from.

**Level 2 — the recovery document.** The guarantee that survives arbitrary bugs. A small,
self-contained writer that takes the source Markdown and the collected diagnostics and emits
a valid DOCX: a short banner page naming the failure, then every source line as a paragraph in
the body style. No charts, no numbering, no images, no templates, no extensions. It uses
Python-docx directly, shares nothing with the normal render path, and is wrapped so it cannot
raise. This is the level that makes the promise literal — "even if any type of bug occurs" —
because it depends on almost nothing.

**Level 3 — clean failure.** If level 2 cannot run, print the diagnostics and remove any
partial output. Exit 2. Never a traceback.

### Guardrails

These hold at every level and are what make degraded output trustworthy rather than merely
present:

- **Never silent.** Every fallback emits a diagnostic with severity, code and remediation.
  The existing `--diagnostics-json` and `--diagnostics-sarif` outputs already carry them.
- **Never invisible.** A placeholder is written into the document itself, so a reader holding
  only the DOCX can see that something was replaced. Silently dropping content is worse than
  failing, because it looks like success.
- **Never marked clean.** Exit `0` means nothing was lost. Exit `3` means the file was written
  with fallbacks, matching the existing precedent of `mddocx math-check --strict`. Exit `2`
  means nothing was written. A CI job that cannot accept degradation uses exit code 3.
- **Never corrupt.** Validation continues to gate the write for every level, including
  recovery. A level that fails validation is not written, and the ladder steps down.
- **Never stale, never torn.** Write to a temporary file in the destination directory and
  `os.replace` it into position. This fixes D10 and makes "was the output updated?"
  answerable. On a failed run, preserve the previous output and report that it was not updated (D9).
- **Deterministic.** The recovery document is byte-reproducible like every other output, so
  `ReproducibilityConfig` and the golden-corpus work in the roadmap (Q3) continue to apply.

### Where the code changes

| File | Change |
|---|---|
| `diagnostics/reporter.py` | add `record()` (append, never raise) and `has_errors` |
| `render/renderer.py` | checkpoint/rollback and placeholder at the `_render_block` boundary |
| `render/context.py` | expose the checkpoint on the render context if the block surfaces need it |
| `config.py` | new `ResilienceConfig(mode, recover, placeholder_style)` |
| `config_validation.py` | validate the mode literal alongside the existing policy checks |
| `api.py` | drive levels 1–3 in `_compile`; atomic write in `render_file` |
| `compiler.py` | `CompilationResult.completed_with_fallbacks` currently keys on `MATH201` alone; generalise it |
| `cli.py` | `--strict` / `--balanced` / `--best-effort` flags; exit code 3; `--traceback` (already added) |
| `batch.py`, `project.py` | they already continue per file; give each file the same ladder |
| `styles/default.py` | the placeholder style |

## Part 3 — Work list

Sizes as in `docs/ROADMAP.md`: **S** ≈ a day, **M** ≈ a week, **L** ≈ multi-week.

| # | Item | Priority | Size | Acceptance criterion |
|---|---|---|---|---|
| R1 | Preserve and report previous output on failure | P1 | S | The DOCX is written to a temporary file and `os.replace`d into position; a simulated failure mid-write leaves either the previous file or no file, never a truncated one; a failed run reports that the output path was not updated (D9, D10) |
| R2 | Non-raising `record()` on the reporter | P1 | S | `record()` appends an error diagnostic without raising; `emit()` keeps raising; existing callers are unchanged; a test asserts both behaviours |
| R3 | `ResilienceConfig` and its validation | P1 | S | `mode` accepts `strict`/`balanced`/`best_effort` and rejects anything else with `CONFIG3xx`; defaults preserve today's behaviour until R4 lands |
| R4 | Per-element isolation at the block boundary | P1 | L | A document whose only defect is one malformed chart, one missing data source, one unsupported diagram and one unrenderable row of each type still produces a DOCX; the file passes `validate_docx_package`; each failure appears as a placeholder naming its diagnostic code; exit code is 3 (D6) |
| R5 | Rollback completeness | P1 | M | After a fallback, the package contains no orphaned media, workbook, numbering or relationship parts relative to a document that never contained the failing block; byte-comparison of the fallback against a hand-authored equivalent document passes |
| R6 | Text-only recovery document | P1 | M | When the pipeline fails outside the block loop, a valid DOCX is still written containing every source line as body text plus a banner naming the failure; the fallback writer is wrapped so it cannot raise; byte-reproducible (D6, D7) |
| R7 | Ladder orchestration and exit codes | P1 | M | `balanced` writes a document or steps down; `strict` reproduces today's abort on the same input; exit codes are 0 / 3 / 2 as specified, asserted per level; `Compiler.compile_string().completed_with_fallbacks` is true for every level-1 and level-2 result |
| R8 | CLI flags and reporting | P1 | S | `--strict`, `--balanced` (default) and `--best-effort` select the mode; the output path, every fallback diagnostic and the exit code are reported consistently for single, batch and project builds |
| R9 | Front-matter policy | P2 | S | Malformed front matter downgrades to a warning that names the ignored block, and the body still converts, or the fatal behaviour is explicitly documented as intended (see Part 5, D8) |
| R10 | Limit policy for oversized input | P2 | S | Exceeding `max_input_bytes` either converts the leading portion under a named truncation diagnostic or documents the abort; exceeding a structural limit (`LIMIT403`–`LIMIT406`) degrades the offending subtree instead of the document (D7) |
| R11 | Resilience documentation | P2 | S | `docs/COMPATIBILITY.md` and the README state the guarantee, the modes, the exit codes and what a placeholder looks like; the degraded-output path is documented as supported rather than incidental |
| R12 | **Dependency-free fidelity self-check** — `mddocx verify document.md document.docx`, plus `Compiler.verify()` in the API | P1 | L | With no process launched and no network access, the command compares the source AST against the emitted package and reports every missing, extra or altered heading, paragraph, run, list item, table row, table cell, equation, image, alt text, note, hyperlink, bookmark, field and style as diagnostics with codes; a document mddocx just rendered reports zero drift; a hand-edited package reports the specific drift; `--json` and a non-zero exit on drift make it a CI gate. This is the check every other item in Part 4 depends on, and the feature that lets a user validate output on a machine with no office suite |
| R13 | Make the office path explicitly optional everywhere | P2 | S | **Partly done.** The `visual` test already reports *not run* with a reason when no office renderer is present, never a pass, and the CI visual job asserts `visual_qa_ready` first so a broken runner cannot skip silently; `doctor` now reports the Word-on-Windows route it always supported and labels the group "Optional visual QA tools". Remaining: `docs/WORD365_QA.md`, `docs/COMPATIBILITY_MATRIX.md` and the README should state the same thing in the same words, and Part 5 decision 4 settles whether the helper stays in the core install |

## Part 4 — Verification, without an office suite

The plan is only worth its estimate if a degraded document is easier to trust than a missing
one, and that trust has to be available on a machine that has nothing installed but Python.
Every check below therefore runs in-process. Office rendering appears once, at the end, as an
optional cross-check rather than a gate.

### The gate: mddocx audits its own output

mddocx already parses a finished package back (`inspection.py`, `validation.py`,
`schema_order.py`) and it already traverses the source AST. Those two capabilities together
are enough to answer the only question that matters — *does this DOCX contain what the
Markdown said?* — with no external tool. That check is the project's real differentiator, and
it is work item R12 below: a fidelity self-check that compares the source AST against the
emitted package element by element (headings and their levels, paragraph text and inline runs,
list nesting and markers, table rows and cells, equations, images and alt text, notes,
hyperlinks, bookmarks, styles, fields) and reports every drift as a diagnostic.

Once it exists, resilience is verifiable by construction rather than by inspection:

- **One broken element per fixture.** A fixture corpus in which each document has exactly one
  deliberately broken element, for every element that can break. Each asserts four things with
  no external process: a DOCX exists, it passes `validate_docx_package` and the content-model
  checks, the placeholder names the right diagnostic code, and the exit code is 3. This is the
  error-path matrix the roadmap lists as Q9, given a concrete shape.
- **Everything that survived is intact.** Run the R12 fidelity check over each degraded
  document and assert that the parts that did *not* fail match the source exactly. This is what
  separates "wrote a file" from "wrote the right file", and it is the check that the audit's
  hand verification had to fake with an external renderer.
- **Monotonicity.** For documents with no failures, `balanced` output is byte-identical to
  `strict` output. Resilience must not drift the good path, and this is the cheapest possible
  check on that.
- **The roadmap's fuzz item (Q5) gets a definition.** "Generated documents always render" means
  the ladder never reaches level 3 for any generated input: hypothesis-generated Markdown must
  always yield a package that validates *and* passes the fidelity check.
- **No new tracebacks.** The 89-case adversarial corpus from the audit is already a test: no
  case may raise anything other than `MddocxError`, and no case may return an unreadable
  package. The same corpus runs with every office tool hidden from `shutil.which`, which is
  how `tests/test_no_office_dependency.py` now pins the independence claim.
- **Byte-reproducibility.** Both the normal and the recovery path render identically twice,
  which the existing `ReproducibilityConfig` plumbing already makes checkable.

### The optional cross-check

The repository's `visual` pytest marker drives LibreOffice page rendering, and it has earned
its place for one narrow purpose: catching layout and pagination regressions that no structural
check can see, because they are properties of the *renderer* rather than of the package. Keep
it that way, and never let it become the gate:

- It runs as a separate, opt-in job that may be skipped on a machine without the tools, and it
  never blocks a release on their absence.
- It is marked such that a missing LibreOffice reports as *not run*, never as *passed*. A
  silently skipped visual test that reads as green is worse than no visual test.
- It is a nightly or pre-release job, not a per-commit requirement, because it needs a native
  office install that contributors are not expected to have.

The one thing this audit did use it for — confirming that a document built from
surrogate-containing input opens in a real office application — is exactly its correct role:
reassurance that the package is readable beyond what a parser can prove, never the test that
decides whether the feature works.

## Part 5 — Roadmap decisions

Strict conversion stays the default, including in v2. Recovery is explicitly enabled by the
caller. Its initial scope is malformed chart/data-table declarations and unsupported diagram
syntax detected before package mutation. Malformed front matter, limit violations, invalid
templates, resource-policy failures, and unexpected internal errors are fatal. The broader
ladder below is design history for potential later work.

Three choices shape the work and are not this document's to make:

1. **What is the default mode, and when does it change?** `balanced` is the behaviour the
   guarantee asks for, but it changes what exit code an existing script sees on a document with
   a broken element: today 2 and no file, afterwards 3 and a file. That is a behaviour change
   for anyone checking `status != 0` expecting no output. Adopting `balanced` as the default in
   1.5.0 keeps it in a release already dedicated to defect prevention (`docs/ROADMAP.md`,
   Milestones); deferring it to 2.0 keeps 1.5.0 free of behaviour changes.
2. **Is malformed front matter fatal (D8)?** The crash is fixed either way. The open question
   is whether a mistyped metadata key should be able to prevent a document whose body is
   perfectly valid from being written. The resilient answer is no: ignore the settings block
   with a warning and convert the body.
3. **Does an oversized input abort (D7)?** A 20 MB limit that produces nothing is a hard
   failure mode; a limit that converts the first portion and says so is a softer one. The
   second is more useful and requires an explicit truncation contract.
4. **Does the office-suite helper belong in the core package at all?** `visual_qa.py`,
   the `mddocx visual-qa` command, the `visual` marker and the CI office job form a coherent
   unit that most users cannot run. Three defensible options: keep it as it is and keep saying
   it is optional (R13); move it behind an extra so the default install carries only the code
   paths it can actually exercise; or keep the comparison and raster-diff helpers, which need
   only Pillow, and drop the tool-discovery and subprocess conversion that require an office
   install. The third separates what is useful everywhere from what needs someone else's
   software.

## Suggested sequence

1. **R1–R3** land together as the non-breaking foundation: atomic writes, `record()`, and the
   config surface with today's behaviour as the default.
2. **R12** lands early, ahead of the ladder, and for an uncomfortable but honest reason: it is
   the only way to check the ladder without an office suite. It also happens to be the feature
   worth leading with, since "your converter can prove its own output is correct, offline" is a
   stronger claim than any amount of graceful degradation.
3. **R4–R5** are the substantive change and carry the risk. Land them behind `balanced`, off by
   default, and accept them only when the degraded fixtures pass the R12 fidelity check.
4. **R6–R8** complete the ladder and make it selectable and reportable.
5. **R9–R11** resolve the policy questions and document the guarantee.
6. **R13** demotes the office path to an explicitly optional cross-check, so nothing in the
   documentation, the CI configuration or the test report implies that a user needs it.
7. Flip the default in the release that can carry a behaviour change, with the exit-code
   contract, the fidelity check and the degraded fixtures as the gate.
