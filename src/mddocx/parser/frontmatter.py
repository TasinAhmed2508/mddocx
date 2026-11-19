from __future__ import annotations

from typing import Any

from mddocx.diagnostics import Diagnostic, MddocxError


def split_front_matter(
    markdown: str, *, source_file: str | None = None
) -> tuple[dict[str, Any], str, int]:
    """Return (metadata, body, body_line_offset) for YAML-style front matter.

    PyYAML is used when available. A deterministic scalar fallback keeps the core
    library usable without adding a hard YAML runtime dependency.

    An unparseable block raises ``MddocxError(PARSE353)`` naming the offending
    file and line, so malformed settings never surface as a raw PyYAML
    traceback.
    """
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, markdown, 0

    close_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() in {"---", "..."}:
            close_index = idx
            break
    if close_index is None:
        return {}, markdown, 0

    raw = "".join(lines[1:close_index])
    data: dict[str, Any]
    try:
        import yaml  # type: ignore
    except ImportError:
        data = _fallback_yaml(raw)
    else:
        try:
            loaded = yaml.safe_load(raw)
        except Exception as exc:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "PARSE353",
                    f"Unable to parse YAML front matter: {type(exc).__name__}",
                    source_file,
                    _error_line(exc),
                    "Fix or remove the YAML block between the leading '---' fences.",
                )
            ) from exc
        data = loaded if isinstance(loaded, dict) else {}

    body = "".join(lines[close_index + 1 :])
    return data, body, close_index + 1


def _error_line(exc: Exception) -> int | None:
    """Return the 1-based body line a PyYAML failure points at, when known."""
    mark = getattr(exc, "problem_mark", None)
    line = getattr(mark, "line", None)
    return line + 2 if isinstance(line, int) else None


def _fallback_yaml(raw: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        result[key] = _scalar(value)
    return result


def _scalar(value: str) -> Any:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    low = value.lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    if low in {"null", "none", "~", ""}:
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value
