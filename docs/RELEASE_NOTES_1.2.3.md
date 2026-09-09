# mddocx-native 1.2.3

Version 1.2.3 contains the complete fidelity-first compiler and AI-media work introduced in 1.2.2,
plus a cross-platform security-test correction discovered by the release CI matrix.

## Highlights

- Base64 `data:image/...;base64,...` images render as validated native Word DrawingML.
- Safe public HTTPS images are allowed by default; the interactive shell asks once whether to
  block them with `RESOURCE201` and remembers the choice.
- Common ChatGPT, Claude, Gemini, and MathJax equations render as native editable OMML.
- A typed staged compiler, semantic index, layout plan, deterministic table-width allocator,
  source boundary, extension protocols, style map, JSON/SARIF diagnostics, and migration guide are
  included.
- Unsafe SVG references are validated with the required hardened `lxml` parser consistently on
  Windows, Linux, and macOS before optional SVG-to-PNG conversion is attempted.

## Remote-resource controls

```console
mddocx report.md --block-remote-resources
mddocx report.md --allow-remote-resources
```

Allowing HTTPS preserves scheme, public-address, redirect, MIME, size, and SVG safety checks.
Base64 data URIs remain local and never use the network.

See [ARCHITECTURE.md](ARCHITECTURE.md), [V2_MIGRATION.md](V2_MIGRATION.md), and
[feature-matrix.json](feature-matrix.json) for the full design and compatibility contract.
