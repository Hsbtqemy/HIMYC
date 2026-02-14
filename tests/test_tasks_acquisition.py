"""Tests des steps fetch_*: propagation des options HTTP via profil d'acquisition."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from howimetyourcorpus.core.models import EpisodeRef, ProjectConfig, SeriesIndex
from howimetyourcorpus.core.pipeline.tasks import (
    DownloadOpenSubtitlesStep,
    FetchEpisodeStep,
    FetchSeriesIndexStep,
)


class _SeriesStoreStub:
    def __init__(self) -> None:
        self.saved_index: SeriesIndex | None = None

    def save_series_index(self, index: SeriesIndex) -> None:
        self.saved_index = index


class _SeriesAdapterStub:
    id = "subslikescript"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def discover_series(self, series_url: str, **kwargs) -> SeriesIndex:
        self.calls.append({"series_url": series_url, **kwargs})
        return SeriesIndex(
            series_title="Test",
            series_url=series_url,
            episodes=[EpisodeRef("S01E01", 1, 1, "Pilot", "https://example.test/ep1")],
        )


def test_fetch_series_index_uses_acquisition_http_options(monkeypatch) -> None:
    adapter = _SeriesAdapterStub()
    monkeypatch.setattr(
        "howimetyourcorpus.core.pipeline.tasks.AdapterRegistry.get",
        lambda _source_id: adapter,
    )
    config = ProjectConfig(
        project_name="t",
        root_dir=Path("."),
        source_id="subslikescript",
        series_url="https://subslikescript.com/series/X",
        rate_limit_s=7.0,
        user_agent="CustomAgent/1.0",
        acquisition_profile_id="safe_v1",
    )
    store = _SeriesStoreStub()

    result = FetchSeriesIndexStep(config.series_url).run({"store": store, "config": config})

    assert result.success
    assert store.saved_index is not None
    assert len(adapter.calls) == 1
    call = adapter.calls[0]
    assert call["rate_limit_s"] == 7.0
    assert call["timeout_s"] == 45.0
    assert call["retries"] == 4
    assert call["backoff_s"] == 3.0
    assert "acq=safe_v1" in str(call["user_agent"])


class _EpisodeStoreStub:
    def __init__(self) -> None:
        self.saved_html: str | None = None
        self.saved_raw: str | None = None
        self.saved_meta: dict | None = None

    def has_episode_raw(self, episode_id: str) -> bool:
        return False

    def load_series_index(self):
        return None

    def save_episode_html(self, episode_id: str, html: str) -> None:
        self.saved_html = html

    def save_episode_raw(self, episode_id: str, raw_text: str, meta: dict) -> None:
        self.saved_raw = raw_text
        self.saved_meta = meta


class _EpisodeDbStub:
    def __init__(self) -> None:
        self.status_updates: list[tuple[str, str]] = []

    def set_episode_status(self, episode_id: str, status: str) -> None:
        self.status_updates.append((episode_id, status))


class _EpisodeAdapterStub:
    id = "subslikescript"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def fetch_episode_html(self, episode_url: str, **kwargs) -> str:
        self.calls.append({"episode_url": episode_url, **kwargs})
        return "<html><body>ok</body></html>"

    def parse_episode(self, html: str, episode_url: str) -> tuple[str, dict]:
        return "TED: hello", {"selectors_used": ["x"], "warnings": []}


def test_fetch_episode_uses_acquisition_http_options(monkeypatch) -> None:
    adapter = _EpisodeAdapterStub()
    monkeypatch.setattr(
        "howimetyourcorpus.core.pipeline.tasks.AdapterRegistry.get",
        lambda _source_id: adapter,
    )
    config = ProjectConfig(
        project_name="t",
        root_dir=Path("."),
        source_id="subslikescript",
        series_url="https://subslikescript.com/series/X",
        rate_limit_s=1.0,
        user_agent="Agent/2.0",
        acquisition_profile_id="fast_v1",
    )
    store = _EpisodeStoreStub()
    db = _EpisodeDbStub()

    result = FetchEpisodeStep("S01E01", "https://subslikescript.com/series/X/season-1/episode-1").run(
        {"store": store, "config": config, "db": db}
    )

    assert result.success
    assert store.saved_html is not None
    assert store.saved_raw == "TED: hello"
    assert len(adapter.calls) == 1
    call = adapter.calls[0]
    assert call["rate_limit_s"] == 1.0
    assert call["timeout_s"] == 20.0
    assert call["retries"] == 2
    assert call["backoff_s"] == 1.0
    assert "acq=fast_v1" in str(call["user_agent"])


class _OpenSubsStoreStub:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.saved_content: str | None = None
        self.saved_lang: str | None = None

    def save_episode_subtitle_content(self, episode_id: str, lang: str, content: str, fmt: str):
        self.saved_content = content
        self.saved_lang = lang
        p = self.root / f"{episode_id}_{lang}.{fmt}"
        p.write_text(content, encoding="utf-8")
        return p

    def save_episode_subtitles(self, episode_id: str, lang: str, content: str, fmt: str, cues_audit):
        self.saved_content = content
        self.saved_lang = lang


def test_download_opensubtitles_uses_acquisition_http_options(monkeypatch, tmp_path: Path) -> None:
    captured_init: dict[str, object] = {}

    class _ClientStub:
        def __init__(self, **kwargs):
            captured_init.update(kwargs)

        def search(self, imdb_id: str, season: int, episode: int, language: str):
            return [SimpleNamespace(file_id=1234)]

        def download(self, file_id: int) -> str:
            assert file_id == 1234
            return "1\n00:00:00,000 --> 00:00:01,000\nHello\n"

    monkeypatch.setattr(
        "howimetyourcorpus.core.pipeline.tasks.OpenSubtitlesClient",
        _ClientStub,
    )

    config = ProjectConfig(
        project_name="t",
        root_dir=tmp_path,
        source_id="subslikescript",
        series_url="https://subslikescript.com/series/X",
        rate_limit_s=4.0,
        user_agent="Agent/3.0",
        acquisition_profile_id="safe_v1",
    )
    store = _OpenSubsStoreStub(tmp_path)
    step = DownloadOpenSubtitlesStep(
        episode_id="S01E01",
        season=1,
        episode=1,
        lang="en",
        api_key="api-key",
        imdb_id="tt0460649",
    )

    result = step.run({"store": store, "db": None, "config": config})

    assert result.success
    assert store.saved_content is not None
    assert captured_init["api_key"] == "api-key"
    assert captured_init["timeout_s"] == 45.0
    assert captured_init["retries"] == 4
    assert captured_init["backoff_s"] == 3.0
    assert captured_init["min_interval_s"] == 4.0
    assert "acq=safe_v1" in str(captured_init["user_agent"])
