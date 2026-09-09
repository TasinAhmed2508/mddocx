# mddocx-native 1.2.2

Version 1.2.2 is the fidelity-first compiler and AI-media compatibility release.

## Highlights

- Converts Base64 `data:image/...;base64,...` images into validated native Word DrawingML.
- Supports common ChatGPT, Claude, Gemini, and MathJax delimiters and produces native OMML.
- Adds native handling for equation tags, check marks, vector arrows, matrices, aligned equations,
  text runs, boxes, fractions, radicals, scripts, and other common AI-generated TeX.
- Introduces the typed staged `Compiler`, semantic index, inspectable layout plan, deterministic
  table-width allocator, source acquisition boundary, validated extension protocols, and style map.
- Adds source-located JSON/SARIF diagnostics with remediation guidance.
- Expands regression, security, Word 365, visual, packaging, and cross-platform CI gates.

## Remote image preference

Validated public HTTPS images are allowed by default in the API and ordinary CLI. On the first
interactive-shell launch, mddocx asks whether to block remote HTTPS images with `RESOURCE201`.
Pressing Enter keeps the default **allow** behavior, and the shell remembers the choice.

Per-render overrides:

```console
mddocx report.md --block-remote-resources
mddocx report.md --allow-remote-resources
```

Allowing HTTPS does not disable network protections. Scheme validation, public-address checks,
domain allowlists, redirect limits, MIME validation, download limits, and hardened SVG handling
remain enforced. Base64 data URIs are always decoded locally and never use the network.

## Compatibility

- Python: 3.11, 3.12, and 3.13
- Operating systems: Windows, Linux, and macOS
- Primary document authority: Microsoft Word 365
- Secondary visual compatibility: LibreOffice Writer
- Public Python API compatibility level remains v1; the staged compiler is additive.

See [ARCHITECTURE.md](ARCHITECTURE.md), [V2_MIGRATION.md](V2_MIGRATION.md), and
[feature-matrix.json](feature-matrix.json) for implementation and compatibility details.
