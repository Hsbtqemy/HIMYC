"""Tests ciblés BuildDbIndexStep (performance/skip)."""

from __future__ import annotations

from howimetyourcorpus.core.pipeline.tasks import BuildDbIndexStep


class _FakeStore:
    def __init__(self, clean_by_episode: dict[str, str]):
        self._clean_by_episode = clean_by_episode

    def has_episode_clean(self, episode_id: str) -> bool:
        return bool(self._clean_by_episode.get(episode_id, ""))

    def load_episode_text(self, episode_id: str, kind: str = "clean") -> str:
        assert kind == "clean"
        return self._clean_by_episode.get(episode_id, "")


class _FakeDb:
    def __init__(self, indexed: list[str] | None = None):
        self._indexed = set(indexed or [])
        self.get_indexed_calls = 0
        self.index_calls: list[str] = []

    def get_episode_ids_indexed(self) -> list[str]:
        self.get_indexed_calls += 1
        return sorted(self._indexed)

    def index_episode_text(self, episode_id: str, clean_text: str) -> None:
        self._indexed.add(episode_id)
        self.index_calls.append(episode_id)


def test_build_db_index_prefetches_indexed_ids_once() -> None:
    store = _FakeStore(
        {
            "S01E01": "already indexed",
            "S01E02": "to index",
            "S01E03": "to index too",
        }
    )
    db = _FakeDb(indexed=["S01E01"])
    step = BuildDbIndexStep(["S01E01", "S01E02", "S01E03"])
    result = step.run({"store": store, "db": db}, force=False)

    assert result.success
    assert db.get_indexed_calls == 1
    assert db.index_calls == ["S01E02", "S01E03"]


def test_build_db_index_force_does_not_read_indexed_ids() -> None:
    store = _FakeStore({"S01E01": "force reindex"})
    db = _FakeDb(indexed=["S01E01"])
    step = BuildDbIndexStep(["S01E01"])
    result = step.run({"store": store, "db": db}, force=True)

    assert result.success
    assert db.get_indexed_calls == 0
    assert db.index_calls == ["S01E01"]
