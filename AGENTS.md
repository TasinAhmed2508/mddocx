## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- `graphify-out/` is git-ignored, so a fresh clone has no graph. If `graphify-out/graph.json` is
  missing, build it once with `graphify extract . --code-only --no-cluster --out .` (AST-only,
  no API key) before querying.
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## User font preference

Use SutonnyMJ for Bangla text in generated DOCX/PDF documents. Keep Markdown
and the AST in Unicode; apply Bijoy glyph encoding only at the DOCX output
boundary. Preserve English text in a Latin font and visually verify the output.
Do not use Google Drive for this task unless the user requests it again.

For this agreement, omit decorative Markdown horizontal separators (`---`).
Retain the table grid, photo boxes, and signature dotted lines.
