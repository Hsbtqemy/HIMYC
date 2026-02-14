"""Profils d'acquisition (scraping/fetch)."""

from .profiles import (
    DEFAULT_USER_AGENT,
    AcquisitionHttpOptions,
    DEFAULT_ACQUISITION_PROFILE_ID,
    AcquisitionProfile,
    format_http_options_summary,
    get_profile,
    list_profile_ids,
    resolve_http_options,
    resolve_http_options_for_config,
)

__all__ = [
    "AcquisitionProfile",
    "AcquisitionHttpOptions",
    "DEFAULT_USER_AGENT",
    "DEFAULT_ACQUISITION_PROFILE_ID",
    "format_http_options_summary",
    "get_profile",
    "list_profile_ids",
    "resolve_http_options",
    "resolve_http_options_for_config",
]
