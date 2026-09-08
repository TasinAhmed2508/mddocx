from __future__ import annotations

from io import BytesIO
from pathlib import Path
import socket
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from mddocx import MetadataConfig, ResourcePolicy, sanitize_markdown_metadata
from mddocx.config import ImageConfig, ValidationConfig
from mddocx.diagnostics import MddocxError
from mddocx.resources import ResourceResolver
from mddocx.resources.resolver import _SafeRedirectHandler
from mddocx.validation import validate_docx_package


def _package(extra_name: str | None = None, extra_data: bytes = b"x") -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        package.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        package.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>',
        )
        if extra_name:
            package.writestr(extra_name, extra_data)
    return stream.getvalue()


def test_local_resource_path_cannot_escape_markdown_directory(tmp_path: Path):
    base = tmp_path / "document"
    base.mkdir()
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"not needed")
    resolver = ResourceResolver(base, ResourcePolicy(), ImageConfig())

    try:
        with pytest.raises(MddocxError, match="escapes the Markdown directory") as exc:
            resolver.resolve("../secret.png")
        assert exc.value.diagnostic.code == "RESOURCE203"
    finally:
        resolver.close()


def test_remote_resources_are_disabled_by_default(tmp_path: Path):
    resolver = ResourceResolver(tmp_path, ResourcePolicy(), ImageConfig())

    try:
        with pytest.raises(MddocxError) as exc:
            resolver.resolve("https://example.com/image.png")
        assert exc.value.diagnostic.code == "RESOURCE201"
    finally:
        resolver.close()


def test_private_remote_addresses_and_unlisted_domains_are_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    resolver = ResourceResolver(
        tmp_path,
        ResourcePolicy(allow_remote_resources=True, allowed_domains=("example.com",)),
        ImageConfig(),
    )

    try:
        with pytest.raises(MddocxError) as domain_error:
            resolver._validate_remote_url("https://attacker.invalid/a.png")
        assert domain_error.value.diagnostic.code == "RESOURCE209"
        with pytest.raises(MddocxError) as private_error:
            resolver._validate_remote_url("https://example.com/a.png")
        assert private_error.value.diagnostic.code == "RESOURCE211"
    finally:
        resolver.close()


def test_docx_validation_rejects_traversal_macros_and_oversized_xml():
    with pytest.raises(MddocxError) as traversal:
        validate_docx_package(_package("../escape.xml"), ValidationConfig())
    assert traversal.value.diagnostic.code == "DOCX404"

    with pytest.raises(MddocxError) as macros:
        validate_docx_package(_package("word/vbaProject.bin"), ValidationConfig())
    assert macros.value.diagnostic.code == "DOCX408"

    with pytest.raises(MddocxError) as oversized:
        validate_docx_package(
            _package("word/large.xml", b"<root>" + b"x" * 100 + b"</root>"),
            ValidationConfig(max_xml_part_size=50),
        )
    assert oversized.value.diagnostic.code == "DOCX405"


def test_ai_metadata_cleaning_preserves_render_config_and_code_examples():
    markdown = """---
conversation_id: secret-chat
title: Exported conversation
model: example-model
theme: modern
toc: true
---

# Authored content

```yaml
conversation_id: example-inside-code
model: should-stay
```
"""
    result = sanitize_markdown_metadata(markdown, MetadataConfig(ai_export="auto"))

    assert result.report.detected_export_metadata
    assert "conversation_id: secret-chat" not in result.markdown
    assert "title: Exported conversation" not in result.markdown
    assert "model: example-model" not in result.markdown
    assert "theme: modern" in result.markdown
    assert "toc: true" in result.markdown
    assert "conversation_id: example-inside-code" in result.markdown
    assert "model: should-stay" in result.markdown


def test_keep_policy_does_not_mutate_ai_export():
    markdown = "---\nconversation_id: abc\ntitle: Keep me\n---\n\nBody"
    result = sanitize_markdown_metadata(markdown, MetadataConfig(ai_export="keep"))

    assert result.markdown == markdown
    assert not result.report.changed


def test_redirect_limit_and_external_svg_references_are_blocked(tmp_path: Path):
    resolver = ResourceResolver(
        tmp_path,
        ResourcePolicy(
            allow_remote_resources=True,
            allow_private_hosts=True,
            max_redirects=0,
        ),
        ImageConfig(),
    )
    svg = tmp_path / "external.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>',
        encoding="utf-8",
    )
    try:
        handler = _SafeRedirectHandler(resolver)
        with pytest.raises(MddocxError) as redirect:
            handler.redirect_request(None, None, 302, "Found", {}, "https://example.com/b.png")
        assert redirect.value.diagnostic.code == "RESOURCE210"

        with pytest.raises(MddocxError) as external:
            resolver._convert_svg(svg)
        assert external.value.diagnostic.code == "IMAGE207"
    finally:
        resolver.close()
