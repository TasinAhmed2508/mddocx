# Changelog

## Unreleased

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
