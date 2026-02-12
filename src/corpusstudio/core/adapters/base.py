"""Interface des adapters source + registre."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from corpusstudio.core.models import EpisodeRef, SeriesIndex


class SourceAdapter(Protocol):
    """Protocol pour un adapteur de source (discover, fetch, parse)."""

    id: str

    def discover_series(self, series_url: str) -> SeriesIndex:
        """Parse la page série et retourne l'index des épisodes."""
        ...

    def fetch_episode_html(self, episode_url: str) -> str:
        """Récupère le HTML de la page épisode (délégué au pipeline avec rate limit)."""
        ...

    def parse_episode(self, html: str, episode_url: str) -> tuple[str, dict]:
        """
        Extrait le transcript depuis le HTML.
        Returns:
            (raw_text, meta) avec meta contenant selectors, warnings, etc.
        """
        ...

    def normalize_episode_id(self, season: int, episode: int) -> str:
        """Retourne l'id canonique (ex: S01E01)."""
        ...


class AdapterRegistry:
    """Registre des adapters disponibles."""

    _adapters: dict[str, SourceAdapter] = {}

    @classmethod
    def register(cls, adapter: SourceAdapter) -> None:
        cls._adapters[adapter.id] = adapter

    @classmethod
    def get(cls, source_id: str) -> SourceAdapter | None:
        return cls._adapters.get(source_id)

    @classmethod
    def list_ids(cls) -> list[str]:
        return list(cls._adapters.keys())
