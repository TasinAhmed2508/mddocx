## Workspace conventions

- Name the active source checkout `mddocx-<version>` using `[project].version` from `pyproject.toml`. Rename the checkout when the package version changes and verify Git still works afterward.
- Keep `D:\Project\mddocx` limited to the active checkout and `mddocx-explainer.mp4`. Use staging outside this folder for virtual environments, builds, draft videos, and generated review files.
- Preserve working-tree changes when moving or cleaning a checkout. Use the Recycle Bin for workspace files the user asks to remove.
- Use ordinary Git and source inspection for repository work. Graphify was uninstalled at the user's request.

## User font preference

Use SutonnyMJ for Bangla text in generated DOCX/PDF documents. Keep Markdown
and the AST in Unicode; apply Bijoy glyph encoding only at the DOCX output
boundary. Preserve English text in a Latin font and visually verify the output.
Do not use Google Drive for this task unless the user requests it again.

For this agreement, omit decorative Markdown horizontal separators (`---`).
Retain the table grid, photo boxes, and signature dotted lines.
