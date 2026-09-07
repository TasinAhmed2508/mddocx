# Performance gate

`mddocx benchmark` renders a deterministic synthetic technical document containing headings, paragraphs, lists, equations, links, and tables, then runs structural inspection.

```bash
mddocx benchmark --sections 100 --max-seconds 15 --max-peak-mb 512
```

The command exits non-zero if the configured time, traced Python-memory, or structural gate fails. CI should use thresholds appropriate to its runner and track results over time rather than interpreting one workstation result as a universal benchmark.
