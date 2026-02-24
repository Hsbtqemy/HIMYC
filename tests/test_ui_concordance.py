"""Tests UI ciblés pour les comportements Concordance."""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from howimetyourcorpus.app.tabs.tab_concordance import ConcordanceTabWidget
from howimetyourcorpus.core.storage.db import KwicHit


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_filter_hits_by_speaker_returns_only_matching_speaker(
    qapp: QApplication,  # noqa: ARG001
) -> None:
    tab = ConcordanceTabWidget(
        get_db=lambda: None,
        on_open_inspector=lambda _episode_id: None,
    )
    hits = [
        KwicHit(
            episode_id="S01E01",
            title="Pilot",
            left="",
            match="hello",
            right="",
            position=0,
            segment_id="S01E01:sentence:0",
            kind="sentence",
            speaker="Ted",
        ),
        KwicHit(
            episode_id="S01E01",
            title="Pilot",
            left="",
            match="hello",
            right="",
            position=0,
            segment_id="S01E01:sentence:1",
            kind="sentence",
            speaker="Robin",
        ),
    ]

    filtered = tab._filter_hits_by_speaker(hits, "ted")

    assert len(filtered) == 1
    assert filtered[0].speaker == "Ted"


def test_filter_hits_by_speaker_returns_empty_when_no_match(
    qapp: QApplication,  # noqa: ARG001
) -> None:
    tab = ConcordanceTabWidget(
        get_db=lambda: None,
        on_open_inspector=lambda _episode_id: None,
    )
    hits = [
        KwicHit(
            episode_id="S01E01",
            title="Pilot",
            left="",
            match="hello",
            right="",
            position=0,
            segment_id="S01E01:sentence:0",
            kind="sentence",
            speaker="Ted",
        ),
    ]

    filtered = tab._filter_hits_by_speaker(hits, "Barney")

    assert filtered == []
