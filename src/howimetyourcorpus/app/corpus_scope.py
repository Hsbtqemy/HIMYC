"""Fonctions pures pour la résolution de scope Corpus (filtrage IDs + capacités)."""

from __future__ import annotations

import logging
from typing import Callable

from howimetyourcorpus.core.models import SeriesIndex


ScopeCapabilities = dict[str, tuple[bool, bool, bool, bool]]


def normalize_scope_mode(scope_mode: str | None, *, default_mode: str = "selection") -> str:
    mode = (scope_mode or "").strip().lower()
    return mode or default_mode


def resolve_scope_ids(
    *,
    scope_mode: str | None,
    all_episode_ids: list[str],
    current_episode_id: str | None,
    selected_episode_ids: list[str],
    season: int | None,
    get_episode_ids_for_season: Callable[[int], list[str]],
) -> list[str]:
    mode = normalize_scope_mode(scope_mode)
    if mode == "current":
        return [current_episode_id] if current_episode_id else []
    if mode == "selection":
        return list(selected_episode_ids)
    if mode == "season":
        if season is None:
            return []
        return list(get_episode_ids_for_season(int(season)))
    if mode == "all":
        return list(all_episode_ids)
    return []


def has_non_empty_value(value: str | None) -> bool:
    return bool((value or "").strip())


def build_episode_url_by_id(index: SeriesIndex) -> dict[str, str]:
    return {ref.episode_id: ref.url for ref in index.episodes}


def filter_ids_with_source_url(*, ids: list[str], episode_url_by_id: dict[str, str]) -> list[str]:
    return [eid for eid in ids if has_non_empty_value(episode_url_by_id.get(eid))]


def filter_ids_with_raw(*, ids: list[str], has_episode_raw: Callable[[str], bool]) -> list[str]:
    return [eid for eid in ids if has_episode_raw(eid)]


def filter_ids_with_clean(*, ids: list[str], has_episode_clean: Callable[[str], bool]) -> list[str]:
    return [eid for eid in ids if has_episode_clean(eid)]


def filter_runnable_ids_for_full_workflow(
    *,
    ids: list[str],
    episode_url_by_id: dict[str, str],
    has_episode_raw: Callable[[str], bool],
    has_episode_clean: Callable[[str], bool],
) -> list[str]:
    return [
        eid
        for eid in ids
        if has_episode_clean(eid)
        or has_episode_raw(eid)
        or has_non_empty_value(episode_url_by_id.get(eid))
    ]


def build_episode_scope_capabilities(
    *,
    index: SeriesIndex,
    has_episode_raw: Callable[[str], bool],
    has_episode_clean: Callable[[str], bool],
    log: logging.Logger | None = None,
) -> ScopeCapabilities:
    episode_url_by_id = build_episode_url_by_id(index)
    capabilities: ScopeCapabilities = {}
    for eid in [e.episode_id for e in index.episodes]:
        has_url = has_non_empty_value(episode_url_by_id.get(eid))
        try:
            has_raw = bool(has_episode_raw(eid))
        except Exception:
            if log:
                log.exception("Failed to check RAW availability for %s", eid)
            has_raw = False
        try:
            has_clean = bool(has_episode_clean(eid))
        except Exception:
            if log:
                log.exception("Failed to check CLEAN availability for %s", eid)
            has_clean = False
        capabilities[eid] = (has_url, has_raw, has_clean, has_url or has_raw or has_clean)
    return capabilities


def resolve_episode_scope_capabilities_cache(
    *,
    cache: ScopeCapabilities,
    index: SeriesIndex,
    has_episode_raw: Callable[[str], bool],
    has_episode_clean: Callable[[str], bool],
    log: logging.Logger | None = None,
) -> ScopeCapabilities:
    expected_ids = [e.episode_id for e in index.episodes]
    if len(cache) != len(expected_ids) or any(eid not in cache for eid in expected_ids):
        return build_episode_scope_capabilities(
            index=index,
            has_episode_raw=has_episode_raw,
            has_episode_clean=has_episode_clean,
            log=log,
        )
    return cache
