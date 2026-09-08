from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re


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
        first = self.authors[0]
        surname = first.split(",", 1)[0].strip() if "," in first else first.split()[-1]
        if len(self.authors) == 1:
            return surname
        if len(self.authors) == 2:
            second = (
                self.authors[1].split(",", 1)[0].strip()
                if "," in self.authors[1]
                else self.authors[1].split()[-1]
            )
            return f"{surname} & {second}"
        return f"{surname} et al."


class BibliographyDatabase:
    def __init__(self, entries: dict[str, BibliographyEntry] | None = None):
        self.entries = entries or {}

    @classmethod
    def load(cls, path: str | Path | None) -> "BibliographyDatabase":
        if path is None:
            return cls()
        path = Path(path)
        if not path.is_file():
            return cls()
        if path.suffix.lower() in {".json", ".csljson"}:
            return cls._from_csl_json(json.loads(path.read_text(encoding="utf-8")))
        return cls._from_bibtex(path.read_text(encoding="utf-8"))

    @classmethod
    def _from_csl_json(cls, data) -> "BibliographyDatabase":
        items = (
            data
            if isinstance(data, list)
            else list(data.values())
            if isinstance(data, dict)
            else []
        )
        entries = {}
        for item in items:
            key = str(item.get("id") or item.get("citation-key") or "").strip()
            if not key:
                continue
            authors = []
            for a in item.get("author", []) or []:
                family, given = a.get("family", ""), a.get("given", "")
                authors.append(f"{family}, {given}".strip(", "))
            issued = item.get("issued", {}).get("date-parts", [["n.d."]])
            year = str(issued[0][0]) if issued and issued[0] else "n.d."
            entries[key] = BibliographyEntry(
                key,
                str(item.get("title", "")),
                authors,
                year,
                str(item.get("container-title", "")),
                str(item.get("publisher", "")),
                str(item.get("DOI", "")),
                str(item.get("URL", "")),
            )
        return cls(entries)

    @classmethod
    def _from_bibtex(cls, text: str) -> "BibliographyDatabase":
        entries: dict[str, BibliographyEntry] = {}
        pos = 0
        while True:
            m = re.search(r"@(\w+)\s*\{\s*([^,]+),", text[pos:], re.S)
            if not m:
                break
            absolute_start = pos + m.start()
            body_start = pos + m.end()
            depth = 1
            i = body_start
            in_quote = False
            escaped = False
            while i < len(text) and depth:
                ch = text[i]
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_quote = not in_quote
                elif not in_quote:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                i += 1
            body = text[body_start : i - 1] if depth == 0 else text[body_start:]
            key = m.group(2).strip()
            fields: dict[str, str] = {}
            fm_re = re.compile(
                r"(\w[\w-]*)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\"|([^,\n]+))\s*,?",
                re.S,
            )
            for fm in fm_re.finditer(body):
                fields[fm.group(1).lower()] = (
                    (fm.group(2) or fm.group(3) or fm.group(4) or "").strip().replace("\n", " ")
                )
            authors = [
                a.strip()
                for a in re.split(r"\s+and\s+", fields.get("author", ""), flags=re.I)
                if a.strip()
            ]
            entries[key] = BibliographyEntry(
                key=key,
                title=fields.get("title", "").strip("{}"),
                authors=authors,
                year=fields.get("year", "n.d."),
                journal=fields.get("journal", fields.get("booktitle", "")),
                publisher=fields.get("publisher", ""),
                doi=fields.get("doi", ""),
                url=fields.get("url", ""),
            )
            pos = i if i > absolute_start else absolute_start + 1
        return cls(entries)

    def cite(self, keys: list[str], style: str = "author-year", suffix: str | None = None) -> str:
        found = [self.entries.get(k) for k in keys]
        if style in {"ieee", "numeric"}:
            values = [
                str(list(self.entries).index(k) + 1) if k in self.entries else "?" for k in keys
            ]
            text = "[" + ", ".join(values) + "]"
        else:
            pieces = [f"{e.author_short}, {e.year}" if e else k for k, e in zip(keys, found)]
            text = "(" + "; ".join(pieces) + ")"
        if suffix:
            text = text[:-1] + f", {suffix}" + text[-1]
        return text

    def formatted_entries(self, style: str = "author-year") -> list[tuple[str, str]]:
        items = list(self.entries.values())
        if style in {"ieee", "numeric"}:
            return [(e.key, f"[{i}] {self._format_entry(e)}") for i, e in enumerate(items, 1)]
        items.sort(key=lambda e: (e.author_short.lower(), e.year, e.title.lower()))
        return [(e.key, self._format_entry(e)) for e in items]

    @staticmethod
    def _format_entry(e: BibliographyEntry) -> str:
        authors = "; ".join(e.authors) if e.authors else e.key
        parts = [
            f"{authors} ({e.year}).",
            e.title + ("." if e.title and not e.title.endswith(".") else ""),
        ]
        if e.journal:
            parts.append(e.journal + ".")
        elif e.publisher:
            parts.append(e.publisher + ".")
        if e.doi:
            parts.append("https://doi.org/" + e.doi)
        elif e.url:
            parts.append(e.url)
        return " ".join(p for p in parts if p).strip()
