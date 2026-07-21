"""Unit tests for the SSRF outbound URL validator."""

import pytest

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.scanners.url_validator import validate_outbound_url


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data",  # cloud metadata endpoint
        "http://127.0.0.1:8080/admin",
        "http://127.0.0.2/",
        "http://localhost:8000/api",
        "http://LOCALHOST/feed",
        "http://foo.localhost/feed",
        "http://10.0.0.5/internal",
        "http://172.16.1.10/internal",
        "http://192.168.1.1/router",
        "http://169.254.10.10/link-local",
        "http://[::1]/ipv6-loopback",
        "http://[fe80::1]/ipv6-link-local",
    ],
)
def test_rejects_private_and_reserved_hosts(url):
    with pytest.raises(ValueError):
        validate_outbound_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "gopher://example.com/",
        "example.com/no-scheme",
    ],
)
def test_rejects_non_http_schemes(url):
    with pytest.raises(ValueError):
        validate_outbound_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/feed",
        "http://export.arxiv.org/api/query",
        "https://api.example.com:8443/v1/items?q=test",
        "http://8.8.8.8/public-dns",
    ],
)
def test_accepts_public_urls(url):
    validate_outbound_url(url)  # should not raise


def test_allow_private_setting_bypasses_private_checks(monkeypatch):
    monkeypatch.setattr(settings, "ssrf_allow_private", True)
    validate_outbound_url("http://192.168.1.10/feed")
    validate_outbound_url("http://localhost:8080/api")
    # Scheme validation still applies even when private hosts are allowed.
    with pytest.raises(ValueError):
        validate_outbound_url("file:///etc/passwd")
