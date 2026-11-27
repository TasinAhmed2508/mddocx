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
| Local image URI paths | A shared decoder handles spaces, Bangla filenames, and literal escaped percent signs once. Tests check embedded bytes, decoded dependencies, watch rebuilds, project include rebasing, cache invalidation, output collision protection, containment, and invalid-path diagnostics. Project AST paths are re-encoded after rebasing so a second stage does not decode percent signs twice. |
| Persistent image cache | Invalid and oversized entries are refetched and atomically repaired. SVG/WebP settings and SVG resolution participate in cache keys. The repaired body-and-table fixture produces identical DOCX bytes and verifies offline. |
| Malformed HTML tables | Non-whitespace text outside cells or captions is preserved as source text with `TABLE202`. Six previously silent losses and a valid whitespace case have regression coverage. |
| Template bookmarks | `tests/test_template_bookmarks.py` covers reserved names and IDs in bodies, headers, footers, footnotes, and endnotes, with output validation enabled and disabled. It checks generated REF instructions, internal links, and start/end IDs. |
| Cached caption numbers | `tests/test_caption_numbering.py` covers anonymous captions, five block types, both caption positions, document/section numbering, native/static references, title policy, and recovery. Captions count actual emissions. Forward reference caches are refreshed before serialization. Offline verification detects edited cached caption and reference values. |
| Native Word section numbers | Source heading counters replace a dependency on visible heading numbering. Word 16.0 updates controlled table and equation documents to 1.1 and 2.1 with correct forward references, with heading numbering enabled and disabled. Hidden counters initialize lazily, preserving the first wide table's landscape section. |
| Equation alignment | Numbered equation cell preferred widths now match their 88/12 table grid. Native Word drawings were inspected with heading numbering enabled and disabled; formulas occupy the intended formula region and numbers remain at the right margin. |
| Explicit document identifiers | The normalizer reserves explicit IDs before allocating automatic heading IDs, using the shared AST walker instead of a second traversal implementation. Focused cases cover later targets, suffix collisions, repeat normalization, and reuse for a different document. |
| Normalized AST cache upgrades | Advance the internal parser/normalizer cache revision so rc4 entries cannot bypass nested-caption and identifier fixes. A seeded legacy cache reproduces DOCX416 before the change; afterward it rebuilds once, verifies, and subsequent cache hits produce identical bytes. |
| Imported table targets | The semantic index now includes `DataTableBlock` identifiers. A local CSV fixture checks staged resolution, native caption/reference output, and offline verification together. |
| Nested captions and list markers | Captions and attributes are associated inside quotes, callouts, and list items. Table/equation items without an opening paragraph receive a native list marker before their content. The independent verifier checks that marker and the surrounding content in order. |
| Package inspection | Header/footer bookmarks participate in duplicate-name and reference checks. Inspection uses the XML already parsed by validation. |
| Dead-code screening | Ruff checks unused imports and local variables. A reference-name scan across Python source, tests, and scripts found no private function name appearing only at its definition. This screening does not establish reachability for every dynamic hook or public API. |

The latest changes and their user-visible effects are listed in
[CHANGELOG.md](../CHANGELOG.md). The integration branch passed 898 nonvisual tests
before the template-bookmark work, and all 13 CI jobs passed on `eac05ee`. Newer
changes require their own qualification; do not reuse that result as their proof.

The template-bookmark changes passed 912 local nonvisual tests with two optional
visual tests deselected. Ruff, formatting, the existing 11-file mypy gate, and the
diagnostic-catalog check also passed. All 13 hosted CI jobs passed on `bab11c7` in
[run 45880125278](https://github.com/TasinAhmed2508/mddocx/actions/runs/45880125278).

Duplicate names are more than a package-cleanliness issue. Word retains one
bookmark and ignores the others, as documented in
[Microsoft's bookmark implementation notes](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/88454e96-31cb-4112-b7c2-e6b0f84a2637).

## Local Windows installation check

The workstation had two older installations. Its isolated console tool still ran
1.5.0rc2, and the system Python had 1.3.1 editable metadata pointing at a removed
checkout. The console tool and system Python were both updated from the qualified
public 1.5.0rc4 wheel, with SHA-256
`eeb369373eba00dc435e2e2bbd8ae3a908f3d40358ebf8eca9ccc640690a29e5`.

The following checks passed from CMD and the installed packages, without a source
checkout on `PYTHONPATH`:

- `mddocx --version`, `mddocx-native --version`, and `python -m mddocx --version`
  all report 1.5.0rc4.
- `mddocx shell --no-menu` reaches its interactive prompt and exits cleanly.
- The tool directory is present in the persistent user PATH.
- `mddocx doctor` passes, including the bundled JavaScript runtime, SVG conversion,
  and CSL support.
- The retained ChatGPT sphere-equation fixture converts without diagnostics,
  contains 22 native editable equations, and verifies offline across 43 units.
  The original Downloads files were no longer present at their supplied paths.

These installed-release checks do not qualify the newer integration-branch fixes
as part of the unchanged rc4 release archives.

## Caption numbering qualification

The initial cached-number mismatch is corrected. Earlier captions without identifiers
now advance later caption numbers, and both forward and backward references display
the final values. This applies to figures, tables, listings, imported tables, and charts.
Known recovery placeholders do not consume caption numbers. There are 49 targeted
caption cases. The combined nonvisual suite passed 961 tests, with two optional visual
tests deselected. Ruff, formatting, the 11-file mypy gate, and diagnostic checks passed.

Follow-up Word automation isolated the earlier timeout to save/export operations.
Field updates pass in Word 16.0 for four controlled documents: tables and equations,
each with visible heading numbering enabled and disabled. Word recognizes the two
native equations in each equation document. Captured live Word XML was repackaged
for QA and verifies without findings (nine checked units for each table document,
seven for each equation document). These are live XML captures, not successful Word
SaveAs round trips.

Native Word body drawings were inspected for these cases; each reports one page.
The equation drawings were repeated after matching cell preferred widths to their
table grid. SaveAs2 and PDF export remain unqualified: export also stalled on a plain
one-paragraph baseline. Identified automation processes were stopped, and no user
documents were altered. Inputs, XML captures, and drawings remain outside the checkout
under `D:\Project\.mddocx-active-work\caption-review`.

The combined follow-up passed 979 local nonvisual tests with two optional visual
tests deselected. There are now 58 targeted caption cases, including equation cell
widths, and nine additional normalizer/nested-target cases. Ruff, formatting, the
11-file mypy gate, the diagnostic catalog, and `git diff --check` passed. A separate
Word drawing of nested table/equation list items was inspected and reports one page;
its source and generated DOCX verify across nine units. Empty items, nested-only
lists, and equations followed by explanatory text were also checked independently.

The imported-table follow-up passed all 13 hosted CI jobs on `b98727a`, including
the Windows/Linux/macOS quality matrix, wheel and source-archive smoke checks, and
the optional LibreOffice visual job in
[run 46026661748](https://github.com/TasinAhmed2508/mddocx/actions/runs/46026661748).
After the local-image URI fix, the local suite passed 1,000 nonvisual tests with
two optional visual tests deselected. Ruff, formatting, the 11-file mypy gate,
diagnostic-catalog synchronization, and whitespace checks passed. This newer image
change still requires its own hosted candidate and archive qualification.

The first rc5 candidate's Windows/Python 3.13 job exposed a platform difference:
resolving a decoded null character no longer raised the `ValueError` caught on
Python 3.12. It reported a missing image and allowed the project build to continue.
The shared decoder now rejects nulls explicitly before filesystem resolution.
The 77 resource/project/watch checks pass on Python 3.12, and 15 focused image-path
checks pass on Python 3.13. The first candidate qualification was cancelled and
must be replaced by a run of the corrected commit before release.

## Qualification still required

- Optional Word SaveAs/PDF export qualification remains incomplete on this workstation.
- Continue the review across the remaining paths; the whole-code review is not
  certified complete by the private-name scan.
- Qualify the final candidate on the platform matrix and clean release archives.
- Keep Word/LibreOffice layout evidence separate from in-process fidelity results.
- Publish a new release for post-rc4 fixes. The existing 1.5.0rc4 archives remain
  unchanged.

The machine-readable construct scope remains
[`feature-matrix.json`](../src/mddocx/feature-matrix.json). Broader 2.x interface and
verification work remains in [FIDELITY_FIRST_V2_PLAN.md](FIDELITY_FIRST_V2_PLAN.md).
