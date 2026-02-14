"""Helpers UI pour normaliser les chemins et formats d'export."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence


def normalize_export_path(
    path: Path,
    selected_filter: str | None,
    *,
    allowed_suffixes: Sequence[str],
    default_suffix: str,
    filter_to_suffix: Mapping[str, str] | None = None,
) -> Path:
    """Assure une extension valide à partir du suffixe saisi ou du filtre choisi."""
    allowed = tuple(s.lower() for s in allowed_suffixes)
    suffix = path.suffix.lower()
    if suffix in allowed:
        return path
    chosen = (selected_filter or "").upper()
    if filter_to_suffix:
        for token, mapped_suffix in filter_to_suffix.items():
            if token.upper() in chosen:
                return path.with_suffix(mapped_suffix.lower())
    return path.with_suffix(default_suffix.lower())


def resolve_export_key(
    path: Path,
    selected_filter: str | None,
    *,
    suffix_to_key: Mapping[str, str],
    filter_to_key: Mapping[str, str] | None = None,
    default_key: str | None = None,
) -> str | None:
    """Résout la clé de format: suffixe explicite prioritaire, sinon filtre, sinon défaut."""
    suffix_key = suffix_to_key.get(path.suffix.lower())
    if suffix_key is not None:
        return suffix_key
    chosen = (selected_filter or "").upper()
    if filter_to_key:
        for token, key in filter_to_key.items():
            if token.upper() in chosen:
                return key
    return default_key
