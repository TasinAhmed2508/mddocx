from __future__ import annotations

import shlex


def split_command(line: str) -> list[str]:
    """Tokenize shell input without destroying Windows backslashes."""
    parts = shlex.split(line, posix=False)
    result: list[str] = []
    for part in parts:
        if len(part) >= 2 and part[0] == part[-1] and part[0] in {"'", '"'}:
            part = part[1:-1]
        result.append(part)
    return result
