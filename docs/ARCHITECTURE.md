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
5. **Render** maps the AST to editable Word structures: OMML equations,
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
