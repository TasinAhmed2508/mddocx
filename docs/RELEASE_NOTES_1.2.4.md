# mddocx-native 1.2.4

Version 1.2.4 is the fully qualified follow-up to 1.2.3. It retains the Base64-image,
AI-math, RESOURCE201, DOCX-fidelity, and portable SVG-security improvements while making the
release pipeline reproducible.

## Quality and publishing

- Ruff is pinned to 0.15.10 so developer machines and GitHub runners use the same lint contract.
- The release workflow now runs compilation, the non-visual test suite, lint, formatting, and the
  targeted type-check gate before building any distribution.
- GitHub Release creation and PyPI Trusted Publishing cannot start unless verification succeeds.
- The independent CI workflow continues to validate Python 3.11–3.13 on Windows, Linux, and macOS,
  plus Linux LibreOffice visual rendering and clean wheel/source-distribution installation.

See [the 1.2.3 notes](RELEASE_NOTES_1.2.3.md) and
[the 1.2.2 notes](RELEASE_NOTES_1.2.2.md) for the complete functionality delivered by this release
line.
