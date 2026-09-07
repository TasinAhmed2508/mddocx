# AI / Chat Export Metadata Sanitization

`mddocx` 1.2 removes export-only provenance from downloaded AI/chat Markdown before the Markdown parser builds the canonical AST.

## Why

Conversation exports can contain metadata that is useful to the exporting application but undesirable in a professional Word document, for example:

- conversation/chat/thread/message IDs;
- model/model-slug/provider/platform fields;
- created/updated/exported timestamps;
- share/source/conversation URLs;
- hidden HTML metadata comments;
- explicit `Conversation Metadata` / `Export Details` sections;
- standalone timestamps attached to `User`/`Assistant` role headings;
- YAML front matter populated by an export tool.

If export front matter contains fields such as `title`, `author`, or `created_at`, older versions could also use them as Word document properties. Version 1.2 filters those fields when an export signature is detected.

## Policies

### `auto` (default)

Conservative. Removes only high-confidence export metadata, explicit metadata sections/comments, and role timestamps. Ordinary document content and normal mddocx front matter are preserved.

```console
mddocx chat.md -o chat.docx
mddocx chat.md -o chat.docx --ai-metadata auto
```

### `strip`

More aggressive for recognized metadata/provenance keys. Useful for exports from tools with minimal provenance markers.

```console
mddocx chat.md -o chat.docx --ai-metadata strip
```

### `keep`

Disables source sanitization.

```console
mddocx chat.md -o chat.docx --ai-metadata keep
```

## Preview before rendering

```console
mddocx metadata inspect chat.md
mddocx metadata inspect chat.md --json
```

The report includes whether export metadata was detected, source lines that would be removed, front-matter fields that would be filtered, and the detection reasons.

## Clean Markdown without creating DOCX

```console
mddocx metadata clean chat.md -o clean-chat.md
```

The cleaner preserves source line count by replacing removed metadata with blank lines. This keeps compiler diagnostics aligned with the original downloaded file.

## Project configuration

```yaml
render:
  ai_metadata: auto
```

Each source/include is sanitized before the project AST is merged.

## Python API

```python
from mddocx import MetadataConfig, RenderConfig, render

config = RenderConfig(metadata=MetadataConfig(ai_export="auto"))
render("downloaded-chat.md", "conversation.docx", config)
```

Inspection without rendering:

```python
from mddocx import MetadataConfig, sanitize_markdown_metadata

source = open("downloaded-chat.md", encoding="utf-8").read()
result = sanitize_markdown_metadata(source, MetadataConfig(ai_export="auto"))
print(result.report.to_json())
```

## Safety / false-positive controls

The default sanitizer intentionally does **not**:

- delete `User`, `Assistant`, `Human`, or `System` role headings;
- remove ordinary URLs/links;
- strip arbitrary key/value paragraphs in the middle of a document;
- modify fenced code examples just because they contain keys such as `model` or `conversation_id`;
- remove normal mddocx front matter unless an export/provenance signature is detected.

If a document intentionally needs its export metadata, use `keep`.

## DOCX core-property cleanup

For newly generated documents without a template, mddocx also removes python-docx's synthetic creator/created/modified defaults when the user has not supplied those properties. Explicit user metadata remains supported. Existing template metadata is preserved.
