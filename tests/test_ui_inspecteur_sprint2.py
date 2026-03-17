"""Tests non-régression Sprint 2 — US-205 : états partiels, mismatch contexte, transitions onglets."""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from howimetyourcorpus.app.tabs.tab_inspecteur import InspectorTabWidget  # noqa: E402
from howimetyourcorpus.app.tabs.tab_inspecteur_sous_titres import InspecteurEtSousTitresTabWidget  # noqa: E402
from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex  # noqa: E402
from howimetyourcorpus.core.normalize.profiles import NormalizationProfile  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

_EPISODES = [
    EpisodeRef(episode_id="S01E01", season=1, episode=1, title="Pilot",
               url="u1", source_id="src"),
    EpisodeRef(episode_id="S01E02", season=1, episode=2, title="Purple Giraffe",
               url="u2", source_id="src"),
]


class _FakeConfig:
    normalize_profile = "default_en_v1"


class _FakeStore:
    """Store configurable épisode-par-épisode pour états partiels."""

    def __init__(
        self,
        *,
        raw_episodes: set[str] | None = None,
        clean_episodes: set[str] | None = None,
    ) -> None:
        self._raw = raw_episodes if raw_episodes is not None else {"S01E01", "S01E02"}
        self._clean = clean_episodes if clean_episodes is not None else {"S01E01", "S01E02"}
        self._index = SeriesIndex(series_title="T", series_url="u", episodes=_EPISODES)
        self.loaded_episodes: list[str] = []

    def load_series_index(self) -> SeriesIndex:
        return self._index

    def load_episode_notes(self, episode_id: str) -> str:  # noqa: ARG002
        return ""

    def save_episode_notes(self, episode_id: str, text: str) -> None:  # noqa: ARG002
        pass

    def load_episode_text(self, episode_id: str, kind: str = "raw") -> str:
        self.loaded_episodes.append(episode_id)
        return "text"

    def load_episode_transform_meta(self, episode_id: str):  # noqa: ARG002
        return None

    def load_episode_preferred_profiles(self) -> dict[str, str]:
        return {}

    def save_episode_preferred_profiles(self, p: dict[str, str]) -> None:  # noqa: ARG002
        pass

    def load_source_profile_defaults(self) -> dict[str, str]:
        return {}

    def has_episode_raw(self, episode_id: str) -> bool:
        return episode_id in self._raw

    def has_episode_clean(self, episode_id: str) -> bool:
        return episode_id in self._clean

    def load_custom_profiles(self) -> dict[str, NormalizationProfile]:
        return {}

    def load_episode_subtitle_content(self, episode_id: str, lang: str):  # noqa: ARG002
        return None


class _FakeDb:
    def __init__(
        self,
        *,
        segments: dict[str, list] | None = None,
        tracks: dict[str, list] | None = None,
    ) -> None:
        self._segments = segments or {}
        self._tracks = tracks or {}

    def get_segments_for_episode(self, episode_id: str, kind: str | None = None):  # noqa: ARG002
        return list(self._segments.get(episode_id, []))

    def get_tracks_for_episode(self, episode_id: str):
        return list(self._tracks.get(episode_id, []))


def _inspector(store, db) -> InspectorTabWidget:
    tab = InspectorTabWidget(
        get_store=lambda: store,
        get_db=lambda: db,
        get_config=lambda: _FakeConfig(),
        run_job=lambda _s: None,
        show_status=lambda _m, _t=3000: None,
    )
    tab.refresh()
    return tab


def _combined(store, db) -> InspecteurEtSousTitresTabWidget:
    tab = InspecteurEtSousTitresTabWidget(
        get_store=lambda: store,
        get_db=lambda: db,
        get_config=lambda: _FakeConfig(),
        run_job=lambda _s: None,
        refresh_episodes=lambda: None,
        show_status=lambda _m, _t=3000: None,
    )
    tab.refresh()
    return tab


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# États partiels
# ---------------------------------------------------------------------------

def test_partial_raw_only_segment_btn_disabled(qapp: QApplication) -> None:  # noqa: ARG001
    """RAW présent, CLEAN absent → Segmenter désactivé, Normaliser actif."""
    store = _FakeStore(raw_episodes={"S01E01"}, clean_episodes=set())
    db = _FakeDb()
    tab = _inspector(store, db)
    assert tab.inspect_norm_btn.isEnabled(), "Normaliser doit être actif si RAW présent"
    assert not tab.inspect_segment_btn.isEnabled(), "Segmenter doit être désactivé sans CLEAN"


def test_partial_clean_no_segments_export_disabled(qapp: QApplication) -> None:  # noqa: ARG001
    """CLEAN présent, segments absents → Exporter désactivé, Segmenter actif."""
    store = _FakeStore(raw_episodes={"S01E01"}, clean_episodes={"S01E01"})
    db = _FakeDb(segments={})
    tab = _inspector(store, db)
    assert tab.inspect_segment_btn.isEnabled(), "Segmenter doit être actif si CLEAN présent"
    assert not tab.inspect_export_segments_btn.isEnabled(), "Exporter doit être désactivé sans segments"


def test_partial_nothing_all_action_buttons_disabled(qapp: QApplication) -> None:  # noqa: ARG001
    """Sans RAW ni CLEAN ni segments → tous les boutons d'action désactivés."""
    store = _FakeStore(raw_episodes=set(), clean_episodes=set())
    db = _FakeDb()
    tab = _inspector(store, db)
    assert not tab.inspect_norm_btn.isEnabled()
    assert not tab.inspect_segment_btn.isEnabled()
    assert not tab.inspect_export_segments_btn.isEnabled()


def test_pret_alignement_reflects_partial_state(qapp: QApplication) -> None:  # noqa: ARG001
    """Le statut Prêt alignement liste correctement les éléments manquants en état partiel."""
    # CLEAN présent, pas de segments, pas de tracks
    store = _FakeStore(raw_episodes={"S01E01"}, clean_episodes={"S01E01"})
    db = _FakeDb(segments={}, tracks={})
    tab = _inspector(store, db)
    text = tab.pret_alignement_label.text()
    assert "Non" in text
    assert "segments" in text
    assert "tracks SRT" in text
    assert "CLEAN" not in text  # CLEAN est présent


# ---------------------------------------------------------------------------
# Transitions d'onglets (widget combiné)
# ---------------------------------------------------------------------------

def test_combined_episode_change_propagates_to_inspector(qapp: QApplication) -> None:  # noqa: ARG001
    """Changer l'épisode dans le widget combiné met à jour le sous-tab Inspecteur."""
    store = _FakeStore()
    db = _FakeDb()
    tab = _combined(store, db)

    # Initialement sur S01E01
    assert tab.inspector_tab._current_episode_id == "S01E01"

    # Changer vers S01E02 via le combo commun
    idx = tab.episode_combo.findData("S01E02")
    assert idx >= 0
    tab.episode_combo.setCurrentIndex(idx)

    assert tab.inspector_tab._current_episode_id == "S01E02"


def test_combined_episode_change_propagates_to_subtitles(qapp: QApplication) -> None:  # noqa: ARG001
    """Changer l'épisode dans le widget combiné met à jour le sous-tab Sous-titres."""
    store = _FakeStore()
    db = _FakeDb()
    tab = _combined(store, db)

    idx = tab.episode_combo.findData("S01E02")
    tab.episode_combo.setCurrentIndex(idx)

    assert tab.subtitles_tab.subs_episode_combo.currentData() == "S01E02"


def test_combined_episode_preserved_after_refresh(qapp: QApplication) -> None:  # noqa: ARG001
    """Après refresh, l'épisode sélectionné est conservé (pas de retour à S01E01)."""
    store = _FakeStore()
    db = _FakeDb()
    tab = _combined(store, db)

    idx = tab.episode_combo.findData("S01E02")
    tab.episode_combo.setCurrentIndex(idx)
    assert tab.episode_combo.currentData() == "S01E02"

    tab.refresh()

    assert tab.episode_combo.currentData() == "S01E02"
    assert tab.inspector_tab._current_episode_id == "S01E02"


def test_combined_rapid_episode_switches_no_crash(qapp: QApplication) -> None:  # noqa: ARG001
    """Des changements rapides d'épisode ne provoquent pas de crash/état incohérent."""
    store = _FakeStore()
    db = _FakeDb()
    tab = _combined(store, db)

    for _ in range(5):
        idx_e01 = tab.episode_combo.findData("S01E01")
        idx_e02 = tab.episode_combo.findData("S01E02")
        tab.episode_combo.setCurrentIndex(idx_e02)
        tab.episode_combo.setCurrentIndex(idx_e01)

    # Pas de crash et état cohérent
    eid = tab.episode_combo.currentData()
    assert tab.inspector_tab._current_episode_id == eid
    assert tab.subtitles_tab.subs_episode_combo.currentData() == eid


# ---------------------------------------------------------------------------
# Mismatch de contexte (Expert détecte via ExpertTransverseTabWidget)
# ---------------------------------------------------------------------------

def test_expert_detects_context_mismatch(qapp: QApplication) -> None:  # noqa: ARG001
    """L'Expert détecte que deux onglets pointent vers des épisodes différents."""
    from howimetyourcorpus.app.tabs.tab_expert import ExpertTransverseTabWidget

    store = _FakeStore()
    db = _FakeDb()

    # Simuler deux onglets avec des épisodes différents
    class _MockInspectorTab:
        episode_combo = type("Combo", (), {
            "currentData": lambda self: "S01E01",
            "currentText": lambda self: "S01E01",
        })()

    class _MockAlignTab:
        align_episode_combo = type("Combo", (), {
            "currentData": lambda self: "S01E02",
            "currentText": lambda self: "S01E02",
        })()

    expert = ExpertTransverseTabWidget(
        get_store=lambda: None,
        get_db=lambda: None,
        get_inspector_tab=lambda: _MockInspectorTab(),
        get_preparer_tab=lambda: None,
        get_alignment_tab=lambda: _MockAlignTab(),
        get_personnages_tab=lambda: None,
        get_undo_stack=lambda: None,
    )
    expert.refresh()

    text = expert.summary_edit.toPlainText()
    assert "Context consistent: no" in text


def test_expert_context_consistent_when_same_episode(qapp: QApplication) -> None:  # noqa: ARG001
    """L'Expert confirme la cohérence quand tous les onglets renseignés sont sur le même épisode."""
    from howimetyourcorpus.app.tabs.tab_expert import ExpertTransverseTabWidget

    class _MockTabSameEp:
        episode_combo = type("Combo", (), {
            "currentData": lambda self: "S01E01",
            "currentText": lambda self: "S01E01",
        })()

    expert = ExpertTransverseTabWidget(
        get_store=lambda: None,
        get_db=lambda: None,
        get_inspector_tab=lambda: _MockTabSameEp(),
        get_preparer_tab=lambda: None,
        get_alignment_tab=lambda: None,
        get_personnages_tab=lambda: None,
        get_undo_stack=lambda: None,
    )
    expert.refresh()

    text = expert.summary_edit.toPlainText()
    assert "Context consistent: yes" in text
