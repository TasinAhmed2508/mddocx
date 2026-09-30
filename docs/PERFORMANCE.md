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
