# Phase 7 — Project / Build Mode (v0.8.0)

Version 0.8.0 adds a project-oriented build layer on top of the existing Markdown → AST → DOCX compiler. The normal single-file `mddocx file.md` workflow remains unchanged.

## Project manifest

A project is rooted by `mddocx.yml`:

```yaml
version: 1
output: build/report.docx
sources:
  - chapters/*.md
variables:
  product: mddocx
  version: 0.8.0
render:
  title: Project Report
  title_page: true
  toc: true
  heading_numbering: true
  equation_numbering: section
  caption_numbering: section
  bibliography: references.bib
  auto_bibliography: true
project:
  max_include_depth: 32
  undefined_variables: error
watch:
  interval: 1.0
```

`source` globs are expanded deterministically in lexical order. Every source must remain inside the project root.

## Build commands

```bash
mddocx project init my-report
mddocx project info my-report
mddocx build my-report
mddocx build my-report --check
mddocx build my-report --force
mddocx watch my-report
```

`mddocx watch --once` uses the same watcher/build path but exits after its initial build; it is mainly useful for automation and QA.

## Includes

A standalone directive includes another Markdown file at that position:

```markdown
@include ../includes/security.md
```

Quoted paths are also accepted:

```markdown
@include "../shared/introduction.md"
```

Rules:

- resolution is relative to the including Markdown file;
- includes must remain inside the project root;
- absolute paths are rejected;
- recursive include cycles are rejected with a structured diagnostic;
- include depth is bounded by `project.max_include_depth`;
- include directives inside fenced code blocks are preserved as code and are not expanded;
- included files remain distinct parser sources, so source-file diagnostics and cross-chapter document semantics are retained.

## Variables

Project variables use inert text substitution:

```yaml
variables:
  product: mddocx
  release: 0.8.0
```

```markdown
This document was built with {{ product }} {{ release }}.
```

Variables are scalar only and cannot contain newlines. No Python, shell, template expression, or environment-variable evaluation occurs.

Undefined variables can be configured as:

```yaml
project:
  undefined_variables: error  # error | keep | empty
```

A literal variable marker can be escaped with a leading backslash.

## Relative resources

Images referenced from chapter files remain relative to the chapter at authoring time:

```text
project/
  chapters/a.md
  images/plot.png
```

```markdown
![Plot](../images/plot.png)
```

The project compiler safely rebases the image path to the project root before DOCX rendering. Resource traversal outside the root remains forbidden.

## Incremental builds

Successful builds write an internal state file under:

```text
.mddocx/build-state.json
```

The state records:

- manifest path;
- output path;
- source/include/resource/template/bibliography dependencies;
- deterministic dependency fingerprint;
- output SHA-256.

A subsequent build is skipped when all dependencies and the generated artifact hash still match. Changing an input dependency or modifying the generated DOCX forces a rebuild.

## Watch mode

`mddocx watch` uses a bounded polling watcher and does not require a native filesystem-event dependency. It watches the project tree while ignoring `.mddocx`, VCS/virtual-environment caches, and the generated output itself.

The watcher reloads `mddocx.yml` after changes, so source lists, globs, variables, render configuration, and output paths can be changed during an authoring session.

## Python API

```python
from mddocx import build_project, compile_project, load_project

manifest = load_project("report/")
compiled = compile_project(manifest)
result = build_project(manifest)

print(result.output_path)
print(result.fingerprint)
print(result.output_sha256)
```

## Security boundaries

Project mode adds no code execution. In addition to the existing renderer protections:

- manifest source paths cannot escape the root;
- manifest output paths cannot escape the root;
- include traversal and absolute include paths are rejected;
- include cycles/depth are bounded;
- project variables are inert scalar text;
- local resources referenced by project Markdown cannot escape the root;
- project YAML is parsed with `yaml.safe_load`;
- remote resources follow the normal resource policy, which allows validated public HTTPS by
  default and can be explicitly blocked.

## Deliberate limitations

- Includes are block-level standalone directives, not arbitrary inline transclusion.
- Variable expansion is deliberately not a general template language.
- Watch mode uses polling for portability rather than platform-specific filesystem APIs.
- Project builds currently produce one DOCX artifact per manifest; multi-target project graphs are a future extension.
