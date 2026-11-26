# Maintenance review after 1.5.0rc4

This review is in progress. A passing test suite proves the covered cases, not the
absence of defects throughout the library. The review follows the user entry points
through parsing, normalization, layout, resource acquisition, rendering, validation,
and publication. The completed 1.4.3 review is recorded separately in
[MAINTENANCE_AUDIT_1.4.3.md](MAINTENANCE_AUDIT_1.4.3.md).

## Current evidence

| Area | Evidence and limits |
| --- | --- |
| Product explainer | The revised local video is 64 seconds, 1920 by 1080, 30 fps, with English narration. Eleven key moments were inspected, and the full MP4 decoded without errors. It demonstrates native equations, merged tables, repeated headers, portrait/landscape transitions, and image syntax. The image URL is explicitly shortened for display. |
| Report appearance | The Report theme and its heading and table behavior are covered in `tests/test_table_and_setup_rc2.py`. Optional page rendering remains separate from structural verification. |
| Editable equations | `tests/test_equation_conformance_corpus.py` checks 250 deterministic cases across ten families through the Python converter without an external math engine. It checks native OMML structure and semantic validation. This is evidence for the corpus, not unrestricted TeX compatibility. |
| Direct image links | `tests/test_resilient_resources.py` covers body, table, note, and linked images, repeated URLs, failures, and links that must not trigger a download. |
| Persistent image cache | Invalid and oversized entries are refetched and atomically repaired. SVG/WebP settings and SVG resolution participate in cache keys. The repaired body-and-table fixture produces identical DOCX bytes and verifies offline. |
| Malformed HTML tables | Non-whitespace text outside cells or captions is preserved as source text with `TABLE202`. Six previously silent losses and a valid whitespace case have regression coverage. |
| Template bookmarks | `tests/test_template_bookmarks.py` covers reserved names and IDs in bodies, headers, footers, footnotes, and endnotes, with output validation enabled and disabled. It checks generated REF instructions, internal links, and start/end IDs. |
| Package inspection | Header/footer bookmarks participate in duplicate-name and reference checks. Inspection uses the XML already parsed by validation. |
| Dead-code screening | Ruff checks unused imports and local variables. A reference-name scan across Python source, tests, and scripts found no private function name appearing only at its definition. This screening does not establish reachability for every dynamic hook or public API. |

The latest changes and their user-visible effects are listed in
[CHANGELOG.md](../CHANGELOG.md). The integration branch passed 898 nonvisual tests
before the template-bookmark work, and all 13 CI jobs passed on `eac05ee`. Newer
changes require their own qualification; do not reuse that result as their proof.

The template-bookmark changes passed 912 local nonvisual tests with two optional
visual tests deselected. Ruff, formatting, the existing 11-file mypy gate, and the
diagnostic-catalog check also passed. Their hosted qualification is pending.

Duplicate names are more than a package-cleanliness issue. Word retains one
bookmark and ignores the others, as documented in
[Microsoft's bookmark implementation notes](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/88454e96-31cb-4112-b7c2-e6b0f84a2637).

## Confirmed issue still open

Cached caption numbering ignores earlier captions without identifiers. For example,
two tables captioned `First` and `Second {#second}` currently display `Table 1` twice,
and `[Table @second]` initially displays `Table 1`. The desired values are `Table 1`,
`Table 2`, and `Table 2`, consistent with the native Word sequence after updating
fields. Review both `references.py` and `render/citations.py`, including figure,
listing, section-scoped, and recovery behavior before changing the counter policy.

## Qualification still required

- Finish the caption-numbering correction and its independent regression cases.
- Continue the review across the remaining paths; the whole-code review is not
  certified complete by the private-name scan.
- Qualify the final candidate on the platform matrix and clean release archives.
- Keep Word/LibreOffice layout evidence separate from in-process fidelity results.
- Publish a new release for post-rc4 fixes. The existing 1.5.0rc4 archives remain
  unchanged.

The machine-readable construct scope remains
[`feature-matrix.json`](../src/mddocx/feature-matrix.json). Broader 2.x interface and
verification work remains in [FIDELITY_FIRST_V2_PLAN.md](FIDELITY_FIRST_V2_PLAN.md).
