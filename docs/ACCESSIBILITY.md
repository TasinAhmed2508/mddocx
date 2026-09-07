# Accessibility auditing

Run:

```bash
mddocx accessibility output.docx
mddocx accessibility output.docx --strict
mddocx accessibility output.docx --json
```

The v1 auditor checks image/chart alternative text, semantic table header rows, heading-level jumps, empty hyperlinks, and document title metadata. `--strict` fails on medium-or-higher findings. `--fail-on` can select `high`, `medium`, `low`, or `info`.

The audit is a deterministic structural check, not a substitute for Microsoft Accessibility Checker or human review. It is designed to catch common regressions before delivery.
