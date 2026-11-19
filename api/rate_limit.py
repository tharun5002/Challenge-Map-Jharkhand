"""Per-IP rate limiting for the unauthenticated and write-heavy endpoints.

Plan section 7 asks for ``slowapi`` limits on ``/auth/*`` and ``/complaints``.
Counters live in process memory, which is correct for a single-worker demo —
with several workers each would keep its own counter. That limitation is stated
in ``api/README.md`` rather than papered over.

Set ``RATE_LIMIT_ENABLED=false`` to turn the limiter off (the test suite does
this so its many short-lived clients never contend for the same bucket).
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

#: slowapi limit strings, one per sensitive surface.
LOGIN_LIMIT = "5/minute"
REGISTER_LIMIT = "5/minute"
REFRESH_LIMIT = "20/minute"
SUBMIT_LIMIT = "20/minute"

DISABLED_VALUES = {"0", "false", "no", "off"}


def rate_limiting_enabled() -> bool:
    """Read the switch fresh so tests and deployments can flip it."""
    return (
        os.environ.get("RATE_LIMIT_ENABLED", "true").strip().lower()
        not in DISABLED_VALUES
    )


limiter = Limiter(key_func=get_remote_address, enabled=rate_limiting_enabled())

__all__ = [
    "LOGIN_LIMIT",
    "REFRESH_LIMIT",
    "REGISTER_LIMIT",
    "SUBMIT_LIMIT",
    "limiter",
    "rate_limiting_enabled",
]
