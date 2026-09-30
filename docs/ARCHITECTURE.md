# How mddocx works

mddocx is a Markdown-to-Word compiler. It converts content into native Word
elements instead of taking a screenshot or flattening the document. Equations
remain editable OMML, charts remain editable ChartML with an embedded workbook,
and headings, lists, tables, notes, references, and images remain structured.

```mermaid
flowchart TD
    A["Markdown input<br/>file, string, project, or AI output"]
    B["Clean and prepare<br/>metadata, math delimiters, security limits"]
    C["Parse Markdown<br/>CommonMark/GFM + mddocx extensions"]
    D["Canonical document model<br/>headings, text, lists, tables, math, media"]
    E["Normalize and validate<br/>stable IDs, hierarchy, source diagnostics"]
    F["Plan layout<br/>widths, sections, landscape tables, pagination intent"]
    G["Render native Word content<br/>styles, OMML, DrawingML, ChartML, fields, notes"]
    H["Build DOCX package<br/>XML parts, relationships, metadata"]
    I["Validate and test<br/>structure, security, accessibility, reproducibility"]
    J["Editable Microsoft Word document"]

    A --> B --> C --> D --> E --> F --> G --> H --> I --> J

    E -. "warnings and errors" .-> K["Stable diagnostics<br/>code, severity, file, line, explanation"]
    G -. "unsupported equation fallback" .-> K
    I -. "validation failure" .-> K
```

## Component architecture

```mermaid
flowchart LR
    subgraph Entry["User entry points"]
        CLI["CLI"]
        SHELL["Interactive shell"]
        API["Python API"]
        BATCH["Batch / project mode"]
    end

    subgraph Core["Typed compiler services"]
        ACQ["Source acquisition"]
        PARSER["Markdown parser"]
        AST["Canonical AST"]
        NORM["Normalizer + semantic index"]
        PLAN["Layout planner"]
    end

    subgraph Output["Native Word backend"]
        CTX["Typed render context"]
        MATH["OMML math renderer"]
        MEDIA["Resource resolver + DrawingML"]
        DOCX["OOXML package finalizer"]
        VALIDATE["Structural / accessibility validation"]
    end

    CLI --> ACQ
    SHELL --> ACQ
    API --> ACQ
    BATCH --> ACQ
    ACQ --> PARSER --> AST --> NORM --> PLAN --> CTX
    CTX --> MATH --> DOCX
    CTX --> MEDIA --> DOCX
    CTX --> DOCX --> VALIDATE
```

## Image-resource decision flow

```mermaid
flowchart TD
    SRC["Markdown image source"] --> KIND{"Source kind?"}
    KIND -->|"data:image/...;base64"| DATA["Preflight encoded size"]
    DATA --> DECODE["Strict Base64 decode"]
    DECODE --> MIME["Validate declared MIME and actual image"]
    KIND -->|"Local path"| CONTAIN["Resolve beneath document/project root"]
    CONTAIN --> MIME
    KIND -->|"HTTP(S) image syntax"| PREF{"Remote resources allowed?"}
    PREF -->|"No"| R201["RESOURCE201 with remediation"]
    PREF -->|"Yes"| HOST["Validate scheme, host, DNS and redirects"]
    HOST --> SIZE["Stream with hard size limit"]
    SIZE --> MIME
    MIME --> FORMAT{"Word-compatible raster?"}
    FORMAT -->|"PNG/JPEG/GIF/BMP/TIFF"| EMBED["Embed native DrawingML"]
    FORMAT -->|"WebP/SVG enabled"| CONVERT["Hardened local conversion"]
    CONVERT --> EMBED
    EMBED --> FIT["Preserve aspect ratio and fit usable page width"]
    FIT --> ALT["Attach alt text / decorative metadata"]
```

The `data:` branch is always local and never consults the network preference. Public HTTP(S) is
allowed by the library and ordinary CLI by default. On the first interactive-shell launch, the
user can choose to block it; the shell stores only that boolean preference. Even when HTTPS is
allowed, private/reserved addresses, unsafe redirects, invalid MIME types, oversized downloads,
and external SVG references remain blocked. Non-image responses and acquisition failures become
clickable figure fallbacks unless strict-image mode is selected; ordinary links never enter this flow.

## Module ownership

Each concern has exactly one owner, and data flows one way: configuration and text come in,
WordprocessingML goes out.

| Concern | Owner | Depends on |
|---|---|---|
| Which script is this text? | [`scripts.py`](../src/mddocx/scripts.py) | Unicode data only |
| Which font does each slot use? | [`styles/fonts.py`](../src/mddocx/styles/fonts.py) | `config`, `styles/themes.py` |
| How is a run or paragraph written to Word XML? | [`ooxml/text.py`](../src/mddocx/ooxml/text.py) | `scripts`, `python-docx` XML helpers |
| How is a package part registered? | [`ooxml/package.py`](../src/mddocx/ooxml/package.py) | `zipfile`, `lxml` |
| How is a note part built? | [`ooxml/notes.py`](../src/mddocx/ooxml/notes.py) | `ooxml/package.py`, `ooxml/text.py`, inline AST |
| Who decides direction and applies policy? | [`render/renderer.py`](../src/mddocx/render/renderer.py) | all of the above |

Flow: `RenderConfig + ThemeSpec → FontSlots`; `text → scripts → (font slot, direction)`;
`(font slot, direction) → ooxml/text.py → w:r / w:p`; `note AST → ooxml/notes.py → package part`.

The block renderer is split the same way: [`render/renderer.py`](../src/mddocx/render/renderer.py)
holds the per-render state, the `render()` sequence, the `_render_block` dispatch table, the inline
engine, and the text/direction policy. Every Word surface is a module in the same package whose
functions take the live renderer:

| Surface | Owner | Depends on |
|---|---|---|
| Template loading, core properties, field updates | [`render/document_setup.py`](../src/mddocx/render/document_setup.py) | `docx`, `validation`, `sections` |
| Page geometry, margins, orientation | [`render/sections.py`](../src/mddocx/render/sections.py) | `docx`, `headers_footers` |
| Headers and footers | [`render/headers_footers.py`](../src/mddocx/render/headers_footers.py) | `ooxml/fields.py` |
| Title page, abstract, table of contents | [`render/front_matter.py`](../src/mddocx/render/front_matter.py) | `ooxml/fields.py`, `ooxml/text.py` |
| Headings, paragraphs, quotes, callouts, definition lists, flow breaks | [`render/text_blocks.py`](../src/mddocx/render/text_blocks.py) | `ooxml/fields.py`, `lists`, `sections` |
| Bullets, ordered lists, task items | [`render/lists.py`](../src/mddocx/render/lists.py) | `ooxml/numbering.py`, `ooxml/tasks.py` |
| Tables, widths, landscape planning | [`render/tables.py`](../src/mddocx/render/tables.py) | `layout.py`, `ooxml/utils.py`, `citations`, `sections` |
| Imported data tables and data-path containment | [`render/data_tables.py`](../src/mddocx/render/data_tables.py) | `data.py`, `citations`, `tables` |
| Charts and ChartEntry validation | [`render/charts.py`](../src/mddocx/render/charts.py) | `ooxml/charts.py`, `data.py`, `data_tables`, `citations` |
| Images, Mermaid diagrams, figure placement | [`render/figures.py`](../src/mddocx/render/figures.py) | `resources`, `ooxml/fields.py`, `citations` |
| Fenced code and listing captions | [`render/code_blocks.py`](../src/mddocx/render/code_blocks.py) | `diagrams`, `text_layout.py`, `figures`, `citations` |
| Block math and numbered equations | [`render/math_blocks.py`](../src/mddocx/render/math_blocks.py) | `ooxml/fields.py`, `tables` |
| Captions, cross-references, bibliography | [`render/citations.py`](../src/mddocx/render/citations.py) | `ooxml/fields.py`, `references.py` |

The rules that keep the structure from drifting:

- Script classification stays free of Word, OOXML, and configuration knowledge.
- The font rule — explicit configuration, then the configured fallback list, then the theme
  font — is defined once in `styles/fonts.py`. Word styles and document runs both read
  `FontSlots`, so they cannot disagree about a script's font.
- Direction policy (`off`, `auto`, `force`) lives in the renderer. The XML layer only writes
  the decision it is given.
- Footnotes and endnotes are one implementation parameterized by `NotePart`. A new note kind
  extends that spec rather than adding a module.
- Every added package part goes through `ooxml/package.py`, so content types and relationships
  are registered consistently.
- Text surfaces created outside the block renderer (title page, abstract, TOC title, captions,
  bibliography, headers, footers) call `renderer._apply_text_policy` so they inherit the same
  font slots and direction as body content.
- Block surfaces are renderer-taking functions (`render_table(renderer, node)`), not classes or
  mixins. They never build render state and never call `render()`; the renderer is the only
  orchestrator and the only owner of the dispatch table.
- Surface modules import each other only along the edges in the table above:
  `document_setup → sections`, `sections → headers_footers`, `text_blocks → lists, sections`,
  `tables → sections`, `data_tables → tables`, `charts → data_tables`,
  `code_blocks → figures`, and `math_blocks → tables` (the borderless-table helper).
  Numbered-reference presentation — captions, cross-references, bibliography — is shared
  through `citations` rather than re-implemented per surface.
  `render/renderer.py` may import every surface; no surface imports `renderer.py` at runtime
  (only under `TYPE_CHECKING` for annotations), which keeps the package acyclic.
- `render/renderer.py` stays the orchestrator: `tests/test_render_module_boundaries.py` fails
  if it grows past 700 lines or loses the shared entry points
  (`_style`, `_configure_run`, `_apply_text_policy`, `_render_inlines`).

## Stages

1. **Clean and prepare** removes high-confidence AI/chat export metadata,
   recognizes equation syntax commonly emitted by ChatGPT, Claude, Gemini, and
   other LaTeX-producing systems, protects code and currency text, and applies
   input/resource limits.
2. **Parse** converts CommonMark/GFM and documented mddocx extensions into a
   canonical AST. The parser does not execute Markdown, TeX, code, or remote
   resources.
3. **Normalize and validate** removes parser quirks, coalesces text, normalizes
   math, assigns stable heading identifiers, checks hierarchy and table shape,
   and records source-located diagnostics.
4. **Plan layout** makes page-sensitive decisions before OOXML is written. For
   example, a wide table can receive a deterministic landscape section and the
   following content can return to portrait orientation.
5. **Render** maps the AST to editable Word structures: MathJax-validated OMML equations,
   DrawingML images, ChartML charts, Word numbering, fields, bookmarks,
   footnotes/endnotes, citations, headers, footers, and tables.
6. **Finalize and validate** scrubs generated metadata when configured,
   produces deterministic package parts, checks relationships and XML safety,
   and exposes structural, accessibility, performance, LibreOffice, and Word
   365 qualification checks.

The v1 façade (`render`, `render_string`, and `MarkdownWord`) remains available.
The staged `Compiler` additionally exposes parse, normalize, plan, render, check,
and compile operations with typed results and diagnostics.

The supported construct contract is maintained in
[`feature-matrix.json`](feature-matrix.json). Word 365 is the primary output
authority; LibreOffice is used as a secondary automated rendering signal.
