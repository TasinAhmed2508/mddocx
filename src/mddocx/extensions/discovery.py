from __future__ import annotations

from importlib import metadata
from inspect import isclass
from typing import Any

from mddocx.diagnostics import Diagnostic, MddocxError


def load_entrypoint_extensions(names: tuple[str, ...], group: str = "mddocx.extensions") -> tuple[Any, ...]:
    """Load only explicitly named extensions from Python entry points.

    No installed extension is imported unless its name is present in ``names``.
    """
    if not names:
        return ()
    requested = list(dict.fromkeys(names))
    available = metadata.entry_points()
    selected = available.select(group=group) if hasattr(available, "select") else available.get(group, [])
    by_name: dict[str, list[Any]] = {}
    for entrypoint in selected:
        by_name.setdefault(entrypoint.name, []).append(entrypoint)

    loaded: list[Any] = []
    for name in requested:
        matches = by_name.get(name, [])
        if not matches:
            raise MddocxError(Diagnostic("error", "PLUGIN401", f"Extension entry point not found: {name}"))
        if len(matches) > 1:
            raise MddocxError(Diagnostic("error", "PLUGIN402", f"Multiple extension entry points share the name: {name}"))
        try:
            value = matches[0].load()
            loaded.append(value() if isclass(value) else value)
        except MddocxError:
            raise
        except Exception as exc:
            raise MddocxError(Diagnostic("error", "PLUGIN403", f"Unable to load extension entry point: {name}")) from exc
    return tuple(loaded)
