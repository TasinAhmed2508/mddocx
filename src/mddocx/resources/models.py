from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from mddocx.diagnostics import Diagnostic

ImageFormat = Literal["png", "jpeg", "gif", "bmp", "tiff"]
FallbackReason = Literal[
    "not_image",
    "not_found",
    "http_error",
    "timeout",
    "blocked",
    "too_large",
    "invalid_image",
    "unsupported_format",
]


@dataclass(slots=True)
class ResourceRequest:
    source: str
    kind: Literal["image"] = "image"
    source_file: str | None = None
    line: int | None = None
    alt_text: str = ""
    title: str | None = None


@dataclass(slots=True)
class ResolvedImage:
    path: Path
    source_url: str | None
    media_type: str
    format: ImageFormat
    width_px: int
    height_px: int
    frame_count: int
    from_cache: bool = False


@dataclass(slots=True)
class ResourceFallback:
    source: str
    reason: FallbackReason
    diagnostic: Diagnostic


ResourceResolution: TypeAlias = ResolvedImage | ResourceFallback
