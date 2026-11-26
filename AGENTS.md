## Workspace conventions

- The active source folder under `D:\Project\mddocx` must be named `mddocx-<version>`, using the exact `[project].version` from `pyproject.toml`, including any prerelease suffix (for example, `mddocx-1.5.0rc2`).
- Check the folder name when starting roadmap work and again after a version change. If it differs, rename the existing checkout from its parent directory, then verify that the folder name matches the version and that `git status` works at the new path. If the destination already exists, report the conflict and preserve both directories.
- Keep `D:\Project\mddocx` limited to the active checkout and `mddocx-explainer.mp4`. Use staging outside this folder for virtual environments, builds, draft videos, and generated review files.
- Preserve working-tree changes when moving or cleaning a checkout. Use the Recycle Bin for workspace files the user asks to remove.
- Use ordinary Git and source inspection for repository work. Graphify was uninstalled at the user's request.
- Consult `docs/MAINTENANCE_AUDIT_1.5.md` for current review evidence and confirmed open defects. Verify the current code and checks before treating an earlier result as proof.

## User font preference

Use SutonnyMJ for Bangla text in generated DOCX/PDF documents. Keep Markdown
and the AST in Unicode; apply Bijoy glyph encoding only at the DOCX output
boundary. Preserve English text in a Latin font and visually verify the output.
Do not use Google Drive for this task unless the user requests it again.

For this agreement, omit decorative Markdown horizontal separators (`---`).
Retain the table grid, photo boxes, and signature dotted lines.
