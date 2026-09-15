# mddocx

[![PyPI](https://img.shields.io/pypi/v/mddocx-native)](https://pypi.org/project/mddocx-native/)
[![Python](https://img.shields.io/pypi/pyversions/mddocx-native)](https://pypi.org/project/mddocx-native/)
[![CI](https://github.com/TasinAhmed2508/mddocx/actions/workflows/ci.yml/badge.svg)](https://github.com/TasinAhmed2508/mddocx/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/TasinAhmed2508/mddocx)](https://github.com/TasinAhmed2508/mddocx/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Deterministic Markdown-to-DOCX compilation for professional, editable Microsoft Word documents.

mddocx converts Markdown into native Word structures instead of screenshots or flattened pages. Headings, lists, tables, equations, charts, links, references, footnotes, headers, footers, and other document elements remain editable in Microsoft Word.

## What it does

- Converts Markdown files or strings into native DOCX documents.
- Preserves editable Word headings, paragraphs, lists, tables, hyperlinks, and code blocks.
- Supports nested lists, task lists, blockquotes, callouts, page breaks, and section breaks.
- Produces editable Word equations using OMML rather than images.
- Creates editable Office charts backed by embedded Excel workbooks.
- Supports CSV and JSON data for charts and native Word tables.
- Handles local, HTTPS, and Base64 `data:image/...;base64,...` images, plus captions, bookmarks,
  cross-references, footnotes, endnotes, and citations.
- Supports themes, fonts, templates, right-to-left text, headers, footers, tables of contents, and page fields.
- Provides project mode for compiling multiple Markdown chapters into one document.
- Includes diagnostics, document inspection, accessibility checks, and profiling utilities.
- Provides privacy-aware metadata handling for exported AI/chat conversations.
- Accepts common equation syntax copied from ChatGPT, Claude, Gemini, and other MathJax/LaTeX-producing assistants.

## Installation

mddocx requires Python 3.11 or newer.

### Install from PyPI

The distribution is published as `mddocx-native`; the Python import and command remain `mddocx`:

```bash
python -m pip install --upgrade mddocx-native
```

Verify the installation:

```bash
mddocx --version
mddocx doctor
```

### Install a downloaded wheel

Download the `.whl` file from the [latest GitHub Release](https://github.com/TasinAhmed2508/mddocx/releases/latest), open a terminal in the download directory, and run:

```bash
python -m pip install ./mddocx_native-1.3.1-py3-none-any.whl
```

On Windows PowerShell, the equivalent command is:

```powershell
python -m pip install .\mddocx_native-1.3.1-py3-none-any.whl
```

You can also install the wheel directly from the v1.3.1 GitHub Release:

```bash
python -m pip install "https://github.com/TasinAhmed2508/mddocx/releases/download/v1.3.1/mddocx_native-1.3.1-py3-none-any.whl"
```

### Install from GitHub

```bash
python -m pip install "git+https://github.com/TasinAhmed2508/mddocx.git@v1.3.1"
```

### Install for local development

```bash
git clone https://github.com/TasinAhmed2508/mddocx.git
cd mddocx
python -m pip install -e ".[dev]"
```

Optional features:

```bash
python -m pip install "mddocx-native[math]"
python -m pip install "mddocx-native[images]"
python -m pip install "mddocx-native[math,images]"

# Add arbitrary local CSL style support
python -m pip install "mddocx-native[academic]"
```

## Quick start

Create a file named report.md:

    # Quarterly Report

    ## Summary

    This report is generated from Markdown and remains fully editable in Word.

    | Metric | Value |
    | --- | ---: |
    | Revenue | 125,000 |
    | Growth | 18% |

Convert it to Word:

    mddocx report.md -o report.docx

## Command-line interface

    mddocx document.md -o document.docx
    mddocx document.md --theme academic
    mddocx document.md --template company.docx
    mddocx document.md --toc --page-numbers
    mddocx document.md --header "Project Report" --footer "Confidential"
    mddocx document.md --diagnostics-json diagnostics.json
    mddocx document.md --strict-math
    mddocx math-check document.md
    mddocx inspect document.docx --strict
    mddocx accessibility document.docx --strict
    mddocx doctor
    mddocx api --json

For multi-file document projects:

    mddocx project init report
    mddocx build report
    mddocx project info report
    mddocx watch report

For interactive use:

    mddocx shell

Run mddocx --help for the complete command reference.

## Python API

    from mddocx import RenderConfig, render, render_string

    render("report.md", "report.docx")

    config = RenderConfig(theme="modern")
    document = render_string("# Generated report\n\nEditable Word content.", config=config)

    with open("generated.docx", "wb") as file:
        file.write(document)

The public API is documented in docs/API_STABILITY.md and can also be inspected with mddocx api --json.
The additive compiler-stage mapping and behavioral changes are documented in
`docs/V2_MIGRATION.md`.

For callers that need the output, diagnostics, and profiling data together, use the staged-v2
compiler service:

    from mddocx import Compiler

    result = Compiler().compile_string("# Report\n\nInline \\(x^2\\).")
    print(result.success, result.diagnostics, result.stats)
    print(result.layout_plan.tables)

The same service exposes `parse_string`, `parse_file`, `normalize`, `plan`, `render`,
`check_string`, `check_file`, `compile_string`, and `compile_file`, so applications can
inspect canonical AST and layout decisions without duplicating compiler internals.

### AI-generated equations

Common inline forms (`\\(...\\)` and `$...$`), display forms (`\\[...\\]` and `$$...$$`),
and `math`, `latex`, or `tex` fenced blocks are converted to editable Word equations. Math-like
text inside code spans and ordinary code fences is preserved as code, and common currency forms
are preserved as text.

When an equation uses syntax that the active math engine cannot convert, mddocx preserves its
source as editable text and emits a `MATH201` warning. Use `--strict-math` when every equation must
be native Word math and conversion should fail on the first unsupported expression. See
`docs/AI_MATH_COMPATIBILITY.md` for the tested compatibility contract.

Run `mddocx math-check document.md` before conversion to see the active math engine and the number
of equations that can be rendered natively. Add `--json` for automation or `--strict` to return
exit code 3 when any equation requires a fallback.

## YAML front matter

Document settings can be defined at the top of a Markdown file:

    ---
    title: Research Report
    author: Example Author
    theme: academic
    toc: true
    page_numbers: true
    auto_landscape_tables: true
    header: Research Group
    footer: Confidential
    ---

## Privacy and security defaults

- Bounded public HTTP(S) image resources are allowed by default. Failed image syntax becomes a
  clickable fallback; ordinary Markdown links are never downloaded.
- Base64 image data URIs are decoded locally, never sent over the network, and remain subject to
  the configured per-resource size limit and image validation.
- HTTPS image downloads can be explicitly enabled and restricted by domain.
- Use `--block-remote-resources` for a single noninteractive conversion, or
  `--allow-remote-resources` to override a saved shell block for one render.
- Local resource paths cannot escape the document or project directory.
- Download size, MIME type, redirects, and network destinations are constrained.
- SVG parsing rejects external references and uses hardened XML handling.
- Code blocks and TeX are never executed.
- AI/chat export metadata is removed conservatively before Markdown parsing when enabled.

## Project layout

    mddocx/
    ├── src/mddocx/        # Package source code
    ├── docs/              # User and technical documentation
    ├── dist/              # Local build output, when generated
    ├── .github/workflows/ # CI and release automation
    ├── pyproject.toml     # Package metadata and build configuration
    └── README.md          # Project overview and usage guide

## Documentation

Detailed documentation is available in the docs directory, including compatibility, API stability, interactive CLI, charts and data, AI export metadata, accessibility, and extensions.

See the [1.3.0 release notes](docs/RELEASE_NOTES_1.3.0.md) for resilient resources, smart equations,
academic references, and the existing [1.2.4 release notes](docs/RELEASE_NOTES_1.2.4.md) for Base64-image,
AI-math, compiler, layout, security-policy, and migration summary.

The compiler stages and system architecture are described in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The machine-readable supported
feature contract is [docs/feature-matrix.json](docs/feature-matrix.json).

The machine-readable fidelity contract is `docs/feature-matrix.json`; every listed feature links
its accepted syntax, canonical AST, native Word representation, diagnostic behavior, host status,
and tracked regression evidence.

The complete staged engineering program is preserved in
`docs/FIDELITY_FIRST_V2_PLAN.md`; progress and compatibility notes remain additive until a
qualified 2.x release is ready.

Microsoft Word 365 release qualification, including the reusable Windows automation script, is
documented in `docs/WORD365_QA.md`.

## Releases

Release builds are generated by GitHub Actions. Each versioned release publishes the wheel and source archive as downloadable GitHub Release assets.

- [Latest release](https://github.com/TasinAhmed2508/mddocx/releases/latest)
- [All releases](https://github.com/TasinAhmed2508/mddocx/releases)
- [All version tags](https://github.com/TasinAhmed2508/mddocx/tags)
- [PyPI package](https://pypi.org/project/mddocx-native/)

## License

Released under the [MIT License](LICENSE).

### Bangla document forms and scanned-document transcriptions

Use `mddocx input.md -o output.docx --theme bengali-document` for compact
Bangla documents (10 pt, single spacing). Bangla output runs use SutonnyMJ
by default, with Unicode-to-Bijoy encoding applied only to Word XML. The output contains editable
Word tables and can be imported into Google Docs. Google Docs may substitute fonts
and reflow pages; verify the imported document before relying on page fidelity.

Plain `text` fences with a box-drawn photo placeholder, at least five labelled
fields, and paired pipe-separated address columns render as native form tables.
Plain-text three-column tables with at least two dashed row separators render as
native tables; continuation lines within a ruled row stay in the same cells.
Programming language fences remain code. Unsupported layouts remain literal code.

Numeric Gemini `[cite: 1]` export tokens outside code are removed by default.
Citation-suffixed matching closing fences are repaired so following paragraphs
are parsed correctly. `--ai-metadata keep` preserves the numeric markers
as text after the repaired closing fence. Markers inside fenced or inline code
remain literal. The converter preserves transcribed values; it does not infer
missing cells or correct discrepancies against a scanned reference.

For layouts that require merged cells, use an explicit `layout-table` YAML fence.
Rows must have equal numbers of string cells; widths are positive relative weights.
Merge coordinates are zero-based `[row, column]` pairs with inclusive endpoints.
Covered cells must be empty, and merge rectangles cannot overlap. This preserves
content and makes scan-specific structure explicit rather than guessing from text.

````markdown
```layout-table
widths: [15, 37, 7, 41]
rows:
  - [Floor, East, West, ""]
  - [Roof, Terrace, "", Owner]
  - [First, Owner, Stairs, Owner]
  - [Ground, Owner, "", Owner]
merges:
  - from: [0, 2]
    to: [0, 3]
  - from: [1, 1]
    to: [1, 2]
  - from: [2, 2]
    to: [3, 2]
```
````

The source Markdown and compiler AST always retain Unicode Bangla. Install
SutonnyMJ on the machine used to open or export DOCX; the font is not bundled.
Mixed English text retains a Latin font. Bijoy-encoded DOCX text depends on
SutonnyMJ and does not have Unicode Bangla copy/search semantics. The PDF
preview provides the intended visual result. `RenderConfig.fonts.bengali`
defaults to `SutonnyMJ`; set it to a Unicode font for Unicode output, or `None`
to disable this output pass. Bijoy conversion uses the pinned MPL-2.0
[bijoy2unicode library](https://github.com/Mad-FOX/bijoy2unicode), with padding
for its end-of-word lookahead and a SutonnyMJ-compatible la-phala glyph fix.
