# mddocx

`mddocx` is a deterministic Markdown → Microsoft Word compiler. It parses Markdown into a
canonical AST, normalizes it, and renders native Word structures instead of flattening content
into screenshots or manually prefixed text.

Version **1.2.0** keeps the stable v1 compiler/API contract and adds privacy-aware AI/chat export metadata sanitization. High-confidence export provenance is removed before parsing by default, while normal `mddocx` front matter and the actual conversation content remain intact. Version 1.1 added the discoverable interactive console; version 1.0 established the production API and release gates.

## Word compatibility notes

The 1.x series retains the 0.4.x–0.9.x Microsoft Word hardening for real-world technical Markdown: list markers use Unicode-capable fonts and compact native indentation, built-in headings are black, n-ary equations avoid empty placeholder boxes, square roots emit Word-valid OMML, and common Pandoc/simple fixed-width tables are normalized into native Word tables. These are renderer-level fixes; no document-specific substitutions are used.

## What it renders natively

- Word paragraphs and H1–H6 headings
- bold, italic, strikethrough, inline code, blockquotes, and editable code blocks
- native Word hyperlinks
- native ordered, unordered, and nested numbering
- native Word checkbox content controls for common Markdown task lists
- native editable Word tables with repeated headers and row pagination policy
- native editable Office charts (column, bar, line, pie, scatter) backed by embedded `.xlsx` workbooks
- CSV/JSON data imports for charts and native Word tables
- inline/display Office Math (OMML), including fractions, roots, limits, n-ary operators,
  matrices, aligned equations, cases, accents, vectors, Greek symbols, and common operators
- PNG/JPEG images plus optional WebP/SVG conversion
- page breaks, section breaks, headers, footers, PAGE fields, TOC fields, STYLEREF fields,
  bookmarks, document metadata, native SEQ/REF cross-references, captions, footnotes, and endnotes

## Phase 3 capabilities

- existing `.docx` templates, with optional preservation of their page setup and `MD *` styles
- built-in `default`, `academic`, `modern`, and `minimal` themes
- custom body/heading/code fonts plus East-Asian and complex-script font slots
- Unicode-safe XML text handling and native Word RTL/bidi paragraph/run properties
- WebP and SVG input through the optional `images` extra; SVG external references are blocked
- opt-in HTTPS image downloading with scheme/domain/redirect/MIME/size and non-global-host checks
- deterministic table width heuristics and optional automatic landscape sections for wide tables
- custom AST/render extensions and parser/document transform hooks
- structured JSON diagnostics
- render timing and optional peak-memory statistics
- per-render math caching and optional on-disk remote-resource caching
- semantic versioning, compatibility documentation, examples, and stable public rendering entry points

## Install

```bash
python -m pip install -e .
```

Optional features:

```bash
python -m pip install -e '.[math]'
python -m pip install -e '.[frontmatter]'
python -m pip install -e '.[images]'
python -m pip install -e '.[dev,images]'
```

`latex2mathml` is optional because the project owns a deterministic safe LaTeX-subset converter.
PyYAML is a core dependency because project manifests and bounded chart/data fence specs use safe YAML parsing. `openpyxl` is also a core dependency in v0.9.0 because every native Office chart embeds an editable Excel workbook. A scalar front-matter fallback is still retained for embedded Markdown metadata. The `images` extra installs
Pillow, CairoSVG, and defusedxml for WebP/SVG handling.

## CLI

```bash
mddocx document.md
mddocx document.md -o document.docx
mddocx document.md --check
mddocx document.md --theme academic
mddocx document.md --template company.docx
mddocx document.md --font "Aptos" --heading-font "Aptos Display"
mddocx document.md --rtl auto --auto-landscape-tables
mddocx document.md --toc --page-numbers --header "Project" --footer "Confidential"
mddocx document.md --diagnostics-json diagnostics.json --profile --profile-memory
mddocx inspect output.docx --strict
mddocx doctor
mddocx visual-qa output.docx --baseline-dir qa/baseline
mddocx template inspect company.docx
mddocx document.md --heading-numbering --caption-numbering section --equation-numbering section
mddocx document.md --code-line-numbers --code-language-labels --page-x-of-y
mddocx project init report
mddocx build report
mddocx project info report
mddocx watch report
mddocx data inspect data/results.csv --json
mddocx accessibility output.docx --strict
mddocx benchmark --sections 100 --max-seconds 15 --max-peak-mb 512
mddocx api --json
mddocx metadata inspect downloaded-chat.md
mddocx metadata clean downloaded-chat.md -o clean.md
```

Remote images remain disabled by default. To opt in and restrict hosts:

```bash
mddocx document.md --allow-remote-resources --allow-domain images.example.com
```

Manual layout directives:

```markdown
<!-- pagebreak -->
<!-- sectionbreak -->
```


## AI/chat export metadata sanitization (v1.2)

Downloaded conversations often contain provenance such as conversation IDs, model names, export timestamps, source URLs, hidden HTML comments, or YAML fields. `mddocx` now removes high-confidence export metadata **before Markdown parsing** by default:

```console
mddocx downloaded-chat.md -o conversation.docx
```

The default policy is `auto`. It preserves conversation roles and content, equations, code, tables, links, normal authored front matter, and examples inside fenced code blocks. Removed lines are replaced with blank source lines internally so diagnostic line numbers still refer to the original Markdown. AI-derived title/author/date fields are also prevented from leaking into DOCX core properties; synthetic `python-docx` author/date defaults are scrubbed for newly generated non-template documents unless the user supplied explicit document properties.

Preview what will be removed:

```console
mddocx metadata inspect downloaded-chat.md
mddocx metadata inspect downloaded-chat.md --json
```

Write a cleaned Markdown copy without rendering:

```console
mddocx metadata clean downloaded-chat.md -o clean.md
```

Override behavior when needed:

```console
mddocx downloaded-chat.md -o conversation.docx --ai-metadata strip
mddocx downloaded-chat.md -o conversation.docx --ai-metadata keep
```

Project manifests can set the same policy:

```yaml
render:
  ai_metadata: auto   # auto | strip | keep
```

`auto` is intentionally conservative and only removes strong export/provenance patterns near document boundaries or explicit metadata sections. `strip` is more aggressive for recognized metadata keys. `keep` preserves the source metadata exactly. See `docs/AI_EXPORT_METADATA.md` for detection rules and examples.

## Interactive console (v1.1)

For users who do not want to memorize flags, start the discoverable console:

```console
mddocx shell
```

It provides a menu and REPL over the **same** compiler/API used by the normal CLI. Common commands include:

```text
render report.md -o report.docx
build --open
watch
doctor
inspect
accessibility
config
template inspect corporate.dotx
data inspect results.csv
fonts aptos
recent
open
help
```

The shell detects the current workspace/project, includes a Markdown file picker and guided render wizard, preserves Windows paths containing backslashes/spaces, and keeps path/settings-only recent history. It never adds a generic shell-execution escape. Remote resources remain opt-in and retain the normal mddocx network restrictions.

Top-level convenience commands are also available:

```console
mddocx recent
mddocx open
mddocx report.md -o report.docx --open
mddocx build . --open
```

See `docs/INTERACTIVE_CLI.md` for the complete console guide.

## YAML front matter

```yaml
---
title: AI Research Report
author: Example
subject: Native Word output
keywords: markdown, docx, omml
page_size: A4
orientation: portrait
theme: academic
toc: true
page_numbers: true
auto_landscape_tables: true
rtl: auto
header: Research Group
footer: Confidential
---
```

Explicit `RenderConfig` values take precedence over front matter when they conflict.

## Python API

```python
from mddocx import (
    FontConfig,
    FooterConfig,
    HeaderConfig,
    RenderConfig,
    TableConfig,
    TOCConfig,
    render,
    render_string,
)

render("report.md", "report.docx")
render("report.md", "branded.docx", template="company.docx")

config = RenderConfig(
    theme="modern",
    fonts=FontConfig(body="Aptos", headings="Aptos Display"),
    toc=TOCConfig(enabled=True),
    table=TableConfig(auto_landscape=True),
    header=HeaderConfig(enabled=True, document_title=True, section_title=True),
    footer=FooterConfig(enabled=True, page_number=True),
)
blob = render_string("# Report\n\n$$\\sum_{i=1}^n i$$", config=config)
```

For custom AST nodes, use `MarkdownWord.render_ast()` together with an extension. See
`docs/EXTENSIONS.md`.

## Stable v1 API

`mddocx` 1.x follows the public compatibility policy in `docs/API_STABILITY.md`. Run `mddocx api --json` to inspect the frozen API surface. New compatible 1.x releases may add optional features, but established v1 public names and semantics require a deprecation cycle before removal or incompatible change.

## Production QA

Use `mddocx inspect FILE.docx --strict` for OOXML/OMML integrity, `mddocx accessibility FILE.docx --strict` for common structural accessibility issues, and `mddocx benchmark` for a deterministic large-document performance gate. See `docs/COMPATIBILITY_MATRIX.md`, `docs/ACCESSIBILITY.md`, and `docs/PERFORMANCE.md`.

## Architecture

```text
Markdown -> Markdown Parser -> Canonical AST -> Normalizer -> DOCX Renderer -> OOXML/OMML
```

The parser and AST do not depend on `python-docx`. Low-level Word XML is centralized under
`mddocx.ooxml`, math conversion under `mddocx.math`, resource security under `mddocx.resources`,
and extension hooks under `mddocx.extensions`.

## Security defaults

- code blocks and TeX are never executed
- remote resources are disabled by default
- local image paths cannot escape the Markdown base directory
- remote resources default to HTTPS only and block private/loopback/link-local/non-global hosts
- redirects, download size, MIME types, and optional domains are constrained
- SVG parsing uses defused XML and rejects external references
- MathML parsing disables DTD/network/entity resolution

## Compatibility and limitations

See `docs/COMPATIBILITY.md`. The project validates generated OOXML structurally and reopens
integration outputs with `python-docx`; pixel-identical layout across Word versions is not a goal.
SVG is rasterized to PNG before embedding for broad DOCX compatibility. Word performs final font
fallback, line wrapping, shaping, and pagination.




## Phase 7 project/build mode

Version 0.8.0 can compile a document project instead of requiring one monolithic Markdown file.

```yaml
# mddocx.yml
version: 1
output: build/report.docx
sources:
  - chapters/*.md
variables:
  product: mddocx
render:
  title: Project Report
  title_page: true
  toc: true
  heading_numbering: true
  equation_numbering: section
  caption_numbering: section
```

A chapter can include shared Markdown with a standalone directive:

```markdown
@include ../includes/conventions.md
```

Then build or watch the whole project:

```bash
mddocx build .
mddocx project info .
mddocx watch .
```

Project includes and resources are constrained to the project root, include cycles are rejected, project variables are inert scalar substitutions, and successful builds use `.mddocx/build-state.json` to skip unchanged artifacts while verifying the output SHA-256. See `docs/PHASE7.md`.

## Phase 6 Word professional features

Version 0.7.0 adds:

- native multilevel Word heading numbering (no manually prefixed heading text);
- section-scoped figure/table/listing/equation numbering and field-backed references;
- configurable title pages, abstracts, organizations, and keyword blocks;
- advanced headers/footers with first/even variants and bounded native field templates;
- `Page X of Y` fields;
- GitHub-style and `:::` callouts/admonitions;
- editable Pygments syntax highlighting, optional code line numbers, highlighted lines, and language labels;
- a centralized Markdown attribute parser;
- CriticMarkup `{>>...<<}` comments compiled to native Word comments;
- `mddocx template inspect TEMPLATE.docx`;
- stronger validation for dangling hyperlinks/REF fields, duplicate bookmarks, and comment integrity.

See `docs/PHASE6.md`.

## Phase 5B professional Word semantics

Version 0.6.0 adds document-wide semantic references and publication features:

- explicit Markdown identifiers on headings, figures, tables, equations, and code listings;
- centralized Word-safe bookmark/reference registry with duplicate-target detection;
- native `SEQ` caption numbering and native `REF` cross-references for figures, tables, equations, and listings;
- section-scoped equation numbering such as `(2.1)` without converting OMML equations to images;
- internal Word hyperlinks for Markdown `#fragment` links;
- native Word endnotes as an alternative to footnotes;
- citation AST plus BibTeX and CSL-JSON bibliography loading with basic APA/author-year/IEEE/numeric formatting;
- explicit or automatic bibliography generation;
- image alt/title metadata, decorative-image marking, percentage sizing, and left/center/right placement;
- definition-list compatibility;
- deterministic offline Mermaid support for flowchart/graph, sequence, state, class, ER, mindmap, timeline, pie, journey, and gantt subsets.

Example:

```markdown
![Architecture](architecture.png){#fig-arch width=70% align=center caption="System architecture"}

See [Figure @fig-arch].

$$
E=mc^2
$$ {#eq-energy}

See [Equation @eq-energy] and [@smith2025, p. 42].

## References

::: bibliography
:::
```

See `docs/PHASE5B.md` for syntax, configuration, citation behavior, Mermaid coverage, and deliberately bounded compatibility rules.

## Phase 5A QA and fidelity tools

Version 0.5.0 adds three operational QA commands without changing the normal conversion command:

- `mddocx inspect FILE.docx` audits OOXML/package integrity, native Word structures and common math/list/layout failure signals.
- `mddocx doctor` reports Python/dependency/runtime readiness and whether local page-render visual QA is available.
- `mddocx visual-qa FILE.docx --baseline-dir DIR` renders pages through LibreOffice/soffice + `pdftoppm` and compares them with a visual baseline.

The test suite also contains a 600-equation native-OMML regression corpus and an opt-in rendered-page snapshot test. See `docs/PHASE5A.md`.


## Phase 4 operational features

The 0.4.x Phase 4 line adds release/CI hardening without changing `render()`, `render_string()`, or `MarkdownWord`:

- reproducible DOCX ZIP ordering/timestamps and artifact SHA-256 reporting;
- defensive generated-package validation;
- configurable input/AST complexity limits;
- opt-in persistent normalized-AST cache;
- explicitly named Python entry-point plugins;
- deterministic batch/directory conversion;
- SARIF 2.1.0 diagnostics.

Batch CLI example:

```text
mddocx reports/ --recursive --output-dir word-output/ --ast-cache .mddocx-cache
```

CI diagnostics example:

```text
mddocx report.md --diagnostics-sarif diagnostics.sarif --profile
```

See `docs/PHASE4.md` for configuration details and trust-boundary notes.


## Footnotes and Mermaid

Common Markdown footnotes such as `text[^1]` plus `[^1]: note` compile to native Word footnotes. Inline mathematics inside a footnote remains OMML-editable.

Mermaid fences are rendered offline using bounded project-owned renderers for common flowchart/graph and sequence diagrams plus safe subsets of state, class, ER, mindmap, timeline, pie, journey, and gantt. This is not the Mermaid JavaScript runtime: unsupported constructs remain editable code and emit `DIAGRAM201`. Use `--no-mermaid` to always preserve Mermaid as source code, or `--mermaid-strict` to fail on unsupported syntax.


## Phase 8 native charts and data imports

A chart fence produces a real Office chart plus an embedded editable workbook:

````markdown
```chart {#fig-sales caption="Quarterly sales"}
type: column
title: Quarterly performance
source: data/quarterly.csv
category: Quarter
series_fields: [Revenue, Profit]
```

See [Figure @fig-sales].
````

Inline chart data is also supported:

````markdown
```chart
type: line
title: Accuracy
categories: [A, B, C]
series:
  - name: Score
    values: [91, 94, 92]
```
````

Import the same CSV/JSON source as a native Word table:

````markdown
```data-table {#tbl-results caption="Benchmark results"}
source: data/results.json
columns: [Model, Accuracy, Latency]
```
````

Supported structured sources are UTF-8 CSV and JSON arrays of objects (or `{ "rows": [...] }`). Data paths are confined to the Markdown/project base directory. In project mode, these files participate in dependency fingerprints and automatically trigger rebuilds when changed.
