from __future__ import annotations

import re

from .macros import expand_newcommands
from .models import NormalizedEquation

_ALIASES = {
    r"\dfrac": r"\frac",
    r"\tfrac": r"\frac",
    r"\textnormal": r"\text",
    r"\rm": r"\mathrm",
}
_INVISIBLE = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}
_TAG = re.compile(r"(?<!\\)\\tag\*?\s*\{([^{}]*)\}\s*$")
_PRESCRIPT = re.compile(r"(?<!\\)\\prescript(?![A-Za-z])")


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
    expanded = expand_newcommands(text)
    if expanded != text:
        text = expanded
        repairs.append("expanded equation-local macros")
    for old, new in _ALIASES.items():
        pattern = re.compile(re.escape(old) + r"(?![A-Za-z])")
        replaced = pattern.sub(lambda _: new, text)
        if replaced != text:
            text = replaced
            repairs.append(f"normalized {old} to {new}")
    rewritten = _rewrite_prescripts(text)
    if rewritten != text:
        text = rewritten
        repairs.append("normalized prescript")
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


def _rewrite_prescripts(text: str) -> str:
    cursor = 0
    pieces: list[str] = []
    for match in _PRESCRIPT.finditer(text):
        if match.start() < cursor:
            continue
        start = match.end()
        groups: list[str] = []
        for _ in range(3):
            while start < len(text) and text[start].isspace():
                start += 1
            if start == len(text) or text[start] != "{":
                break
            depth, escaped = 1, False
            for end in range(start + 1, len(text)):
                char = text[end]
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        groups.append(text[start + 1 : end])
                        start = end + 1
                        break
            else:
                break
        if len(groups) == 3:
            sup, sub, base = groups
            pieces.extend([text[cursor : match.start()], f"{{}}_{{{sub}}}^{{{sup}}}{{{base}}}"])
            cursor = start
    return "".join(pieces) + text[cursor:]


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
