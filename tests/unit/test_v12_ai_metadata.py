from __future__ import annotations

from mddocx import MetadataConfig, sanitize_markdown_metadata
from mddocx.parser import MarkdownParser


def test_auto_strips_ai_export_front_matter_identity_but_keeps_render_config():
    source = """---
title: Exported Chat
author: AI Assistant
conversation_id: conv-123
model: example-model
created_at: 2026-08-16T10:00:00Z
theme: academic
toc: true
---
# Useful answer

Keep this content.
"""
    cleaned = sanitize_markdown_metadata(source)
    assert cleaned.report.detected_export_metadata
    assert set(cleaned.report.removed_front_matter_keys) >= {
        "title", "author", "conversation_id", "model", "created_at"
    }
    doc = MarkdownParser().parse(source)
    assert doc.metadata["theme"] == "academic"
    assert doc.metadata["toc"] is True
    assert "title" not in doc.metadata
    assert "author" not in doc.metadata
    assert "created_at" not in doc.metadata


def test_normal_mddocx_front_matter_metadata_is_preserved_when_no_export_signature():
    source = """---
title: Human Authored Report
author: Ada Lovelace
created_at: 2026-08-16T10:00:00Z
theme: modern
---
# Report
"""
    result = sanitize_markdown_metadata(source)
    assert not result.report.detected_export_metadata
    assert not result.report.changed
    doc = MarkdownParser().parse(source)
    assert doc.metadata["title"] == "Human Authored Report"
    assert doc.metadata["author"] == "Ada Lovelace"


def test_auto_removes_boundary_metadata_and_role_timestamp_but_keeps_roles_and_content():
    source = """Conversation ID: conv-1
Model: example-model
Exported at: 2026-08-16T08:00:00Z

## User
[2026-08-16 08:01]
What is a derivative?

## Assistant
A derivative measures a rate of change.
"""
    result = sanitize_markdown_metadata(source)
    assert result.report.detected_export_metadata
    assert "Conversation ID:" not in result.markdown
    assert "Model:" not in result.markdown
    assert "Exported at:" not in result.markdown
    assert "[2026-08-16 08:01]" not in result.markdown
    assert "## User" in result.markdown
    assert "## Assistant" in result.markdown
    assert "What is a derivative?" in result.markdown


def test_explicit_metadata_section_is_removed_without_hardcoding_provider():
    source = """# Conversation Metadata

- Model: alpha-2
- Created at: 2026-08-16T08:00:00Z
- Source URL: https://example.invalid/chat/123

# Discussion

Important content.
"""
    result = sanitize_markdown_metadata(source)
    assert result.report.changed
    assert "Conversation Metadata" not in result.markdown
    assert "alpha-2" not in result.markdown
    assert "# Discussion" in result.markdown
    assert "Important content." in result.markdown


def test_auto_does_not_strip_metadata_like_content_in_middle_of_document():
    source = """# Machine Learning Notes

This section discusses a model and its source.

## Experiment

Model: ResNet-50
Source: ImageNet
Accuracy: 76.1%

## Conclusion

Keep the experiment metadata because it is document content.
"""
    result = sanitize_markdown_metadata(source)
    assert "Model: ResNet-50" in result.markdown
    assert "Source: ImageNet" in result.markdown
    assert "Accuracy: 76.1%" in result.markdown


def test_metadata_examples_inside_code_fences_are_never_sanitized():
    source = """# Example

```yaml
conversation_id: example-only
model: example-model
exported_at: 2026-08-16T08:00:00Z
```
"""
    result = sanitize_markdown_metadata(source)
    assert "conversation_id: example-only" in result.markdown
    assert "model: example-model" in result.markdown


def test_keep_policy_preserves_export_metadata_and_reports_detection():
    source = """---
title: Exported Chat
conversation_id: conv-123
model: example-model
---
Conversation ID: conv-123
Model: example-model
"""
    result = sanitize_markdown_metadata(source, MetadataConfig(ai_export="keep"))
    assert result.markdown == source
    assert result.report.detected_export_metadata
    doc = MarkdownParser(metadata_config=MetadataConfig(ai_export="keep")).parse(source)
    assert doc.metadata["title"] == "Exported Chat"
    assert doc.metadata["conversation_id"] == "conv-123"


def test_strip_policy_removes_recognized_boundary_metadata_without_provider_marker():
    source = """Model: custom-model
Created: 2026-08-16

# Answer
Content.
"""
    auto = sanitize_markdown_metadata(source, MetadataConfig(ai_export="auto"))
    forced = sanitize_markdown_metadata(source, MetadataConfig(ai_export="strip"))
    assert "Model: custom-model" not in auto.markdown
    assert "Model: custom-model" not in forced.markdown
    assert "# Answer" in forced.markdown


def test_auto_keeps_role_timestamp_when_no_export_signature_exists():
    source = """# Interview Transcript

## User
[2026-08-16 08:01]
A timestamp here is part of the authored transcript.
"""
    result = sanitize_markdown_metadata(source, MetadataConfig(ai_export="auto"))
    assert "[2026-08-16 08:01]" in result.markdown
    assert not result.report.detected_export_metadata
