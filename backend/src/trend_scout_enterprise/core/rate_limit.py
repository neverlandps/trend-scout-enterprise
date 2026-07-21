"""Shared slowapi rate limiter instance.

Mounted on the app in main.py and used by routers via the ``@limiter.limit``
decorator. Rate limiting is disabled in testing mode so the test-suite is not
throttled.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from trend_scout_enterprise.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    enabled=not settings.testing,
)
