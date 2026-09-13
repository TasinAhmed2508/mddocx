from __future__ import annotations

import base64
import binascii
import hashlib
import socket
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from mddocx.config import ImageConfig, ResourcePolicy
from mddocx.diagnostics import Diagnostic, MddocxError
from .media import MediaInfo
from .models import ResourceFallback, ResourceRequest, ResourceResolution, ResolvedImage
from .network import validate_remote_url
from .preparation import convert_svg, prepare_image


_IMAGE_MIMES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
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
        """Compatibility API: resolve an image or raise its diagnostic."""
        result = self.resolve_image(ResourceRequest(source=source))
        if isinstance(result, ResourceFallback):
            raise MddocxError(result.diagnostic)
        return result.path

    def resolve_image(self, request: ResourceRequest) -> ResourceResolution:
        """Resolve an image without making ordinary conversion failures fatal."""
        try:
            path, source_url, from_cache = self._acquire(request.source)
            path, info = self._prepare_image_info(path, source_hint=request.source)
            return ResolvedImage(
                path=path,
                source_url=source_url,
                media_type=info.media_type,
                format=info.format,  # type: ignore[arg-type]
                width_px=info.width,
                height_px=info.height,
                frame_count=info.frames,
                from_cache=from_cache,
            )
        except MddocxError as exc:
            diagnostic = exc.diagnostic
            diagnostic.source_file = request.source_file
            diagnostic.line = request.line
            mode = getattr(self.policy, "image_failure", "clickable_fallback")
            if mode == "error":
                raise
            diagnostic.severity = "warning"
            return ResourceFallback(
                request.source, self._fallback_reason(diagnostic.code), diagnostic
            )

    def _acquire(self, source: str) -> tuple[Path, str | None, bool]:
        parsed = urlparse(source)
        if parsed.scheme.lower() == "data":
            return self._resolve_data_uri(source), None, False
        if parsed.scheme or parsed.netloc:
            return self._resolve_remote(source)
        return self._resolve_local(source), None, False

    @staticmethod
    def _fallback_reason(code: str) -> str:
        return {
            "RESOURCE201": "blocked",
            "RESOURCE204": "not_found",
            "RESOURCE205": "too_large",
            "RESOURCE206": "not_image",
            "RESOURCE207": "http_error",
            "RESOURCE212": "timeout",
            "IMAGE204": "invalid_image",
            "IMAGE201": "unsupported_format",
            "IMAGE202": "unsupported_format",
            "IMAGE203": "unsupported_format",
        }.get(code, "invalid_image")

    def _resolve_data_uri(self, source: str) -> Path:
        """Decode a bounded inline image without treating it as a remote resource."""
        try:
            metadata, payload = source.split(",", 1)
        except ValueError as exc:
            raise MddocxError(
                Diagnostic("error", "IMAGE210", "Malformed image data URI: missing payload.")
            ) from exc

        parts = metadata[5:].split(";")
        mime = parts[0].lower()
        parameters = {part.lower() for part in parts[1:] if part}
        if mime not in _IMAGE_MIMES:
            raise MddocxError(
                Diagnostic("error", "IMAGE201", f"Unsupported inline image MIME type: {mime}")
            )
        if "base64" not in parameters:
            raise MddocxError(
                Diagnostic("error", "IMAGE210", "Inline images must use Base64-encoded data URIs.")
            )

        compact = "".join(payload.split())
        # Check the maximum possible decoded length before allocating the byte buffer.
        if (len(compact) * 3) // 4 > self.policy.max_resource_size + 2:
            raise MddocxError(
                Diagnostic("error", "RESOURCE205", "Inline image exceeds configured size limit.")
            )
        try:
            data = base64.b64decode(compact, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise MddocxError(
                Diagnostic("error", "IMAGE210", "Inline image contains invalid Base64 data.")
            ) from exc
        if len(data) > self.policy.max_resource_size:
            raise MddocxError(
                Diagnostic("error", "RESOURCE205", "Inline image exceeds configured size limit.")
            )

        suffix = _IMAGE_MIMES[mime]
        target = self.temp_dir / f"{hashlib.sha256(data).hexdigest()}{suffix}"
        if not target.exists():
            target.write_bytes(data)
        return self._prepare_image(target, source_hint=mime)

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

    def _resolve_remote(self, source: str) -> tuple[Path, str, bool]:
        if not self.policy.allow_remote_resources:
            raise MddocxError(
                Diagnostic(
                    "error",
                    "RESOURCE201",
                    "Remote resources are blocked by the active resource policy.",
                    remediation=(
                        "Allow remote resources in configuration or use "
                        "--allow-remote-resources for this render."
                    ),
                )
            )
        self._validate_remote_url(source)
        cache_key = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if self.cache_dir and self.policy.cache_remote_resources:
            matches = list(self.cache_dir.glob(f"{cache_key}.*"))
            if matches:
                # Cache contains only content that passed full validation previously.
                return matches[0], source, True

        handler = _SafeRedirectHandler(self)
        opener = build_opener(handler)
        req = Request(source, headers={"User-Agent": "mddocx/0.4 (+https image fetch)"})
        try:
            with opener.open(req, timeout=self.policy.timeout_seconds) as response:
                final_url = response.geturl()
                self._validate_remote_url(final_url)
                target = self.temp_dir / f"{cache_key}.download"
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
        except (TimeoutError, socket.timeout) as exc:
            raise MddocxError(
                Diagnostic("error", "RESOURCE212", f"Remote image timed out: {source}")
            ) from exc
        except (HTTPError, URLError, OSError) as exc:
            raise MddocxError(
                Diagnostic("error", "RESOURCE207", f"Unable to download remote resource: {source}")
            ) from exc
        try:
            prepared, info = self._prepare_image_info(target, source_hint=source)
        except MddocxError:
            target.unlink(missing_ok=True)
            raise
        if self.cache_dir and self.policy.cache_remote_resources:
            # Cache keys include the canonical final URL and response validators.
            validators = "|".join(
                (
                    final_url,
                    response.headers.get("ETag", ""),
                    response.headers.get("Last-Modified", ""),
                )
            )
            validated_key = hashlib.sha256(validators.encode("utf-8")).hexdigest()[:16]
            cached = self.cache_dir / f"{cache_key}.{validated_key}{info.suffix}"
            if not cached.exists():
                cached.write_bytes(prepared.read_bytes())
            prepared = cached
        return prepared, final_url, False

    def _validate_remote_url(self, url: str) -> None:
        validate_remote_url(url, self.policy)

    def _prepare_image(self, path: Path, source_hint: str) -> Path:
        return self._prepare_image_info(path, source_hint)[0]

    def _prepare_image_info(self, path: Path, source_hint: str) -> tuple[Path, MediaInfo]:
        return prepare_image(path, temp_dir=self.temp_dir, policy=self.policy, images=self.images)

    def _convert_svg(self, path: Path) -> Path:
        return convert_svg(path, self.temp_dir, self.images)
