"""Helpers ProjectStore pour la persistance de l'index série."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex


def save_series_index(store: Any, series_index: SeriesIndex) -> None:
    """Sauvegarde l'index série en JSON."""
    path = Path(store.root_dir) / "series_index.json"
    payload = {
        "series_title": series_index.series_title,
        "series_url": series_index.series_url,
        "episodes": [
            {
                "episode_id": episode.episode_id,
                "season": episode.season,
                "episode": episode.episode,
                "title": episode.title,
                "url": episode.url,
                **({"source_id": episode.source_id} if episode.source_id else {}),
            }
            for episode in series_index.episodes
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_series_index(store: Any) -> SeriesIndex | None:
    """Charge l'index série depuis JSON. Retourne None si absent."""
    path = Path(store.root_dir) / "series_index.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    episodes: list[EpisodeRef] = []
    for row in payload.get("episodes", []):
        if not isinstance(row, dict):
            continue
        episodes.append(
            EpisodeRef(
                episode_id=row.get("episode_id", ""),
                season=int(row.get("season", 0)),
                episode=int(row.get("episode", 0)),
                title=row.get("title", "") or "",
                url=row.get("url", "") or "",
                source_id=row.get("source_id"),
            )
        )
    return SeriesIndex(
        series_title=payload.get("series_title", ""),
        series_url=payload.get("series_url", ""),
        episodes=episodes,
    )
