"""Profils d'acquisition (politique de scraping)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AcquisitionProfile:
    """Profil d'acquisition: politique de débit/réglages HTTP par défaut."""

    id: str
    label: str
    default_rate_limit_s: float
    timeout_s: float
    retries: int
    backoff_s: float
    description: str


@dataclass(frozen=True)
class AcquisitionHttpOptions:
    """Options HTTP résolues pour les appels réseau des adapteurs."""

    user_agent: str
    rate_limit_s: float
    timeout_s: float
    retries: int
    backoff_s: float
    acquisition_profile_id: str


DEFAULT_ACQUISITION_PROFILE_ID = "balanced_v1"
DEFAULT_USER_AGENT = "HowIMetYourCorpus/0.1 (research)"

PROFILES: dict[str, AcquisitionProfile] = {
    "balanced_v1": AcquisitionProfile(
        id="balanced_v1",
        label="Balanced",
        default_rate_limit_s=2.0,
        timeout_s=30.0,
        retries=3,
        backoff_s=2.0,
        description="Débit équilibré: bon compromis vitesse/stabilité.",
    ),
    "safe_v1": AcquisitionProfile(
        id="safe_v1",
        label="Safe",
        default_rate_limit_s=4.0,
        timeout_s=45.0,
        retries=4,
        backoff_s=3.0,
        description="Débit plus prudent pour limiter les erreurs HTTP/rate-limit.",
    ),
    "fast_v1": AcquisitionProfile(
        id="fast_v1",
        label="Fast",
        default_rate_limit_s=1.0,
        timeout_s=20.0,
        retries=2,
        backoff_s=1.0,
        description="Débit rapide, à utiliser si la source est tolérante.",
    ),
}


def list_profile_ids() -> list[str]:
    """Retourne les IDs de profils d'acquisition disponibles."""
    return list(PROFILES.keys())


def get_profile(profile_id: str | None) -> AcquisitionProfile | None:
    """Résout un profil d'acquisition depuis son ID."""
    if profile_id and profile_id in PROFILES:
        return PROFILES[profile_id]
    return PROFILES.get(DEFAULT_ACQUISITION_PROFILE_ID)


def resolve_http_options(
    *,
    acquisition_profile_id: str | None,
    user_agent: str | None,
    rate_limit_s: float | None,
) -> AcquisitionHttpOptions:
    """Construit les options HTTP effectives à partir du profil + overrides config."""
    profile = get_profile(acquisition_profile_id)
    if profile is None:
        profile = PROFILES[DEFAULT_ACQUISITION_PROFILE_ID]

    resolved_rate_limit = float(rate_limit_s) if rate_limit_s is not None else profile.default_rate_limit_s
    if resolved_rate_limit <= 0:
        resolved_rate_limit = profile.default_rate_limit_s

    base_ua = (user_agent or DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT
    ua_marker = f"acq={profile.id}"
    resolved_user_agent = base_ua if ua_marker in base_ua else f"{base_ua} ({ua_marker})"

    return AcquisitionHttpOptions(
        user_agent=resolved_user_agent,
        rate_limit_s=resolved_rate_limit,
        timeout_s=profile.timeout_s,
        retries=profile.retries,
        backoff_s=profile.backoff_s,
        acquisition_profile_id=profile.id,
    )


def resolve_http_options_for_config(
    config: Any,
    *,
    user_agent_override: str | None = None,
) -> AcquisitionHttpOptions:
    """Résout les options HTTP à partir d'un ProjectConfig-like."""
    return resolve_http_options(
        acquisition_profile_id=getattr(config, "acquisition_profile_id", None) if config is not None else None,
        user_agent=user_agent_override or (getattr(config, "user_agent", None) if config is not None else None),
        rate_limit_s=getattr(config, "rate_limit_s", None) if config is not None else None,
    )
