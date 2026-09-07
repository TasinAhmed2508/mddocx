# Executive Summary

mddocx 1.0 freezes the public API while preserving native, editable Word semantics.

> [!NOTE]
> This acceptance document intentionally combines equations, native tables, task controls, cross-references, charts, code, and accessibility metadata.

## Stable API

The public API is machine-readable through `mddocx api --json`. Existing rendering and project entry points remain available in the 1.x series.

- [x] Native Word structures
- [x] Editable OMML equations
- [x] Editable Office charts
- [x] Structural accessibility audit
- [x] Deterministic performance gate

## Native Mathematics

The quadratic formula remains editable:

$$
x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}
$$ {#eq-quadratic}

and a bounded sum is

$$
\sum_{i=1}^{n} i = \frac{n(n+1)}{2}.
$$

# Advanced Native Charts

## Revenue with a secondary value axis

```chart {#fig-revenue caption="Revenue and margin with a secondary value axis"}
type: column
title: Quarterly performance
categories: [Q1, Q2, Q3, Q4]
series:
  - name: Revenue
    values: [100, 120, 135, 150]
  - name: Margin
    values: [20, 24, 30, 32]
secondary_series: [Margin]
secondary_axis:
  title: Margin (%)
  min: 0
  max: 40
  number_format: '0'
legend: bottom
data_labels: true
gridlines: false
style: 10
x_axis:
  title: Quarter
y_axis:
  title: Revenue (USD thousands)
  min: 0
  max: 200
  number_format: '0'
```

See [Figure @fig-revenue]. The chart remains native ChartML and its data stays editable in the embedded workbook.

## Bounded scatter chart

```chart {#fig-scatter caption="Measured response by input"}
type: scatter
title: Response curve
categories: [0, 1, 2, 3, 4, 5]
series:
  - name: Response
    values: [0, 1.2, 2.8, 4.1, 5.0, 5.4]
legend: none
data_labels: true
x_axis:
  title: Input
  min: 0
  max: 5
y_axis:
  title: Response
  min: 0
  max: 6
  number_format: '0.0'
```

# Semantic Tables and References

| Capability | Native Word form | v1 gate |
|---|---|---:|
| Equations | OMML | Pass |
| Charts | ChartML + XLSX | Pass |
| Lists | Word numbering | Pass |
| Tables | Word table | Pass |

## Code remains editable

```python {linenos=true label=true caption="Deterministic render smoke" #lst-smoke}
from mddocx import render
render("input.md", "output.docx")
```

# Package Integrity

The release validator checks required OOXML parts, internal relationships, math structure, bookmarks, comments, drawing IDs, note IDs, and native chart-to-workbook relationships.

## Review note

This sentence is marked for review.{>>Native Word comments remain part of the stable v1 renderer.<<}

# Accessibility and Performance

The accessibility gate checks image/chart alternative text, semantic table headers, heading hierarchy, empty hyperlinks, and document title metadata. The performance gate renders a deterministic technical document and checks elapsed time, traced Python allocation, package structure, and SHA-256 output.

## Final acceptance

A v1 release is accepted only when the historical suite, structural inspection, accessibility gate, performance gate, deterministic rebuild, installed-wheel smoke test, and rendered-page QA all pass.
