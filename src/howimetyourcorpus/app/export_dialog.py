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
        for token, mapped_suffix in sorted(
            filter_to_suffix.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
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
        for token, key in sorted(
            filter_to_key.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if token.upper() in chosen:
                return key
    return default_key


def build_export_success_message(
    *,
    subject: str,
    count: int | None = None,
    count_label: str | None = None,
    path: Path | None = None,
) -> str:
    """Construit un message de succès export homogène (avec quantité + fichier)."""
    base = (subject or "Export terminé").strip().rstrip(".")
    message = base
    if count is not None and count_label:
        message += f" : {count} {count_label}."
    else:
        message += "."
    if path is not None:
        message += f" Fichier: {path.name}"
    return message
