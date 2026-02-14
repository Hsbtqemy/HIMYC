"""Tests des steps fetch_*: propagation des options HTTP via profil d'acquisition."""

from __future__ import annotations

from pathlib import Path

from howimetyourcorpus.core.models import EpisodeRef, ProjectConfig, SeriesIndex
from howimetyourcorpus.core.pipeline.tasks import FetchEpisodeStep, FetchSeriesIndexStep


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
