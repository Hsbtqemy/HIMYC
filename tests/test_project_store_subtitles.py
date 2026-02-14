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


def test_remove_subtitle_deletes_normalize_meta(tmp_path: Path) -> None:
    store = _init_store(tmp_path)
    d = _subs_dir(tmp_path, "S01E04")
    p_srt = d / "en.srt"
    p_meta = d / "en_normalize_meta.json"
    p_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    p_meta.write_text('{"profile_id":"default_en_v1"}', encoding="utf-8")

    store.remove_episode_subtitle("S01E04", "en")

    assert not p_srt.exists()
    assert not p_meta.exists()


def test_normalize_subtitle_track_persists_normalize_meta(tmp_path: Path) -> None:
    class _DbStub:
        def __init__(self) -> None:
            self.rows = [{"cue_id": "cue-1", "text_raw": " Hello  world ", "text_clean": ""}]

        def get_cues_for_episode_lang(self, episode_id: str, lang: str):
            return list(self.rows)

        def update_cue_text_clean(self, cue_id: str, text_clean: str) -> None:
            for row in self.rows:
                if row["cue_id"] == cue_id:
                    row["text_clean"] = text_clean
                    return

    store = _init_store(tmp_path)
    db = _DbStub()

    nb = store.normalize_subtitle_track(db, "S01E05", "en", "default_en_v1", rewrite_srt=False)

    assert nb == 1
    meta = store.load_subtitle_normalize_meta("S01E05", "en")
    assert meta is not None
    assert meta.get("profile_id") == "default_en_v1"
    assert meta.get("updated_cues") == 1
    assert meta.get("rewrite_srt") is False
