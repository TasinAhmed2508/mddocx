from __future__ import annotations

import hashlib
from pathlib import Path

from .ast.base import Document
from .ast.codec import document_from_json, document_to_json
from .config import CacheConfig

_AST_CACHE_SCHEMA = "mddocx-ast-v2"


class AstCache:
    def __init__(self, config: CacheConfig, base_dir: Path):
        self.config = config
        root = config.directory or (base_dir / ".mddocx-cache")
        self.directory = Path(root).expanduser().resolve()

    def key(self, markdown: str, source_file: str | None) -> str:
        digest = hashlib.sha256()
        digest.update(_AST_CACHE_SCHEMA.encode("ascii"))
        digest.update(b"\0")
        digest.update((source_file or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(markdown.encode("utf-8"))
        return digest.hexdigest()

    def load(self, key: str) -> Document | None:
        path = self.directory / f"{key}.json"
        try:
            if not path.is_file() or path.stat().st_size > self.config.max_entry_bytes:
                return None
            return document_from_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, UnicodeError):
            return None

    def save(self, key: str, document: Document) -> None:
        text = document_to_json(document)
        data = text.encode("utf-8")
        if len(data) > self.config.max_entry_bytes:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{key}.json"
        temp = self.directory / f".{key}.tmp"
        temp.write_bytes(data)
        temp.replace(target)
