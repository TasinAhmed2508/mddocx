# Compatibility Matrix

This matrix distinguishes implemented behavior from behavior covered by the current tracked
regression suite. Structural checks do not claim pixel-level certification on every Word release.

## Runtime

| Surface | Status | Notes |
|---|---|---|
| Python 3.11+ | Supported | Declared package floor. |
| Linux/macOS/Windows | Portable design | Core uses Python + OOXML. SVG conversion additionally depends on the optional CairoSVG stack. |
| No AI service at runtime | Supported | Parsing/rendering are deterministic. |

## Markdown / document semantics

| Feature | Status |
|---|---|
| H1–H6, paragraphs, emphasis, strike, code | Implemented; broad regression coverage pending |
| links and blockquotes | Implemented; broad regression coverage pending |
| ordered/unordered/nested lists | Implemented; broad regression coverage pending |
| Markdown tables | Implemented; broad regression coverage pending |
| inline/display math | Tested for the AI-math corpus documented in `AI_MATH_COMPATIBILITY.md` |
| PNG/JPEG | Implemented; broad regression coverage pending |
| WebP/SVG | Implemented with `mddocx[images]`; broad regression coverage pending |
| page/section break directives | Implemented; broad regression coverage pending |
| YAML front matter | Implemented; broad regression coverage pending |
| arbitrary embedded HTML | Not supported by design |
| arbitrary TeX macro execution | Not supported by design |

## Word structures

| Structure | Status | Notes |
|---|---|---|
| Word paragraphs/headings/styles | Tested | Native WordprocessingML. |
| native numbering | Tested | No manually typed bullet/number prefixes. |
| native tables | Tested | Repeat-header and row-split properties included. |
| native OMML equations | Tested | Editable Office Math, not equation images. |
| hyperlinks | Tested | External relationship-backed links. |
| TOC/PAGE/STYLEREF fields | Tested | Hosts may require/update fields on open. |
| headers/footers/bookmarks/metadata | Tested | Native package parts/properties. |
| automatic landscape table sections | Tested | Uses Word section semantics and page breaks. |
| RTL/bidi properties | Tested structurally | Word performs shaping/font selection. |

## Microsoft Word targets

The OOXML/OMML emitted by `mddocx` targets modern desktop Microsoft Word and Microsoft 365.
Word 2016/2019/2021 are expected to understand the core structures used here, but this repository
has not performed a full visual certification matrix for each build. SVG input is rasterized before
embedding, avoiding dependence on a host's native SVG rendering support.

## Other office suites

LibreOffice and other DOCX consumers may open the package, but field updates, OMML appearance,
font substitution, and pagination can differ. They are not currently visual-regression targets.
