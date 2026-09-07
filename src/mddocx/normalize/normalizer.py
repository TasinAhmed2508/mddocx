from __future__ import annotations
from mddocx.ast.base import Document


class Normalizer:
    """Stable normalization boundary. Phase 1 parser already emits canonical nodes."""

    def normalize(self, document: Document) -> Document:
        return document
