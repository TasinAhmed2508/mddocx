---
title: Compiler Fidelity Report
author: mddocx regression suite
toc: true
page_numbers: true
heading_numbering: true
auto_bibliography: true
bibliography: references.bib
citation_style: numeric
---

# Introduction {#sec-introduction}

This technical report cites a source [@smith2025] and links to
[Equation @eq-energy], [Table @tbl-results], and [Listing @lst-example].

The inline identity \(E=mc^2\) remains editable.[^native]

[^native]: Native equations use OMML and preserve inline **formatting**.

## Method

> [!NOTE] Compatibility
> Mathematical and document structures should remain native.

- [x] Parse the document
- [ ] Validate the output

$$
\boxed{E=mc^2}
$$ {#eq-energy}

```python {#lst-example caption="Compilation example" linenos=true}
result = compiler.compile_string(markdown)
```

| Model | Native equations | Status |
| --- | ---: | --- |
| mddocx | 2 | Pass |

Table: Regression results {#tbl-results}

```chart {#fig-quality caption="Quality score"}
type: column
title: Conversion quality
categories: [Baseline, Improved]
series:
  - name: Score
    values: [60, 100]
legend: bottom
data_labels: true
```

Compiler
: A deterministic program that maps Markdown to native Word structures.

## Conclusion

Return to [Section @sec-introduction].
