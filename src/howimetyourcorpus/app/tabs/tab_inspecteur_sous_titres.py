"""§15.4 — Onglet Inspecteur + Sous-titres fusionnés : un onglet, deux colonnes (Transcript à gauche, SRT à droite), épisode partagé + Undo/Redo (BP3)."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.app.tabs.tab_inspecteur import InspectorTabWidget
from howimetyourcorpus.app.tabs.tab_sous_titres import SubtitleTabWidget


class InspecteurEtSousTitresTabWidget(QWidget):
    """§15.4 — Widget fusionné Inspecteur + Sous-titres : un sélecteur d'épisode, deux colonnes (Transcript à gauche, SRT à droite)."""

    def __init__(
        self,
        get_store: Callable[[], Any],
        get_db: Callable[[], Any],
        get_config: Callable[[], Any],
        run_job: Callable[[list], None],
        refresh_episodes: Callable[[], None],
        show_status: Callable[[str, int], None],
        undo_stack: QUndoStack | None = None,  # Basse Priorité #3
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._get_config = get_config
        self._run_job = run_job
        self._refresh_episodes = refresh_episodes
        self._show_status = show_status

        layout = QVBoxLayout(self)
        # Un seul sélecteur d'épisode en haut (§15.4)
        row = QHBoxLayout()
        row.addWidget(QLabel("Épisode:"))
        self.episode_combo = QComboBox()
        self.episode_combo.setToolTip("§15.4 — Épisode courant pour Transcript et Sous-titres.")
        self.episode_combo.currentIndexChanged.connect(self._on_episode_changed)
        row.addWidget(self.episode_combo)
        row.addStretch()
        layout.addLayout(row)

        self.inspector_tab = InspectorTabWidget(
            get_store=get_store,
            get_db=get_db,
            get_config=get_config,
            run_job=run_job,
            show_status=show_status,
        )
        self.subtitles_tab = SubtitleTabWidget(
            get_store=get_store,
            get_db=get_db,
            run_job=run_job,
            refresh_episodes=refresh_episodes,
            show_status=show_status,
        )
        
        # Basse Priorité #3 : Propager undo_stack vers le tab sous-titres
        if undo_stack:
            self.subtitles_tab.undo_stack = undo_stack
        self.inspector_tab.set_episode_selector_visible(False)
        self.subtitles_tab.set_episode_selector_visible(False)

        self._main_split = QSplitter(Qt.Orientation.Horizontal)
        self._main_split.addWidget(self._wrap_label(self.inspector_tab, "Transcript (RAW/CLEAN, segments)"))
        self._main_split.addWidget(self._wrap_label(self.subtitles_tab, "Sous-titres SRT (pistes, import, normaliser)"))
        self._main_split.setStretchFactor(0, 1)
        self._main_split.setStretchFactor(1, 1)
        layout.addWidget(self._main_split)
        self._restore_combined_splitter()

    @staticmethod
    def _wrap_label(widget: QWidget, title: str) -> QWidget:
        """Enveloppe un widget dans une zone avec titre (pour lisibilité dans le splitter)."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(QLabel(title))
        v.addWidget(widget)
        return w

    def _on_episode_changed(self) -> None:
        eid = self.episode_combo.currentData()
        if not eid:
            return
        self.inspector_tab.set_episode_and_load(eid)
        self.subtitles_tab.set_episode_and_load(eid)

    def refresh(self) -> None:
        """Recharge la liste des épisodes et synchronise les deux panneaux (préserve l'épisode courant)."""
        current_episode_id = self.episode_combo.currentData()
        self.episode_combo.blockSignals(True)
        self.episode_combo.clear()
        store = self._get_store()
        if store:
            index = store.load_series_index()
            if index and index.episodes:
                for e in index.episodes:
                    self.episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
                if current_episode_id:
                    for i in range(self.episode_combo.count()):
                        if self.episode_combo.itemData(i) == current_episode_id:
                            self.episode_combo.setCurrentIndex(i)
                            break
        self.episode_combo.blockSignals(False)
        self.inspector_tab.refresh()
        self.subtitles_tab.refresh()
        # Recharger l'épisode conservé dans les deux panneaux (inspector_tab.refresh a pu remettre le sien à 0)
        if current_episode_id:
            self.set_episode_and_load(current_episode_id)

    def _restore_combined_splitter(self) -> None:
        settings = QSettings()
        val = settings.value("inspecteur_sous_titres/mainSplitter")
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            try:
                self._main_split.setSizes([int(x) for x in val[:2]])
            except (TypeError, ValueError):
                pass

    def save_state(self) -> None:
        """Sauvegarde splitters et notes (délégué à l'Inspecteur + splitter fusionné)."""
        settings = QSettings()
        settings.setValue("inspecteur_sous_titres/mainSplitter", self._main_split.sizes())
        self.inspector_tab.save_state()

    def refresh_profile_combo(self, profile_ids: list[str], current: str | None) -> None:
        """Met à jour le combo profil (délégué à l'Inspecteur)."""
        self.inspector_tab.refresh_profile_combo(profile_ids, current)

    def set_episode_and_load(self, episode_id: str) -> None:
        """Sélectionne l'épisode et charge les deux panneaux (ex. depuis Concordance)."""
        for i in range(self.episode_combo.count()):
            if self.episode_combo.itemData(i) == episode_id:
                self.episode_combo.setCurrentIndex(i)
                break
        self.inspector_tab.set_episode_and_load(episode_id)
        self.subtitles_tab.set_episode_and_load(episode_id)
