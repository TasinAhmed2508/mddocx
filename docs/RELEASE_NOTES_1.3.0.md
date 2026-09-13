# mddocx-native 1.3.0

Version 1.3 makes technical and academic conversions resilient when documents contain remote
figures, animated GIFs, complex equations, citations, and web references.

## Resilient images

- Only Markdown image syntax downloads media. Ordinary links always remain Word hyperlinks.
- Public HTTP and HTTPS images are supported by default with bounded downloads, redirect checks,
  content-based image validation, and successful-resource caching.
- Failed or non-image resources become readable clickable fallbacks and produce diagnostics.
- Use `--strict-images` when every image must embed successfully.
- GIF files are embedded unchanged. Animated GIF playback remains dependent on the Word client.

## Smart equations

- Equations use a bundled, pinned MathJax 4.1.3 sidecar first, then local Python engines, and
  remain native editable Office Math when conversion and structural validation succeed.
- Conservative normalization repairs common AI-generated LaTeX presentation variants without
  algebraically rewriting expressions.
- `mddocx math-check FILE.md --json` reports the selected engine, normalization repairs, and
  fallback details for each equation.
- Unsupported expressions remain editable source text unless `--strict-math` is selected.
- A deterministic 250-equation corpus covers ten academic construct families.

## Academic references

- APA is the new default citation style; IEEE, numeric, author-year, and Chicago author-date are
  supported compatibility choices.
- Install `mddocx-native[academic]` to execute arbitrary local CSL styles through citeproc-py.
- DOI values are normalized to canonical `https://doi.org/` links.
- Bibliography inclusion can be limited to cited works or include all local entries.
- `mddocx link-check` validates ordinary and bibliography links separately from conversion.

## Compatibility

The v1 Python entry points remain available. Existing remote-resource flags and legacy citation
style names continue to work. The package version is 1.3.0.

The release candidate passed the complete automated suite, including Word-backed visual QA on
Windows, and a Word 365 read-only qualification of the technical-report fixture.
