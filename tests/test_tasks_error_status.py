"""Tests de fiabilité: statut ERROR posé quand une étape échoue."""

from __future__ import annotations

from pathlib import Path

from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus, SeriesIndex
from howimetyourcorpus.core.pipeline.tasks import (
    BuildDbIndexStep,
    NormalizeEpisodeStep,
    RebuildSegmentsIndexStep,
    SegmentEpisodeStep,
)


class _StatusDbStub:
    def __init__(self) -> None:
        self.status_updates: list[tuple[str, str]] = []

    def set_episode_status(self, episode_id: str, status: str) -> None:
        self.status_updates.append((episode_id, status))


class _NormalizeStoreStub:
    def has_episode_clean(self, episode_id: str) -> bool:
        return False

    def load_episode_text(self, episode_id: str, kind: str = "raw") -> str:
        assert kind == "raw"
        return ""


class _NormalizeSuccessStoreStub:
    def __init__(self) -> None:
        self.saved_profile_id: str | None = None

    def has_episode_clean(self, episode_id: str) -> bool:
        return False

    def load_episode_text(self, episode_id: str, kind: str = "raw") -> str:
        assert kind == "raw"
        return "Hello world"

    def save_episode_clean(
        self,
        episode_id: str,
        clean_text: str,
        stats,
        debug,
        *,
        profile_id: str | None = None,
    ) -> None:
        self.saved_profile_id = profile_id


class _SegmentStoreStub:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def load_episode_text(self, episode_id: str, kind: str = "clean") -> str:
        assert kind == "clean"
        return ""


class _IndexStoreStub:
    def has_episode_clean(self, episode_id: str) -> bool:
        return True

    def load_episode_text(self, episode_id: str, kind: str = "clean") -> str:
        assert kind == "clean"
        return "Clean text"


def test_normalize_marks_error_when_raw_missing() -> None:
    db = _StatusDbStub()
    step = NormalizeEpisodeStep("S01E01", "default_en_v1")
    result = step.run(
        {
            "store": _NormalizeStoreStub(),
            "db": db,
            "custom_profiles": {},
        }
    )
    assert not result.success
    assert result.message == "No raw text: S01E01"
    assert db.status_updates[-1] == ("S01E01", EpisodeStatus.ERROR.value)


def test_normalize_persists_profile_id_in_store_metadata() -> None:
    db = _StatusDbStub()
    store = _NormalizeSuccessStoreStub()
    step = NormalizeEpisodeStep("S01E01", "default_en_v1")
    result = step.run(
        {
            "store": store,
            "db": db,
            "custom_profiles": {},
        }
    )
    assert result.success
    assert store.saved_profile_id == "default_en_v1"
    assert db.status_updates[-1] == ("S01E01", EpisodeStatus.NORMALIZED.value)


def test_segment_marks_error_when_clean_missing(tmp_path: Path) -> None:
    db = _StatusDbStub()
    step = SegmentEpisodeStep("S01E02")
    result = step.run(
        {
            "store": _SegmentStoreStub(tmp_path),
            "db": db,
        }
    )
    assert not result.success
    assert result.message == "No clean text: S01E02"
    assert db.status_updates[-1] == ("S01E02", EpisodeStatus.ERROR.value)


def test_build_index_marks_error_when_indexing_fails() -> None:
    class _IndexDbStub(_StatusDbStub):
        def get_episode_ids_indexed(self) -> list[str]:
            return []

        def index_episode_text(self, episode_id: str, clean_text: str) -> None:
            raise RuntimeError("sqlite write failed")

    db = _IndexDbStub()
    step = BuildDbIndexStep(["S01E03"])
    result = step.run({"store": _IndexStoreStub(), "db": db})
    assert not result.success
    assert "Indexing failed for S01E03:" in result.message
    assert db.status_updates[-1] == ("S01E03", EpisodeStatus.ERROR.value)


def test_rebuild_segments_returns_failure_when_one_episode_fails(tmp_path: Path) -> None:
    class _RebuildStore:
        def __init__(self, root_dir: Path) -> None:
            self.root_dir = root_dir
            self._index = SeriesIndex(
                series_title="Test",
                series_url="",
                episodes=[EpisodeRef("S01E01", 1, 1, "E1", "u1")],
            )

        def load_series_index(self) -> SeriesIndex:
            return self._index

        def has_episode_clean(self, episode_id: str) -> bool:
            return episode_id == "S01E01"

        def load_episode_text(self, episode_id: str, kind: str = "clean") -> str:
            assert kind == "clean"
            return "Hello. Hi there."

    class _RebuildDb(_StatusDbStub):
        def upsert_segments(self, episode_id: str, kind: str, segments) -> None:
            raise RuntimeError("write segments failed")

        def delete_align_runs_for_episode(self, episode_id: str) -> None:
            pass

    result = RebuildSegmentsIndexStep().run({"store": _RebuildStore(tmp_path), "db": _RebuildDb()})
    assert not result.success
    assert "write segments failed" in result.message
