# Phase 6 — Word Professional Features (v0.7.0)

Phase 6 builds higher-level Word authoring features on top of the Phase 5B semantic reference layer while preserving the core invariant: content that should remain editable in Word remains editable.

## Native heading numbering

Enable native multilevel Word numbering for H1–H6 (up to a configurable depth):

```python
from mddocx import HeadingNumberingConfig, RenderConfig

config = RenderConfig(
    heading_numbering=HeadingNumberingConfig(enabled=True, max_level=3)
)
```

CLI:

```bash
mddocx report.md --heading-numbering --heading-numbering-depth 3
```

Heading text is not prefixed manually; Word numbering definitions are used.

## Section-scoped captions and equations

```python
from mddocx import ReferenceConfig, RenderConfig

config = RenderConfig(
    references=ReferenceConfig(
        equation_number_format="section",
        caption_number_format="section",
    )
)
```

This produces numbering such as `Equation 2.1`, `Table 2.1`, and `Listing 2.1`, with native field-backed cross-references.

## Title page, abstract, and keywords

Front matter:

```yaml
---
title: Research Report
subtitle: Experimental Edition
organization: Example Lab
author: Ada Example
title_page: true
abstract: A concise summary of the work.
keywords:
  - Markdown
  - DOCX
  - OMML
---
```

Python configuration is available through `TitlePageConfig` and `AbstractConfig`.

## Header/footer field templates

Headers and footers can contain a bounded set of Word fields:

```text
{PAGE}
{NUMPAGES}
{DATE}
{CREATEDATE}
{SAVEDATE}
{AUTHOR}
{TITLE}
{SUBJECT}
{SECTION}
{SECTIONPAGES}
{FILENAME}
{DOCPROPERTY:Property Name}
```

Example:

```bash
mddocx report.md \
  --header "{TITLE} — {AUTHOR}" \
  --footer "Confidential" \
  --page-x-of-y
```

First-page and even-page variants are also supported.

## Callouts / admonitions

GitHub-style alerts:

```markdown
> [!NOTE]
> This remains editable Word text.
```

Container syntax:

```markdown
::: warning Compatibility boundary
This is a bounded, semantic callout.
:::
```

Supported kinds: `note`, `tip`, `important`, `warning`, `caution`, and `example`.

## Editable syntax-highlighted code

Pygments tokenization is used only for formatting; code is never executed.

```markdown
```python {#lst-build caption="Build function" linenos=true highlight="3-4" label=true}
def build():
    ...
```
```

Code remains normal Word runs. Per-block attributes can override global line-number/language-label settings.

## Central Markdown attributes

The project now owns a reusable attribute parser supporting:

```markdown
{#identifier .class key=value flag=true}
```

It is shared by headings, figures, equations, tables, and fenced code rather than reimplementing ad-hoc key parsing per feature.

## Native Word comments

CriticMarkup comment syntax is supported:

```markdown
This claim{>>Please verify this sentence before publication.<<} needs review.
```

The visible document does not contain the comment text. It is emitted as a native Word comment in `word/comments.xml` with a real comment reference in the document body.

Comments do not execute or evaluate their contents.

## Template inspection

```bash
mddocx template inspect corporate.docx
mddocx template inspect corporate.docx --json
```

Reports page size, margins, style counts/custom styles, headers/footers, and core title/author metadata.

## Stronger DOCX validation

`mddocx inspect` and generated-output validation now additionally detect:

- dangling internal hyperlinks;
- REF fields targeting missing bookmarks;
- duplicate bookmark names;
- inconsistent native Word comment references/definitions.

## Security

Phase 6 does not change the security model:

- code blocks are tokenized for highlighting but never executed;
- comments are inert text metadata;
- field templates use a fixed allowlist rather than arbitrary Word field instructions from Markdown;
- callout containers recognize only a bounded set of semantic kinds;
- existing resource/path/XML/network limits remain active.
