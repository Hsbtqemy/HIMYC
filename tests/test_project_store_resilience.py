"""Tests de robustesse JSON pour ProjectStore."""

from __future__ import annotations

import json
from pathlib import Path

from howimetyourcorpus.core.models import ProjectConfig
from howimetyourcorpus.core.storage.project_store import ProjectStore


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
