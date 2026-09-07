from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RecentDocument:
    source: str
    output: str
    action: str
    workspace: str
    created_at: str
    settings: dict[str, Any]


def state_directory() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "mddocx"
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "mddocx"
    return Path.home() / ".local" / "state" / "mddocx"


def recent_path() -> Path:
    return state_directory() / "recent.json"


def repl_history_path() -> Path:
    return state_directory() / "shell-history.txt"


def load_recent(limit: int = 20) -> list[RecentDocument]:
    path = recent_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(raw, list):
        return []
    items: list[RecentDocument] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            items.append(
                RecentDocument(
                    source=str(item.get("source", "")),
                    output=str(item.get("output", "")),
                    action=str(item.get("action", "render")),
                    workspace=str(item.get("workspace", "")),
                    created_at=str(item.get("created_at", "")),
                    settings=dict(item.get("settings") or {}),
                )
            )
        except (TypeError, ValueError):
            continue
    return items[: max(0, limit)]


def add_recent(
    *,
    source: Path,
    output: Path,
    action: str,
    workspace: Path,
    settings: dict[str, Any] | None = None,
    limit: int = 30,
) -> None:
    """Persist paths/settings only. Never persist document content."""
    entry = RecentDocument(
        source=str(source.resolve()),
        output=str(output.resolve()),
        action=action,
        workspace=str(workspace.resolve()),
        created_at=datetime.now(timezone.utc).isoformat(),
        settings=dict(settings or {}),
    )
    existing = load_recent(limit=limit)
    key = (entry.source.casefold(), entry.output.casefold(), entry.action)
    kept = [x for x in existing if (x.source.casefold(), x.output.casefold(), x.action) != key]
    payload = [asdict(entry), *(asdict(x) for x in kept[: max(0, limit - 1)])]
    path = recent_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        # Recent history is a convenience feature and must never make rendering fail.
        return
