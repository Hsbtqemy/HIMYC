"""Tests unitaires des fonctions pures de scope Corpus."""

from __future__ import annotations

from howimetyourcorpus.app.corpus_scope import (
    build_profile_by_episode,
    build_episode_scope_capabilities,
    build_episode_url_by_id,
    filter_ids_with_clean,
    filter_ids_with_raw,
    filter_ids_with_source_url,
    filter_runnable_ids_for_full_workflow,
    normalize_scope_mode,
    resolve_scope_ids,
    resolve_episode_scope_capabilities_cache,
)
from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex


def _sample_index() -> SeriesIndex:
    return SeriesIndex(
        series_title="s",
        series_url="u",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "Pilot", "https://src/1"),
            EpisodeRef("S01E02", 1, 2, "Purple Giraffe", ""),
            EpisodeRef("S01E03", 1, 3, "Sweet Taste of Liberty", "   "),
        ],
    )


def test_build_episode_url_and_filter_source_url() -> None:
    index = _sample_index()
    by_id = build_episode_url_by_id(index)
    assert by_id["S01E01"] == "https://src/1"
    assert filter_ids_with_source_url(
        ids=["S01E01", "S01E02", "S01E03"],
        episode_url_by_id=by_id,
    ) == ["S01E01"]


def test_normalize_scope_mode_and_resolve_scope_ids() -> None:
    assert normalize_scope_mode(None) == "selection"
    assert normalize_scope_mode(" CURRENT ") == "current"
    assert resolve_scope_ids(
        scope_mode="current",
        all_episode_ids=["S01E01", "S01E02"],
        current_episode_id="S01E02",
        selected_episode_ids=["S01E01"],
        season=1,
        get_episode_ids_for_season=lambda _season: ["S01E01", "S01E02"],
    ) == ["S01E02"]
    assert resolve_scope_ids(
        scope_mode="selection",
        all_episode_ids=["S01E01", "S01E02"],
        current_episode_id="S01E02",
        selected_episode_ids=["S01E01"],
        season=1,
        get_episode_ids_for_season=lambda _season: ["S01E01", "S01E02"],
    ) == ["S01E01"]
    assert resolve_scope_ids(
        scope_mode="season",
        all_episode_ids=["S01E01", "S01E02"],
        current_episode_id="S01E02",
        selected_episode_ids=["S01E01"],
        season=1,
        get_episode_ids_for_season=lambda _season: ["S01E01", "S01E02"],
    ) == ["S01E01", "S01E02"]
    assert resolve_scope_ids(
        scope_mode="all",
        all_episode_ids=["S01E01", "S01E02"],
        current_episode_id="S01E02",
        selected_episode_ids=["S01E01"],
        season=1,
        get_episode_ids_for_season=lambda _season: ["S01E01", "S01E02"],
    ) == ["S01E01", "S01E02"]


def test_filter_ids_with_raw_clean_and_runnable() -> None:
    ids = ["S01E01", "S01E02", "S01E03"]
    has_raw = {"S01E02"}
    has_clean = {"S01E03"}
    by_id = {"S01E01": "https://src/1", "S01E02": "", "S01E03": ""}
    assert filter_ids_with_raw(ids=ids, has_episode_raw=lambda eid: eid in has_raw) == ["S01E02"]
    assert filter_ids_with_clean(ids=ids, has_episode_clean=lambda eid: eid in has_clean) == ["S01E03"]
    assert filter_runnable_ids_for_full_workflow(
        ids=ids,
        episode_url_by_id=by_id,
        has_episode_raw=lambda eid: eid in has_raw,
        has_episode_clean=lambda eid: eid in has_clean,
    ) == ["S01E01", "S01E02", "S01E03"]


def test_build_scope_capabilities_handles_callback_errors() -> None:
    index = _sample_index()

    def _has_raw(eid: str) -> bool:
        if eid == "S01E02":
            raise RuntimeError("boom raw")
        return eid == "S01E01"

    def _has_clean(eid: str) -> bool:
        if eid == "S01E03":
            raise RuntimeError("boom clean")
        return eid == "S01E01"

    caps = build_episode_scope_capabilities(
        index=index,
        has_episode_raw=_has_raw,
        has_episode_clean=_has_clean,
    )
    assert caps["S01E01"] == (True, True, True, True)
    assert caps["S01E02"] == (False, False, False, False)
    assert caps["S01E03"] == (False, False, False, False)


def test_resolve_scope_capabilities_cache_reuses_or_rebuilds() -> None:
    index = _sample_index()
    built = build_episode_scope_capabilities(
        index=index,
        has_episode_raw=lambda _eid: False,
        has_episode_clean=lambda _eid: False,
    )
    same = resolve_episode_scope_capabilities_cache(
        cache=dict(built),
        index=index,
        has_episode_raw=lambda _eid: True,
        has_episode_clean=lambda _eid: True,
    )
    assert same == built

    changed_index = SeriesIndex(
        series_title="s",
        series_url="u",
        episodes=index.episodes + [EpisodeRef("S01E04", 1, 4, "Return", "")],
    )
    rebuilt = resolve_episode_scope_capabilities_cache(
        cache=dict(built),
        index=changed_index,
        has_episode_raw=lambda _eid: False,
        has_episode_clean=lambda _eid: False,
    )
    assert "S01E04" in rebuilt


def test_build_profile_by_episode_priority_order() -> None:
    refs = [
        EpisodeRef("S01E01", 1, 1, "Pilot", "u", source_id="subslikescript"),
        EpisodeRef("S01E02", 1, 2, "Purple", "u", source_id="alt_source"),
        EpisodeRef("S01E03", 1, 3, "Liberty", "u", source_id=None),
    ]
    profiles = build_profile_by_episode(
        episode_refs=refs,
        episode_ids=["S01E01", "S01E02", "S01E03"],
        batch_profile="default_en_v1",
        episode_preferred_profiles={"S01E01": "episode_pref_v2"},
        source_profile_defaults={"subslikescript": "source_default_v1", "alt_source": "source_alt_v1"},
    )
    assert profiles == {
        "S01E01": "episode_pref_v2",
        "S01E02": "source_alt_v1",
        "S01E03": "default_en_v1",
    }
