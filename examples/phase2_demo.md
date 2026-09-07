---
title: mddocx Phase 2 Demonstration
author: OpenAI
subject: Native editable Word structures
keywords: markdown, docx, omml, phase2
toc: true
page_numbers: true
header: mddocx Phase 2
footer: Editable native Word output
---

# Advanced Mathematics

Inline math remains editable: $\left(\frac{x+1}{y-1}\right)^2$.

An nth root:

$$
\sqrt[3]{x^2+y^2}
$$

A summation and integral:

$$
\sum_{i=1}^{n} i^2 + \int_0^\infty e^{-x}\,dx
$$

A limit:

$$
\lim_{x\to0}\frac{\sin x}{x}=1
$$

A matrix:

$$
\begin{bmatrix}
a & b \\ c & d
\end{bmatrix}
$$

A piecewise expression:

$$
\begin{cases}
x^2 & x>0 \\ -x & x\le0
\end{cases}
$$

Aligned equations:

$$
\begin{aligned}
a&=b+c \\ d&=e-f
\end{aligned}
$$

Vectors and accents: $\vec{v}+\hat{x}+\bar{y}$.

# Tables and Pagination

| Feature | Native Word behavior | Status |
|---|---|---:|
| Header rows | Repeat across pages | Yes |
| Widths | Constrained to usable page width | Yes |
| Short rows | Avoid split | Yes |
| Long rows | May split when necessary | Yes |
| Inline math | $E=mc^2$ stays editable | Yes |
| Links | [OpenAI](https://openai.com) | Yes |

1. Native numbering
2. Nested content
   - Bullet level
   - Another bullet
3. Continues as Word numbering

```python
def phase_two():
    return "editable code"
```

<!-- sectionbreak -->

# Second Section

This section demonstrates a native Word section break. Headings receive bookmarks, and the
document contains native TOC and PAGE fields.
