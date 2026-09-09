# Staged v2 migration guide

The v2 work is additive during stabilization. Existing `render()`, `render_string()`, and
`MarkdownWord` calls remain supported by public API version 1. No v1 public name is deprecated in
the current release.

## Entry-point mapping

| Existing v1 workflow | Staged v2 service |
|---|---|
| `render(input, output, config)` | `Compiler(config).compile_file(input, output)` |
| `render_string(markdown, config)` | `Compiler(config).compile_string(markdown)` |
| `MarkdownWord.check_file(path)` | `Compiler(config).check_file(path)` |
| direct `MarkdownParser.parse(...)` use | `Compiler(config).parse_string(...)` |
| direct normalizer use | `Compiler(config).normalize(document)` |
| no v1 equivalent | `Compiler(config).plan(document)` |
| `MarkdownWord.render_ast(document)` | `Compiler(config).render(document)` |

`CompilationResult` carries DOCX bytes, diagnostics, stage statistics, an optional output path,
and the layout plan used for the render. `DocumentStageResult` and `LayoutStageResult` expose
intermediate artifacts without writing files.

## Configuration precedence

The effective order is:

1. library defaults;
2. project manifest values;
3. document front matter;
4. explicit library caller or CLI values.

Explicit caller configuration continues to override document front matter. Configurations are
deep-copied and validated at compiler boundaries; invalid cross-field values fail with
`CONFIG401` before rendering begins. The current nested configuration dataclasses remain accepted,
so no source migration is required yet.

Template owners can map canonical paragraph styles with `StyleMapConfig`, for example
`{"MD Normal": "Company Body", "MD Heading 1": "Company Heading"}`. Mapped styles must exist in
the template. Missing targets fail with `TEMPLATE401`, or can produce `TEMPLATE201` plus canonical
style fallback when `missing="warning"` is explicitly selected.

## Behavioral corrections

- Unsupported math is preserved as editable source and reported with `MATH201` by default. Use
  strict math mode for fail-fast behavior.
- Unterminated explicit math delimiters are preserved and reported with source-located `MATH101`.
- Unsupported raw HTML is preserved as visible literal text; it is never executed or silently
  discarded.
- Headings without explicit identifiers receive stable normalized identifiers.
- Automatic landscape table decisions are made in an inspectable layout plan before Word objects
  are emitted.

## CLI compatibility and exit codes

Existing command names remain stable. Normal success returns `0`, compilation or usage failures
return `2`, and strict math preflight returns `3` when a fallback or malformed explicit delimiter
is found. `--diagnostics-json` and `math-check --json` remain the machine-readable automation
interfaces.

## Deprecation schedule

There are no active deprecations. A future 2.x release may freeze immutable configuration
snapshots or move advanced extension hooks, but equivalent public protocols and at least one minor
release of warnings must exist before any v1-compatible name is removed.
