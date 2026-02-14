"""Calcul agrégé des statuts workflow pour l'onglet Corpus."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from howimetyourcorpus.app.workflow_advice import WorkflowStatusCounts
from howimetyourcorpus.core.models import EpisodeStatus, SeriesIndex

logger = logging.getLogger(__name__)


def load_episode_status_map(db: Any, episode_ids: list[str]) -> dict[str, str]:
    """Retourne les statuts DB par épisode (fallback vide en cas d'erreur)."""
    if not db or not episode_ids:
        return {}
    try:
        return db.get_episode_statuses(episode_ids)
    except Exception:
        logger.exception("Failed to load episode statuses")
        return {}


def compute_workflow_status(
    *,
    index: SeriesIndex,
    store: Any,
    db: Any,
    status_map: Mapping[str, str] | None = None,
) -> tuple[WorkflowStatusCounts, list[str]]:
    """Calcule les compteurs workflow agrégés et la liste d'épisodes en erreur."""
    episode_ids = [ref.episode_id for ref in index.episodes]
    statuses_raw = dict(status_map) if status_map is not None else load_episode_status_map(db, episode_ids)
    statuses = {eid: (statuses_raw.get(eid) or "").lower() for eid in episode_ids}
    fetched_statuses = {
        EpisodeStatus.FETCHED.value,
        EpisodeStatus.NORMALIZED.value,
        EpisodeStatus.INDEXED.value,
    }
    normalized_statuses = {
        EpisodeStatus.NORMALIZED.value,
        EpisodeStatus.INDEXED.value,
    }
    n_fetched = sum(
        1
        for eid in episode_ids
        if statuses.get(eid) in fetched_statuses or store.has_episode_raw(eid)
    )
    n_norm = sum(
        1
        for eid in episode_ids
        if statuses.get(eid) in normalized_statuses or store.has_episode_clean(eid)
    )
    n_segmented = 0
    n_indexed = 0
    if db and episode_ids:
        try:
            segmented_ids = set(db.get_episode_ids_with_segments(kind="sentence"))
        except Exception:
            logger.exception("Failed to load segmented episode ids")
            segmented_ids = set()
        try:
            indexed_ids = set(db.get_episode_ids_indexed())
        except Exception:
            logger.exception("Failed to load indexed episode ids")
            indexed_ids = set()
        episode_set = set(episode_ids)
        n_segmented = len(episode_set & segmented_ids)
        n_indexed = len(episode_set & indexed_ids)
    error_ids = [
        eid for eid in episode_ids if statuses.get(eid) == EpisodeStatus.ERROR.value
    ]
    n_with_srt = 0
    n_aligned = 0
    if db and episode_ids:
        try:
            tracks_by_ep = db.get_tracks_for_episodes(episode_ids)
        except Exception:
            logger.exception("Failed to load subtitle tracks by episode")
            tracks_by_ep = {}
        try:
            runs_by_ep = db.get_align_runs_for_episodes(episode_ids)
        except Exception:
            logger.exception("Failed to load alignment runs by episode")
            runs_by_ep = {}
        n_with_srt = sum(1 for eid in episode_ids if tracks_by_ep.get(eid))
        n_aligned = sum(1 for eid in episode_ids if runs_by_ep.get(eid))
    return (
        WorkflowStatusCounts(
            n_total=len(episode_ids),
            n_fetched=n_fetched,
            n_norm=n_norm,
            n_segmented=n_segmented,
            n_indexed=n_indexed,
            n_error=len(error_ids),
            n_with_srt=n_with_srt,
            n_aligned=n_aligned,
        ),
        error_ids,
    )
