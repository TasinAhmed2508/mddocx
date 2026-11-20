# Performance gate

`mddocx benchmark` renders a deterministic synthetic technical document containing headings, paragraphs, lists, equations, links, and tables, then runs structural inspection.

```bash
mddocx benchmark --sections 100 --max-seconds 15 --max-peak-mb 512
```

The command exits non-zero if the configured time, traced Python-memory, or structural gate fails. CI should use thresholds appropriate to its runner and track results over time rather than interpreting one workstation result as a universal benchmark.

CI measures small (1 section), medium (20 sections), and large (100 sections) documents. The small
and medium corpora keep a 30-second/512-MiB ceiling on every runner. The large corpus uses a
30-second budget on Linux and a 60-second budget on macOS and Windows, because the hosted macOS
and Windows runners are substantially slower: on 2026-09-30 the large corpus measured 33.7 seconds
on macOS and 44.7 seconds on Windows while Linux stayed inside the 30-second budget. The 512-MiB
memory ceiling is enforced everywhere.

Script classification is ASCII-fast-pathed. `is_rtl_text`, `has_cjk`, and `has_complex_script`
return after a single C-level scan when the text is ASCII, so per-run script detection costs the
same order of magnitude as a simple length check for Latin-only documents.

A Windows Python 3.11 qualification run on 2026-09-09 measured the small corpus at 0.366 seconds
and 2.8 MiB peak traced memory, and the large corpus at 8.949 seconds and 4.3 MiB. These values
are an observed stabilization baseline, not a promise for every machine; the CI ceilings are the
enforced release budget.

## Roadmap integration baseline

Measured on Windows with Python 3.11.15 and Node 26.13.0 on the same environment. Each
elapsed figure is the median of five runs. Peak memory comes from a separate run with
Python allocation tracing. Use `scripts/roadmap_benchmark.py --runs 5` with `PYTHONPATH`
pointing at each checkout's `src` directory to reproduce the measurements.

| Workload | 1.4.3 median | Ordered OOXML integration | Peak Python memory, 1.4.3 to integration | DOCX bytes, 1.4.3 to integration | Math engines observed |
| --- | ---: | ---: | ---: | ---: | --- |
| 20 mixed sections | 2.972 s | 2.961 s | 3,154,001 to 3,148,368 | 38,906 to 38,899 | MathJax, mddocx-basic |
| 60 × 24 table | 1.406 s | 1.537 s | 3,528,195 to 3,518,823 | 40,978 to 40,982 | — |
| 20 distinct equations | 1.331 s | 1.395 s | 2,926,271 to 2,926,722 | 35,143 to 35,144 | MathJax, mddocx-basic |
| 40 repeated equations | 0.189 s | 0.208 s | 2,921,530 to 2,919,442 | 35,163 to 35,164 | MathJax |
| 61-node Mermaid flowchart | 0.386 s | 0.414 s | 3,516,572 to 3,514,210 | 193,047 to 193,048 | — |
| Project with eight includes | 0.139 s | 0.147 s | 2,935,550 to 2,934,329 | 35,148 to 35,149 | — |

The seven normalized corpus snapshots match 1.4.3. Package hashes differ after ordered
OOXML emission changes the arrangement of properties. The corpus records text, native
structures, fields, and relationships independently of package bytes.

Five alternating pairs on the integration branch measured MathJax batching at **1.3733 s
to 0.2013 s** for distinct equations and **3.0194 s to 0.5481 s** for the mixed report.
Output was byte-identical with batching enabled and disabled. The shared ZIP finalization
prototype measured **0.1429 s to 0.1348 s** for a document with a native note and four
charts. It stayed below the 10% adoption threshold and was removed.

## Release candidate table rendering

In five alternating pairs on Windows, using Python 3.12.10 and Node 26.13.0,
resolving the paragraph style once per table reduced the median conversion time for
the 60 × 24 table from **1.5094 s to 0.7709 s** (49%). The mixed workload went from
**0.5378 s to 0.4916 s**. Each workload produced identical DOCX bytes in all ten runs.
The measurements compare the change against commit `52938bc` using a fresh Python
process per run and exclude interpreter startup from the timed conversion.

## Large equation batches

Five paired runs on Windows with Python 3.12 and the same Node.js runtime
compared the current candidate with released commit `5198533`. The workload
contains 160 distinct inline equations from `x^{0}+1` through `x^{159}+1`.
Chunking the requests reduced median compilation time from **11.6446 s to
0.5427 s**. The 20-section mixed report measured **0.5164 s and 0.5143 s**,
respectively. Each workload produced byte-identical DOCX files across all runs.

For 600 distinct fractions with `latex2mathml` on the same Python version,
removing the redundant OMML cache reduced retained Python allocations from
366,536 to 120,489 bytes under `tracemalloc`. The combined OMML SHA-256 matched
commit `889a360`. This measurement covers Python allocations in the converter.

## Chemistry equations

On Windows with Python 3.12, five alternating pairs of strict conversions rendered
40 distinct reactions of the form `\ce{n H2 + O2 -> n H2O}` for `n` from 1 to 40.
Grouping the reactions into one bundled MathJax request reduced median conversion
time from **3.560 s to 0.316 s**. Both modes produced byte-identical DOCX files.

The 20-section mixed report measured **0.586 s to 0.573 s** across five alternating
pairs, comparing commit `e32a386` with the chemistry changes. All outputs matched byte
for byte.

## Imported tables

Five alternating pairs on Windows with Python 3.12 parsed the same CSV of 8,000 rows
and 32 columns. Each run averaged 12 parses. Compared with commit `82e93e8`, median
parser CPU time per parse fell from **0.0573 s to 0.0404 s**. Peak traced Python
memory per parse fell from **20.73 MiB to 15.79 MiB**. The parsed datasets matched.

Microsoft Word laid out an 84-row, eight-column survey in **seven pages with compact
Report-theme cells**, down from nine pages with body paragraph spacing. Both exports
contain all 84 record IDs exactly once, with repeated table headers and portrait
pages before and after the landscape section.

## Repeated Python-only alignments

On Windows with Python 3.12 and Node.js disabled, five alternating pairs of
strict conversions generated documents with 160 occurrences of the same
two-pair alignment containing a nested matrix and a fraction. The median
conversion CPU time was **0.484 s with the math cache disabled** and **0.281 s
with it enabled**. All ten DOCX files were byte-identical.

## Paragraph style lookup

Five alternating pairs on Windows with Python 3.12.11 compared the style cache against
commit `56e5e85`, timing `Compiler().compile_string(source)` in a fresh process per run.
The table and mixed report use the existing roadmap workloads. The heading stress test
joins 2,000 blocks of `f"## Checkpoint {i}\n\nOne short result."` with blank lines.

| Workload | Before | After | DOCX bytes |
| --- | ---: | ---: | ---: |
| 2,000 headings and paragraphs | 4.905 s | 1.972 s | 60,987 |
| 20 mixed sections | 0.571 s | 0.493 s | 38,895 |
| 60 × 24 table | 0.807 s | 0.791 s | 40,982 |

All ten DOCX files for each workload had the same SHA-256 hash.

## Math preflight

Five alternating pairs on Windows with Python 3.12.11 and bundled MathJax compared
`inspect_math` against commit `fefb31a`. Each process inspected a Markdown document
containing 80 distinct inline equations from `x^{0}+1` through `x^{79}+1`. The median
time decreased from **5.672 s to 0.201 s**. The JSON report matched byte for byte.
The 20-section mixed conversion measured **0.497 s to 0.491 s**, with identical
DOCX bytes across the ten runs.
