from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Iterable
from xml.etree import ElementTree

from mddocx.csl import CslProcessor, CslUnavailable

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.I)


def canonical_doi(value: str) -> str:
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I)
    doi = doi.rstrip(".,; ")
    return f"https://doi.org/{doi}" if _DOI_RE.fullmatch(doi) else ""


@dataclass(slots=True, frozen=True)
class BibliographySegment:
    text: str
    href: str | None = None


@dataclass(slots=True)
class BibliographyEntry:
    key: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = "n.d."
    journal: str = ""
    publisher: str = ""
    doi: str = ""
    url: str = ""

    @property
    def author_short(self) -> str:
        if not self.authors:
            return self.key
        surnames = [a.split(",", 1)[0].strip() if "," in a else a.split()[-1] for a in self.authors]
        if len(surnames) == 1:
            return surnames[0]
        if len(surnames) == 2:
            return f"{surnames[0]} & {surnames[1]}"
        return f"{surnames[0]} et al."


class BibliographyDatabase:
    def __init__(self, entries: dict[str, BibliographyEntry] | None = None):
        self.entries = entries or {}
        self.diagnostics: list[str] = []
        self._citation_order: list[str] = []
        self._csl: CslProcessor | None = None
        self._find_doi_conflicts()

    def resolve_style(self, requested: str, style_file: str | Path | None = None) -> str:
        """Validate a local CSL file and select its supported bundled rendering profile."""
        if style_file is None:
            return requested
        path = Path(style_file)
        if not path.is_file():
            self.diagnostics.append(f"CITE205 CSL style file not found: {path}")
            return requested
        try:
            root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
        except (OSError, ElementTree.ParseError) as exc:
            self.diagnostics.append(f"CITE205 Invalid CSL style {path}: {exc}")
            return requested
        if root.tag.rsplit("}", 1)[-1] != "style":
            self.diagnostics.append(f"CITE205 Invalid CSL style root in {path}")
            return requested
        try:
            self._csl = CslProcessor(path, self.entries.values())
            return "csl-local"
        except (CslUnavailable, ValueError, OSError) as exc:
            self.diagnostics.append(f"CITE206 Could not activate CSL style {path}: {exc}")
        return requested

    @classmethod
    def load(cls, path: str | Path | None) -> "BibliographyDatabase":
        if path is None or not Path(path).is_file():
            return cls()
        source = Path(path)
        if source.suffix.lower() in {".json", ".csljson"}:
            return cls._from_csl_json(json.loads(source.read_text(encoding="utf-8")))
        return cls._from_bibtex(source.read_text(encoding="utf-8"))

    @classmethod
    def _from_csl_json(cls, data) -> "BibliographyDatabase":
        items = (
            data
            if isinstance(data, list)
            else list(data.values())
            if isinstance(data, dict)
            else []
        )
        entries: dict[str, BibliographyEntry] = {}
        for item in items:
            key = str(item.get("id") or item.get("citation-key") or "").strip()
            if not key:
                continue
            authors = [
                f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                for a in item.get("author", []) or []
            ]
            issued = item.get("issued", {}).get("date-parts", [["n.d."]])
            entries[key] = BibliographyEntry(
                key,
                str(item.get("title", "")),
                authors,
                str(issued[0][0]) if issued and issued[0] else "n.d.",
                str(item.get("container-title", "")),
                str(item.get("publisher", "")),
                str(item.get("DOI", "")),
                str(item.get("URL", "")),
            )
        return cls(entries)

    @classmethod
    def _from_bibtex(cls, text: str) -> "BibliographyDatabase":
        entries: dict[str, BibliographyEntry] = {}
        header = re.compile(r"@(\w+)\s*\{\s*([^,]+),", re.S)
        pos = 0
        while match := header.search(text, pos):
            start, depth, quoted, escaped, i = match.end(), 1, False, False, match.end()
            while i < len(text) and depth:
                char = text[i]
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = not quoted
                elif not quoted:
                    depth += char == "{"
                    depth -= char == "}"
                i += 1
            fields = cls._bib_fields(text[start : i - 1] if depth == 0 else text[start:])
            key = match.group(2).strip()
            authors = [
                a.strip()
                for a in re.split(r"\s+and\s+", fields.get("author", ""), flags=re.I)
                if a.strip()
            ]
            entries[key] = BibliographyEntry(
                key,
                fields.get("title", "").strip("{}"),
                authors,
                fields.get("year", "n.d."),
                fields.get("journal", fields.get("booktitle", "")),
                fields.get("publisher", ""),
                fields.get("doi", ""),
                fields.get("url", ""),
            )
            pos = max(i, match.end())
        return cls(entries)

    @staticmethod
    def _bib_fields(body: str) -> dict[str, str]:
        pattern = re.compile(
            r"(\w[\w-]*)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\"|([^,\n]+))\s*,?", re.S
        )
        return {
            m.group(1).lower(): (m.group(2) or m.group(3) or m.group(4) or "")
            .strip()
            .replace("\n", " ")
            for m in pattern.finditer(body)
        }

    def _find_doi_conflicts(self) -> None:
        seen: dict[str, BibliographyEntry] = {}
        for entry in self.entries.values():
            doi = canonical_doi(entry.doi)
            if doi and doi in seen and seen[doi].key != entry.key:
                self.diagnostics.append(
                    f"CITE203 DOI {doi} is shared by {seen[doi].key} and {entry.key}"
                )
            elif doi:
                seen[doi] = entry
            if entry.doi and not doi:
                self.diagnostics.append(f"CITE204 Invalid DOI for {entry.key}: {entry.doi}")

    def cite(self, keys: list[str], style: str = "author-year", suffix: str | None = None) -> str:
        for key in keys:
            if key in self.entries and key not in self._citation_order:
                self._citation_order.append(key)
        if style == "csl-local" and self._csl is not None:
            return self._csl.cite(keys, suffix)
        if style in {"ieee", "numeric"}:
            values = [
                str(self._citation_order.index(k) + 1) if k in self._citation_order else "?"
                for k in keys
            ]
            text = "[" + ", ".join(values) + "]"
        else:
            text = (
                "("
                + "; ".join(
                    f"{e.author_short}, {e.year}" if (e := self.entries.get(k)) else k for k in keys
                )
                + ")"
            )
        return text[:-1] + f", {suffix}" + text[-1] if suffix else text

    def formatted_entries(
        self, style: str = "author-year", keys: Iterable[str] | None = None
    ) -> list[tuple[str, str]]:
        return [
            (key, "".join(s.text for s in parts))
            for key, parts in self.formatted_segments(style, keys)
        ]

    def formatted_segments(
        self, style: str = "author-year", keys: Iterable[str] | None = None
    ) -> list[tuple[str, tuple[BibliographySegment, ...]]]:
        selected = [
            self.entries[k] for k in dict.fromkeys(keys or self.entries) if k in self.entries
        ]
        if style == "csl-local" and self._csl is not None:
            return [
                (key, self._linkify(text))
                for key, text in self._csl.bibliography(entry.key for entry in selected)
            ]
        numeric = style in {"ieee", "numeric"}
        if numeric:
            order = self._citation_order + [
                e.key for e in selected if e.key not in self._citation_order
            ]
            selected.sort(key=lambda e: order.index(e.key))
        else:
            selected.sort(
                key=lambda e: (e.author_short.casefold(), e.year, e.title.casefold(), e.key)
            )
        return [
            (e.key, self._segments(e, style, i if numeric else None))
            for i, e in enumerate(selected, 1)
        ]

    @staticmethod
    def _linkify(text: str) -> tuple[BibliographySegment, ...]:
        parts: list[BibliographySegment] = []
        pos = 0
        for match in re.finditer(r"https?://[^\s]+", text):
            if match.start() > pos:
                parts.append(BibliographySegment(text[pos : match.start()]))
            target = match.group(0).rstrip(".,;)")
            parts.append(BibliographySegment(target, target))
            if suffix := match.group(0)[len(target) :]:
                parts.append(BibliographySegment(suffix))
            pos = match.end()
        if pos < len(text):
            parts.append(BibliographySegment(text[pos:]))
        return tuple(parts) or (BibliographySegment(""),)

    @staticmethod
    def _segments(
        e: BibliographyEntry, style: str, number: int | None
    ) -> tuple[BibliographySegment, ...]:
        authors = "; ".join(e.authors) if e.authors else e.key
        if style in {"ieee", "numeric"}:
            lead = f"[{number}] {authors}, “{e.title}.”"
        elif style in {"chicago", "chicago-author-date"}:
            lead = f"{authors}. {e.year}. “{e.title}.”"
        else:
            lead = f"{authors} ({e.year}). {e.title}{'' if e.title.endswith('.') else '.'}"
        venue = e.journal or e.publisher
        lead += f" {venue}." if venue else ""
        target = canonical_doi(e.doi) or e.url.strip()
        parts = [BibliographySegment(lead.strip())]
        if target:
            parts += [BibliographySegment(" "), BibliographySegment(target, target)]
        return tuple(parts)
