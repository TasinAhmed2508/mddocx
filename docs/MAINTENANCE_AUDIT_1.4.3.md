# mddocx maintenance audit for 1.4.3

The review covered the tracked Python package, tests, public API contract, packaging, and release
workflows. It followed the CLI, shell, batch, project, and Python entry points through source
loading, parsing, normalization, layout, resource resolution, Word generation, validation, and
publication. The expected load is a local conversion, including long documents and parallel
invocations that may share a cache. The bundled MathJax implementation was treated as vendored
code. Its Python integration was reviewed.

| Finding | Change in 1.4.3 |
| --- | --- |
| Project cache keys omitted explicit render settings. A changed configuration could return an older DOCX, and a state file containing a JSON array could stop the build. | Explicit settings bypass the manifest cache. Malformed state triggers a rebuild. Old cache entries are invalidated once. |
| Project includes bypassed the single-file size limit. Concurrent AST cache writers shared one temporary filename. | Includes use the common bounded reader. DOCX, AST cache and build-state writes share the atomic file writer with unique temporary names. |
| Rendering a wide table rebuilt the row's Word cell list per column and walked the same inline text twice. | Resolve cells and inline text once per row. Reuse intrinsic column widths when planning landscape layout. |
| Validating a DOCX reopened the archive and parsed its XML twice. File compilation also reread the DOCX it just wrote. | Inspect parsed parts directly after validation. Return the bytes supplied to the atomic writer. |
| The text and AST rendering paths independently planned layout, invoked the renderer and finalized the package. | Both call the same implementation, including the extension hooks and final validation. |
| A paginated flowchart rebuilt the Mermaid graph for every panel. Repeated equations reran the same math engine. | Parse and level each flowchart once. Keep a bounded cache of successful equation conversions and copy XML for each insertion. |
| Heading suffix allocation and bookmark checks repeated lookups as documents grew. Two private math helpers had no callers. | Track the next suffix, reuse the bookmark set, and remove the unreachable helpers. |

Local Windows medians over three runs each, comparing 1.4.2 and the 1.4.3 candidate:

| Workload | 1.4.2 | Candidate |
| --- | ---: | ---: |
| Wide table with 80 data rows and 24 columns | 3.971 s | 1.933 s |
| Mixed document with 60 sections | 10.250 s | 9.335 s |
| Paginated Mermaid flowchart with 121 nodes | 0.824 s | 0.588 s |

The two documents had matching SHA-256 hashes after normalizing ZIP metadata. The flowchart
panels matched byte for byte. These timings describe the three local workloads.

The main remaining performance costs are MathJax startup for distinct expressions and repeated
ZIP serialization when several optional Word parts are added. Both need a separate design and
measurement pass because they cross process or package ownership boundaries. Layout-plan lookup
also remains linear per lookup. The release keeps the public plan representation used by
extensions. The project limit applies per source file. Aggregate expansion across includes still
needs its own resource policy.
