# Phase 5B — Professional Word Semantics

Phase 5B (`mddocx` 0.6.0) adds document-wide semantic references and publication features while retaining the compiler boundary:

```text
Markdown -> canonical AST -> normalization/reference registry -> DOCX renderer -> WordprocessingML/OMML
```

## Identifiers, bookmarks, and cross-references

Supported block identifiers include headings, figures, tables, display equations, and code listings.

```markdown
## Results {#results}

![Architecture](architecture.png){#fig-architecture caption="System architecture"}

$$
E=mc^2
$$ {#eq-energy}

```python {#lst-api caption="Rendering entry point"}
render("input.md", "output.docx")
```
```

Cross-reference syntax:

```markdown
See [Section @results].
See [Figure @fig-architecture].
See [Equation @eq-energy].
See [Listing @lst-api].
```

Non-section references are emitted as native Word `REF` fields targeting bookmarks whose visible numbers are driven by native `SEQ` fields. Markdown links to `#fragment` identifiers become internal Word hyperlinks. `ReferenceConfig(enabled=False)` preserves readable static reference text without emitting REF/SEQ numbering infrastructure.

## Captions and numbering

Figure, table, equation, and listing identifiers participate in a centralized reference registry. Captions use the project `MD Caption` style and are black by default.

Tables can use:

```markdown
| Model | Score |
|---|---:|
| A | 94 |

Table: Evaluation results {#tbl-results}
```

Images and code fences can carry captions in attribute lists. Caption position and labels are configurable with `ReferenceConfig`.

Equation numbering supports document-wide numbers and H1-section-scoped numbers. Section-scoped mode emits native hidden Word counters plus a visible composite equation number such as `(2.1)`; the equation itself remains editable OMML.

## Notes

`NotesConfig(style="footnote")` keeps the existing native Word footnote behavior. `NotesConfig(style="endnote")` creates `word/endnotes.xml` and native endnote references. Basic inline formatting and inline OMML are preserved inside notes.

Front matter:

```yaml
notes: endnote
```

## Citations and bibliography

Phase 5B introduces a citation AST independent from DOCX rendering. Supported source formats are BibTeX and CSL-JSON.

```markdown
A compiler architecture can be cited [@smith2025].
A locator can be included [@smith2025, p. 42].
Multiple sources are supported [@smith2025; @lee2026].
```

Configuration:

```python
CitationConfig(
    bibliography=Path("references.bib"),
    style="apa",
    auto_bibliography=False,
)
```

Or front matter:

```yaml
bibliography: references.bib
citation_style: apa
```

An explicit bibliography block is:

```markdown
## References

::: bibliography
:::
```

If that block is immediately preceded by a heading matching the configured bibliography title, mddocx reuses the explicit heading rather than generating a duplicate heading.

Current styles are deterministic project-owned `apa`, `author-year`, `ieee`, and `numeric` formatters. They intentionally do not claim full CSL processor compatibility.

## Figures and accessibility

Image attributes include:

```markdown
![Architecture](architecture.png "Architecture title"){
  #fig-architecture width=72% align=center caption="Compilation pipeline"
}
```

The renderer writes Word drawing alt text/title metadata. `decorative=true` marks a drawing decorative using the Word decorative extension and clears normal descriptive alt text. Width percentages are bounded to the usable section width and preserve aspect ratio. Alignment supports `left`, `center`, and `right`.

## Definition lists

Common simple definition-list syntax is normalized into semantic definition-list AST nodes:

```markdown
Compiler
: A deterministic program that maps one representation to another.
```

Terms render bold with an indented definition paragraph.

## Mermaid

Mermaid rendering remains offline, deterministic, bounded, and non-executing. The Markdown source is never passed to a shell, browser, Node.js runtime, or remote rendering service.

Supported safe subsets include:

- `flowchart` / `graph`
- `sequenceDiagram`
- `stateDiagram` / `stateDiagram-v2`
- `classDiagram`
- `erDiagram`
- `mindmap`
- `timeline`
- `pie`
- `journey`
- `gantt`

These are compatibility renderers, not a full implementation of Mermaid JavaScript semantics. Unsupported syntax either falls back to editable code with `DIAGRAM201` or fails when strict Mermaid mode is enabled.

## Inspection

`mddocx inspect` now reports reference/caption and publication structures including SEQ/REF field counts, internal hyperlinks, endnote references/definitions, drawing accessibility metadata, OMML integrity, and relationship integrity.

```bash
mddocx inspect report.docx --strict
```

## Acceptance criteria

The Phase 5B release fixture is a 30-page technical/academic DOCX containing native equations, section equation numbering, captions, cross-references, tables, figures, code listings, task controls, endnotes, citations, a bibliography, definition lists, page fields, headers/footers, and multiple Mermaid families. Release QA requires structural inspection plus rendered-page visual inspection.

## Intentional limits

- Full CSL style-language execution is not implemented.
- Mermaid support is a deterministic safe subset, not the Mermaid JS engine.
- Word/LibreOffice may display field results differently until fields are updated by the host application.
- Numbered display equations currently use borderless one-row layout tables for stable centered-equation/right-number positioning. Generic accessibility auditors may flag those layout tables as lacking header rows; semantic data tables still receive header-row markup.
- The renderer does not execute code, TeX macros, Mermaid JavaScript, or bibliography scripts.
