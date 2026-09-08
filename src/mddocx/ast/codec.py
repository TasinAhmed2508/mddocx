from __future__ import annotations

from dataclasses import fields
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from .base import Document, Node, SourcePosition
from .block import (
    BlockQuote,
    BulletList,
    CodeBlock,
    Heading,
    HorizontalRule,
    ImageBlock,
    ListItem,
    MathBlock,
    OrderedList,
    PageBreak,
    Paragraph,
    SectionBreak,
    Table,
    TableCell,
    TableRow,
    ChartBlock,
    DataTableBlock,
    BibliographyBlock,
    DefinitionList,
    DefinitionItem,
    Callout,
)
from .inline import (
    Emphasis,
    HardBreak,
    Image,
    InlineCode,
    InlineMath,
    Link,
    SoftBreak,
    Strikethrough,
    Strong,
    Text,
    FootnoteReference,
    CrossReference,
    Citation,
    Comment,
)

_NODE_TYPES = {
    cls.__name__: cls
    for cls in (
        Document,
        Heading,
        Paragraph,
        BlockQuote,
        BulletList,
        OrderedList,
        ListItem,
        CodeBlock,
        MathBlock,
        Table,
        TableRow,
        TableCell,
        ImageBlock,
        ChartBlock,
        DataTableBlock,
        BibliographyBlock,
        DefinitionList,
        DefinitionItem,
        Callout,
        HorizontalRule,
        PageBreak,
        SectionBreak,
        Text,
        Strong,
        Emphasis,
        Strikethrough,
        InlineCode,
        Link,
        InlineMath,
        CrossReference,
        Citation,
        Comment,
        SoftBreak,
        HardBreak,
        Image,
        FootnoteReference,
    )
}

AST_SCHEMA_NAME = "mddocx-ast"
AST_SCHEMA_VERSION = 2


def document_to_json(document: Document) -> str:
    payload = {
        "schema": AST_SCHEMA_NAME,
        "version": AST_SCHEMA_VERSION,
        "document": _encode(document),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def document_from_json(text: str) -> Document:
    payload = json.loads(text)
    if not isinstance(payload, dict) or payload.get("schema") != AST_SCHEMA_NAME:
        raise ValueError("Cached AST has no recognized schema identifier.")
    if payload.get("version") != AST_SCHEMA_VERSION:
        raise ValueError(
            f"Cached AST schema version {payload.get('version')!r} is not supported; "
            f"expected {AST_SCHEMA_VERSION}."
        )
    value = _decode(payload.get("document"))
    if not isinstance(value, Document):
        raise ValueError("Cached AST root is not a Document.")
    return value


def _encode(value: Any) -> Any:
    if isinstance(value, Node):
        return {
            "__node__": type(value).__name__,
            **{f.name: _encode(getattr(value, f.name)) for f in fields(value)},
        }
    if isinstance(value, SourcePosition):
        return {
            "__source__": True,
            **{f.name: _encode(getattr(value, f.name)) for f in fields(value)},
        }
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, date):
        return {"__date__": value.isoformat()}
    if isinstance(value, Path):
        return {"__path__": str(value)}
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported AST cache value: {type(value).__name__}")


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if "__node__" in value:
        name = value["__node__"]
        cls = _NODE_TYPES.get(name)
        if cls is None:
            raise ValueError(f"Unknown cached AST node: {name}")
        kwargs = {k: _decode(v) for k, v in value.items() if k != "__node__"}
        return cls(**kwargs)
    if value.get("__source__") is True:
        return SourcePosition(**{k: _decode(v) for k, v in value.items() if k != "__source__"})
    if "__datetime__" in value:
        return datetime.fromisoformat(value["__datetime__"])
    if "__date__" in value:
        return date.fromisoformat(value["__date__"])
    if "__path__" in value:
        return Path(value["__path__"])
    return {k: _decode(v) for k, v in value.items()}
