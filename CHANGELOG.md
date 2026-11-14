# Changelog

## Unreleased — content-model validation

Generated documents are now validated against the WordprocessingML content model, not only
against the ZIP and relationship structure that surrounds it. Until now a document whose
`w:pPr` followed a run, whose `w:rPr` followed its text, or whose `w:tblBorders` followed
`w:tblLook` was well-formed XML that still opened, so nothing reported it: Word either
declined the content or quietly ignored the misplaced element. Those sequences are now
checked before the file is written.

### Added

- `mddocx.ooxml.sequence` owns the ECMA-376 sibling sequences mddocx emits — paragraph, run,
table, table-row, table-cell, section, paragraph-border, cell-margin, table-border, style and
list-level properties — and the two operations that follow from them: `insert_ordered()`,
used by every emitter that builds an element by hand, and `get_or_add()`, which reuses the
single child the schema allows instead of writing a second one. `mddocx.schema_order` reads
the same tables to check a finished document, so a sequence is defined exactly once.
- `inspect_docx`/`inspect_docx_bytes` report `schema_order_violations` for the body,
headers, footers, footnotes, endnotes, comments, styles and the numbering part; they count
as structural issues, so `mddocx inspect --strict` exits 2 and names each departure.
- Render-time validation raises the new `DOCX422` diagnostic instead of writing a document
Word may refuse, with `ValidationConfig.validate_schema_order` (default `True`) and the
existing `--no-validate-output` flag as the single-render escape hatch.
- Regression coverage reproduces the 1.4.0 bookmark defect (`w:pPr` written after a
bookmark), checks run properties that trail their text, and renders the shipped fixtures and
the hand-written XML surfaces with zero violations.

### Changed

- The library's positioning now leads with the property most users care about: mddocx writes
  OOXML directly, so a conversion needs no office suite, no Microsoft Word, no LibreOffice, no
  Java, no browser, and no network, and it verifies its own output in-process. The README states
  this in its opening section and among the headline capabilities, and
  `docs/COMPATIBILITY_MATRIX.md` gained explicit runtime rows for the office suite, Java, browser
  and external converters all reading "not required".
- The optional page-render cross-check is labelled as optional wherever it appears: `mddocx
  visual-qa` says so in its own help text, `docs/PHASE5A.md` marks the section optional and
  states that nothing in normal conversion depends on it, and `docs/COMPATIBILITY_MATRIX.md`
  moves it under a maintainer-only heading.
- The machine-readable fidelity contract records the secondary renderer signal as
  `optional_renderer` instead of a vendor-named field, so the contract no longer reads as though
  an office application participates in a conversion. The v1 values and the Word 365 authority
  column are unchanged; `tests/test_release_contract.py` requires the renamed key.
- `docs/FIDELITY_FIRST_V2_PLAN.md`, the source of truth for the staged 2.x program, now states
  the governing constraint up front: the library may not acquire an outside dependency, the
  dependency-free structural and round-trip checks are the primary fidelity gate, and a renderer
  is at most an optional secondary signal that never gates a release. `docs/ROADMAP.md` aligns
  U11, Q10 and Q5 with the same rule.

### Fixed

- Ten out-of-sequence emissions found by the new check: `w:tblBorders` after `w:tblLook`;
`w:shd` after `w:spacing`/`w:ind` in paragraph properties (body and styles); `w:cantSplit`
after `w:tblHeader`; `w:tcMar` and `w:shd` after `w:vAlign`; `w:bidi` after `w:jc`;
`w:rFonts` after `w:u`, `w:i` or `w:strike` in hyperlink and note runs; and `w:suff`
written after `w:lvlText` in list levels. Emitted XML changes only in element order; rendered
content is unchanged.
- List numbering now attaches `w:numPr` through the ordered accessor instead of appending it
  to `w:pPr`.
- Malformed YAML front matter no longer escapes as a raw PyYAML traceback with exit code 1.
  `split_front_matter` raises the new `PARSE353` diagnostic naming the file and the line
  inside the block, with remediation text, so the failure matches every other unparseable
  YAML block in the document and exits 2.
- Markdown containing a lone surrogate no longer crashes the byte-size limit check with an
  uncaught `UnicodeEncodeError`. The limit is measured with `surrogatepass`, and the invalid
  code point is dropped at the XML boundary exactly like the other code points XML 1.0
  forbids, so the document still compiles.
- `figures.add_image_path` no longer swallows every failure with `pass` while attaching an
  image's accessibility metadata: it reports `A11Y202` naming the image, because a silently
  missing alt text is the accessibility defect `mddocx accessibility` is meant to catch. The
  missing-alt-text warning now uses `A11Y101`, the documented image code, instead of `A11Y201`,
  which documents a missing table header row.
- The command-line entry point no longer lets an unexpected exception type reach the terminal as
  a Python traceback. An internal defect now prints `INTERNAL500` with the exception type, a
  pointer to the issue tracker, and an exit code of 2; `--traceback` prints the full stack when
  the report needs it.
- `mddocx doctor` now reports visual-QA readiness accurately instead of requiring LibreOffice:
  it recognises Microsoft Word driven through COM automation on Windows, and it labels the whole
  group "Optional visual QA tools" stating that page rendering is an optional layout
  cross-check that document conversion does not need. Previously a Windows machine with Word was
  told visual QA was unavailable even though the renderer would have worked.
- The optional visual regression test now reports *not run* with a clear reason when no office
  renderer is installed, rather than failing with an unexplained error or reading as a pass. The
  CI visual job asserts `visual_qa_ready` before running it, so a runner missing the tools fails
  loudly instead of silently skipping every visual test.
- `tests/test_no_office_dependency.py` pins the independence claim: conversion, images, tables,
  equations, TOC and page fields all render with every office tool hidden from `shutil.which`,
  `doctor` still passes, and the visual helper raises a clear error rather than hanging.

## 1.4.3 — Compiler maintenance and performance

- Reuse validated equation conversions, table measurements, flowchart parsing and layout levels,
  and parsed DOCX parts. File compilation returns the bytes it wrote without reopening the output.
- Share the layout, rendering, and finalization path for Markdown and document AST inputs.
  Use one atomic file writer for DOCX output and compiler caches.
- Keep project builds with explicit configuration out of the manifest cache. Rebuild if the
  saved state is malformed, and stream dependency hashes without loading whole files into memory.
- Apply the Markdown input size limit to each project source and include before parsing.
- Remove unused private math helpers and avoid repeated bookmark and heading identifier lookups.

## 1.4.2 — Flowcharts, tables, and conversion safety

- Preserve labeled Mermaid flowchart connections and divide long diagrams into readable,
  overlapping panels; keep branch conditions and multilingual node labels as editable text.
- Convert HTML line breaks in Markdown tables to Word line breaks and keep table headers with
  the first data row.
- Detect Bangla in mixed-language documents and choose an installed Bangla font automatically,
  while preserving the font settings for other scripts. The guided theme menu no longer requires
  a separate Bangla option.
- Prevent document output and diagnostic reports from overwriting source, template, resource,
  or other output files; replace DOCX files only after writing a complete temporary file.
- Report invalid project settings clearly and show conversion warnings in batch and interactive
  modes. Invalid YAML value types no longer cause unhandled type errors.
- Preserve invalid inline math markers as text instead of interrupting conversion.

## 1.4.1 — Install diagnostics and collision safety

This release fixes the failures that surround a conversion rather than the conversion itself: an
install that resolves to a different project, a documented command missing from the published
wheel, an optional engine reported as ready when it could not run, and Bangla output that could be
unreadable with no warning.

### Fixes

- `mddocx` now reports the unrelated PyPI project named `mddocx`, which ships the same `mddocx`
  package directory and the same `mddocx` console script and therefore overwrites this one when
  both are installed. `mddocx` warns with the exact uninstall/reinstall commands, `mddocx doctor`
  lists the conflict and fails, and the new `mddocx-native` command runs through a launcher that
  lives outside the shared package, so it cannot be overwritten: in a corrupted environment it
  refuses with the repair commands instead of silently executing the other project
  (`MDDOCX_ALLOW_IMPORT_CONFLICT=1` bypasses the refusal).
- Running `mddocx` with no arguments on an interactive terminal now opens the guided console
  with quick-start lines instead of failing with an argparse usage error. Non-interactive
  invocations keep the previous exit-code-2 usage error.
- `mddocx doctor` now converts one equation to prove the math pipeline works, and reports the
  engine that actually ran, the JavaScript runtime it found, and why the engine is unavailable
  when it is. A MathJax sidecar script with no JavaScript runtime is no longer reported as
  available, and `mddocx math-check` no longer claims the MathJax engine when equations fall
  back to another one. It also probes SVG support, because CairoSVG can be installed and still
  fail when the native cairo library is absent.
- Bangla output no longer produces unreadable glyphs silently: a configured Bangla font that is
  not installed raises a `FONT301` warning explaining the options, and the new `--bengali-font`
  option accepts a font name, `none` to disable the output pass, or `auto` to use the legacy
  `SutonnyMJ` font when installed and an installed Unicode Bangla font otherwise. Project
  manifests accept `render.bengali_font`.
- Documents without Bangla text skip the Bangla output pass instead of rewriting every Word XML
  part and rebuilding the package.
- Section-scoped figure, table, and listing counters now emit the Word `\r` reset switch
  instead of a carriage return, so caption numbering restarts in each new section as
  documented for `caption_number_format="section"`.
- Heading and caption bookmarks are written after `w:pPr`, matching the WordprocessingML
  `CT_P` sequence instead of preceding the paragraph properties.
- `python -m mddocx` now runs the command-line interface instead of failing with
  `No module named mddocx.__main__`.

### Changed

- `latex2mathml` is now a core dependency, so a plain `pip install mddocx-native` always has a
  real equation engine when no JavaScript runtime is available. The `math` extra remains for
  compatibility.
- Added `all` and `mathjax` extras: `mddocx-native[all]` installs the math, image, and academic
  extras together, and `[mathjax]` additionally provides a Node.js runtime for the bundled
  MathJax engine.
- The build requires setuptools 77 or newer, the first release that accepts the PEP 639 license
  expression and license-file metadata this project already declares.
- README documentation links are absolute so they resolve on the PyPI project page, and the
  install section documents the `mddocx` name conflict, the `mddocx-native` command, and a
  troubleshooting list.

### Internal

- Consolidated script and font policy: Unicode classification moved to `mddocx.scripts`,
  font-slot resolution to `mddocx.styles.fonts` (one rule shared by Word styles and runs),
  package part registration to `mddocx.ooxml.package`, and footnotes and endnotes into one
  spec-driven `mddocx.ooxml.notes` module. Rendered output is byte-identical for the
  multilingual, notes, comments, charts, figure, and bibliography fixtures.
- Split the 1,683-line `mddocx.render.renderer` into a 480-line orchestrator plus
  per-surface modules (`front_matter`, `text_blocks`, `lists`, `tables`, `data_tables`,
  `charts`, `figures`, `code_blocks`, `math_blocks`, `citations`, `document_setup`,
  `sections`, `headers_footers`). Block surfaces are now functions that receive the live
  renderer, so line counts, file ownership, and the direction/font policy are easier to
  audit; rendered output is byte-identical across an 18-document corpus.

### Performance

- Fast-path ASCII text in direction and script classification. `is_rtl_text`, `has_cjk`,
  and `has_complex_script` now return after one C-level ASCII scan and de-duplicate code
  points before range checks, removing the overhead the 1.4.0 script slots added to
  Latin-only documents.

### CI

- Give the large-document benchmark a platform-aware budget: 30 seconds on Linux and 60
  seconds on macOS and Windows hosted runners, which measured the 100-section corpus at
  33.7 seconds and 44.7 seconds respectively.
- The clean-install smoke test now exercises the documented entry points (`mddocx`,
  `mddocx-native`, and `python -m mddocx`) and adds a second environment that installs the
  `all` extra from the built wheel and converts an equation-heavy fixture.

## 1.4.0 — Multilingual script coverage

This release makes the script-aware output boundary cover every writing system the
renderer accepts, instead of Bengali, CJK and right-to-left text only.

### Complex-script font coverage

- The Word complex-script font slot (`w:cs`) is now applied to every complex script —
  Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam,
  Sinhala, Thai, Lao, Tibetan, Myanmar, Khmer, Ethiopic, Mongolian, Syriac, Thaana,
  Arabic and Hebrew — through `--complex-script-font` and `RenderConfig.fonts`.
- Indic, Southeast Asian and other left-to-right complex scripts receive the font slot
  without inheriting right-to-left direction.
- CJK detection now includes the extension planes, Hangul Jamo, compatibility
  ideographs and halfwidth Katakana so large East Asian documents keep the
  configured East Asian font.

### Direction and fonts on every text surface

- Right-to-left paragraph direction, run direction, and script font slots now reach the
  title page, abstract, table-of-contents title, captions, bibliography heading and
  entries, headers, footers, footnotes, and endnotes. Previously these surfaces rendered
  Arabic or Hebrew text without bidi properties.
- Bibliography hyperlinks in right-to-left entries are emitted with the correct
  complex-script font and run direction.

### Fixes

- Prevent unbounded memory growth when mixed-script OCR text leaves an isolated Bengali
  vowel mark before Bijoy font conversion.

### Verification

- Added a polyglot fixture and a multilingual regression suite covering script
  detection, font slots, direction modes, native structure preservation, and the
  Unicode-to-Bijoy output boundary for headers, tables, and notes.

## 1.3.1 — Bangla documents and merged layout tables

- Render Bengali runs in SutonnyMJ using Bijoy glyph encoding at the DOCX output boundary while preserving Unicode Markdown and Latin text.
- Add the `bengali-document` theme, editable identity forms and photo boxes, and validated `layout-table` fences with horizontal and vertical cell merges.
- Repair citation-suffixed closing fences from exported Markdown without changing code literals.
- Add regression coverage for table geometry, font encoding, mixed-language runs and invalid merge definitions.

## 1.3.0 — Resilient resources, smart equations, and academic references

This release fixes the main failure modes seen when converting AI-generated, technical, and
academic Markdown into editable Word documents.

### Resilient resources and layout

- Fixed standalone HTML `<img>` elements, including validated Base64 data URIs and images inside
  `<details>` exports, so they use the native DOCX image pipeline instead of appearing as literal
  HTML.
- Fixed remote-image handling with bounded HTTP(S) downloads, redirect checks, content-based image
  validation, successful-resource caching, timeout diagnostics, and readable clickable fallbacks
  when an image cannot be embedded.
- Fixed the resource policy so ordinary Markdown links remain Word hyperlinks and are never
  downloaded as images.
- Fixed static and animated GIF handling so GIF media is embedded unchanged, with client playback
  behavior documented.
- Fixed wide-table layout drift by emitting fixed Word table-layout metadata with synchronized
  grid and cell widths for Microsoft Word and LibreOffice.

### Smart equations

- Fixed common AI-generated LaTeX wrapper and delimiter variants through conservative,
  renderer-safe normalization without algebraically rewriting expressions.
- Added a pinned MathJax 4.1.3 sidecar as the first equation engine, with native editable Office
  Math output when structural and semantic validation succeeds.
- Fixed equation fallback behavior so unsupported expressions remain readable and editable source
  text; `--strict-math` is available when fallback must fail the conversion.
- Added `mddocx math-check FILE.md --json` with engine, normalization, validation, warning, and
  fallback details, plus a deterministic 250-equation conformance corpus.

### Academic references and links

- Added APA as the default citation style while retaining IEEE, numeric, author-year, and Chicago
  author-date compatibility choices.
- Added optional arbitrary local CSL style processing through `mddocx-native[academic]`.
- Fixed DOI normalization to produce canonical `https://doi.org/` hyperlinks and added citation
  and bibliography cross-links inside the generated DOCX.
- Added cited-only or all-entry bibliography inclusion and `mddocx link-check` for separate
  ordinary-link and bibliography-link validation.

### Compatibility and release quality

- Preserved the stable v1 Python entry points and legacy remote-resource and citation options.
- Added regression coverage for resilient resources, smart equations, academic references,
  HTML images, table widths, and the complete release contract.
- Updated the GitHub Release action to the supported Node 24-based v3 line.

## 1.2.4 — Reproducible release quality gates

- Pinned Ruff 0.15.10 in the development toolchain so local and hosted CI enforce the same
  established lint contract instead of changing behavior when a new Ruff release appears.
- Added a mandatory release-candidate verification job; GitHub Release and PyPI publishing now
  wait for tests, compilation, lint, formatting, and targeted type checks to pass.

## 1.2.3 — Cross-platform SVG security validation

- Made unsafe SVG reference validation use the required hardened `lxml` parser so security checks
  run consistently in clean Windows, Linux, and macOS installations before optional conversion.

## 1.2.2 — Fidelity-first compiler and AI media compatibility

- Safe public HTTPS images are now allowed by default; the interactive shell asks once whether to
  block them with `RESOURCE201`, remembers the choice, and supports per-render overrides.
- Added bounded local decoding of Base64 image data URIs, including MIME validation, invalid-data
  diagnostics, format verification, deduplication, native DOCX embedding, and regression coverage.
- Added native handling for common AI-generated `\tag`, `\checkmark`, and `\overrightarrow`
  equations.
- Added fence-aware AI math normalization for `\\(...\\)`, `$...$`, `\\[...\\]`, `$$...$$`, and `math`/`latex`/`tex` fenced blocks.
- Prevented currency ranges, inline code, and non-math code fences from being misclassified as equations.
- Prevented an unmatched display delimiter from consuming the remaining document.
- Added the first tracked regression suite, including an equation-heavy ChatGPT fixture with 20 display equations and two inline equations.
- Unsupported fallback-parser commands now produce explicit diagnostics and readable source fallbacks by default; `--strict-math` restores fail-fast behavior.
- Added `mddocx math-check`, `inspect_math()`, and `inspect_math_file()` for non-writing equation preflight with text or JSON reports.
- Restored pytest execution in CI so a release cannot pass with no collected tests.
- Restored the Windows/Linux/macOS and Python 3.11-3.13 CI matrix, added full Ruff lint and formatting gates, and cleared the existing lint backlog.
- Added the staged-v2 `Compiler` and typed `CompilationResult` interfaces while retaining the v1 rendering facade.
- Replaced the no-op normalizer with renderer-safe semantic normalization for text, math sources, heading levels, irregular tables, and duplicate document identifiers.
- Versioned serialized AST/cache payloads independently and made incompatible caches fail closed and rebuild cleanly.
- Added regression coverage for local traversal, disabled remote resources, domain allowlists, private-address blocking, unsafe DOCX paths, macros, oversized XML parts, and fence-aware AI metadata privacy.
- Added project-mode regression coverage for reproducible incremental builds, dependency tracking, includes, variable substitution, configuration precedence, path containment, and include cycles.
- Added a deterministic technical-report acceptance fixture covering native equations, lists/tasks, tables, charts/workbooks, code listings, citations, bibliography, notes, definitions, bookmarks, cross-references, headings, TOC, and page fields.
- Propagated source locations to inline AST nodes and added file/line evidence to unresolved link, reference, citation, and footnote diagnostics.
- Added a reusable Word 365 automation smoke script and release qualification checklist for open/repair detection, equation counts, pagination, and PDF export.
- Added layout regression coverage for deterministic wide-table landscape sections, portrait restoration, repeated table headers, and non-splitting rows.
- Added an explicit, inspectable layout-planning stage with typed table decisions and per-stage timing.
- Expanded the staged compiler service with typed parse, normalize, plan, render, check, and compile operations.
- Added source-located `MATH101` diagnostics for unterminated explicit math delimiters and math fences.
- Hardened the optional external math engine so literal unconverted TeX commands cannot be reported as successful native math.
- Defined the raw HTML policy: unsupported HTML is preserved as literal editable text instead of being silently discarded.
- Added stable generated heading identifiers during normalization.
- Added a machine-readable feature/fidelity matrix and release-contract tests linking supported constructs to tracked evidence.
- Added round-trip, images/alt-text, Unicode/RTL/XML safety, templates, CLI exit-code, and paths-with-spaces regressions.
- Added a Linux LibreOffice/Poppler visual smoke job and clean wheel/source-distribution install and CLI smoke gates.
- Added the exact Fidelity-First v2 program to the repository, plus a machine-readable feature matrix and staged migration guide.
- Expanded layout planning to cover heading pagination, short/long code treatment, captions, figures, charts, tables, equations, and explicit page/section-break intent.
- Added a renderer-independent semantic index for stable heading/target IDs, citations, notes, and unresolved references.
- Added a typed UTF-8 source-acquisition stage with stable `SOURCE401`/`SOURCE402` diagnostics and remediation text.
- Added public, versioned AST/layout extension protocols with validated plugin results and isolated failures.
- Added a template style-mapping layer with pre-render target validation and `TEMPLATE201`/`TEMPLATE401` diagnostics.
- Added a shared typed render context and extracted native math rendering/fallback behavior into a focused component.
- Migrated CLI, batch, project, and interactive conversion paths onto the same typed `Compiler` service.
- Added remediation fields to diagnostics and SARIF properties for actionable machine-readable failures.
- Added small/medium/large benchmark gates and recorded measured stabilization baselines.
- Moved deterministic table-width allocation into the layout planner so renderers consume one
  inspectable orientation-aware width decision.
- Rejected incompatible layout plans returned by extensions with stable `PLUGIN409` diagnostics.

## 1.2.1 — Packaging and release improvements

- Published the project under the unique PyPI distribution name `mddocx-native` while preserving the `mddocx` import package and command-line interface.
- Added secure PyPI Trusted Publishing through GitHub Actions.
- Expanded installation documentation for PyPI, downloaded wheels, GitHub source installs, and local development.
- Added professional package metadata, project links, classifiers, and MIT licensing.
- Removed generated package metadata from source control and improved release discoverability.

## 1.2.0 — AI/chat export metadata sanitization

- Added provider-agnostic AI/chat export metadata sanitization before Markdown parsing, enabled by default with the conservative `auto` policy.
- Removes high-confidence conversation IDs, model/provenance fields, export timestamps, source URLs, explicit metadata sections, metadata HTML comments, and standalone role timestamps while preserving conversation roles/content.
- AI-export YAML front matter is filtered so export-derived title/author/date values do not leak into Word core properties; ordinary authored `mddocx` front matter remains unchanged when no export signature is detected.
- Newly generated non-template DOCX files now scrub synthetic `python-docx` author/created/modified defaults unless explicit document properties were supplied.
- Added `MetadataConfig`, `MetadataSanitizationReport`, `SanitizedMarkdown`, and `sanitize_markdown_metadata()` as additive stable-v1 public APIs.
- Added `--ai-metadata auto|strip|keep`, `mddocx metadata inspect`, and `mddocx metadata clean`.
- Added project-manifest `render.ai_metadata` and interactive-shell metadata inspection/configuration.
- Sanitization is line-number preserving and fence-aware so code examples containing metadata-like strings are not silently modified.
- Added real render/project/CLI regression coverage for source content preservation and Word core-property privacy.
- Public API compatibility version remains `1`; no frozen v1 names were removed.

## 1.1.0 — Interactive CLI and Windows UX

- Added `mddocx shell`, a menu + REPL console layered over the existing stable v1 compiler services rather than a second renderer.
- Added workspace detection, Markdown/DOCX/data discovery, guided file selection, render/check/build/watch/project-init/configuration workflows, and Windows-safe quoted path tokenization.
- Added interactive doctor, structural inspection, accessibility, template, data, font, benchmark, recent-output, diagnostics, and diagnostic-explanation tools.
- Added persistent command history/autocomplete through `prompt-toolkit`, with a non-TTY fallback for redirected input.
- Added path/settings-only recent-document history and `mddocx recent` / `mddocx open`. Document content is never persisted in recent metadata.
- Added `--open` to single-file rendering and project builds, using the operating-system default application without hard-coding Microsoft Word.
- The guided render wizard detects remote HTTPS hosts and can allow only those hosts for one render; existing private-host and resource-safety rules remain enforced.
- Added interactive-CLI regression coverage for Windows paths, guided rendering, project settings, shell dispatch, and recent history.
- Public API compatibility version remains `1`; no frozen v1 names were removed or changed incompatibly.

## 1.0.0 — Stable public API and production release gate

- Established public API version `1` with an explicit machine-readable frozen API manifest (`mddocx api`).
- Added Word accessibility auditing for alt text, semantic table headers, heading hierarchy, empty links, and document title metadata (`mddocx accessibility`).
- Added deterministic large-document performance gating with time, memory, structural inspection, and SHA-256 reporting (`mddocx benchmark`).
- Expanded native ChartML controls with axis titles, numeric bounds, number formats, data labels, legend placement, Office chart styles, gridline control, and secondary value axes for column/bar/line charts.
- Strengthened DOCX inspection/validation for duplicate relationship IDs, duplicate drawing IDs, duplicate footnote/endnote IDs, and invalid chart-to-workbook relationship sets.
- Added cross-platform GitHub Actions CI, Linux visual regression, packaging workflow, API stability policy, compatibility matrix, accessibility/performance guidance, chart documentation, and a release checklist.
- Preserved the established v0.x rendering/project APIs while promoting them to the stable v1 compatibility contract.

## 0.9.0 — Phase 8 native editable charts and structured data

- Added semantic `chart` and `data-table` AST blocks parsed from bounded YAML fence specifications.
- Added native editable Office ChartML generation for column, horizontal bar, line, pie, and scatter charts.
- Every generated chart embeds its own deterministic `.xlsx` workbook so chart data remains editable from Microsoft Word instead of being flattened to an image.
- Added CSV and JSON tabular data loaders with explicit row/column limits and structured diagnostics.
- Added chart binding by category/x column and one or more numeric series fields.
- Added native Word table imports from CSV/JSON, including existing captions, bookmarks, cross-references, repeated headers, and table layout policy.
- Added chart captions/cross-references through the existing Figure/SEQ/REF architecture and image-style accessibility descriptions for chart drawings.
- Project builds now rebase, confine, track, fingerprint, and watch chart/table data dependencies alongside Markdown/includes/images/templates/bibliographies.
- Added `mddocx data inspect DATA.csv|json` for validating data shape before rendering.
- Extended `mddocx inspect` with native chart and embedded-workbook counts.
- Hardened chapter-scoped caption/equation sequence reset behavior for LibreOffice/Word compatibility while retaining editable Word fields.
- Added deterministic nested workbook packaging so repeated chart renders remain byte-identical.
- Added Phase 8 parser/data/chart/project/CLI regression tests and a five-page integrated native-chart acceptance project.
- Public package version advanced to 0.9.0 without changing existing single-file or project APIs.

## 0.8.0 — Phase 7 project/build mode

- Added `mddocx.yml` project manifests with deterministic ordered source lists and lexical source globs.
- Added secure recursive standalone `@include` directives resolved relative to the including Markdown file.
- Added include traversal protection, cycle detection, bounded include depth, and fenced-code protection.
- Added inert scalar `{{ variable }}` substitution with configurable undefined-variable behavior and no code execution.
- Added multi-file AST assembly with cross-chapter references, footnotes, citations, equations, tables, diagrams, and other existing semantic features preserved.
- Added safe rebasing of chapter-relative image resources while retaining project-root path confinement.
- Added `mddocx build`, `mddocx watch`, `mddocx project init`, and `mddocx project info`.
- Added deterministic incremental build state that tracks source/include/image/template/bibliography dependencies, input fingerprint, and output SHA-256.
- Incremental builds now rebuild if the generated DOCX is modified outside mddocx.
- Added a portable bounded polling watcher that ignores generated output/cache directories and reloads the manifest after changes.
- Fixed Word DATE/CREATEDATE/SAVEDATE field switch escaping so compatible renderers no longer show a stray backslash after formatted dates.
- Added a real multi-chapter acceptance project and project-mode security/incremental/CLI regression tests.
- Public package version advanced to 0.8.0 without changing the existing single-file rendering APIs.

## 0.7.0 — Phase 6 Word professional features

- Added native multilevel heading numbering using Word numbering definitions.
- Added section-scoped figure/table/listing captions in addition to existing section-scoped equation numbering.
- Added professional title page, subtitle, organization, abstract, and keyword rendering.
- Expanded headers/footers with first-page/even-page variants, PAGE/NUMPAGES and bounded field templates.
- Added native Word comments from CriticMarkup `{>>...<<}` annotations.
- Added GitHub-style and bounded `:::` callouts/admonitions with dedicated Word styles.
- Added editable Pygments token highlighting, code line numbers, per-line highlighting, and optional language labels.
- Centralized Markdown attribute-list parsing.
- Added `mddocx template inspect` for page/style/header/footer metadata.
- Strengthened inspection/validation for dangling internal links, dangling REF fields, duplicate bookmarks, and comment-package consistency.
- Expanded the regression suite to 120 tests plus the opt-in rendered-page regression.
- Public rendering entry points remain backward compatible.

## 0.6.0 — Phase 5B professional Word semantics

- Added centralized semantic identifiers/bookmark registry for headings, figures, tables, equations, listings, and cross-reference targets.
- Added native Word `SEQ` captions and `REF` cross-references, internal hyperlinks, and section-scoped equation numbering while preserving editable OMML.
- Added figure/table/listing captions and configurable labels/positions.
- Added native Word endnotes as an alternative to footnotes, including inline formatting and OMML.
- Added citation AST plus BibTeX/CSL-JSON loading, deterministic APA/author-year/IEEE/numeric formatting, and explicit/automatic bibliography generation.
- Added image accessibility metadata, decorative-image marking, percentage sizing, and figure alignment.
- Added definition-list normalization/rendering.
- Expanded deterministic offline Mermaid compatibility to safe subsets of state, class, ER, mindmap, timeline, pie, journey, and gantt in addition to flowchart/graph/sequence.
- Extended DOCX inspection for SEQ/REF fields, endnotes, internal hyperlinks, and image accessibility.
- Added 100+ regression tests and a 30-page integrated Phase 5B acceptance document.
- Fixed duplicate explicit bibliography headings and a duplicate section-break insertion edge case.
- Stable public rendering entry points remain unchanged.

## 0.5.0 — Phase 5A Word QA and fidelity hardening

- Added native Word checkbox content controls for common Markdown task-list syntax (`[x]` / `[ ]`) while preserving ordinary native list numbering.
- Added `mddocx inspect` with package, relationship, OMML, list, task, footnote, table, media, section, field and placeholder diagnostics.
- Added `mddocx doctor` for runtime/dependency/visual-QA capability checks.
- Added `mddocx visual-qa` plus a reusable LibreOffice/pdftoppm page-render comparison API and an opt-in visual regression fixture.
- Added a deterministic 600-equation fallback-parser/OMML regression corpus and expanded common mathematical symbols/functions.
- Hardened generated-DOCX validation with uncompressed-size limits, macro rejection, duplicate-part checks, relationship validation, and OMML structural checks.
- Kept suspicious visible placeholder characters as inspector warnings by default, with an opt-in fatal validation policy for controlled pipelines.
- Stable rendering APIs remain unchanged.

## 0.4.2 — Word footnotes, matrix delimiters, Mermaid diagrams

- Added native Markdown footnote references/definitions using Word `footnotes.xml`.
- Footnote bodies support basic inline formatting and native OMML inline equations.
- Added scalable OMML delimiter growth for matrix environments such as `bmatrix`.
- Added deterministic offline Mermaid rendering for common `flowchart`, `graph`, and `sequenceDiagram` fences.
- Unsupported Mermaid families fall back to editable code with a structured diagnostic unless strict mode is enabled.
- Fixed sequence return-arrow parsing and soft-break preservation inside hyperlink labels.
- Added regression tests for footnotes, matrix delimiters, Mermaid rendering, and escaped footnote syntax.

## 0.4.1 — Word compatibility hardening

- Fixed Unicode list markers rendering as square boxes in Microsoft Word by assigning an explicit Unicode-capable marker font rather than legacy Symbol/Wingdings inheritance.
- Improved nested-list indentation and marker spacing; ordered and unordered markers now use predictable native Word numbering properties.
- Changed all built-in heading styles to explicit black text instead of inheriting Word's blue built-in heading color.
- Reworked MathML → OMML n-ary rendering so integrals, contour integrals, sums, products, and repeated integrals do not emit empty Word equation placeholders.
- Fixed Word radical OMML by always emitting the required degree container and hiding it correctly for square roots.
- Improved accent/vector conversion and added robust handling for boxed expressions, math variants, unbraced fraction arguments, grouped delimiter superscripts, mathematical vertical bars, and common symbols.
- Added normalization for common Pandoc/simple fixed-width Markdown tables so they become native editable Word tables.
- Added the real-world Markdown stress document as a regression fixture and Word-compatibility structural tests.
- Public package version advanced to 0.4.1 without changing the stable render APIs.

## 0.4.0

- Added reproducible DOCX package finalization with stable part ordering and ZIP timestamps.
- Added defensive generated-package validation for required parts, XML integrity, path safety, and limits.
- Added configurable input/AST/table/image/equation/nesting limits.
- Added opt-in persistent normalized-AST caching using a project-owned JSON codec.
- Added explicit Python entry-point plugin discovery; installed plugins are never auto-imported.
- Added deterministic multi-file/directory batch conversion in the Python API and CLI.
- Added SARIF 2.1.0 diagnostics for CI/code-scanning ingestion.
- Extended profiling with output SHA-256 and AST-cache-hit state.
- Added Phase-4 operational-maturity documentation and regression coverage.
- Public package version advanced to 0.4.0 without changing the stable rendering entry points.

## 0.3.0

- Completed the planned Phase-3 production-hardening surface.
- Added existing `.docx` template support with optional preservation of template page setup/styles.
- Added `default`, `academic`, `modern`, and `minimal` themes plus custom/script-aware font slots.
- Added Unicode sanitization and Word-native RTL/bidi paragraph/run properties.
- Added optional WebP/SVG handling; SVG external references are rejected before conversion.
- Added opt-in HTTPS remote image downloads with domain, redirect, MIME, size, DNS/IP, and cache policy.
- Added advanced deterministic table width heuristics and optional automatic landscape sections.
- Added custom AST/parser/transform/render extension hooks and `render_ast()`.
- Added JSON diagnostics, render timing, peak-memory instrumentation, math caching, and remote cache support.
- Added compatibility, extension, performance, security guidance, Phase-3 examples, and regression tests.
- Public package version advanced to 0.3.0 under semantic versioning.

## 0.2.0

- Completed the Phase-2 implementation surface.
- Expanded the internal LaTeX parser and MathML → OMML converter for nth roots, limits,
  n-ary operators, matrices, scalable delimiters, accents/vectors, aligned equations, and cases.
- Added native Word TOC, PAGE, and STYLEREF fields plus heading bookmarks.
- Added headers, footers, document metadata, YAML front matter, and section-break handling.
- Added table width allocation, cell padding, repeated-header configuration, and short/long row
  pagination policy.
- Added image-title captions with keep-with-next behavior.
- Expanded CLI options and Phase-2 regression/integration tests.

## 0.1.0

- Initial Phase-1 implementation.
- Canonical AST and markdown-it-py parser.
- Native Word paragraphs, headings, hyperlinks, tables, lists, code, images, and OMML equations.
- CLI, diagnostics, resource security checks, tests, and implementation status.
