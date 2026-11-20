## Workspace conventions

- Name the active local source checkout `mddocx-<version>` using the exact `[project].version` value from `pyproject.toml`, including any prerelease suffix (for example, `mddocx-1.5.0rc2`).
- Whenever you change the package version, rename the existing checkout from its parent directory as part of the same task. Continue work from the new path and verify that the folder name matches the version and that `git status` works there. If the destination already exists, report the conflict and preserve both directories.
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
