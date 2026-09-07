# Implementation Status

Current Phase: v1.2.0 — AI/chat export metadata sanitization

## Completed

### v1.2 export metadata privacy

- High-confidence AI/chat export metadata is removed before Markdown parsing by default (`auto`).
- Normal conversation content/roles and ordinary mddocx front matter remain intact; source line numbers are preserved by blank-line replacement.
- Export-derived identity/provenance fields are filtered before they can populate Word core properties.
- Synthetic python-docx author/created/modified defaults are scrubbed for newly generated non-template DOCX files unless the user supplied explicit properties.
- `--ai-metadata`, `mddocx metadata inspect`, `mddocx metadata clean`, project `render.ai_metadata`, and interactive-shell metadata controls are available.
- Sanitization is provider-agnostic, boundary-aware, and fenced-code-aware; it does not special-case individual conversation IDs/equations/documents.


### v1.1 interactive CLI

- `mddocx shell` adds a discoverable menu + REPL over the stable compiler API.
- Workspace awareness discovers project, Markdown, DOCX, image, template, and structured-data assets.
- Guided rendering supports file selection, theme choice, exact-host remote-resource consent, render statistics, and optional OS-native opening.
- Interactive project build/watch/init/configuration, check, doctor, inspect, accessibility, template, data, fonts, benchmark, diagnostics and recent-document tools are available.
- Windows paths with backslashes/spaces are preserved by the shell tokenizer.
- `prompt-toolkit` provides command history/completion on interactive terminals; redirected stdin uses a plain-input fallback.
- Recent metadata stores paths/settings only and never document content.
- Existing direct CLI commands and the public API v1 contract remain backward compatible.

### v1.0 production gate

- Public API version `1` is frozen through `get_public_api_manifest()` and `mddocx api`.
- Existing single-file, batch, project/build/watch, extension, inspection, chart/data, citation/reference, native Word and OMML entry points remain backward compatible.
- Native ChartML now supports axis titles, value bounds, number formats, data labels, legend placement, Office chart style IDs, optional gridlines, and secondary value axes for column/bar/line series.
- `mddocx accessibility` audits common document accessibility regressions structurally without requiring Microsoft Word.
- `mddocx benchmark` provides a deterministic large-document performance gate with elapsed time, traced Python peak allocation, structure counts and output hash.
- DOCX inspection/validation detects duplicate relationship IDs, duplicate drawing IDs, duplicate note IDs and invalid chart/workbook relationship sets in addition to prior OOXML/OMML checks.
- Cross-platform GitHub Actions test matrix, Linux visual-regression job, and release-artifact workflow are included.
- API stability, compatibility, chart, accessibility, performance and release-checklist documentation are included.

### Prior compiler functionality

- Markdown → canonical AST → normalization → native Word renderer architecture.
- Native Word paragraphs/headings/lists/tables/fields/bookmarks/comments/footnotes/endnotes/captions/cross-references/task controls.
- Editable OMML mathematics and native ChartML + embedded XLSX charts.
- PNG/JPEG/WebP/SVG resources, bounded remote resources, RTL/Unicode, templates/themes and accessibility metadata.
- BibTeX/CSL-JSON citation pipeline, safe offline Mermaid compatibility renderer, code highlighting/callouts and project variables/includes.
- Reproducible DOCX packages, package validation, JSON/SARIF diagnostics, persistent AST cache, plugin hooks and batch/project build system.

## Tests

- v1.2 full suite: 176 tests collected; 175 passed in the normal run with the one opt-in visual test skipped, and that visual test passed separately.
- The opt-in page-render visual regression remains separate from the normal suite and requires LibreOffice/soffice plus pdftoppm.
- v1 acceptance release validation records structural, accessibility, reproducibility, isolated-wheel and visual-render checks.

## Known Limitations

- Automated visual CI uses LibreOffice; Microsoft Word should still be used for a representative manual release smoke pass when available because Word is not available in headless CI.
- Secondary axes are supported for column, bar and line charts; radar/stock/area/combo families, trendlines and error bars are not part of the v1 stable chart surface.
- Accessibility auditing is structural and does not replace Microsoft Accessibility Checker or human review.
- Citation styles are deterministic project-owned formatters rather than a complete CSL implementation.
- Mermaid support remains a safe bounded renderer rather than arbitrary Mermaid JavaScript execution.
- DOCX pagination remains host-dependent because Word documents are reflowable.

## Security Decisions

- No Markdown code execution, generated Python execution or shell execution.
- Remote resources remain disabled by default and bounded when explicitly enabled.
- YAML uses safe loading; project includes/data sources remain project-root confined.
- XML parsing remains defensive and macros are rejected by generated-package validation.
- Compiler/input/resource/package limits remain enabled.
- Plugins are explicit opt-in entry points, never automatically imported.

## Architecture Decisions

- v1 public API is defined at the package boundary; OOXML/parser internals remain non-public implementation details.
- Accessibility and performance gates are independent QA layers over the compiler rather than renderer-specific special cases.
- Advanced chart configuration is represented in the canonical AST and emitted as standards-based ChartML; chart data remains editable in embedded XLSX workbooks.
- Release compatibility prioritizes semantic native Word structure over host-specific pixel-identical pagination.

## Breaking Changes

- None to the established public v1 rendering or project APIs.
- v1.2 adds metadata privacy behavior with `auto` as the new default source-sanitization policy; users who intentionally need export metadata can select `keep`.
- Public API compatibility version remains `1`.

## Recommended Next Task

Continue additive 1.x work with corporate template mapping/branding packages, plugin SDK versioning, very-large-document optimization/image deduplication, and optional DOCX → Markdown extraction as a separate compiler direction.
