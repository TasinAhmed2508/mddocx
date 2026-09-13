from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from mddocx.config import ResourcePolicy
from mddocx.diagnostics import Diagnostic, MddocxError


def validate_remote_url(url: str, policy: ResourcePolicy) -> None:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in {value.lower() for value in policy.allowed_schemes}:
        raise MddocxError(
            Diagnostic(
                "error", "RESOURCE208", f"Remote URL scheme is not allowed: {scheme or '(none)'}"
            )
        )
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        raise MddocxError(Diagnostic("error", "RESOURCE208", "Remote URL has no host."))
    if policy.allowed_domains:
        allowed = tuple(domain.lower().lstrip(".") for domain in policy.allowed_domains)
        if not any(host == domain or host.endswith("." + domain) for domain in allowed):
            raise MddocxError(
                Diagnostic(
                    "error", "RESOURCE209", f"Remote host is not in the allowed domain list: {host}"
                )
            )
    if policy.allow_private_hosts:
        return
    try:
        addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise MddocxError(
            Diagnostic("error", "RESOURCE207", f"Unable to resolve remote host: {host}")
        ) from exc
    if any(not ipaddress.ip_address(info[4][0]).is_global for info in addresses):
        raise MddocxError(
            Diagnostic(
                "error",
                "RESOURCE211",
                "Private, loopback, link-local, or non-global remote hosts are blocked.",
            )
        )
