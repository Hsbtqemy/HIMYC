"""§15.4 — Onglet Inspecteur + Sous-titres fusionnés : un onglet, deux colonnes (Transcript à gauche, SRT à droite), épisode partagé."""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.app.tabs.tab_inspecteur import InspectorTabWidget
from howimetyourcorpus.app.tabs.tab_sous_titres import SubtitleTabWidget

logger = logging.getLogger(__name__)


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
        on_open_pilotage: Callable[[], None] | None = None,
        on_open_validation: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._get_config = get_config
        self._run_job = run_job
        self._refresh_episodes = refresh_episodes
        self._show_status = show_status
        self._on_open_validation = on_open_validation

        layout = QVBoxLayout(self)
        # Un seul sélecteur d'épisode en haut (§15.4)
        row = QHBoxLayout()
        row.addWidget(QLabel("Épisode:"))
        self.episode_combo = QComboBox()
        self.episode_combo.setToolTip("§15.4 — Épisode courant pour Transcript et Sous-titres.")
        self.episode_combo.currentIndexChanged.connect(self._on_episode_changed)
        row.addWidget(self.episode_combo)
        open_validation_btn = QPushButton("Aller à Validation & Annotation")
        open_validation_btn.setToolTip(
            "Passe à l'onglet Validation & Annotation pour alignement et assignation/propagation personnages."
        )
        open_validation_btn.setEnabled(self._on_open_validation is not None)
        open_validation_btn.clicked.connect(self._open_validation_tab)
        row.addWidget(open_validation_btn)
        row.addStretch()
        layout.addLayout(row)
        workflow_hint = QLabel(
            "Position workflow: ici = QA épisode + normalisation pistes SRT. "
            "Assignation personnages et propagation = onglet Validation & Annotation."
        )
        workflow_hint.setStyleSheet("color: #666;")
        workflow_hint.setWordWrap(True)
        layout.addWidget(workflow_hint)

        self.inspector_tab = InspectorTabWidget(
            get_store=get_store,
            get_db=get_db,
            get_config=get_config,
            run_job=run_job,
            show_status=show_status,
            on_open_pilotage=on_open_pilotage,
        )
        self.subtitles_tab = SubtitleTabWidget(
            get_store=get_store,
            get_db=get_db,
            run_job=run_job,
            refresh_episodes=refresh_episodes,
            show_status=show_status,
        )
        self.inspector_tab.set_episode_selector_visible(False)
        self.subtitles_tab.set_episode_selector_visible(False)

        self._main_split = QSplitter(Qt.Orientation.Horizontal)
        self._main_split.addWidget(self._wrap_label(self.inspector_tab, "Transcript (RAW/CLEAN, segments)"))
        self._main_split.addWidget(self._wrap_label(self.subtitles_tab, "Sous-titres SRT (pistes, import, normaliser)"))
        self._main_split.setStretchFactor(0, 1)
        self._main_split.setStretchFactor(1, 1)
        layout.addWidget(self._main_split)
        self._restore_combined_splitter()

    def _open_validation_tab(self) -> None:
        if self._on_open_validation:
            self._on_open_validation()

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
        try:
            self.inspector_tab.set_episode_and_load(eid)
        except Exception:
            logger.exception("Failed to sync inspector panel for episode %s", eid)
        try:
            self.subtitles_tab.set_episode_and_load(eid)
        except Exception:
            logger.exception("Failed to sync subtitles panel for episode %s", eid)

    def refresh(self) -> None:
        """Recharge la liste des épisodes et synchronise les deux panneaux."""
        current_episode = self.episode_combo.currentData()
        self.inspector_tab.refresh()
        self.subtitles_tab.refresh()
        current_inspect = self.inspector_tab.inspect_episode_combo.currentData()
        # Le combo supérieur reflète les épisodes déjà chargés côté Inspecteur.
        self.episode_combo.blockSignals(True)
        self.episode_combo.clear()
        target_episode = current_episode or current_inspect
        target_index = -1
        for idx in range(self.inspector_tab.inspect_episode_combo.count()):
            label = self.inspector_tab.inspect_episode_combo.itemText(idx)
            episode_id = self.inspector_tab.inspect_episode_combo.itemData(idx)
            self.episode_combo.addItem(label, episode_id)
            if target_episode and episode_id == target_episode:
                target_index = idx
        if target_index >= 0:
            self.episode_combo.setCurrentIndex(target_index)
        self.episode_combo.blockSignals(False)
        selected_episode = self.episode_combo.currentData()
        if selected_episode and str(selected_episode) != str(current_inspect or ""):
            self.set_episode_and_load(str(selected_episode))

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
                if self.episode_combo.currentIndex() != i:
                    # Le signal currentIndexChanged déclenche _on_episode_changed.
                    self.episode_combo.setCurrentIndex(i)
                else:
                    self.inspector_tab.set_episode_and_load(episode_id)
                    self.subtitles_tab.set_episode_and_load(episode_id)
                return
        self.inspector_tab.set_episode_and_load(episode_id)
        self.subtitles_tab.set_episode_and_load(episode_id)

    def set_job_busy(self, busy: bool) -> None:
        """Désactive les actions de mutation pendant un job global."""
        self.episode_combo.setEnabled(not busy)
        self.inspector_tab.set_job_busy(busy)
        self.subtitles_tab.set_job_busy(busy)
