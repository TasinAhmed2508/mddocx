from __future__ import annotations

import hashlib
import ipaddress
import mimetypes
import socket
import re
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from mddocx.config import ImageConfig, ResourcePolicy
from mddocx.diagnostics import Diagnostic, MddocxError


_IMAGE_MIMES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, resolver: "ResourceResolver") -> None:
        super().__init__()
        self.resolver = resolver
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > self.resolver.policy.max_redirects:
            raise MddocxError(
                Diagnostic("error", "RESOURCE210", "Remote resource exceeded redirect limit.")
            )
        target = urljoin(req.full_url, newurl)
        self.resolver._validate_remote_url(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


class ResourceResolver:
    def __init__(self, base_dir: Path, policy: ResourcePolicy, images: ImageConfig | None = None):
        self.base_dir = base_dir.resolve()
        self.policy = policy
        self.images = images or ImageConfig()
        self._temp = tempfile.TemporaryDirectory(prefix="mddocx-")
        self.temp_dir = Path(self._temp.name)
        self.cache_dir = (
            Path(policy.cache_directory).expanduser().resolve() if policy.cache_directory else None
        )
        if self.cache_dir and policy.cache_remote_resources:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        self._temp.cleanup()

    def resolve(self, source: str) -> Path:
        parsed = urlparse(source)
        if parsed.scheme or parsed.netloc:
            return self._resolve_remote(source)
        return self._resolve_local(source)

    def _resolve_local(self, source: str) -> Path:
        candidate = (self.base_dir / source).resolve()
        try:
            candidate.relative_to(self.base_dir)
        except ValueError as exc:
            raise MddocxError(
                Diagnostic("error", "RESOURCE203", "Resource path escapes the Markdown directory.")
            ) from exc
        if not candidate.is_file():
            raise MddocxError(Diagnostic("error", "RESOURCE204", f"Resource not found: {source}"))
        if candidate.stat().st_size > self.policy.max_resource_size:
            raise MddocxError(
                Diagnostic("error", "RESOURCE205", "Resource exceeds configured size limit.")
            )
        return self._prepare_image(candidate, source_hint=source)

    def _resolve_remote(self, source: str) -> Path:
        if not self.policy.allow_remote_resources:
            raise MddocxError(Diagnostic("error", "RESOURCE201", "Remote resources are disabled."))
        self._validate_remote_url(source)
        cache_key = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if self.cache_dir and self.policy.cache_remote_resources:
            matches = list(self.cache_dir.glob(f"{cache_key}.*"))
            if matches:
                return self._prepare_image(matches[0], source_hint=source)

        handler = _SafeRedirectHandler(self)
        opener = build_opener(handler)
        req = Request(source, headers={"User-Agent": "mddocx/0.4 (+https image fetch)"})
        try:
            with opener.open(req, timeout=self.policy.timeout_seconds) as response:
                final_url = response.geturl()
                self._validate_remote_url(final_url)
                content_type = response.headers.get_content_type().lower()
                if self.policy.validate_mime and content_type not in _IMAGE_MIMES:
                    raise MddocxError(
                        Diagnostic(
                            "error", "RESOURCE206", f"Unsupported remote MIME type: {content_type}"
                        )
                    )
                suffix = (
                    _IMAGE_MIMES.get(content_type)
                    or Path(urlparse(final_url).path).suffix.lower()
                    or ".img"
                )
                target_dir = (
                    self.cache_dir
                    if self.cache_dir and self.policy.cache_remote_resources
                    else self.temp_dir
                )
                target = target_dir / f"{cache_key}{suffix}"
                total = 0
                with target.open("wb") as f:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > self.policy.max_resource_size:
                            f.close()
                            target.unlink(missing_ok=True)
                            raise MddocxError(
                                Diagnostic(
                                    "error",
                                    "RESOURCE205",
                                    "Remote resource exceeds configured size limit.",
                                )
                            )
                        f.write(chunk)
        except MddocxError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise MddocxError(
                Diagnostic("error", "RESOURCE207", f"Unable to download remote resource: {source}")
            ) from exc
        return self._prepare_image(target, source_hint=source)

    def _validate_remote_url(self, url: str) -> None:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in {s.lower() for s in self.policy.allowed_schemes}:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "RESOURCE208",
                    f"Remote URL scheme is not allowed: {scheme or '(none)'}",
                )
            )
        host = (parsed.hostname or "").rstrip(".").lower()
        if not host:
            raise MddocxError(Diagnostic("error", "RESOURCE208", "Remote URL has no host."))
        if self.policy.allowed_domains:
            allowed = tuple(d.lower().lstrip(".") for d in self.policy.allowed_domains)
            if not any(host == d or host.endswith("." + d) for d in allowed):
                raise MddocxError(
                    Diagnostic(
                        "error",
                        "RESOURCE209",
                        f"Remote host is not in the allowed domain list: {host}",
                    )
                )
        if not self.policy.allow_private_hosts:
            try:
                infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
            except socket.gaierror as exc:
                raise MddocxError(
                    Diagnostic("error", "RESOURCE207", f"Unable to resolve remote host: {host}")
                ) from exc
            for info in infos:
                address = ipaddress.ip_address(info[4][0])
                if not address.is_global:
                    raise MddocxError(
                        Diagnostic(
                            "error",
                            "RESOURCE211",
                            "Private, loopback, link-local, or non-global remote hosts are blocked.",
                        )
                    )

    def _prepare_image(self, path: Path, source_hint: str) -> Path:
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg"}:
            self._verify_raster(path)
            return path
        if suffix == ".webp":
            if not self.images.webp_conversion:
                raise MddocxError(Diagnostic("error", "IMAGE202", "WebP conversion is disabled."))
            return self._convert_webp(path)
        if suffix == ".svg":
            if not self.images.svg_conversion:
                raise MddocxError(Diagnostic("error", "IMAGE203", "SVG conversion is disabled."))
            return self._convert_svg(path)
        guessed = mimetypes.guess_type(source_hint)[0]
        raise MddocxError(
            Diagnostic(
                "error", "IMAGE201", f"Unsupported image type: {guessed or suffix or 'unknown'}"
            )
        )

    @staticmethod
    def _verify_raster(path: Path) -> None:
        try:
            from PIL import Image

            with Image.open(path) as image:
                image.verify()
        except ImportError:
            return
        except Exception as exc:
            raise MddocxError(
                Diagnostic("error", "IMAGE204", f"Invalid raster image: {path.name}")
            ) from exc

    def _convert_webp(self, path: Path) -> Path:
        try:
            from PIL import Image
        except ImportError as exc:
            raise MddocxError(
                Diagnostic("error", "IMAGE205", "WebP conversion requires Pillow.")
            ) from exc
        target = self.temp_dir / f"{hashlib.sha256(path.read_bytes()).hexdigest()}.png"
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

    def _convert_svg(self, path: Path) -> Path:
        data = path.read_bytes()
        try:
            from defusedxml import ElementTree as DET
        except ImportError as exc:
            raise MddocxError(
                Diagnostic("error", "IMAGE208", "SVG conversion requires the mddocx[images] extra.")
            ) from exc
        try:
            root = DET.fromstring(data)
        except Exception as exc:
            raise MddocxError(
                Diagnostic("error", "IMAGE206", f"Unsafe or invalid SVG: {path.name}")
            ) from exc
        for element in root.iter():
            for key, value in element.attrib.items():
                local = key.rsplit("}", 1)[-1].lower()
                if local in {"href", "src"} and value and not value.startswith(("data:", "#")):
                    raise MddocxError(
                        Diagnostic(
                            "error", "IMAGE207", "External references inside SVG are blocked."
                        )
                    )
                for match in re.finditer(r"url\(\s*['\"]?([^)'\"]+)", value or "", flags=re.I):
                    target = match.group(1).strip()
                    if not target.startswith(("#", "data:")):
                        raise MddocxError(
                            Diagnostic(
                                "error",
                                "IMAGE207",
                                "External CSS references inside SVG are blocked.",
                            )
                        )
            text = element.text or ""
            if "@import" in text.lower():
                raise MddocxError(
                    Diagnostic("error", "IMAGE207", "CSS imports inside SVG are blocked.")
                )
            for match in re.finditer(r"url\(\s*['\"]?([^)'\"]+)", text, flags=re.I):
                target = match.group(1).strip()
                if not target.startswith(("#", "data:")):
                    raise MddocxError(
                        Diagnostic(
                            "error", "IMAGE207", "External CSS references inside SVG are blocked."
                        )
                    )
        try:
            import cairosvg
        except ImportError as exc:
            raise MddocxError(
                Diagnostic("error", "IMAGE208", "SVG conversion requires the mddocx[images] extra.")
            ) from exc
        target = self.temp_dir / f"{hashlib.sha256(data).hexdigest()}.png"
        if target.exists():
            return target
        try:
            cairosvg.svg2png(
                bytestring=data, write_to=str(target), dpi=self.images.svg_dpi, unsafe=False
            )
        except Exception as exc:
            raise MddocxError(
                Diagnostic("error", "IMAGE209", f"Unable to convert SVG: {path.name}")
            ) from exc
        return target
