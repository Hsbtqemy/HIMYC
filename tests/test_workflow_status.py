"""Tests unitaires du calcul d'état workflow (Pilotage > Corpus)."""

from __future__ import annotations

from howimetyourcorpus.app.workflow_status import (
    compute_workflow_status,
    load_episode_status_map,
)
from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex


class _StoreStub:
    def __init__(self, *, raw_ids: set[str] | None = None, clean_ids: set[str] | None = None) -> None:
        self._raw_ids = raw_ids or set()
        self._clean_ids = clean_ids or set()

    def has_episode_raw(self, episode_id: str) -> bool:
        return episode_id in self._raw_ids

    def has_episode_clean(self, episode_id: str) -> bool:
        return episode_id in self._clean_ids


class _DbStub:
    def __init__(
        self,
        *,
        statuses: dict[str, str] | None = None,
        segmented_ids: set[str] | None = None,
        indexed_ids: set[str] | None = None,
        tracks_by_ep: dict[str, list[object]] | None = None,
        runs_by_ep: dict[str, list[int]] | None = None,
    ) -> None:
        self._statuses = statuses or {}
        self._segmented_ids = segmented_ids or set()
        self._indexed_ids = indexed_ids or set()
        self._tracks_by_ep = tracks_by_ep or {}
        self._runs_by_ep = runs_by_ep or {}

    def get_episode_statuses(self, episode_ids: list[str]) -> dict[str, str]:
        return {eid: self._statuses[eid] for eid in episode_ids if eid in self._statuses}

    def get_episode_ids_with_segments(self, *, kind: str) -> list[str]:
        assert kind == "sentence"
        return list(self._segmented_ids)

    def get_episode_ids_indexed(self) -> list[str]:
        return list(self._indexed_ids)

    def get_tracks_for_episodes(self, episode_ids: list[str]) -> dict[str, list[object]]:
        return {eid: self._tracks_by_ep.get(eid, []) for eid in episode_ids}

    def get_align_runs_for_episodes(self, episode_ids: list[str]) -> dict[str, list[int]]:
        return {eid: self._runs_by_ep.get(eid, []) for eid in episode_ids}


def _index() -> SeriesIndex:
    return SeriesIndex(
        series_title="Test",
        series_url="https://example.test",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "E1", "u1"),
            EpisodeRef("S01E02", 1, 2, "E2", "u2"),
            EpisodeRef("S01E03", 1, 3, "E3", "u3"),
        ],
    )


def test_compute_workflow_status_aggregates_db_and_files() -> None:
    counts, error_ids = compute_workflow_status(
        index=_index(),
        store=_StoreStub(raw_ids={"S01E03"}, clean_ids={"S01E01"}),
        db=_DbStub(
            statuses={"S01E01": "fetched", "S01E02": "normalized", "S01E03": "error"},
            segmented_ids={"S01E02", "S99E99"},
            indexed_ids={"S01E02", "S01E03"},
            tracks_by_ep={"S01E01": [1], "S01E03": [2]},
            runs_by_ep={"S01E03": [1]},
        ),
    )
    assert counts.n_total == 3
    assert counts.n_fetched == 3
    assert counts.n_norm == 2
    assert counts.n_segmented == 1
    assert counts.n_indexed == 2
    assert counts.n_error == 1
    assert counts.n_with_srt == 2
    assert counts.n_aligned == 1
    assert error_ids == ["S01E03"]


def test_load_episode_status_map_handles_db_failure() -> None:
    class BrokenDb:
        def get_episode_statuses(self, _episode_ids: list[str]) -> dict[str, str]:
            raise RuntimeError("db down")

    assert load_episode_status_map(BrokenDb(), ["S01E01"]) == {}


def test_compute_workflow_status_is_resilient_to_db_failures() -> None:
    class PartialBrokenDb:
        def get_episode_ids_with_segments(self, *, kind: str) -> list[str]:
            raise RuntimeError("boom segments")

        def get_episode_ids_indexed(self) -> list[str]:
            raise RuntimeError("boom indexed")

        def get_tracks_for_episodes(self, episode_ids: list[str]) -> dict[str, list[int]]:
            raise RuntimeError("boom tracks")

        def get_align_runs_for_episodes(self, episode_ids: list[str]) -> dict[str, list[int]]:
            raise RuntimeError("boom runs")

    counts, error_ids = compute_workflow_status(
        index=_index(),
        store=_StoreStub(raw_ids={"S01E01"}, clean_ids={"S01E01"}),
        db=PartialBrokenDb(),
        status_map={"S01E03": "error"},
    )
    assert counts.n_total == 3
    assert counts.n_fetched == 1
    assert counts.n_norm == 1
    assert counts.n_segmented == 0
    assert counts.n_indexed == 0
    assert counts.n_error == 1
    assert counts.n_with_srt == 0
    assert counts.n_aligned == 0
    assert error_ids == ["S01E03"]


def test_compute_workflow_status_ignores_empty_subtitle_tracks() -> None:
    counts, _error_ids = compute_workflow_status(
        index=_index(),
        store=_StoreStub(),
        db=_DbStub(
            tracks_by_ep={
                "S01E01": [{"lang": "en", "nb_cues": 0}],
                "S01E02": [{"lang": "fr", "nb_cues": 3}],
                "S01E03": [],
            }
        ),
    )
    assert counts.n_with_srt == 1
