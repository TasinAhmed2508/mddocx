# Microsoft Word 365 qualification

Microsoft Word 365 desktop is the primary visual and interoperability authority for mddocx.
Structural OOXML tests run on every pull request; Word automation is intended for a controlled
Windows release machine with Microsoft Word installed.

## Automated smoke check

Generate the reference document, then run:

```powershell
pwsh -File scripts/word365-smoke.ps1 `
  -Document D:\path\to\reference.docx `
  -ExpectedEquations 22 `
  -ExportPdf D:\path\to\reference.pdf
```

The script opens the document read-only with alerts disabled, reads Word's page, paragraph, and
native-equation counts, optionally exports PDF, and always closes Word. A count mismatch, Word COM
failure, repair/open failure, or PDF export failure produces a nonzero PowerShell exit.

## Release corpus

Before publishing a release, qualify:

- the ChatGPT-style sphere fixture in `tests/fixtures/ai_markdown`;
- the full technical report in `tests/fixtures/technical_report`;
- at least one malformed/unsupported-math document that must remain readable with warnings;
- a project build with cross-file includes;
- a wide-table document that enters and leaves a landscape section.

For each document:

1. Run structural inspection and require no broken relationships, invalid XML, dangling references,
   duplicate IDs, malformed radicals, empty n-ary operands, or chart/workbook relationship errors.
2. Open with Word automation and verify the expected native-equation count.
3. Export to PDF and render pages for visual inspection.
4. Confirm equations, boxes, fractions, matrices, fields, charts, tables, notes, captions, and page
   transitions are readable and editable.
5. Save a copy in Word, reopen it, and confirm Word did not remove or repair document structures.

LibreOffice visual regression remains a secondary compatibility signal and is not a replacement for
this Word 365 qualification.

## Recorded qualification evidence

On 2026-09-09, Microsoft Word 365 desktop on Windows opened both current generated packages without
repair and exported them to PDF:

| Corpus | Word pages | Word paragraphs | Native equations | Structural result |
|---|---:|---:|---:|---|
| AI sphere/equation fixture | 2 | 43 | 22 | PASS |
| Technical report (chart, workbook, fields, notes, references) | 2 | 36 | 2 | PASS |

The AI fixture PDF was visually inspected: all equations were present and centered; fractions,
boxes, scripts, and Greek symbols were readable; `\\text{...}` content was upright; and no raw
Markdown math delimiters appeared. This evidence is host/version-specific and should be repeated
for each release candidate.
