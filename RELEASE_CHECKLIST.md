# v1 release checklist

- [ ] `python -m compileall -q src`
- [ ] full non-visual pytest suite passes
- [ ] visual regression passes where LibreOffice + pdftoppm are available
- [ ] `mddocx doctor` passes
- [ ] `mddocx shell --help` and `mddocx --version` smoke tests pass
- [ ] scripted interactive shell acceptance covers render/build/inspect/accessibility/doctor/recent
- [ ] Windows-style quoted/backslash path regression passes
- [ ] recent-history metadata contains paths/settings only, never document content
- [ ] `mddocx benchmark` passes release thresholds
- [ ] v1 acceptance DOCX passes `mddocx inspect --strict`
- [ ] v1 acceptance DOCX passes `mddocx accessibility --strict`
- [ ] forced deterministic rebuild hashes match
- [ ] wheel installs in an isolated target
- [ ] installed wheel renders, inspects, and audits a smoke document
- [ ] changelog and implementation status updated
- [ ] compatibility matrix reviewed
- [ ] public API manifest reviewed for accidental removals
