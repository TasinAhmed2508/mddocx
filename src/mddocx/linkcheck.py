from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import json
import re
import socket
from typing import Iterable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from mddocx.bibliography import BibliographyDatabase, canonical_doi

LinkStatus = Literal[
    "reachable", "redirected", "unverified", "missing", "timeout", "malformed", "skipped"
]


@dataclass(slots=True, frozen=True)
class LinkCheckResult:
    url: str
    status: LinkStatus
    status_code: int | None = None
    final_url: str | None = None
    detail: str = ""

    @property
    def broken(self) -> bool:
        return self.status in {"missing", "malformed"}


def collect_links(markdown: str, bibliography: BibliographyDatabase | None = None) -> list[str]:
    found = [
        m.group(1)
        for m in re.finditer(r"(?<!!)\[[^\]]*\]\((https?://[^\s)]+)(?:\s+[^)]*)?\)", markdown)
    ]
    found += [m.group(1) for m in re.finditer(r"<(https?://[^>]+)>", markdown)]
    found += [
        m.group(0) for m in re.finditer(r"(?<![\w/])(10\.\d{4,9}/[^\s\])}>]+)", markdown, re.I)
    ]
    if bibliography:
        for entry in bibliography.entries.values():
            target = canonical_doi(entry.doi) or entry.url.strip()
            if target:
                found.append(target)
    return list(dict.fromkeys(canonical_doi(value) or value for value in found))


class LinkChecker:
    def __init__(
        self,
        timeout: float = 8.0,
        offline: bool = False,
        user_agent: str = "mddocx-link-check/1.3",
        concurrency: int = 8,
    ):
        self.timeout, self.offline, self.user_agent = timeout, offline, user_agent
        self.concurrency = max(1, min(concurrency, 32))
        self._cache: dict[str, LinkCheckResult] = {}

    def check(self, url: str) -> LinkCheckResult:
        if url in self._cache:
            return self._cache[url]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            result = LinkCheckResult(url, "malformed", detail="Expected an HTTP(S) URL")
        elif self.offline:
            result = LinkCheckResult(url, "skipped", detail="Offline mode")
        else:
            result = self._request(url)
        self._cache[url] = result
        return result

    def _request(self, url: str) -> LinkCheckResult:
        try:
            request = Request(
                url, method="GET", headers={"User-Agent": self.user_agent, "Range": "bytes=0-0"}
            )
            with urlopen(request, timeout=self.timeout) as response:
                code, final = response.status, response.geturl()
                return LinkCheckResult(
                    url, "redirected" if final != url else "reachable", code, final
                )
        except HTTPError as exc:
            if exc.code in {401, 403, 429}:
                return LinkCheckResult(url, "unverified", exc.code, exc.geturl(), str(exc.reason))
            status: LinkStatus = "missing" if exc.code in {404, 410} else "unverified"
            return LinkCheckResult(url, status, exc.code, exc.geturl(), str(exc.reason))
        except (TimeoutError, socket.timeout):
            return LinkCheckResult(url, "timeout", detail="Request timed out")
        except (URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            status: LinkStatus = (
                "timeout" if isinstance(reason, (TimeoutError, socket.timeout)) else "unverified"
            )
            return LinkCheckResult(url, status, detail=str(reason))

    def check_all(self, urls: Iterable[str]) -> list[LinkCheckResult]:
        unique = list(dict.fromkeys(urls))
        if self.offline or len(unique) < 2:
            return [self.check(url) for url in unique]
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            return list(executor.map(self.check, unique))


def results_json(results: Iterable[LinkCheckResult]) -> str:
    return json.dumps([asdict(result) | {"broken": result.broken} for result in results], indent=2)


def results_text(results: Iterable[LinkCheckResult]) -> str:
    return "\n".join(f"{result.status.upper():10} {result.url}" for result in results)
