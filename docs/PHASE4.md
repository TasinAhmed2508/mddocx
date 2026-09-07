# Phase 4 — Operational Maturity

Phase 4 is a post-PRD maturity release. The original PRD defines Phases 1–3; this release keeps the
same compiler architecture and stable public rendering APIs while hardening repeatable production use.

## Reproducible DOCX packages

`ReproducibilityConfig(enabled=True)` is the default. Generated DOCX ZIP entries are emitted in stable
lexicographic order with a fixed ZIP timestamp. This removes packaging-time volatility while preserving
Word content and user-supplied core document metadata.

Disable only when inspecting raw host/package timestamps:

```python
from mddocx import RenderConfig, ReproducibilityConfig

config = RenderConfig(reproducibility=ReproducibilityConfig(enabled=False))
```

## Output package validation

Generated packages are structurally validated by default. Validation checks:

- DOCX ZIP integrity;
- required OOXML package parts;
- unsafe package paths;
- maximum package-part count;
- maximum XML-part size;
- defensive parsing of every XML and relationship part.

Use `validate_docx_package(blob, ValidationConfig())` to validate bytes independently.

## Compilation limits

`CompilationLimits` prevents pathological inputs from consuming unbounded resources:

```python
from mddocx import CompilationLimits, RenderConfig

config = RenderConfig(
    limits=CompilationLimits(
        max_input_bytes=20_000_000,
        max_ast_nodes=100_000,
        max_nesting_depth=64,
        max_table_cells=100_000,
        max_images=5_000,
        max_equations=10_000,
    )
)
```

Limits apply to normal Markdown compilation and custom AST rendering.

## Persistent normalized-AST cache

The cache is opt-in and uses project-owned JSON rather than pickle.

```python
from pathlib import Path
from mddocx import CacheConfig, RenderConfig

config = RenderConfig(
    cache=CacheConfig(ast_enabled=True, directory=Path(".mddocx-cache"))
)
```

The cache key includes the Markdown source and source-file identity. AST caching is automatically disabled
when extensions are active because extension parser/transform semantics can change independently of source.

## Explicit plugin discovery

Third-party plugins can publish Python entry points in the `mddocx.extensions` group. Installed plugins are
never imported merely because they exist. Only explicitly named plugins are loaded:

```python
from mddocx import PluginConfig, RenderConfig

config = RenderConfig(plugins=PluginConfig(names=("my-company-markdown",)))
```

CLI equivalent:

```text
mddocx report.md --plugin my-company-markdown
```

## Batch conversion

```python
from mddocx import render_many

results = render_many(["reports/"], "word-output/", recursive=True)
```

CLI:

```text
mddocx reports/ --recursive --output-dir word-output/
```

Inputs are processed in a deterministic path order. Duplicate output basenames receive a stable path-derived
suffix instead of overwriting another document.

## SARIF diagnostics

In addition to the existing JSON diagnostics, `DiagnosticReporter.to_sarif()` and
`MarkdownWord.diagnostics_sarif()` produce SARIF 2.1.0 for CI/code-scanning ingestion.

```text
mddocx report.md --diagnostics-sarif diagnostics.sarif
```

## Profiling additions

`RenderStats` now includes:

- `output_sha256` for artifact identity;
- `ast_cache_hit` for cache observability;
- existing parse/normalize/render/total timings;
- output bytes and optional peak traced memory.

## Security posture

Phase 4 retains all Phase 3 resource protections and adds compiler/package limits. Persistent AST cache files
are JSON only and are never executed. Plugin entry points are an explicit trust boundary: a plugin is imported
only when the caller explicitly names it.
