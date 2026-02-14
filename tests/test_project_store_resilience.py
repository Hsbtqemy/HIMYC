"""Tests de robustesse JSON pour ProjectStore."""

from __future__ import annotations

import json
from pathlib import Path

from howimetyourcorpus.core.models import ProjectConfig, TransformStats
from howimetyourcorpus.core.storage.project_store import ProjectStore, load_project_config


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


def test_load_series_index_returns_none_on_invalid_json(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    (tmp_path / "series_index.json").write_text("{invalid", encoding="utf-8")

    assert store.load_series_index() is None


def test_load_series_index_skips_malformed_episode_rows(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    (tmp_path / "series_index.json").write_text(
        json.dumps(
            {
                "series_title": "T",
                "series_url": "u",
                "episodes": [
                    {
                        "episode_id": "S01E01",
                        "season": 1,
                        "episode": 1,
                        "title": "ok",
                        "url": "u1",
                    },
                    {
                        "episode_id": "S01E02",
                        "season": "bad",
                        "episode": 2,
                        "title": "bad",
                        "url": "u2",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    index = store.load_series_index()

    assert index is not None
    assert [e.episode_id for e in index.episodes] == ["S01E01"]


def test_load_series_index_skips_missing_episode_id_rows(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    (tmp_path / "series_index.json").write_text(
        json.dumps(
            {
                "series_title": "T",
                "series_url": "u",
                "episodes": [
                    {
                        "episode_id": "s01e01",
                        "season": 1,
                        "episode": 1,
                        "title": "ok",
                        "url": "u1",
                    },
                    {
                        "episode_id": "",
                        "season": 1,
                        "episode": 2,
                        "title": "bad",
                        "url": "u2",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    index = store.load_series_index()

    assert index is not None
    assert [e.episode_id for e in index.episodes] == ["S01E01"]


def test_load_episode_transform_meta_returns_none_on_invalid_json(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    episode_dir = tmp_path / "episodes" / "S01E01"
    episode_dir.mkdir(parents=True, exist_ok=True)
    (episode_dir / "transform_meta.json").write_text("{invalid", encoding="utf-8")

    assert store.load_episode_transform_meta("S01E01") is None


def test_load_project_languages_falls_back_to_defaults_on_invalid_json(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    (tmp_path / "languages.json").write_text("{invalid", encoding="utf-8")

    assert store.load_project_languages() == ProjectStore.DEFAULT_LANGUAGES


def test_save_episode_clean_persists_profile_traceability(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    store.save_episode_clean(
        "S01E01",
        "clean line",
        TransformStats(raw_lines=2, clean_lines=1, merges=1),
        debug={"merge_examples": []},
        profile_id="default_en_v1",
    )
    meta = store.load_episode_transform_meta("S01E01")
    assert meta is not None
    assert meta.get("profile_id") == "default_en_v1"
    assert str(meta.get("normalized_at_utc") or "").endswith("+00:00")


def test_init_project_persists_acquisition_profile_id(tmp_path: Path) -> None:
    config = ProjectConfig(
        project_name="t",
        root_dir=tmp_path,
        source_id="subslikescript",
        series_url="",
        acquisition_profile_id="safe_v1",
    )
    ProjectStore.init_project(config)

    cfg = load_project_config(tmp_path / "config.toml")
    assert cfg.get("acquisition_profile_id") == "safe_v1"


def test_save_config_main_updates_acquisition_profile_id(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    store.save_config_main(acquisition_profile_id="fast_v1")

    cfg = load_project_config(tmp_path / "config.toml")
    assert cfg.get("acquisition_profile_id") == "fast_v1"
