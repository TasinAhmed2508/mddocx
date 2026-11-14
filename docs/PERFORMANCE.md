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
