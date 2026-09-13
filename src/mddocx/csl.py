from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from mddocx.bibliography import BibliographyEntry


class CslUnavailable(RuntimeError):
    pass


def available() -> bool:
    try:
        import citeproc  # noqa: F401
    except ImportError:
        return False
    return True


class CslProcessor:
    """Small adapter isolating citeproc-py's optional API from the compiler."""

    def __init__(self, style_file: str | Path, entries: Iterable["BibliographyEntry"]):
        try:
            from citeproc import CitationStylesBibliography, CitationStylesStyle, formatter
            from citeproc.source.json import CiteProcJSON
        except ImportError as exc:
            raise CslUnavailable(
                "Install mddocx-native[academic] for arbitrary CSL styles"
            ) from exc
        source = CiteProcJSON([self._json_entry(entry) for entry in entries])
        style = CitationStylesStyle(str(style_file), validate=False)
        self._processor = CitationStylesBibliography(style, source, formatter.plain)
        self._citations: dict[tuple[str, ...], object] = {}
        self._registered: set[str] = set()

    @staticmethod
    def _json_entry(entry: "BibliographyEntry") -> dict:
        authors = []
        for name in entry.authors:
            if "," in name:
                family, given = (part.strip() for part in name.split(",", 1))
            else:
                parts = name.split()
                family, given = (parts[-1], " ".join(parts[:-1])) if parts else ("", "")
            authors.append({"family": family, "given": given})
        data = {
            "id": entry.key,
            "type": "article-journal" if entry.journal else "book",
            "title": entry.title,
            "author": authors,
            "issued": {"date-parts": [[entry.year]]},
            "container-title": entry.journal,
            "publisher": entry.publisher,
            "DOI": entry.doi,
            "URL": entry.url,
        }
        return {key: value for key, value in data.items() if value not in ("", [], None)}

    def cite(self, keys: list[str], suffix: str | None = None) -> str:
        from citeproc import Citation, CitationItem

        identity = tuple(keys) + ((suffix or ""),)
        citation = self._citations.get(identity)
        if citation is None:
            items = [
                CitationItem(key, suffix=suffix) if suffix else CitationItem(key) for key in keys
            ]
            citation = Citation(items)
            self._processor.register(citation)
            self._citations[identity] = citation
            self._registered.update(keys)
        return str(self._processor.cite(citation, lambda _item: None))

    def bibliography(self, keys: Iterable[str]) -> list[tuple[str, str]]:
        from citeproc import Citation, CitationItem

        for key in keys:
            if key not in self._registered:
                self._processor.register(Citation([CitationItem(key)]))
                self._registered.add(key)
        rendered = self._processor.bibliography()
        return [
            (key, "".join(str(part) for part in item))
            for key, item in zip(self._processor.keys, rendered)
        ]
