"""Tests des profils d'acquisition (résolution des options HTTP)."""

from __future__ import annotations

from howimetyourcorpus.core.acquisition.profiles import (
    DEFAULT_ACQUISITION_PROFILE_ID,
    format_http_options_summary,
    resolve_http_options,
)


def test_resolve_http_options_safe_profile_uses_profile_network_defaults() -> None:
    opts = resolve_http_options(
        acquisition_profile_id="safe_v1",
        user_agent="HIMYC/1.0",
        rate_limit_s=6.0,
    )

    assert opts.acquisition_profile_id == "safe_v1"
    assert opts.user_agent == "HIMYC/1.0 (acq=safe_v1)"
    assert opts.rate_limit_s == 6.0
    assert opts.timeout_s == 45.0
    assert opts.retries == 4
    assert opts.backoff_s == 3.0


def test_resolve_http_options_fallback_on_unknown_profile() -> None:
    opts = resolve_http_options(
        acquisition_profile_id="unknown_profile",
        user_agent=None,
        rate_limit_s=None,
    )

    assert opts.acquisition_profile_id == DEFAULT_ACQUISITION_PROFILE_ID
    assert "acq=balanced_v1" in opts.user_agent
    assert opts.rate_limit_s == 2.0
    assert opts.timeout_s == 30.0
    assert opts.retries == 3
    assert opts.backoff_s == 2.0


def test_resolve_http_options_does_not_duplicate_user_agent_marker() -> None:
    opts = resolve_http_options(
        acquisition_profile_id="fast_v1",
        user_agent="HowIMetYourCorpus/0.1 (research) (acq=fast_v1)",
        rate_limit_s=1.0,
    )

    assert opts.user_agent.count("acq=fast_v1") == 1


def test_format_http_options_summary_contains_key_runtime_fields() -> None:
    opts = resolve_http_options(
        acquisition_profile_id="safe_v1",
        user_agent="Agent/1.0",
        rate_limit_s=5.0,
    )

    summary = format_http_options_summary(opts)

    assert "profile=safe_v1" in summary
    assert "rate=5.0s" in summary
    assert "timeout=45.0s" in summary
    assert "retries=4" in summary
