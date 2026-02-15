"""Tests de performance/fonctionnel pour propagate_character_names."""

from __future__ import annotations

from pathlib import Path

from howimetyourcorpus.core.models import ProjectConfig
from howimetyourcorpus.core.storage.project_store import ProjectStore


class _PropagationDbStub:
    def __init__(self) -> None:
        self.segment_updates: list[tuple[str, str | None]] = []
        self.bulk_updates_calls = 0
        self.single_update_calls = 0
        self.get_cues_calls_by_lang: dict[str, int] = {}
        self._links = [
            {
                "role": "pivot",
                "segment_id": "S01E01:sentence:0",
                "cue_id": "S01E01:en:0",
            },
            {
                "role": "target",
                "cue_id": "S01E01:en:0",
                "cue_id_target": "S01E01:fr:0",
                "lang": "fr",
            },
        ]
        self._cues_by_lang: dict[str, list[dict]] = {
            "en": [
                {
                    "cue_id": "S01E01:en:0",
                    "n": 0,
                    "start_ms": 0,
                    "end_ms": 1500,
                    "text_raw": "Hello there",
                    "text_clean": "Hello there",
                }
            ],
            "fr": [
                {
                    "cue_id": "S01E01:fr:0",
                    "n": 0,
                    "start_ms": 0,
                    "end_ms": 1500,
                    "text_raw": "Salut",
                    "text_clean": "Salut",
                }
            ],
        }

    def query_alignment_for_episode(self, episode_id: str, run_id: str | None = None):
        assert episode_id == "S01E01"
        assert run_id == "run-1"
        return list(self._links)

    def update_segment_speaker(self, segment_id: str, speaker_explicit: str | None) -> None:
        self.segment_updates.append((segment_id, speaker_explicit))

    def get_cues_for_episode_lang(self, episode_id: str, lang: str):
        assert episode_id == "S01E01"
        self.get_cues_calls_by_lang[lang] = self.get_cues_calls_by_lang.get(lang, 0) + 1
        return [dict(row) for row in self._cues_by_lang.get(lang, [])]

    def update_cues_text_clean_bulk(self, updates: list[tuple[str, str]]) -> int:
        self.bulk_updates_calls += 1
        updated = 0
        for cue_id, text_clean in updates:
            for rows in self._cues_by_lang.values():
                for row in rows:
                    if row.get("cue_id") == cue_id:
                        row["text_clean"] = text_clean
                        updated += 1
                        break
        return updated

    def update_cue_text_clean(self, cue_id: str, text_clean: str) -> None:
        self.single_update_calls += 1
        for rows in self._cues_by_lang.values():
            for row in rows:
                if row.get("cue_id") == cue_id:
                    row["text_clean"] = text_clean
                    return


def _init_store(tmp_path: Path) -> ProjectStore:
    ProjectStore.init_project(
        ProjectConfig(
            project_name="t",
            root_dir=tmp_path,
            source_id="subslikescript",
            series_url="",
        )
    )
    return ProjectStore(tmp_path)


def test_propagate_character_names_uses_bulk_updates_and_cached_cues(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    store.save_character_names(
        [
            {
                "id": "ted",
                "canonical": "Ted",
                "names_by_lang": {"en": "Ted", "fr": "Ted (FR)"},
            }
        ]
    )
    store.save_character_assignments(
        [
            {
                "episode_id": "S01E01",
                "source_type": "segment",
                "source_id": "S01E01:sentence:0",
                "character_id": "ted",
            }
        ]
    )
    db = _PropagationDbStub()

    nb_seg, nb_cue = store.propagate_character_names(db, "S01E01", "run-1")

    assert nb_seg == 1
    assert nb_cue == 2
    assert db.segment_updates == [("S01E01:sentence:0", "ted")]
    assert db.bulk_updates_calls == 1
    assert db.single_update_calls == 0
    assert db.get_cues_calls_by_lang.get("en") == 1
    assert db.get_cues_calls_by_lang.get("fr") == 1
    assert db._cues_by_lang["en"][0]["text_clean"].startswith("Ted: ")
    assert db._cues_by_lang["fr"][0]["text_clean"].startswith("Ted (FR): ")


def test_character_files_roundtrip_names_and_assignments(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    characters = [
        {
            "id": "marshall",
            "canonical": "Marshall",
            "names_by_lang": {"en": "Marshall", "fr": "Marshall"},
        },
        {
            "id": "lily",
            "canonical": "Lily",
            "names_by_lang": {"en": "Lily", "fr": "Lily"},
        },
    ]
    assignments = [
        {
            "episode_id": "S01E01",
            "source_type": "segment",
            "source_id": "S01E01:sentence:12",
            "character_id": "marshall",
        },
        {
            "episode_id": "S01E01",
            "source_type": "cue",
            "source_id": "S01E01:fr:99",
            "character_id": "lily",
        },
    ]

    store.save_character_names(characters)
    store.save_character_assignments(assignments)

    assert store.load_character_names() == characters
    assert store.load_character_assignments() == assignments


def test_character_files_load_returns_empty_list_on_invalid_payload(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    (tmp_path / store.CHARACTER_NAMES_JSON).write_text('{"characters":{"bad":"shape"}}', encoding="utf-8")
    (tmp_path / store.CHARACTER_ASSIGNMENTS_JSON).write_text("{invalid json", encoding="utf-8")

    assert store.load_character_names() == []
    assert store.load_character_assignments() == []


def test_propagate_character_names_prefers_explicit_cue_assignment_over_pivot(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    store.save_character_names(
        [
            {
                "id": "ted",
                "canonical": "Ted",
                "names_by_lang": {"en": "Ted", "fr": "Ted (FR)"},
            },
            {
                "id": "lily",
                "canonical": "Lily",
                "names_by_lang": {"en": "Lily", "fr": "Lily (FR)"},
            },
        ]
    )
    store.save_character_assignments(
        [
            {
                "episode_id": "S01E01",
                "source_type": "segment",
                "source_id": "S01E01:sentence:0",
                "character_id": "ted",
            },
            {
                "episode_id": "S01E01",
                "source_type": "cue",
                "source_id": "S01E01:en:0",
                "character_id": "lily",
            },
        ]
    )
    db = _PropagationDbStub()

    nb_seg, nb_cue = store.propagate_character_names(db, "S01E01", "run-1")

    assert nb_seg == 1
    assert nb_cue == 2
    # Le segment garde son assignation dédiée.
    assert db.segment_updates == [("S01E01:sentence:0", "ted")]
    # Les cues utilisent l'assignation explicite cue (Lily), pas la propagation pivot (Ted).
    assert db._cues_by_lang["en"][0]["text_clean"].startswith("Lily: ")
    assert db._cues_by_lang["fr"][0]["text_clean"].startswith("Lily (FR): ")


def test_propagate_character_names_is_idempotent_when_prefix_already_present(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    store.save_character_names(
        [
            {
                "id": "ted",
                "canonical": "Ted",
                "names_by_lang": {"en": "Ted", "fr": "Ted (FR)"},
            }
        ]
    )
    store.save_character_assignments(
        [
            {
                "episode_id": "S01E01",
                "source_type": "segment",
                "source_id": "S01E01:sentence:0",
                "character_id": "ted",
            }
        ]
    )
    db = _PropagationDbStub()
    db._cues_by_lang["en"][0]["text_clean"] = "Ted: Hello there"
    db._cues_by_lang["fr"][0]["text_clean"] = "Ted (FR): Salut"

    nb_seg, nb_cue = store.propagate_character_names(db, "S01E01", "run-1")

    assert nb_seg == 1
    assert nb_cue == 0
    assert db.bulk_updates_calls == 0
    assert db.single_update_calls == 0
    # Aucun rewrite SRT si aucun changement de cue.
    assert not (tmp_path / "episodes" / "S01E01" / "subs" / "en.srt").exists()
    assert not (tmp_path / "episodes" / "S01E01" / "subs" / "fr.srt").exists()
