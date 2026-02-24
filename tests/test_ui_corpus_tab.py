"""Tests UI de base pour l'onglet Corpus."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from howimetyourcorpus.app.tabs.tab_corpus import CorpusTabWidget


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_corpus_ribbon_is_expanded_by_default_and_toggleable(qapp: QApplication) -> None:
    tab = CorpusTabWidget(
        get_store=lambda: None,
        get_db=lambda: None,
        get_context=lambda: None,
        run_job=lambda steps: None,
        show_status=lambda msg, ms: None,
        refresh_after_episodes_added=lambda: None,
        on_cancel_job=lambda: None,
    )
    assert tab.corpus_ribbon_toggle_btn.isChecked()
    assert not tab.corpus_ribbon_content.isHidden()
    assert tab.corpus_ribbon_toggle_btn.text() == "Masquer le panneau d'actions"

    tab.corpus_ribbon_toggle_btn.click()
    assert not tab.corpus_ribbon_toggle_btn.isChecked()
    assert tab.corpus_ribbon_content.isHidden()
    assert tab.corpus_ribbon_toggle_btn.text() == "Afficher le panneau d'actions"

    tab.corpus_ribbon_toggle_btn.click()
    assert tab.corpus_ribbon_toggle_btn.isChecked()
    assert not tab.corpus_ribbon_content.isHidden()
    assert tab.corpus_ribbon_toggle_btn.text() == "Masquer le panneau d'actions"

