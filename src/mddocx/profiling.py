from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(slots=True)
class RenderStats:
    parse_ms: float = 0.0
    normalize_ms: float = 0.0
    render_ms: float = 0.0
    total_ms: float = 0.0
    peak_memory_bytes: int | None = None
    output_bytes: int = 0
    output_sha256: str | None = None
    ast_cache_hit: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
