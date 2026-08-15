"""Settings must load with safe, sane defaults on a bare checkout — no .env
file, no environment variables set. This is what a first-time `git clone` +
`pip install` + `python run.py` actually experiences, and it's the case the
whole "zero-config" pitch in the README depends on.
"""

from __future__ import annotations

from app.config import Settings


def _bare_settings() -> Settings:
    # _env_file=None stops pydantic-settings from reading the repo's real
    # .env (which may have real keys/secrets in a dev checkout) — this test
    # is specifically about the *default* values, not whatever's configured
    # locally.
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_loads_without_any_env_file():
    s = _bare_settings()
    assert s is not None


def test_auth_defaults_to_open_local_mode():
    s = _bare_settings()
    assert s.auth_enabled is False


def test_secrets_default_to_empty_not_placeholder_text():
    s = _bare_settings()
    # A default like "changeme" or "your-api-key-here" shipped as a real
    # default would be a security foot-gun; every credential must default
    # to empty so is_configured()-style checks correctly report "off".
    for field in (
        "openai_api_key",
        "crowdstrike_client_secret",
        "sophos_client_secret",
        "wazuh_password",
        "stripe_secret_key",
    ):
        assert getattr(s, field) == "", f"{field} has a non-empty default"


def test_xdr_and_realtime_intervals_are_positive():
    s = _bare_settings()
    assert s.xdr_sync_interval_sec > 0
    assert getattr(s, "xdr_near_realtime_interval_sec", 60) > 0


def test_crowdstrike_streaming_defaults_on():
    # This session added CROWDSTRIKE_STREAMING_ENABLED — confirm it defaults
    # to True so real-time push is opt-out, not opt-in, once credentials are set.
    s = _bare_settings()
    assert s.crowdstrike_streaming_enabled is True


def test_rate_limits_are_positive_ints():
    s = _bare_settings()
    assert s.rate_limit_per_minute > 0
    assert s.rate_limit_auth_per_minute > 0
    assert s.rate_limit_chat_per_minute > 0


def test_host_defaults_to_localhost_not_all_interfaces():
    # Binding 0.0.0.0 by default would silently expose a local-first tool to
    # the network — must be an explicit opt-in.
    s = _bare_settings()
    assert s.host in ("127.0.0.1", "localhost")
