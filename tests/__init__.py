"""ChallengeMap test suite.

The rate limiter is switched off here, before any test module imports
``api.main``: the suite creates many short-lived clients from one address, and
with the limiter on they would share a single bucket and start seeing 429s.
``tests/test_rate_limit.py`` turns it back on deliberately.
"""

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
