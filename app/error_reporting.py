"""Optional Sentry error reporting — inert unless SENTRY_DSN is set.

Kept separate from app/metrics.py: metrics are "how much/how often", error
reporting is "what broke and where" (stack traces, breadcrumbs, release
tracking). Both were "Todo" in the SaaS readiness checklist.
"""

from __future__ import annotations

from app.config import settings


def init_error_reporting() -> bool:
    """Call once at startup. Returns True if Sentry was actually initialized."""
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.sentry_environment or "alpha",
        )
        return True
    except ImportError:
        print(
            "SENTRY_DSN is set but the `sentry-sdk` package isn't installed. "
            "Run: pip install sentry-sdk"
        )
        return False
    except Exception as exc:
        print(f"Sentry init failed (continuing without error reporting): {exc}")
        return False
