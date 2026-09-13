from __future__ import annotations

import re

from .models import NormalizedEquation

_ALIASES = {
    r"\dfrac": r"\frac",
    r"\tfrac": r"\frac",
    r"\textnormal": r"\text",
    r"\rm": r"\mathrm",
}
_INVISIBLE = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}
_TAG = re.compile(r"(?<!\\)\\tag\*?\s*\{([^{}]*)\}\s*$")


def normalize_equation(source: str) -> NormalizedEquation:
    """Apply conservative, meaning-preserving compatibility repairs."""
    text = source.strip()
    repairs: list[str] = []
    stripped = _strip_one_delimiter(text)
    if stripped != text:
        text = stripped.strip()
        repairs.append("stripped outer math delimiter")
    if "−" in text:
        text = text.replace("−", "-")
        repairs.append("normalized Unicode minus")
    cleaned = "".join(char for char in text if char not in _INVISIBLE)
    if cleaned != text:
        text = cleaned
        repairs.append("removed invisible formatting characters")
    for old, new in _ALIASES.items():
        pattern = re.compile(re.escape(old) + r"(?![A-Za-z])")
        replaced = pattern.sub(lambda _: new, text)
        if replaced != text:
            text = replaced
            repairs.append(f"normalized {old} to {new}")
    label = None
    match = _TAG.search(text)
    if match:
        label = match.group(1).strip() or None
        # Keep the tag in the compatibility input until the renderer owns Word SEQ fields.
        # Recording it separately lets that migration happen without losing legacy output.
        repairs.append("identified equation tag")
    missing = _missing_closing_braces(text)
    if missing:
        text += "}" * missing
        repairs.append(f"balanced {missing} missing closing brace(s)")
    return NormalizedEquation(source, text, tuple(repairs), label)


def _strip_one_delimiter(text: str) -> str:
    pairs = (("$$", "$$"), (r"\[", r"\]"), (r"\(", r"\)"), ("$", "$"))
    for opening, closing in pairs:
        if (
            text.startswith(opening)
            and text.endswith(closing)
            and len(text) > len(opening) + len(closing)
        ):
            return text[len(opening) : -len(closing)]
    return text


def _missing_closing_braces(text: str) -> int:
    depth = 0
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return 0
    return depth if 0 < depth <= 3 else 0
