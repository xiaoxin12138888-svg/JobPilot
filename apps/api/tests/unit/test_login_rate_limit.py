from __future__ import annotations

from jobpilot_api.api.login_rate_limit import WebLoginRateLimiter


def test_web_login_rate_limit_is_per_client_and_recovers_after_the_window() -> None:
    now = 100.0
    limiter = WebLoginRateLimiter(limit=2, window_seconds=60, clock=lambda: now)

    assert limiter.check("client-a") is None
    assert limiter.check("client-a") is None
    assert limiter.check("client-a") == 60
    assert limiter.check("client-b") is None

    now += 60

    assert limiter.check("client-a") is None
