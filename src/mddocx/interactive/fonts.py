from __future__ import annotations

import os
from pathlib import Path
import sys

_FONT_SUFFIXES = {".ttf", ".otf", ".ttc", ".otc"}


def font_directories() -> tuple[Path, ...]:
    candidates: list[Path] = []
    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        candidates.append(Path(windir) / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        candidates.extend([Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library" / "Fonts"])
    else:
        candidates.extend([Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts", Path.home() / ".local" / "share" / "fonts"])
    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        path = path.expanduser()
        if path in seen or not path.is_dir():
            continue
        seen.add(path); result.append(path)
    return tuple(result)


def discover_fonts(limit: int = 5000) -> tuple[Path, ...]:
    found: list[Path] = []
    seen: set[str] = set()
    for directory in font_directories():
        try:
            for path in directory.rglob("*"):
                if len(found) >= limit:
                    break
                if not path.is_file() or path.suffix.lower() not in _FONT_SUFFIXES:
                    continue
                key = str(path.resolve()).casefold()
                if key not in seen:
                    seen.add(key); found.append(path.resolve())
        except OSError:
            continue
    return tuple(sorted(found, key=lambda p: p.name.casefold()))


def font_display_name(path: Path) -> str:
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(str(path), 12)
        family, style = font.getname()
        return f"{family} {style}".strip()
    except Exception:
        return path.stem
