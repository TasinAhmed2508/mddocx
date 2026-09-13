from __future__ import annotations

import hashlib
import re
from pathlib import Path

from mddocx.config import ImageConfig, ResourcePolicy
from mddocx.diagnostics import Diagnostic, MddocxError

from .media import MediaInfo, inspect_raster


def prepare_image(
    path: Path, *, temp_dir: Path, policy: ResourcePolicy, images: ImageConfig
) -> tuple[Path, MediaInfo]:
    header = path.read_bytes()[:512]
    if header[:5].lstrip().startswith(b"<svg") or b"<svg" in header:
        if not images.svg_conversion:
            raise MddocxError(Diagnostic("error", "IMAGE203", "SVG conversion is disabled."))
        path = convert_svg(path, temp_dir, images)
        return path, inspect_raster(path)
    try:
        info = inspect_raster(path)
    except MddocxError as exc:
        if exc.diagnostic.code == "IMAGE201" and policy.validate_mime:
            raise MddocxError(
                Diagnostic("error", "RESOURCE206", "Resource is not a supported image.")
            ) from exc
        raise
    if info.format == "webp":
        if not images.webp_conversion:
            raise MddocxError(Diagnostic("error", "IMAGE202", "WebP conversion is disabled."))
        path = _convert_webp(path, temp_dir)
        info = inspect_raster(path)
    return path, info


def _convert_webp(path: Path, temp_dir: Path) -> Path:
    try:
        from PIL import Image
    except ImportError as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE205", "WebP conversion requires Pillow.")
        ) from exc
    target = temp_dir / f"{hashlib.sha256(path.read_bytes()).hexdigest()}.png"
    if target.exists():
        return target
    try:
        with Image.open(path) as image:
            image.load()
            image.save(target, format="PNG")
    except Exception as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE204", f"Unable to decode WebP image: {path.name}")
        ) from exc
    return target


def convert_svg(path: Path, temp_dir: Path, images: ImageConfig) -> Path:
    data = path.read_bytes()
    root = _safe_svg(data, path.name)
    _validate_svg_references(root)
    try:
        import cairosvg
    except ImportError as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE208", "SVG conversion requires the mddocx[images] extra.")
        ) from exc
    target = temp_dir / f"{hashlib.sha256(data).hexdigest()}.png"
    if target.exists():
        return target
    try:
        cairosvg.svg2png(bytestring=data, write_to=str(target), dpi=images.svg_dpi, unsafe=False)
    except Exception as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE209", f"Unable to convert SVG: {path.name}")
        ) from exc
    return target


def _safe_svg(data: bytes, name: str):
    try:
        from lxml import etree

        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False, recover=False, huge_tree=False
        )
        return etree.fromstring(data, parser=parser)
    except Exception as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE206", f"Unsafe or invalid SVG: {name}")
        ) from exc


def _validate_svg_references(root) -> None:
    pattern = re.compile(r"url\(\s*['\"]?([^)\"']+)", flags=re.I)
    for element in root.iter():
        for key, value in element.attrib.items():
            local = key.rsplit("}", 1)[-1].lower()
            if local in {"href", "src"} and value and not value.startswith(("data:", "#")):
                raise MddocxError(
                    Diagnostic("error", "IMAGE207", "External references inside SVG are blocked.")
                )
            if any(
                not m.group(1).strip().startswith(("#", "data:"))
                for m in pattern.finditer(value or "")
            ):
                raise MddocxError(
                    Diagnostic(
                        "error", "IMAGE207", "External CSS references inside SVG are blocked."
                    )
                )
        text = element.text or ""
        if "@import" in text.lower() or any(
            not m.group(1).strip().startswith(("#", "data:")) for m in pattern.finditer(text)
        ):
            raise MddocxError(
                Diagnostic("error", "IMAGE207", "External CSS references inside SVG are blocked.")
            )
