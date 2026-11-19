# Compatibility matrix

The executable, machine-readable construct contract is
[`feature-matrix.json`](../src/mddocx/feature-matrix.json). It distinguishes native structure,
diagnostic behavior, Word 365 qualification status, the optional secondary renderer
signal, and the tracked evidence for each feature. This page summarizes host/runtime
policy.

## Runtime

| Component | v1.x policy |
|---|---|
| Python | 3.11–3.13 |
| DOCX format | OOXML / WordprocessingML |
| Equations | native OMML |
| Charts | native ChartML + embedded XLSX |
| Network | disabled by default |
| Office suite | not required |
| Java, browser, external converter | not required |
| Output verification | in-process, in this package |

## Languages and scripts

Markdown and the canonical AST remain Unicode. Script-specific fonts and direction are applied
only to the generated Word XML, including the title page, captions, bibliography, headers,
footers, and notes.

| Script group | Status |
|---|---|
| Latin, Cyrillic, Greek, Vietnamese, Turkish | Unicode text with the body font |
| Bengali | Unicode by default; Bijoy/SutonnyMJ encoding at the DOCX boundary when `fonts.bengali` is set |
| Other complex scripts (Indic, Southeast Asian, Ethiopic, Mongolian, Syriac, Thaana) | `w:cs` font slot through `--complex-script-font`; left-to-right direction preserved |
| Arabic, Hebrew, Persian | automatic bidi direction and right alignment; `--rtl off/auto/force` controls the policy |
| Chinese, Japanese, Korean | `w:eastAsia` font slot through `--east-asia-font`, including extension planes |

## Output hosts

mddocx generates standards-based OOXML intended for Microsoft Word 2019/2021/Microsoft 365 on Windows and Microsoft 365 on macOS. **No office application is required to convert a document or to check the result.** Every conversion and every automated test in this repository validates OOXML structure independently of any office application, including the ECMA-376 content-model element order of every part written: a departure is reported as `DOCX422` instead of being written into the document (`mddocx inspect --strict`, `ValidationConfig.validate_schema_order`). Host independence is itself asserted by `tests/test_no_office_dependency.py`.

The v1 compatibility contract is native semantic structure plus structurally valid OOXML. Pagination and font metrics can reflow between hosts, so the contract deliberately does not promise pixel-identical rendering on any particular one.

### Optional rendering cross-check (for maintainers)

Nothing in the package's normal use reaches for an office application. One helper,
`mddocx visual-qa`, can render a DOCX to page images and diff them against a stored baseline;
it needs LibreOffice/soffice plus `pdftoppm`, or Microsoft Word on Windows. It exists to catch
layout and pagination regressions — properties of a *renderer* rather than of the package —
and is therefore an optional, secondary signal:

- It is not part of conversion, and no feature depends on it.
- A machine without those tools reports the cross-check as unavailable; `mddocx doctor`
  lists them under "Optional visual QA tools" and does not treat them as a requirement.
- A green run is a smoke signal about one renderer, never a claim about every Word version, and
  never a substitute for the structural checks above.

For release qualification, a real Microsoft Word smoke pass on representative documents remains
the strongest human check when a Windows Word environment is available, especially for ChartML
secondary axes, fields, TOCs, and advanced equation layout.

## Interactive CLI

`mddocx shell` uses `prompt-toolkit` for interactive command history/completion and falls back to plain line input when stdin is redirected. The shell is designed for Windows Command Prompt/PowerShell/Windows Terminal, macOS terminals, and common Linux terminals. Windows path handling is regression-tested with drive-letter paths, backslashes, spaces, and quoted arguments.

Opening generated files is delegated to the operating system (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux); no specific Word/LibreOffice executable is hard-coded.
