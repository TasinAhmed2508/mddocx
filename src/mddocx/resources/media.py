from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mddocx.diagnostics import Diagnostic, MddocxError


@dataclass(frozen=True, slots=True)
class MediaInfo:
    format: str
    media_type: str
    suffix: str
    width: int
    height: int
    frames: int


_FORMATS = {
    "PNG": ("png", "image/png", ".png"),
    "JPEG": ("jpeg", "image/jpeg", ".jpg"),
    "GIF": ("gif", "image/gif", ".gif"),
    "BMP": ("bmp", "image/bmp", ".bmp"),
    "TIFF": ("tiff", "image/tiff", ".tiff"),
    "WEBP": ("webp", "image/webp", ".webp"),
}


def inspect_raster(path: Path) -> MediaInfo:
    """Identify and fully verify raster bytes independently of names and headers."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE205", "Image validation requires Pillow.")
        ) from exc
    try:
        with Image.open(path) as image:
            detected = _FORMATS.get((image.format or "").upper())
            if detected is None:
                raise MddocxError(
                    Diagnostic("error", "IMAGE201", "Unsupported raster image format.")
                )
            width, height = image.size
            frames = int(getattr(image, "n_frames", 1))
            if width <= 0 or height <= 0:
                raise ValueError("image has invalid dimensions")
            # Verify every GIF frame so truncated animations cannot enter the package.
            for frame in range(frames):
                image.seek(frame)
                image.load()
    except UnidentifiedImageError as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE201", "Resource bytes are not a recognized image.")
        ) from exc
    except MddocxError:
        raise
    except Exception as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE204", f"Invalid raster image: {path.name}")
        ) from exc
    fmt, media_type, suffix = detected
    return MediaInfo(fmt, media_type, suffix, width, height, frames)
