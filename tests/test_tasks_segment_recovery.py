"""Tests de récupération SegmentEpisodeStep quand fichiers et DB divergent."""

from __future__ import annotations

from pathlib import Path

from howimetyourcorpus.core.pipeline.tasks import SegmentEpisodeStep


class _SegmentStoreStub:
    def __init__(self, root_dir: Path, clean_text: str) -> None:
        self.root_dir = root_dir
        self._clean_text = clean_text

    def load_episode_text(self, episode_id: str, kind: str = "clean") -> str:
        assert kind == "clean"
        return self._clean_text


class _BaseSegmentDbStub:
    def __init__(self) -> None:
        self.upsert_calls: list[tuple[str, str, int]] = []
        self.delete_align_calls: list[str] = []

    def upsert_segments(self, episode_id: str, kind: str, segments) -> None:
        self.upsert_calls.append((episode_id, kind, len(segments)))

    def delete_align_runs_for_episode(self, episode_id: str) -> None:
        self.delete_align_calls.append(episode_id)


class _DbWithoutSegments(_BaseSegmentDbStub):
    def get_segments_for_episode(self, episode_id: str, kind: str | None = None):
        return []


class _DbWithSegments(_BaseSegmentDbStub):
    def get_segments_for_episode(self, episode_id: str, kind: str | None = None):
        if kind in {"sentence", "utterance"}:
            return [{"segment_id": f"{episode_id}:{kind}:0"}]
        return []


def _seed_segments_file(root_dir: Path, episode_id: str) -> None:
    ep_dir = root_dir / "episodes" / episode_id
    ep_dir.mkdir(parents=True, exist_ok=True)
    (ep_dir / "segments.jsonl").write_text('{"segment_id":"legacy"}\n', encoding="utf-8")


def test_segment_rebuilds_when_file_exists_but_db_is_empty(tmp_path: Path) -> None:
    episode_id = "S01E10"
    _seed_segments_file(tmp_path, episode_id)
    db = _DbWithoutSegments()
    store = _SegmentStoreStub(tmp_path, clean_text="Hello world.\nHow are you?")

    result = SegmentEpisodeStep(episode_id).run({"store": store, "db": db})

    assert result.success
    assert result.message == f"Segmented: {episode_id}"
    kinds = {kind for _eid, kind, _n in db.upsert_calls}
    assert kinds == {"sentence", "utterance"}
    assert db.delete_align_calls == [episode_id]


def test_segment_skips_when_file_exists_and_db_is_complete(tmp_path: Path) -> None:
    episode_id = "S01E11"
    _seed_segments_file(tmp_path, episode_id)
    db = _DbWithSegments()
    store = _SegmentStoreStub(tmp_path, clean_text="Should not be read.")

    result = SegmentEpisodeStep(episode_id).run({"store": store, "db": db})

    assert result.success
    assert result.message == f"Already segmented: {episode_id}"
    assert db.upsert_calls == []
    assert db.delete_align_calls == []
