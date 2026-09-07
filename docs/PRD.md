# Product Requirements Document

## Markdown → Word Rendering Library

**Working name:** `mddocx`
**Language:** Python
**Output:** Microsoft Word `.docx`
**Product type:** Python library + CLI
**Primary objective:** Deterministically convert Markdown into professionally structured, highly editable Microsoft Word documents.

---

# 1. Product Vision

`mddocx` will convert Markdown into native Microsoft Word documents while preserving document semantics.

The output must not merely *look* like the Markdown.

It should become a genuine Word document containing:

- native Word paragraphs;
- native headings;
- native editable equations;
- native numbered and bulleted lists;
- native Word tables;
- native hyperlinks;
- embedded images;
- editable code blocks;
- proper sections;
- Word styles;
- correct pagination instructions;
- headers and footers;
- page numbers;
- optional table of contents.

Primary pipeline:

```
Markdown
   ↓
Markdown Parser
   ↓
Canonical Document AST
   ↓
Normalization + Validation
   ↓
DOCX Renderer
   ↓
WordprocessingML + OMML
   ↓
.docx

```

The rendering process must be deterministic.

No AI model should be required at runtime.

---

# 2. Main Product Requirement

The central product principle is:

> Anything that logically should remain editable in Microsoft Word must remain editable.

Examples:

| MarkdownWord output  |                                  |
| -------------------- | -------------------------------- |
| `# Heading`          | Native Word Heading              |
| Paragraph            | Native Word Paragraph            |
| `**bold**`           | Bold Word Run                    |
| `*italic*`           | Italic Word Run                  |
| Markdown list        | Native Word Numbering            |
| Markdown table       | Native Word Table                |
| `$x^2$`              | Native editable Word Equation    |
| `$$...$$`            | Native editable display equation |
| Code block           | Editable Word text               |
| `[link](url)`        | Native Word Hyperlink            |
| Image                | Embedded Word image              |
| Page break directive | Native Word page break           |

Equations must **not** be inserted as screenshots, PNGs, or SVG images when they can be represented using Word's native equation system.

---

# 3. Problems Being Solved

Existing Markdown → DOCX workflows often suffer from:

1. equations becoming images;
2. malformed mathematics;
3. Markdown syntax appearing in the Word document;
4. incorrect nested lists;
5. lists becoming plain text rather than native Word lists;
6. badly formatted tables;
7. tables splitting incorrectly between pages;
8. table headers not repeating;
9. headings becoming separated from following paragraphs;
10. images overflowing page margins;
11. poor code-block formatting;
12. inconsistent spacing;
13. broken Unicode;
14. formatting being hard-coded rather than style-based;
15. inability to edit generated content naturally in Word;
16. poor conversion of ChatGPT/Claude/Gemini Markdown.

This library should solve those problems through a proper document architecture rather than a sequence of regex replacements.

---

# 4. Goals

## G1 — Native Word Structure

Generate genuine WordprocessingML structures instead of approximating them visually.

---

## G2 — Editable Mathematics

Markdown mathematics should become Word Office Math equations.

For example:

```
$$
x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}
$$

```

must produce a Word equation that can later be edited using Microsoft's Equation Editor.

Microsoft Word stores native equations using Office Math Markup Language, or **OMML**. Microsoft 365 supports MathML and LaTeX interoperability with its Office Math system.

---

## G3 — Correct Word Pagination

The renderer must use Word's native pagination controls instead of trying to manually estimate fixed PDF-like pages.

Important controls include:

```
keep_with_next
keep_together
page_break_before
widow_control
section breaks

```

---

## G4 — Native Tables

Markdown tables must become editable Word tables.

They must support:

- wrapping;
- alignment;
- column sizing;
- borders;
- header styling;
- repeated header rows;
- sensible page splitting.

---

## G5 — Correct Lists

Lists must become real Word numbering structures.

Do not render:

```
1. First
2. Second

```

as manually numbered plain text.

---

## G6 — Clean Architecture

Parsing must be independent from DOCX rendering.

No `python-docx` object should exist inside the parser or canonical AST.

---

## G7 — AI Conversation Compatibility

The renderer should handle Markdown commonly produced by:

- ChatGPT;
- Claude;
- Gemini;
- GitHub-style Markdown;
- ordinary Markdown files.

---

# 5. Non-Goals

The initial project will not:

- render PDF;
- execute Markdown code blocks;
- execute arbitrary LaTeX;
- create a complete HTML/CSS rendering engine;
- exactly reproduce ChatGPT's UI appearance;
- exactly reproduce GitHub CSS;
- provide pixel-identical pagination across every version of Microsoft Word;
- implement a complete TeX engine;
- implement a complete Microsoft Word clone;
- support arbitrary embedded HTML in Phase 1.

DOCX is a reflowable document format.

Therefore the target is **semantically correct pagination**, not pixel-identical pagination.

---

# 6. Recommended Technology Stack

Minimum:

```
Python >= 3.11
markdown-it-py
python-docx
lxml
latex2mathml
pytest
Ruff
mypy or Pyright

```

Optional:

```
Pygments
Pillow

```

### `python-docx`

Use for:

- document creation;
- paragraphs;
- runs;
- sections;
- styles;
- tables;
- images;
- basic pagination controls;
- document metadata.

### Direct OOXML manipulation

Use where `python-docx` does not expose enough functionality.

Examples:

- OMML;
- advanced numbering;
- repeated table headers;
- advanced table properties;
- some field codes;
- bookmarks;
- TOC fields;
- custom XML properties.

### `latex2mathml`

Use as the initial LaTeX → Presentation MathML converter.

As of April 2026 the current release is 3.81.0 and requires Python 3.10+.

---

# 7. High-Level Architecture

```
                         Markdown Input
                               │
                               ▼
                        Input Loader
                               │
                               ▼
                       Markdown Parser
                               │
                               ▼
                     Canonical Document AST
                               │
                               ▼
                    Compatibility Normalizer
                               │
                               ▼
                         Validator
                               │
                               ▼
                         DOCX Renderer
                               │
       ┌───────────────────────┼──────────────────────────┐
       │                       │                          │
       ▼                       ▼                          ▼
 Text Renderer           Equation Renderer          Table Renderer
       │                       │                          │
       │                    LaTeX                         │
       │                       ↓                          │
       │                    MathML                        │
       │                       ↓                          │
       │                     OMML                         │
       │                       │                          │
       └───────────────────────┼──────────────────────────┘
                               │
                 WordprocessingML Package
                               │
                               ▼
                            .docx

```

Supporting systems:

```
Style Engine
Numbering Engine
Resource Manager
Image Renderer
Code Renderer
Pagination Policy
Diagnostics Engine
Template Manager
Document Metadata

```

---

# 8. Canonical Document AST

The AST is the stable boundary between Markdown and Word.

Example:

```
Document(
    children=[
        Heading(
            level=1,
            children=[
                Text("Research Report")
            ]
        ),

        Paragraph(
            children=[
                Text("This is "),
                Strong([
                    Text("important")
                ]),
                Text(".")
            ]
        ),

        MathBlock(
            source=r"\frac{x}{y}",
            format="latex"
        )
    ]
)

```

## Required block nodes

```
Document
Heading
Paragraph
BlockQuote
BulletList
OrderedList
ListItem
CodeBlock
MathBlock
Table
TableRow
TableCell
ImageBlock
HorizontalRule
PageBreak
SectionBreak

```

## Required inline nodes

```
Text
Strong
Emphasis
Strikethrough
InlineCode
Link
InlineMath
SoftBreak
HardBreak

```

## AST Rules

**AST-01**

The AST cannot contain `python-docx` objects.

**AST-02**

Every node should retain source-location metadata where possible:

```
SourcePosition(
    file="report.md",
    line=85,
    column=4
)

```

**AST-03**

Math nodes preserve original mathematical source.

**AST-04**

Code nodes preserve their language identifier.

**AST-05**

Image nodes preserve:

```
source
alt
title

```

**AST-06**

Table cells may contain inline AST nodes rather than plain strings.

---

# 9. Markdown Parsing

Recommended pipeline:

```
Markdown
   ↓
markdown-it-py
   ↓
Token Stream
   ↓
ASTBuilder
   ↓
Canonical AST

```

Phase 1 syntax must include:

- headings;
- paragraphs;
- strong;
- emphasis;
- strikethrough;
- inline code;
- fenced code;
- links;
- blockquotes;
- horizontal rules;
- unordered lists;
- ordered lists;
- nested lists;
- tables;
- images;
- inline equations;
- block equations.

---

# 10. Compatibility Normalizer

Markdown produced by different AI systems may vary slightly.

Support common math forms:

```
$x+y$

```

```
$$
x+y
$$

```

```
\(x+y\)

```

```
\[
x+y
\]

```

Normalize these into:

```
InlineMath(...)

```

or:

```
MathBlock(...)

```

The compatibility layer should also normalize:

- line endings;
- list indentation;
- Markdown table alignment;
- excessive blank lines;
- heading IDs;
- task-list markers;
- escaped Markdown characters.

Do not place ChatGPT-specific or Claude-specific logic inside the Word renderer.

---

# 11. DOCX Renderer

Define a rendering interface:

```
class DocxRenderer:

    def render(
        self,
        document: Document,
        config: RenderConfig
    ) -> bytes:
        ...

```

Node dispatch:

```
Heading
   → HeadingRenderer

Paragraph
   → ParagraphRenderer

Table
   → TableRenderer

MathBlock
   → EquationRenderer

ImageBlock
   → ImageRenderer

CodeBlock
   → CodeRenderer

```

The top-level renderer coordinates Word document construction.

---

# 12. Equation Rendering

Equation rendering is a critical feature.

## Required pipeline

```
Markdown Equation
        ↓
     Math AST
        ↓
       LaTeX
        ↓
Presentation MathML
        ↓
       OMML
        ↓
Native Word Equation

```

Microsoft documents that Word uses Office Math internally and supports Presentation MathML import, including constructs corresponding to fractions, roots, superscripts/subscripts, n-ary operators, accents, and delimiters.

---

# 13. Math Architecture

Create:

```
class MathConverter(Protocol):

    def latex_to_mathml(
        self,
        latex: str
    ) -> str:
        ...

    def mathml_to_omml(
        self,
        mathml: str,
        display: bool
    ) -> OMMLElement:
        ...

```

Do not make equation logic part of the generic DOCX renderer.

Use:

```
EquationRenderer
    ↓
MathConverter
    ↓
OMML

```

---

# 14. MathML → OMML

This layer must become an owned part of the project.

An existing Python `mathml2omml` project exists, but its latest published version dates to November 2019.

Therefore:

> `mathml2omml` must not become an irreplaceable architectural dependency.

It may be used:

- for prototyping;
- for reference;
- for differential tests.

Long term, implement or control an internal converter.

Initial supported constructs should include:

```
identifiers
numbers
operators
fractions
square roots
nth roots
superscripts
subscripts
subscript + superscript
parentheses
brackets
absolute-value delimiters
summation
products
integrals
limits
accents
matrices
aligned equations
Greek symbols
common mathematical symbols

```

---

# 15. Inline vs Display Math

Inline:

```
Einstein's equation is $E=mc^2$.

```

Must remain inside the paragraph.

Conceptually:

```
Word paragraph:

Einstein's equation is [OMML equation].

```

Display:

```
$$
E=mc^2
$$

```

Should become a dedicated centered equation paragraph.

Use the appropriate OMML structures for inline and display-mode mathematics.

---

# 16. Math Error Handling

Do not silently insert broken equations.

Example:

```
ERROR MATH201
Unable to convert LaTeX equation.

Source:
\frac{x{

report.md:82

```

Optional configurable fallback:

```
MathFailurePolicy(
    mode="error"
)

```

Possible modes later:

```
error
plain_text
warning

```

Image fallback must not be the default.

---

# 17. Paragraph Rendering

A Markdown paragraph becomes a native Word paragraph.

Inline AST becomes Word runs.

Example:

```
This is **important** and *interesting*.

```

Should generate:

```
Paragraph
 ├─ Run "This is "
 ├─ Run "important" bold=True
 ├─ Run " and "
 ├─ Run "interesting" italic=True
 └─ Run "."

```

Do not create unnecessary paragraphs for individual runs.

---

# 18. Headings

Markdown:

```
# Heading 1
## Heading 2
### Heading 3

```

Map to native Word styles:

```
Heading 1
Heading 2
Heading 3

```

Default heading pagination:

```
keep_with_next = True
keep_together = True

```

H1 may optionally:

```
page_break_before = True

```

through theme/configuration.

---

# 19. Pagination

DOCX pagination must use semantic Word layout controls.

Do not estimate page height manually except where necessary for resources such as image width.

Default pagination policies:

### PAGE-01

Headings should remain with following content.

### PAGE-02

Paragraph widow/orphan protection enabled.

### PAGE-03

Short code blocks should remain together.

### PAGE-04

Display equations should remain together.

### PAGE-05

Images should remain with captions where possible.

### PAGE-06

Small table rows should not split unnecessarily.

### PAGE-07

Long table rows may split if preventing splitting would create unusable layout.

### PAGE-08

Manual Markdown page breaks should become genuine Word page breaks.

---

# 20. Lists

Lists must use native Word numbering.

Example:

```
1. First
2. Second
   - Alpha
   - Beta
3. Third

```

Internally:

```
OrderedList level 0
 ├── Item
 ├── Item
 │    └── BulletList level 1
 │         ├── Item
 │         └── Item
 └── Item

```

The Word renderer must create proper numbering definitions.

Requirements:

- bullets;
- decimal numbering;
- nested numbering;
- proper indentation;
- restart support;
- list continuation;
- paragraph content inside list items.

Never prefix list paragraphs manually with `"1."` or `"•"`.

---

# 21. Tables

Markdown tables must become native editable Word tables.

Example:

```
| Model | Score |
|---|---:|
| A | 94 |
| B | 91 |

```

Must become:

```
Word Table
 ├── Header Row
 ├── Row
 └── Row

```

## Table requirements

Support:

- header rows;
- alignment;
- text wrapping;
- bold header formatting;
- borders;
- padding;
- background shading;
- column width calculation;
- inline formatting in cells;
- links in cells;
- inline equations in cells;
- multiple-page tables.

---

# 22. Table Width Algorithm

Available width:

```
page width
-
left margin
-
right margin
=
usable width

```

Determine preferred column widths based on:

```
content
minimum width
maximum width
alignment
table width

```

Do not let the table silently extend beyond page margins.

Potential strategy:

```
Measure columns
      ↓
Fits?
 ┌────┴────┐
Yes       No
 │          │
Use     Compress
           ↓
       Still too wide?
        ┌────┴────┐
       No        Yes
       │           │
      Use      Wrap cells

```

Phase 3 may add automatic landscape sections.

---

# 23. Table Pagination

The renderer should support:

```
repeat header
avoid splitting short rows
allow splitting large rows

```

Example:

```
PAGE 1

| Name | Result |
|------|--------|
| ...  | ...    |
| ...  | ...    |

PAGE 2

| Name | Result |  ← repeated header
|------|--------|
| ...  | ...    |

```

Use low-level WordprocessingML where required.

---

# 24. Images

Support initially:

```
PNG
JPEG

```

Later:

```
SVG
WebP conversion

```

Input:

```
![Architecture](./images/system.png)

```

Resource resolution:

```
Markdown directory
       ↓
Resolve relative path
       ↓
Validate
       ↓
Read image
       ↓
Calculate usable width
       ↓
Scale if necessary
       ↓
Insert

```

Images must preserve aspect ratio.

Never silently clip an oversized image.

---

# 25. Remote Resources

Default:

```
allow_remote_resources = False

```

If enabled:

```
ResourcePolicy(
    allow_remote_resources=True,
    allowed_schemes=["https"],
    max_download_size=10_000_000
)

```

Additional protections:

- timeout;
- MIME validation;
- size limits;
- redirect limits;
- optional domain restrictions.

---

# 26. Code Blocks

Markdown:

````
```python
def hello():
    print("Hello")
```

````

Word result must remain editable.

Default formatting:

```
monospace font
smaller font
background shading
paragraph spacing
code indentation
line preservation

```

Do not use screenshots.

Pygments may optionally supply syntax-highlight tokens.

Code execution is strictly prohibited.

---

# 27. Blockquotes

Markdown:

```
> Important note.

```

Word result:

- native paragraph;
- quote style;
- left indentation;
- optional border;
- configurable background;
- keep-together when small.

---

# 28. Hyperlinks

Links must become actual Word hyperlinks.

Input:

```
[OpenAI](https://openai.com)

```

Output must be clickable and editable.

Do not render:

```
OpenAI (https://openai.com)

```

unless configuration explicitly requests visible URLs.

---

# 29. Horizontal Rules

Markdown:

```
---

```

should become a Word-compatible visual separator.

Implementation may use:

- paragraph border;
- dedicated separator style.

Avoid using a typed string of underscore/hyphen characters.

---

# 30. Styles System

Styling must use Word styles wherever practical.

Create styles such as:

```
MD Normal
MD Heading 1
MD Heading 2
MD Heading 3
MD Quote
MD Code
MD Caption
MD Table
MD Equation

```

Benefits:

- users can modify styles later;
- generated documents remain maintainable;
- formatting becomes consistent;
- themes become easy to implement.

---

# 31. Theme Model

Example:

```
DocumentTheme(
    page=PageStyle(
        size="A4",
        margin_top=20,
        margin_bottom=20,
        margin_left=22,
        margin_right=22,
    ),

    normal=ParagraphStyle(
        font="Aptos",
        font_size=11,
        line_spacing=1.15,
    ),

    heading1=HeadingStyle(
        font_size=20,
        keep_with_next=True
    ),

    code=CodeStyle(
        font="Consolas",
        font_size=9
    )
)

```

Built-in themes:

Phase 1:

```
default

```

Phase 3:

```
academic
modern
minimal

```

---

# 32. Word Templates

Later allow users to supply:

```
template.docx

```

The renderer should be capable of using existing:

- fonts;
- styles;
- page sizes;
- headers;
- footers;
- branding.

API:

```
render(
    "report.md",
    "report.docx",
    template="corporate-template.docx"
)

```

---

# 33. Page Setup

Support:

```
A4
Letter

```

Later:

```
Legal
custom

```

Configuration:

```
PageConfig(
    size="A4",
    orientation="portrait",
    margins=Margins(
        top=20,
        bottom=20,
        left=22,
        right=22
    )
)

```

---

# 34. Headers and Footers

Phase 2 should support:

```
document title
author
custom text
page number
section title

```

Example:

```
FooterConfig(
    page_number=True
)

```

Page number must be a Word field rather than static text.

---

# 35. Table of Contents

Phase 2:

```
TOCConfig(
    enabled=True,
    min_level=1,
    max_level=3
)

```

Generate native Word TOC field structures where practical.

The document should use proper Word heading styles so Word can rebuild/update the TOC.

---

# 36. Document Metadata

Support:

```
title
author
subject
keywords
comments
created_at

```

Use native DOCX core properties.

---

# 37. YAML Front Matter

Optional Markdown front matter:

```
---
title: AI Research Report
author: Example
page_size: A4
theme: default
toc: true
page_numbers: true
---

# Introduction

```

Front matter may configure rendering.

Explicit API configuration should override front matter when conflicts occur.

---

# 38. Diagnostics

Create a structured diagnostic system.

Every diagnostic contains:

```
Diagnostic(
    severity="warning",
    code="TABLE101",
    message="Table required width exceeds available page width.",
    source_file="report.md",
    line=142
)

```

Categories:

```
PARSE
NORMALIZE
MATH
TABLE
IMAGE
RESOURCE
LIST
DOCX
STYLE
CONFIG
INTERNAL

```

Example:

```
ERROR MATH201

Unsupported mathematical expression.

report.md:87

```

Example:

```
WARNING TABLE102

Table width exceeded page width.
Cell wrapping was applied.

report.md:144

```

---

# 39. Public Python API

Simple:

```
from mddocx import render

render(
    "conversation.md",
    "conversation.docx"
)

```

String:

```
from mddocx import render_string

docx_bytes = render_string("""
# Report

The equation is:

$$
E = mc^2
$$
""")

```

Advanced:

```
from mddocx import MarkdownWord, RenderConfig

converter = MarkdownWord(
    config=RenderConfig(
        theme="default",
        page_size="A4"
    )
)

converter.render_file(
    "input.md",
    "output.docx"
)

```

---

# 40. CLI

Basic:

```
mddocx document.md

```

Explicit output:

```
mddocx document.md -o document.docx

```

Validation only:

```
mddocx document.md --check

```

Theme:

```
mddocx document.md --theme academic

```

Template later:

```
mddocx document.md --template company.docx

```

---

# 41. Repository Structure

Recommended:

```
mddocx/
│
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── IMPLEMENTATION_STATUS.md
│
├── src/
│   └── mddocx/
│       │
│       ├── __init__.py
│       ├── api.py
│       ├── cli.py
│       ├── config.py
│       │
│       ├── parser/
│       │   ├── markdown.py
│       │   ├── builder.py
│       │   └── frontmatter.py
│       │
│       ├── ast/
│       │   ├── base.py
│       │   ├── block.py
│       │   └── inline.py
│       │
│       ├── normalize/
│       │   ├── normalizer.py
│       │   └── compatibility.py
│       │
│       ├── render/
│       │   ├── renderer.py
│       │   ├── paragraphs.py
│       │   ├── headings.py
│       │   ├── lists.py
│       │   ├── tables.py
│       │   ├── images.py
│       │   ├── code.py
│       │   ├── links.py
│       │   └── pagination.py
│       │
│       ├── math/
│       │   ├── converter.py
│       │   ├── latex.py
│       │   ├── mathml.py
│       │   ├── omml.py
│       │   └── mappings.py
│       │
│       ├── ooxml/
│       │   ├── numbering.py
│       │   ├── tables.py
│       │   ├── fields.py
│       │   └── utils.py
│       │
│       ├── styles/
│       │   ├── base.py
│       │   └── default.py
│       │
│       ├── resources/
│       │   ├── resolver.py
│       │   └── images.py
│       │
│       └── diagnostics/
│           ├── codes.py
│           └── reporter.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   ├── fixtures/
│   └── golden/
│
└── examples/

```

---

# 42. Security Requirements

**SEC-01**

Never execute code blocks.

**SEC-02**

Never evaluate generated Python.

**SEC-03**

Never execute arbitrary embedded shell commands.

**SEC-04**

Remote resources disabled by default.

**SEC-05**

Prevent filesystem traversal:

```
../../../etc/passwd

```

**SEC-06**

Validate all resource paths.

**SEC-07**

Set configurable resource size limits.

**SEC-08**

XML parsing must be configured defensively.

**SEC-09**

Temporary files must use isolated temporary directories.

**SEC-10**

Rendering errors must not expose sensitive host paths unnecessarily.

---

# 43. Testing Strategy

Testing must be treated as a product feature.

---

## Unit Tests

Test:

```
Markdown token → AST
AST normalization
inline formatting
list nesting
table conversion
resource resolution
math parsing
LaTeX → MathML
MathML → OMML
Word style creation
numbering definitions
pagination properties
configuration
diagnostics

```

---

# 44. Integration Tests

Pipeline:

```
Markdown
   ↓
Parser
   ↓
AST
   ↓
DOCX Renderer
   ↓
.docx

```

Validate:

- valid ZIP/OOXML package;
- `word/document.xml` exists;
- expected paragraphs exist;
- expected tables exist;
- expected relationships exist;
- equations contain OMML;
- native numbering is present;
- images exist;
- DOCX can be reopened using `python-docx`.

---

# 45. Equation Regression Tests

Create a large equation fixture set.

Categories:

```
basic operators
fractions
roots
powers
subscripts
combined subscripts/superscripts
Greek
integrals
summation
products
limits
matrices
vectors
accents
delimiters
piecewise expressions
aligned equations
nested fractions
nested roots
long equations
inline equations
display equations

```

Examples:

```
x^2

```

```
\frac{x}{y}

```

```
\sqrt{x}

```

```
\sum_{i=1}^{n} i

```

```
\int_0^\infty e^{-x}\,dx

```

```
\begin{bmatrix}
a & b \\
c & d
\end{bmatrix}

```

Every supported fixture must generate native OMML rather than an image.

---

# 46. Table Regression Tests

Test:

```
2-column table
10-column table
long text cells
empty cells
formatted text
links
inline equations
long tables
repeated headers
large rows
nested lists inside cells if supported
very wide tables

```

---

# 47. List Regression Tests

Test:

```
simple bullets
simple numbering
nested bullets
nested numbering
mixed lists
3+ nesting levels
continuation
paragraphs inside items
inline equations
code inside list item

```

---

# 48. Pagination Regression Tests

Create fixtures specifically designed to detect:

```
orphan headings
widows
short tables at page boundary
long tables
display equations near page boundary
code blocks near page boundary
images near page boundary
manual page breaks
section breaks

```

---

# 49. Golden DOCX Testing

Maintain reference documents:

```
basic.docx
lists.docx
tables.docx
math.docx
code.docx
images.docx
pagination.docx
ai-conversation.docx
stress.docx

```

For deterministic XML portions, normalize volatile properties before comparison.

Do not rely solely on binary DOCX equality because DOCX packages may contain changing metadata.

---

# 50. Visual QA

Automated XML tests are not sufficient for Word rendering.

For every major layout change:

```
Generate DOCX
      ↓
Open/render document using available Word-compatible environment
      ↓
Inspect pages
      ↓
Compare against expected layout

```

Check:

- overlapping;
- clipping;
- malformed equations;
- broken tables;
- broken numbering;
- excessive spacing;
- image overflow;
- orphaned headings.

---

# 51. AI Coding-Agent Development Loop

After implementing every meaningful feature, the coding agent must:

```
1. Format source.
2. Run linting.
3. Run type checking.
4. Run feature-specific unit tests.
5. Run complete test suite.
6. Generate relevant DOCX fixtures.
7. Inspect DOCX package structure.
8. Verify editable OMML for equation changes.
9. Perform visual regression checks where applicable.
10. Search for dead code.
11. Search for duplicated implementation.
12. Update IMPLEMENTATION_STATUS.md.

```

A feature is not complete merely because the code runs.

---

# 52. Technical Debt Rules

Do not allow:

- renderer-specific classes inside AST;
- duplicate list implementations;
- duplicate table implementations;
- regex-only Markdown parsing;
- giant renderer functions;
- hard-coded Word XML scattered everywhere;
- XML namespaces duplicated throughout modules;
- unexplained numeric style values;
- silent exception handling;
- commented-out obsolete code;
- abandoned experimental implementations;
- permanent dependence on unmaintained equation libraries;
- business logic inside CLI commands.

Centralize OOXML helpers.

Example:

```
ooxml/
    namespaces.py
    elements.py
    numbering.py
    tables.py

```

---

# 53. PHASE 1 — Core Markdown → Word

## Objective

Build a clean, production-capable foundation.

### Implement

- package/repository;
- parser;
- canonical AST;
- normalization;
- `.docx` renderer;
- paragraph rendering;
- H1–H6;
- bold;
- italic;
- strikethrough;
- inline code;
- code blocks;
- hyperlinks;
- blockquotes;
- horizontal rules;
- basic images;
- simple tables;
- unordered lists;
- ordered lists;
- nested lists;
- default Word styles;
- page setup;
- basic pagination controls;
- manual page breaks;
- diagnostic system;
- CLI;
- Python API.

### Equation requirement

Implement the complete equation architecture:

```
Math AST
MathConverter
OMML insertion

```

At minimum, support:

```
simple inline expressions
powers
subscripts
fractions
square roots
basic Greek symbols

```

The architecture must already support later expansion without changing public APIs.

### Phase 1 acceptance

A typical AI-generated Markdown conversation must convert successfully when it contains:

```
headings
paragraphs
lists
nested lists
tables
links
code
images
basic equations

```

Generated Word content must remain editable.

---

# 54. PHASE 2 — Advanced Equations + Tables + Word Layout

## Objective

Solve the difficult correctness problems.

### Mathematics

Expand OMML support to:

```
nested fractions
nth roots
limits
integrals
summations
products
matrices
delimiters
accents
vectors
aligned equations
piecewise equations
complex subscripts/superscripts

```

Build comprehensive equation regression tests.

### Tables

Implement:

- repeated headers;
- robust width calculations;
- large-row splitting;
- short-row keep-together;
- inline math;
- links;
- configurable styling.

### Pagination

Implement:

- heading protection;
- widow/orphan controls;
- equation protection;
- table row policy;
- image/caption grouping;
- code-block pagination;
- section breaks.

### Word features

Implement:

- headers;
- footers;
- page-number fields;
- TOC;
- bookmarks;
- document metadata;
- YAML front matter.

### Phase 2 acceptance

A 20–50 page technical Markdown document containing:

```
complex mathematics
multiple tables
nested lists
code
images
multiple headings

```

must render into a professionally editable Word document without major structural failures.

---

# 55. PHASE 3 — Production Hardening

## Objective

Turn the renderer into a mature reusable library.

### Implement

- custom `.docx` templates;
- multiple themes;
- custom fonts;
- font fallback;
- broader Unicode;
- RTL architecture where feasible;
- SVG;
- advanced image handling;
- optional remote resources;
- advanced table sizing;
- optional landscape table sections;
- custom AST nodes;
- extension/plugin API;
- JSON diagnostics;
- performance profiling;
- caching;
- memory profiling;
- compatibility matrix;
- public documentation;
- examples;
- semantic versioning;
- stable public API.

---

# 56. AI Markdown Compatibility Test Suite

Maintain real-world style fixtures based on common output patterns.

```
chatgpt-basic.md
chatgpt-math.md
chatgpt-table.md
chatgpt-research.md

claude-basic.md
claude-code.md
claude-long.md

gemini-basic.md
gemini-math.md

mixed-markdown.md

```

These fixtures must contain representative syntax patterns but should not depend on any AI service at runtime.

---

# 57. Implementation Status File

Every development session must update:

```
IMPLEMENTATION_STATUS.md

```

Template:

```
# Implementation Status

Current Phase:

## Completed

## In Progress

## Remaining

## Tests

Passed:
Failed:
Skipped:

## Known Bugs

## Technical Debt

## Architecture Decisions

## Breaking Changes

## Recommended Next Task

```

A coding agent beginning another session must read this file before modifying the repository.

---

# 58. Definition of Done — Feature

A feature is considered complete only when:

1. implementation exists;
2. architecture boundaries are respected;
3. unit tests exist;
4. relevant integration tests exist;
5. regression fixture exists for rendering behavior;
6. error handling exists;
7. diagnostics are meaningful;
8. documentation exists;
9. full test suite passes;
10. dead code is removed;
11. implementation status is updated.

---

# 59. Definition of Done — Library

The library is production-ready when:

- supported Markdown parses consistently;
- Word output contains native structures;
- equations are editable;
- tables are editable;
- lists use native numbering;
- hyperlinks are genuine hyperlinks;
- images fit within their sections;
- headings paginate correctly;
- major equation classes are supported;
- large tables behave sensibly;
- Word styles are used consistently;
- no AI service is required;
- tests cover real-world AI Markdown;
- public Python API is stable;
- CLI is stable;
- diagnostics are documented;
- security requirements are tested;
- representative documents have been visually inspected.

---

# 60. Most Important Architecture Rules

Always:

```
Markdown
   ↓
Parser
   ↓
Canonical AST
   ↓
Normalizer
   ↓
DOCX Renderer
   ↓
WordprocessingML

```

Never:

```
Markdown
→ regex
→ python-docx

```

Never:

```
Parser
→ python-docx objects

```

Never:

```
Equation
→ PNG
→ DOCX

```

when native Word mathematics is possible.

Use:

```
Equation
→ LaTeX
→ MathML
→ OMML
→ Word

```

Never implement list numbering as manually inserted strings.

Use Word numbering definitions.

Never implement table layouts as tab-separated text.

Use native Word tables.

Never attempt to manually calculate all page positions as if DOCX were PDF.

Use Word pagination semantics.

---

# 61. Priority Order

If tradeoffs become necessary, implementation priority is:

```
1. Structural correctness
2. Editable equations
3. Native lists
4. Native tables
5. Pagination quality
6. Content preservation
7. Error handling
8. Compatibility
9. Styling
10. Advanced features

```

Visual beauty must never come at the cost of destroying document editability.

---

# 62. Final Product Principle

The project should not be considered:

> "Markdown formatted and placed inside a Word file."

It should be considered:

> **A deterministic Markdown-to-Word document compiler that converts Markdown semantics into native Microsoft Word structures.**

The fundamental compilation model is:

```
Markdown semantics

Heading
Paragraph
List
Table
Equation
Image
Code
Link

          ↓

Canonical AST

          ↓

Word semantics

Word Heading
Word Paragraph
Word Numbering
Word Table
OMML Equation
DrawingML Image
Formatted Runs
Word Hyperlink

          ↓

Professional Editable DOCX

```

That architectural principle should guide every implementation decision.