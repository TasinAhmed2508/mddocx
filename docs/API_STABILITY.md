# Public API stability — v1

mddocx 1.0 establishes public API version `1`.

The names returned by `mddocx.get_public_api_manifest()` are the supported v1 surface. Compatible 1.x releases may add new names and optional parameters, but must not remove these names or intentionally change their established semantics without a deprecation cycle. Incompatible public API changes require mddocx 2.x.

The stable rendering entry points are `render`, `render_string`, `MarkdownWord.render_file`, `MarkdownWord.render_string`, and `MarkdownWord.render_ast`. Configuration objects exported from `mddocx` are also part of API v1.

Internal modules under `mddocx.ooxml`, parser implementation details, XML helper functions, and private names beginning with `_` are not frozen public API.

Use `mddocx api --json` in CI to record the installed package's API manifest.
