# Interactive CLI (`mddocx shell`)

`mddocx 1.1` adds a discoverable console on top of the stable v1 compiler API. It does **not** contain a second Markdown parser or DOCX renderer.

```text
Interactive console
       ↓
Existing mddocx services/API
       ↓
Canonical compiler pipeline
       ↓
Native DOCX/OMML/ChartML
```

Existing scripted commands continue to work unchanged:

```console
mddocx report.md -o report.docx
mddocx build .
mddocx inspect report.docx --strict
```

The interactive entry point is:

```console
mddocx shell
```

You can also start it in another workspace:

```console
mddocx shell D:\Documents\report-project
```

## Main menu

The console detects the current workspace and shows Markdown, DOCX, image/data assets, and `mddocx.yml` status. The menu exposes:

1. render Markdown;
2. build a project;
3. watch a project;
4. create a project;
5. view/edit common project configuration;
6. check Markdown;
7. inspect generated DOCX structure;
8. run accessibility QA;
9. template/data/font tools;
10. doctor/runtime diagnostics;
11. recent generated documents;
12. help.

The menu is optional. Experienced users can type commands directly:

```text
mddocx [report]> render chapter.md -o chapter.docx
mddocx [report]> build --open
mddocx [report]> watch
mddocx [report]> doctor
mddocx [report]> inspect
mddocx [report]> accessibility
mddocx [report]> template inspect corporate.dotx
mddocx [report]> data inspect data/results.csv
mddocx [report]> fonts aptos
mddocx [report]> diagnostics
mddocx [report]> explain RESOURCE201
mddocx [report]> recent
mddocx [report]> open
mddocx [report]> cd D:\Books\physics
mddocx [physics]> files
```

## Render wizard

Running `render` without a path starts a file picker and asks for output/theme choices. If HTTPS resources are detected, the wizard can opt in **only the detected hosts** for that render. The underlying resource policy continues to block private/loopback/link-local targets.

A completed render prints useful structural counts from `mddocx inspect`, including equations, tables, lists, drawings, and native charts. The console can then open the DOCX using the operating system's registered Word-compatible application.

## Project configuration

`config` displays common `mddocx.yml` settings. The guided editor changes a bounded set of ordinary settings such as theme, title, TOC, heading/caption/equation numbering, Page X of Y, and output path.

Advanced users can make explicit dotted-key changes:

```text
config set render.theme academic
config set render.toc true
config set output build/final.docx
```

YAML is still parsed and written with `PyYAML.safe_load` / `safe_dump`; no executable configuration language is introduced.

## Recent files and privacy

Recent history stores only:

- source path;
- output path;
- action (`render`/`build`);
- workspace path;
- timestamp;
- a small settings mapping.

Markdown or DOCX document content is never saved in shell history metadata.

Top-level equivalents are also available:

```console
mddocx recent
mddocx open
mddocx report.md -o report.docx --open
mddocx build . --open
```

## Windows UX

Interactive tokenization preserves Windows backslashes and quoted paths such as:

```text
render "D:\My Project\report.md" -o "D:\Output Files\report.docx"
```

`prompt-toolkit` supplies persistent command history and completion in normal interactive terminals. When stdin is redirected/piped, mddocx falls back to ordinary line input without terminal-control warnings.

`open` uses the operating-system file association. There is no generic `! command`, shell escape, or Markdown-triggered process execution.

## Security invariants

The shell does not weaken compiler security:

- safe public HTTPS resources are allowed by default; on first launch the shell asks whether to
  block them with `RESOURCE201` and persists the choice in `preferences.json`;
- private/non-global remote hosts stay blocked;
- local resource/project path confinement remains active;
- code blocks are never executed;
- Markdown cannot execute shell/Python/JavaScript;
- plugins remain explicit opt-in entry points;
- XML/YAML parsing remains defensive.

## AI/chat export metadata

The shell uses the same v1.2 metadata sanitizer as the normal CLI. `render` defaults to conservative `auto` cleanup and reports detected export metadata before compiling.

```text
metadata downloaded-chat.md
metadata downloaded-chat.md --strip
metadata downloaded-chat.md --keep
render downloaded-chat.md --ai-metadata auto
```

Project configuration exposes `render.ai_metadata` with `auto`, `strip`, or `keep`.
