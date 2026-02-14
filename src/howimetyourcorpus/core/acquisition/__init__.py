"""Profils d'acquisition (scraping/fetch)."""

from .profiles import (
    DEFAULT_ACQUISITION_PROFILE_ID,
    AcquisitionProfile,
    get_profile,
    list_profile_ids,
)

__all__ = [
    "AcquisitionProfile",
    "DEFAULT_ACQUISITION_PROFILE_ID",
    "get_profile",
    "list_profile_ids",
]
