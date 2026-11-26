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
    with path.open("rb") as stream:
        header = stream.read(512)
    if header[:5].lstrip().startswith(b"<svg") or b"<svg" in header:
        if not images.svg_conversion:
            raise MddocxError(Diagnostic("error", "IMAGE203", "SVG conversion is disabled."))
        path = convert_svg(path, temp_dir, images, max_bytes=policy.max_resource_size)
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


def convert_svg(
    path: Path, temp_dir: Path, images: ImageConfig, *, max_bytes: int = 10_000_000
) -> Path:
    data = path.read_bytes()
    root = _safe_svg(data, path.name)
    _validate_svg_references(root)
    try:
        import resvg_py
    except ImportError as exc:
        raise MddocxError(
            Diagnostic("error", "IMAGE208", "SVG renderer is unavailable. Reinstall mddocx-native.")
        ) from exc
    digest = hashlib.sha256(f"resvg:{images.svg_dpi}:".encode() + data).hexdigest()
    target = temp_dir / f"{digest}.png"
    if target.exists():
        return target
    try:
        import struct
        from lxml import etree

        # Refuse oversized declared viewports before the native renderer allocates them.
        from math import isfinite

        factors = {
            "": 1,
            "px": 1,
            "in": images.svg_dpi,
            "cm": images.svg_dpi / 2.54,
            "mm": images.svg_dpi / 25.4,
            "pt": images.svg_dpi / 72,
            "pc": images.svg_dpi / 6,
            "em": 16,
            "ex": 16,
        }
        dimensions = [300.0, 150.0]
        if root.get("viewBox"):
            view_box = [float(value) for value in re.split(r"[\s,]+", root.get("viewBox").strip())]
            if len(view_box) != 4 or not all(isfinite(value) for value in view_box):
                raise ValueError("Invalid SVG viewBox")
            dimensions = view_box[2:]
        for index, attr in enumerate(("width", "height")):
            value = root.get(attr, "").strip()
            length = re.fullmatch(r"([+\deE.-]+)([a-z%]*)", value, re.I)
            if length and length[2] in factors:
                dimensions[index] = float(length[1]) * factors[length[2]]
        if (
            any(not isfinite(value) or not 0 < value <= 16000 for value in dimensions)
            or dimensions[0] * dimensions[1] > 40_000_000
        ):
            raise ValueError("SVG viewport exceeds the pixel budget")
        png = resvg_py.svg_to_bytes(
            svg_string=etree.tostring(root, encoding="unicode"), dpi=images.svg_dpi
        )
        width, height = struct.unpack(">II", bytes(png[16:24]))
        if width * height > 40_000_000 or len(png) > max_bytes:
            raise ValueError("SVG raster exceeds the output pixel or byte budget")
        target.write_bytes(bytes(png))
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
        root = etree.fromstring(data, parser=parser)
        if root.getroottree().docinfo.doctype or etree.QName(root).localname != "svg":
            raise ValueError("Expected a standalone SVG without a doctype")
        return root
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
