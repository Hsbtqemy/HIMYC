"""Profils d'acquisition (politique de scraping)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AcquisitionProfile:
    """Profil d'acquisition: politique de débit/réglages HTTP par défaut."""

    id: str
    label: str
    default_rate_limit_s: float
    description: str


DEFAULT_ACQUISITION_PROFILE_ID = "balanced_v1"

PROFILES: dict[str, AcquisitionProfile] = {
    "balanced_v1": AcquisitionProfile(
        id="balanced_v1",
        label="Balanced",
        default_rate_limit_s=2.0,
        description="Débit équilibré: bon compromis vitesse/stabilité.",
    ),
    "safe_v1": AcquisitionProfile(
        id="safe_v1",
        label="Safe",
        default_rate_limit_s=4.0,
        description="Débit plus prudent pour limiter les erreurs HTTP/rate-limit.",
    ),
    "fast_v1": AcquisitionProfile(
        id="fast_v1",
        label="Fast",
        default_rate_limit_s=1.0,
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
