"""Security response headers middleware.

Adds standard hardening headers to every response:

- ``X-Content-Type-Options: nosniff``
- ``X-Frame-Options`` (configurable, default ``DENY``)
- ``Referrer-Policy: strict-origin-when-cross-origin``
- ``Content-Security-Policy``: strict ``default-src 'none'; frame-ancestors 'none'``
  for API responses. Report HTML downloads (``/outputs/`` paths or
  ``text/html`` responses) get a relaxed policy so they still render in a
  browser.
- ``Strict-Transport-Security`` only when ``hsts_enabled`` is set (HTTPS
  deployments); local HTTP development leaves it off.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from trend_scout_enterprise.core.config import settings

_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'"
_RELAXED_CSP = "default-src 'self' 'unsafe-inline'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every outgoing response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = settings.frame_options
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        content_type = response.headers.get("content-type", "")
        if request.url.path.startswith("/outputs/") or "text/html" in content_type:
            response.headers["Content-Security-Policy"] = _RELAXED_CSP
        else:
            response.headers["Content-Security-Policy"] = _STRICT_CSP

        if settings.hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
