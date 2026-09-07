# Results and References {#sec-results}

The compiler resolves [Figure @fig-project] from another chapter and [Equation @eq-gaussian] from the mathematics chapter without concatenation-specific hacks.

Project builds are intentionally incremental: if neither the manifest nor any source/include/resource/template/bibliography dependency changes, the DOCX build is skipped.

| Capability | Result |
|---|---|
| Ordered source globs | Pass |
| Nested secure includes | Pass |
| Project variables | Pass |
| Cross-chapter references | Pass |
| Incremental dependency state | Pass |

The architecture follows the principle that native Word structures should remain editable [@knuth1984].

## Build command

```bat {caption="Windows project build" #lst-build linenos=true}
mddocx build .
mddocx project info .
mddocx watch .
```

The same project can be rebuilt continuously during authoring with the bounded polling watcher.
