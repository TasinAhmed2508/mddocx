from __future__ import annotations

from dataclasses import dataclass, field
import re
import shlex

_ATTR_RE = re.compile(r"\{(?P<body>[^{}]+)\}\s*$")


@dataclass(slots=True)
class Attributes:
    identifier: str | None = None
    classes: tuple[str, ...] = ()
    values: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.values.get(key, default)

    def bool(self, key: str, default: bool = False) -> bool:
        value = self.values.get(key)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_attribute_list(text: str) -> Attributes:
    text = text.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return Attributes()
    body = text[1:-1].strip()
    identifier: str | None = None
    classes: list[str] = []
    values: dict[str, str] = {}
    try:
        tokens = shlex.split(body)
    except ValueError:
        tokens = body.split()
    for token in tokens:
        if token.startswith("#") and len(token) > 1:
            identifier = token[1:]
        elif token.startswith(".") and len(token) > 1:
            classes.append(token[1:])
        elif "=" in token:
            key, value = token.split("=", 1)
            values[key.strip()] = value.strip()
        elif token:
            values[token] = "true"
    return Attributes(identifier, tuple(classes), values)


def extract_trailing_attribute_list(text: str) -> tuple[str, Attributes]:
    match = _ATTR_RE.search(text)
    if not match:
        return text, Attributes()
    attrs = parse_attribute_list("{" + match.group("body") + "}")
    return text[: match.start()].rstrip(), attrs


def parse_line_spec(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    result: set[int] = set()
    for part in re.split(r"[,;\s]+", value.strip()):
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            try:
                a, b = int(left), int(right)
            except ValueError:
                continue
            if a > b:
                a, b = b, a
            result.update(range(max(1, a), max(1, b) + 1))
        else:
            try:
                result.add(max(1, int(part)))
            except ValueError:
                continue
    return tuple(sorted(result))
