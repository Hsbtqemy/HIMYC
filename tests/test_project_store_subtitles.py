"""Tests ProjectStore: robustesse des pistes sous-titres vis-a-vis de la casse."""

from __future__ import annotations

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


def _subs_dir(root: Path, episode_id: str) -> Path:
    d = root / "episodes" / episode_id / "subs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_get_subtitle_path_is_case_insensitive_on_lang_and_extension(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    d = _subs_dir(tmp_path, "S01E01")
    p = d / "EN.SRT"
    p.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")

    resolved = store.get_episode_subtitle_path("S01E01", "en")

    assert resolved is not None
    path, fmt = resolved
    assert path == p
    assert fmt == "srt"
    assert store.has_episode_subs("S01E01", "en")


def test_get_subtitle_path_prefers_srt_when_both_exist(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    d = _subs_dir(tmp_path, "S01E02")
    p_vtt = d / "en.VTT"
    p_srt = d / "EN.srt"
    p_vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHi\n", encoding="utf-8")
    p_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")

    resolved = store.get_episode_subtitle_path("S01E02", "en")

    assert resolved is not None
    path, fmt = resolved
    assert path == p_srt
    assert fmt == "srt"


def test_remove_subtitle_deletes_case_variants_and_cues(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    d = _subs_dir(tmp_path, "S01E03")
    p_srt = d / "EN.SRT"
    p_cues = d / "EN_cues.JSONL"
    p_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    p_cues.write_text('{"n": 0}\n', encoding="utf-8")

    store.remove_episode_subtitle("S01E03", "en")

    assert not p_srt.exists()
    assert not p_cues.exists()
