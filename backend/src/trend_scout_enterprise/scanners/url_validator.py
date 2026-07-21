"""Outbound URL validation to guard scanners against SSRF attacks."""

import ipaddress
from urllib.parse import urlparse

from trend_scout_enterprise.core.config import settings

_ALLOWED_SCHEMES = {"http", "https"}
_LOCALHOST_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}


def _is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True for private, loopback, link-local, reserved or otherwise non-public IPs."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_outbound_url(url: str) -> None:
    """Validate that a URL is safe for an outbound HTTP request.

    Checks the scheme (http/https only) and rejects hostnames that are IP
    literals in private/reserved ranges (127.0.0.0/8, 10.0.0.0/8,
    172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, ::1, link-local, ...) as
    well as 'localhost' and its variants. When ``settings.ssrf_allow_private``
    is True the private-host checks are skipped (local development against
    private RSS/API endpoints); the scheme check always applies.

    Note: only IP literals are checked. A hostname that resolves to a private
    IP via DNS (e.g. DNS rebinding, or decimal/hex IP notations such as
    ``2130706433``) is not resolved here; adding DNS-resolution checks is a
    possible future enhancement.

    Args:
        url: The URL about to be requested.

    Raises:
        ValueError: If the URL fails validation.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Outbound URL scheme {scheme!r} is not allowed; only http and https are permitted"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Outbound URL {url!r} has no hostname")

    if settings.ssrf_allow_private:
        return

    host = hostname.lower().rstrip(".")
    if host in _LOCALHOST_NAMES or host.endswith(".localhost"):
        raise ValueError(f"Outbound URL host {hostname!r} is not allowed (localhost)")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Regular DNS hostname, not an IP literal: accepted (see docstring).
        return

    if _is_forbidden_ip(ip):
        raise ValueError(
            f"Outbound URL host {hostname!r} resolves to a private or reserved IP address"
        )
