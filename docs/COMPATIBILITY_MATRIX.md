# Compatibility matrix

## Runtime

| Component | v1.x policy |
|---|---|
| Python | 3.11–3.13 |
| DOCX format | OOXML / WordprocessingML |
| Equations | native OMML |
| Charts | native ChartML + embedded XLSX |
| Network | disabled by default |

## Word-compatible hosts

mddocx generates standards-based OOXML intended for Microsoft Word 2019/2021/Microsoft 365 on Windows and Microsoft 365 on macOS. Automated package tests validate OOXML structure independently of any office application. Automated visual regression in the repository currently uses LibreOffice on Linux because Microsoft Word is not available in headless CI.

A green LibreOffice visual test is not a claim of pixel-identical rendering across Word versions. The v1 compatibility contract is semantic/native structure plus structurally valid OOXML; pagination can reflow between hosts.

For release qualification, use a real Microsoft Word smoke pass for representative documents when a Windows Word environment is available, especially for ChartML secondary axes, fields, TOCs, and advanced equation layout.

## Interactive CLI

`mddocx shell` uses `prompt-toolkit` for interactive command history/completion and falls back to plain line input when stdin is redirected. The shell is designed for Windows Command Prompt/PowerShell/Windows Terminal, macOS terminals, and common Linux terminals. Windows path handling is regression-tested with drive-letter paths, backslashes, spaces, and quoted arguments.

Opening generated files is delegated to the operating system (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux); no specific Word/LibreOffice executable is hard-coded.
