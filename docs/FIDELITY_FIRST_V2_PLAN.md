# mddocx Fidelity-First v2 Technical Improvement Plan

## Summary

Evolve mddocx through a staged v2 program focused on high-fidelity conversion of technical and research documents from GitHub-Flavored Markdown plus documented mddocx extensions into editable Microsoft Word 365 documents.

The current v1.2.1 implementation has a viable end-to-end compiler and broad feature coverage:

`Markdown → metadata sanitization → parser → AST → normalization/extensions → DOCX/OOXML renderer → reproducibility and package validation`

The initial audit also identified several release-critical weaknesses:

- The package contains approximately 10,800 lines of Python across 70 files but no tracked automated tests.
- `pytest` exits with code 5 because the configured `tests/` directory does not exist.
- CI performs compilation, doctor, benchmark, and packaging checks, but no tests, linting, type checking, Word-structure regression tests, or visual regression tests.
- Ruff reports 222 violations, including unused imports and widespread multi-statement lines.
- Mypy is declared as a development dependency but is not enforced in CI and was unavailable in the current environment.
- The `Normalizer` is only a pass-through boundary, leaving parser-specific behavior insufficiently separated from rendering semantics.
- Core behavior is concentrated in very large modules, especially the renderer, interactive shell, CLI, project system, and Markdown parser.
- The documentation claims automated structural and visual regression coverage that is not present in the tracked repository.
- Basic compilation, CLI diagnostics, and a representative in-memory DOCX render currently succeed, so the redesign should retain working behavior while building evidence around it.

Delivery will use a staged v2 approach: establish conformance and regression coverage around v1 first, modularize internals behind the existing façade, then introduce intentional v2 interface changes with a migration path.

## Implementation Changes

### 1. Establish the executable fidelity contract

- Define the supported baseline as GFM/CommonMark behavior from `markdown-it-py`, augmented only by explicitly documented mddocx extensions for math, citations, cross-references, captions, callouts, charts, data tables, footnotes/endnotes, comments, page breaks, and section breaks.
- Create a machine-readable feature matrix connecting every supported construct to:
  - accepted Markdown syntax;
  - canonical AST representation;
  - required native Word/OOXML representation;
  - expected diagnostics for malformed or unsupported input;
  - Word 365 acceptance behavior;
  - LibreOffice compatibility status where relevant.
- Convert representative technical/research documents into permanent fixtures covering prose, nested lists, task lists, code, equations, wide and multi-page tables, figures, citations, bibliography, cross-references, heading numbering, headers/footers, TOC fields, charts, RTL text, and mixed constructs.
- Define fidelity as three independently tested dimensions:
  - semantic fidelity: input meaning and hierarchy survive;
  - native editability: Word elements remain native rather than flattened;
  - presentation fidelity: approved Word 365 reference documents meet layout expectations.
- Correct documentation so it distinguishes implemented behavior, experimentally supported behavior, and planned behavior. Remove claims of automated package or visual regression testing until the corresponding checks exist.

### 2. Rebuild the test and release-quality foundation

- Restore a `tests/` hierarchy with focused suites for metadata/front matter, parser behavior, AST normalization, renderer structure, OOXML helpers, resources/security, CLI, project mode, inspection, accessibility, reproducibility, and public API compatibility.
- Add golden structural tests that inspect normalized OOXML rather than comparing raw ZIP bytes. Assert element semantics, relationships, content types, embedded workbooks, numbering definitions, fields, bookmarks, notes, hyperlinks, and section properties.
- Add round-trip inspection helpers that render Markdown, reopen the DOCX with `python-docx` and direct XML parsing, and compare extracted semantic structure with the expected fixture.
- Add deterministic-output tests under reproducibility mode and deliberately non-deterministic tests where timestamps or template metadata are explicitly requested.
- Restore visual tests on Linux using LibreOffice and Poppler as a secondary rendering signal. Maintain a separate manual Word 365 qualification checklist and reference corpus for release candidates.
- Test Python 3.11, 3.12, and 3.13 on Windows, Linux, and macOS for non-visual suites. Run visual regression on Linux and package verification on a single supported Python version.
- Add CI gates for:
  - test collection and execution;
  - Ruff;
  - gradually strict mypy coverage;
  - wheel and source-distribution builds;
  - installation and CLI smoke tests from the built wheel;
  - benchmark thresholds;
  - public API manifest comparison;
  - DOCX validation and structural regression;
  - documentation/feature-matrix consistency.
- Make the first stabilization milestone fail on zero collected tests so the current false-green state cannot recur.
- Clean all existing Ruff violations without combining this mechanical cleanup with behavioral redesign. Introduce formatting and lint rules only after the current code is clean.
- Add typing incrementally at subsystem boundaries—AST, parser result, renderer context, configuration, diagnostics, project manifest, resource resolver—then tighten mypy by module rather than enabling strict mode globally in one step.

### 3. Refactor into an explicit compiler architecture

- Preserve `render`, `render_string`, and `MarkdownWord` during the compatibility phase, but internally introduce a compiler pipeline with explicit stages:
  - source acquisition and decoding;
  - privacy-aware metadata sanitization;
  - Markdown tokenization/parsing;
  - canonical AST construction;
  - semantic normalization and reference resolution;
  - layout planning;
  - DOCX rendering;
  - package finalization and validation.
- Make normalization a real semantic boundary. It must:
  - eliminate parser-token quirks;
  - normalize nested inline formatting and whitespace;
  - validate block nesting;
  - assign stable identifiers;
  - collect headings, figures, tables, equations, citations, and notes;
  - resolve or record cross-references;
  - derive numbering and section requirements;
  - emit diagnostics without requiring renderer knowledge.
- Add a layout-planning stage between normalization and OOXML emission. It will decide table orientation changes, section boundaries, caption placement, keep-with-next/keep-together behavior, page-break intent, code-block treatment, and other Word layout requirements before objects are written.
- Split the monolithic renderer into focused components for document setup, paragraphs/inlines, lists, tables, math, images/figures, charts, notes/citations, references/fields, sections, and package finalization. Pass a shared typed render context containing the Word document, configuration, diagnostics, numbering registry, reference registry, resource resolver, and relationship/package state.
- Replace long `isinstance` and token-type chains with explicit handler registries where extension is genuinely required. Keep direct dispatch where the node set is closed and registry indirection would add no value.
- Keep direct OOXML manipulation behind narrow, tested adapters. Rendering components must not duplicate namespace construction, relationship handling, field syntax, or package-part registration.
- Treat extension hooks as transformations of documented, versioned AST or layout interfaces. Validate plugin output before rendering and isolate plugin failures with actionable diagnostics.
- Separate CLI parsing from application services. CLI, interactive shell, batch mode, and project mode should call the same typed conversion/build services instead of recreating configuration and error-handling logic.
- Break up oversized CLI and shell modules by command domain while preserving command names during the v1-compatible stages.
- Standardize failures on stable diagnostic codes, source spans, severity, and remediation text. Replace silent exception swallowing where it can hide malformed configuration or fidelity loss; retain best-effort fallback only when a warning is emitted.

### 4. Improve fidelity in prioritized feature waves

1. **Core text and document hierarchy**
   - Lock GFM behavior for headings, paragraphs, emphasis, strikethrough, code spans, links, blockquotes, hard/soft breaks, thematic breaks, and raw HTML policy.
   - Preserve Unicode, XML-safe text, bidirectional text, nested inline styles, bookmarks, and internal links.
   - Verify heading styles, outline levels, numbering, TOC compatibility, widow/orphan controls, and keep-with-next behavior in Word 365.

2. **Lists, tasks, and pagination**
   - Generate true Word numbering definitions for ordered, unordered, nested, restarted, and task lists.
   - Define continuation and indentation behavior for multi-paragraph list items, nested blocks, code, quotations, and tables.
   - Treat explicit breaks, automatic section changes, and list continuation across section boundaries as layout-plan concerns.
   - Test long lists and page-boundary behavior in Word 365 reference documents.

3. **Tables**
   - Preserve header rows, alignment, multiline cell content, nested inline formatting, native widths, and repeat-header settings.
   - Replace heuristic table sizing with a documented width allocator using page width, margins, column content constraints, and configured minimums/maximums.
   - Make wide-table landscape sections deterministic and restore the previous page configuration after the table.
   - Test narrow/wide tables, long cells, merged-layout limitations, page splits, captions, cross-references, and tables mixed with footnotes or equations.

4. **Mathematics**
   - Use native OMML for inline and display math, preserving editability.
   - Establish a conformance corpus for fractions, scripts, roots, matrices, delimiters, aligned expressions, Greek symbols, operators, accents, and numbered equations.
   - Define unsupported-TeX behavior by the configured failure policy: fail, warn with literal fallback, or warn with a clearly marked fallback representation.
   - Test numbering, section-based numbering, bookmarks, cross-references, and equation layout in Word 365.

5. **Figures, resources, charts, citations, and notes**
   - Preserve images as native drawing objects with size constraints, alternative text, captions, stable identifiers, and references.
   - Keep secure resource defaults: local containment, HTTPS allow-listing, private-host blocking, MIME/size limits, redirect revalidation, hardened SVG/XML parsing, and no TeX/code execution.
   - Verify charts as editable ChartML backed by valid embedded XLSX parts, including categories, series, legends, axes, and documented limitations.
   - Normalize citation resolution before rendering and ensure bibliography ordering and formatting are deterministic.
   - Validate native footnote/endnote parts, numbering, relationships, backlinks where applicable, and mixed-note documents.

6. **Templates and professional document features**
   - Introduce a documented style-mapping layer between canonical semantic styles and template styles.
   - Validate templates before rendering and emit diagnostics for missing or incompatible styles instead of silently producing inconsistent output.
   - Test title pages, abstracts, metadata, headers/footers, page fields, odd/even and first-page sections, page sizes, orientation, and template inheritance.
   - Keep privacy sanitization conservative and observable through reports; never silently remove ambiguous user content.

### 5. Define the v2 public surface and migration

- Retain the v1 façade throughout stabilization and internal refactoring. Add deprecation warnings only after equivalent v2 interfaces are available.
- Introduce a v2 `Compiler` service with explicit operations for parsing, normalizing, planning, rendering, checking, and compiling. Each operation returns a typed result containing output, diagnostics, and stage statistics as applicable.
- Replace the deeply mutable nested configuration model with validated, typed configuration objects. Configuration precedence will be explicit:
  - library defaults;
  - project configuration;
  - document front matter;
  - caller or CLI overrides.
- Preserve the existing safety principle that explicit caller configuration overrides document-provided values.
- Version the canonical AST serialization format independently from the Python package and reject incompatible cached AST versions cleanly.
- Publish public protocols for extensions rather than exposing renderer internals.
- Keep `render()` and `render_string()` as convenience wrappers around `Compiler` in v2 unless conformance work demonstrates a concrete reason to remove them.
- Treat v2 CLI command names as stable where possible; breaking changes should focus on ambiguous flags, inconsistent exit codes, or duplicated workflows rather than cosmetic renaming.
- Provide:
  - a v1-to-v2 configuration mapping;
  - public API manifest comparison;
  - CLI migration examples;
  - deprecated-name schedule;
  - behavioral-change notes for any corrected rendering semantics.
- Release v2 only after the reference corpus passes structural checks, the Word 365 manual qualification pass, cross-platform automated suites, packaging verification, and documented performance budgets.

## Test Plan and Acceptance Scenarios

- **Parser conformance:** GFM examples and mddocx extension fixtures generate the exact expected canonical AST, source spans, identifiers, and diagnostics.
- **Semantic normalization:** equivalent Markdown forms normalize consistently; invalid nesting, duplicate IDs, missing references, and unsupported constructs produce stable diagnostics.
- **Core Word structure:** headings, paragraphs, lists, tables, links, bookmarks, fields, notes, equations, images, and charts appear as the expected native OOXML elements and relationships.
- **Technical-paper fixture:** compile a multi-chapter paper containing numbered headings, equations, figures, tables, citations, bibliography, footnotes, code, TOC, cross-references, and appendices; all references resolve and all content remains editable.
- **Long-report fixture:** verify repeated table headers, controlled section changes, landscape table restoration, page fields, headers/footers, and stable pagination behavior in the designated Word 365 qualification environment.
- **Math corpus:** supported TeX constructs generate valid OMML; unsupported syntax follows each configured failure policy without corrupting the package.
- **List corpus:** nested mixed lists, restarts, tasks, multiple paragraphs, and embedded blocks use native numbering and retain intended hierarchy.
- **Chart corpus:** generated ChartML and embedded workbooks are valid, internally consistent, and editable in Word 365.
- **Template corpus:** compatible templates preserve semantic mappings; incompatible templates produce actionable diagnostics.
- **Security:** reject path traversal, disallowed hosts, private/reserved network destinations, unsafe redirects, oversized resources, MIME mismatches, external SVG references, XML entities, and ZIP/package bombs within configured limits.
- **Privacy:** exported chat metadata is removed only under the documented policy; fenced code and ordinary document content are not accidentally stripped.
- **Reproducibility:** identical input and deterministic configuration produce byte-identical output and stable hashes.
- **Failure safety:** malformed Markdown extensions, data sources, templates, cached AST, plugins, images, math, or package parts cannot result in silent corruption.
- **CLI/project behavior:** commands have stable exit codes, machine-readable diagnostics, paths with spaces and Windows drive letters work, project builds use the documented configuration precedence, and watch mode reports recoverable failures.
- **Cross-platform:** all non-visual tests pass on Python 3.11–3.13 across Windows, Linux, and macOS.
- **Visual QA:** LibreOffice rendering remains within approved image-diff tolerances; Word 365 reference documents pass manual semantic, editability, field-update, and presentation checks.
- **Performance:** benchmark representative small, medium, and large documents; establish budgets only from measured v1 baselines, then prevent statistically meaningful regression in runtime, peak memory, and output size.
- **Packaging:** clean-environment installations from both wheel and source distribution can import the public API, run `doctor`, render a fixture, inspect the generated package, and report the correct version.

## Delivery Sequence

1. **Milestone A — Audit baseline:** create the feature matrix, reference corpus, test skeleton, measurable v1 baselines, corrected documentation, and zero-test CI guard.
2. **Milestone B — Stabilize v1:** add critical parser/renderer/package/security tests, clear Ruff, begin typed boundaries, and fix only defects demonstrated by tests.
3. **Milestone C — Compiler boundaries:** implement semantic normalization, layout planning, shared services, and modular renderers behind the current public API.
4. **Milestone D — Fidelity waves:** complete the prioritized Word 365 work for core text, lists, tables, math, figures, charts, citations, notes, templates, and pagination.
5. **Milestone E — v2 interfaces:** introduce validated configuration, typed compiler results, versioned AST serialization, extension protocols, compatibility wrappers, and migration documentation.
6. **Milestone F — Qualification and release:** run the complete platform matrix, security suite, performance gates, package installation tests, LibreOffice visual suite, and Word 365 reference-corpus review before publishing v2.

Each milestone must remain releasable and must not proceed by replacing working behavior without first capturing that behavior in fixtures or explicitly classifying it as a defect.

## Assumptions and Defaults

- Microsoft Word 365 desktop is the primary output authority; LibreOffice is a secondary compatibility and automated visual-regression target.
- Technical and research documents are the primary usage profile.
- GFM is the base Markdown dialect, with mddocx-specific extensions documented separately and never inferred ambiguously.
- Native editability and semantic Word structure take priority over pixel-identical rendering across office applications.
- A major redesign is allowed, but delivery is staged and the current v1 API remains usable until documented v2 replacements exist.
- Current successful basic rendering, security defaults, native OMML equations, editable charts, diagnostic codes, and deterministic-output capability are retained unless a conformance test proves they need correction.
- Historical ZIPs, wheels, and sample outputs at the workspace root are treated as release artifacts/reference inputs, not as the active source tree.
- Existing unsupported optional tools such as LibreOffice and `latex2mathml` are not required for basic conversion; CI and documented optional-feature environments will install them where their tests require them.

