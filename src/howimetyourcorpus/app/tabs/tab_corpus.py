"""Onglet Corpus : arbre épisodes, filtre saison, workflow (découvrir, télécharger, normaliser, indexer, exporter)."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.adapters.base import AdapterRegistry
from howimetyourcorpus.core.export_utils import (
    export_corpus_txt,
    export_corpus_csv,
    export_corpus_json,
    export_corpus_docx,
    export_corpus_utterances_jsonl,
    export_corpus_utterances_csv,
    export_corpus_phrases_jsonl,
    export_corpus_phrases_csv,
)
from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus, SeriesIndex
from howimetyourcorpus.core.normalize.profiles import PROFILES
from howimetyourcorpus.core.pipeline.tasks import (
    FetchSeriesIndexStep,
    FetchAndMergeSeriesIndexStep,
)
from howimetyourcorpus.core.workflow import (
    WorkflowActionError,
    WorkflowActionId,
    WorkflowOptionError,
    WorkflowScope,
    WorkflowScopeError,
    WorkflowService,
)
from howimetyourcorpus.app.feedback import show_error, warn_precondition
from howimetyourcorpus.app.export_dialog import normalize_export_path, resolve_export_key
from howimetyourcorpus.app.models_qt import (
    EpisodesTreeModel,
    EpisodesTreeFilterProxyModel,
    EpisodesTableModel,
    EpisodesFilterProxyModel,
)

logger = logging.getLogger(__name__)


class CorpusTabWidget(QWidget):
    """Widget de l'onglet Corpus : arbre épisodes, saison, cases à cocher, boutons workflow, progression."""

    def __init__(
        self,
        get_store: Callable[[], Any],
        get_db: Callable[[], Any],
        get_context: Callable[[], Any],
        run_job: Callable[[list], None],
        show_status: Callable[[str, int], None],
        refresh_after_episodes_added: Callable[[], None],
        on_cancel_job: Callable[[], None],
        on_open_inspector: Callable[[str], None] | None = None,
        on_open_alignment: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._get_context = get_context
        self._run_job = run_job
        self._show_status = show_status
        self._refresh_after_episodes_added = refresh_after_episodes_added
        self._on_cancel_job = on_cancel_job
        self._on_open_inspector = on_open_inspector
        self._on_open_alignment = on_open_alignment
        self._workflow_service = WorkflowService()
        self._primary_action: Callable[[], None] | None = None
        self._cached_index: SeriesIndex | None = None

        layout = QVBoxLayout(self)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Saison:"))
        self.season_filter_combo = QComboBox()
        self.season_filter_combo.setMinimumWidth(140)
        self.season_filter_combo.currentIndexChanged.connect(self._on_season_filter_changed)
        filter_row.addWidget(self.season_filter_combo)
        filter_row.addWidget(QLabel("Statut:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.setMinimumWidth(160)
        self.status_filter_combo.addItem("Tous", None)
        self.status_filter_combo.addItem("Nouveaux", EpisodeStatus.NEW.value)
        self.status_filter_combo.addItem("Téléchargés", EpisodeStatus.FETCHED.value)
        self.status_filter_combo.addItem("Normalisés", EpisodeStatus.NORMALIZED.value)
        self.status_filter_combo.addItem("Indexés", EpisodeStatus.INDEXED.value)
        self.status_filter_combo.addItem("En erreur", EpisodeStatus.ERROR.value)
        self.status_filter_combo.currentIndexChanged.connect(self._on_status_filter_changed)
        filter_row.addWidget(self.status_filter_combo)
        self.check_season_btn = QPushButton("Cocher la saison")
        self.check_season_btn.setToolTip(
            "Coche tous les épisodes de la saison choisie dans le filtre (ou tout si « Toutes les saisons »)."
        )
        self.check_season_btn.clicked.connect(self._on_check_season_clicked)
        filter_row.addWidget(self.check_season_btn)
        filter_row.addWidget(QLabel("Périmètre action:"))
        self.batch_scope_combo = QComboBox()
        self.batch_scope_combo.setMinimumWidth(200)
        self.batch_scope_combo.addItem("Épisode courant", "current")
        self.batch_scope_combo.addItem("Sélection (coché/lignes)", "selection")
        self.batch_scope_combo.addItem("Saison filtrée", "season")
        self.batch_scope_combo.addItem("Tout le corpus", "all")
        self.batch_scope_combo.setCurrentIndex(1)
        self.batch_scope_combo.setToolTip(
            "Périmètre unifié des actions batch : épisode courant, sélection, saison filtrée ou tout le corpus."
        )
        filter_row.addWidget(self.batch_scope_combo)
        self.scope_preview_label = QLabel("Périmètre: 0 épisode")
        self.scope_preview_label.setStyleSheet("color: #666;")
        filter_row.addWidget(self.scope_preview_label)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Sur macOS, QTreeView + proxy provoque des segfaults ; on utilise une table plate (QTableView).
        _use_table = sys.platform == "darwin"
        if _use_table:
            self.episodes_tree = QTableView()
            self.episodes_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.episodes_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.episodes_tree.setAlternatingRowColors(True)
            self.episodes_tree_model = EpisodesTableModel()
            self.episodes_tree_proxy = EpisodesFilterProxyModel()
            self.episodes_tree_proxy.setSourceModel(self.episodes_tree_model)
            self.episodes_tree.setModel(self.episodes_tree_proxy)
        else:
            self.episodes_tree = QTreeView()
            self.episodes_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.episodes_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.episodes_tree.setRootIsDecorated(True)
            self.episodes_tree.setAlternatingRowColors(True)
            self.episodes_tree_model = EpisodesTreeModel()
            self.episodes_tree_proxy = EpisodesTreeFilterProxyModel()
            self.episodes_tree_proxy.setSourceModel(self.episodes_tree_model)
            self.episodes_tree.setModel(self.episodes_tree_proxy)
        _header = self.episodes_tree.horizontalHeader() if _use_table else self.episodes_tree.header()
        _header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        _header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.episodes_tree.setColumnWidth(0, 32)
        self.episodes_tree.setToolTip("Double-clic sur un épisode : ouvrir dans l'Inspecteur (raw/clean, segments).")
        self.episodes_tree.doubleClicked.connect(self._on_episode_double_clicked)
        selection_model = self.episodes_tree.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._refresh_scope_preview_from_ui)
        self.episodes_tree_model.dataChanged.connect(self._refresh_scope_preview_from_ui)
        self.episodes_tree_model.modelReset.connect(self._refresh_scope_preview_from_ui)
        self.episodes_tree_model.layoutChanged.connect(self._refresh_scope_preview_from_ui)
        self.batch_scope_combo.currentIndexChanged.connect(self._refresh_scope_preview_from_ui)
        layout.addWidget(self.episodes_tree)

        # Bloc 1 — Import (constitution du corpus) §14
        group_import = QGroupBox("1. Importer — Constituer le corpus")
        group_import.setToolTip(
            "Workflow §14 : Découvrir les épisodes, télécharger les transcripts (RAW), importer les SRT (panneau Sous-titres de l'Inspecteur). "
            "Pas de normalisation ni d'alignement ici."
        )
        btn_row1 = QHBoxLayout()
        self.check_all_btn = QPushButton("Tout cocher")
        self.check_all_btn.clicked.connect(self._check_all_episodes)
        self.uncheck_all_btn = QPushButton("Tout décocher")
        self.uncheck_all_btn.clicked.connect(self._uncheck_all_episodes)
        btn_row1.addWidget(self.check_all_btn)
        btn_row1.addWidget(self.uncheck_all_btn)
        self.discover_btn = QPushButton("Découvrir épisodes")
        self.discover_btn.setToolTip("Récupère la liste des épisodes depuis la source (tout le projet).")
        self.discover_btn.clicked.connect(self._discover_episodes)
        self.add_episodes_btn = QPushButton("Ajouter épisodes\n(SRT only)")
        self.add_episodes_btn.setToolTip(
            "Ajoute des épisodes à la main (un par ligne, ex. S01E01). Pour projet SRT uniquement."
        )
        self.add_episodes_btn.clicked.connect(self._add_episodes_manually)
        self.discover_merge_btn = QPushButton("Découvrir (fusionner\nune autre source)...")
        self.discover_merge_btn.setToolTip(
            "Découvre une série depuis une autre source/URL et fusionne avec l'index existant (sans écraser les épisodes déjà présents)."
        )
        self.discover_merge_btn.clicked.connect(self._discover_merge)
        self.fetch_btn = QPushButton("Télécharger")
        self.fetch_btn.setToolTip(
            "Télécharge selon le scope sélectionné (épisode courant, sélection, saison ou tout)."
        )
        self.fetch_btn.clicked.connect(self._fetch_episodes)
        for b in (self.discover_btn, self.add_episodes_btn, self.discover_merge_btn, self.fetch_btn):
            btn_row1.addWidget(b)
        btn_row1.addStretch()
        group_import.setLayout(btn_row1)
        layout.addWidget(group_import)

        # Bloc 2 — Normalisation / segmentation (après import) §14
        group_norm = QGroupBox("2. Transformer / Indexer — Après import")
        group_norm.setToolTip(
            "Workflow §14 : Mise au propre des transcripts (RAW → CLEAN) et segmentation. "
            "Prérequis : au moins un épisode téléchargé (Bloc 1). "
            "Le Bloc 3 se fait dans Validation & Annotation (alignement/personnages) et Concordance."
        )
        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(QLabel("Profil (batch):"))
        self.norm_batch_profile_combo = QComboBox()
        self.norm_batch_profile_combo.addItems(list(PROFILES.keys()))
        self.norm_batch_profile_combo.setToolTip(
            "Profil par défaut pour « Normaliser » (scope courant). "
            "Priorité par épisode : 1) profil préféré (Inspecteur) 2) défaut de la source (Profils) 3) ce profil."
        )
        btn_row2.addWidget(self.norm_batch_profile_combo)
        self.norm_btn = QPushButton("Normaliser")
        self.norm_btn.setToolTip(
            "Bloc 2 — Normalise selon le scope sélectionné. Prérequis : épisodes déjà téléchargés (RAW, Bloc 1)."
        )
        self.norm_btn.clicked.connect(self._normalize_episodes)
        self.segment_btn = QPushButton("Segmenter")
        self.segment_btn.setToolTip(
            "Bloc 2 — Segmente selon le scope sélectionné (épisodes ayant un fichier CLEAN)."
        )
        self.segment_btn.clicked.connect(self._segment_episodes)
        self.all_in_one_btn = QPushButton("Tout faire")
        self.all_in_one_btn.setToolTip(
            "§5 — Enchaînement selon le scope : Télécharger → Normaliser → Segmenter → Indexer DB."
        )
        self.all_in_one_btn.clicked.connect(self._run_all_for_scope)
        self.index_btn = QPushButton("Indexer DB")
        self.index_btn.setToolTip(
            "Bloc 2 — Indexe en base selon le scope sélectionné (épisodes ayant CLEAN)."
        )
        self.index_btn.clicked.connect(self._index_db)
        self.export_corpus_btn = QPushButton("Exporter corpus")
        self.export_corpus_btn.clicked.connect(self._export_corpus)
        self.cancel_job_btn = QPushButton("Annuler")
        self.cancel_job_btn.clicked.connect(self._emit_cancel_job)
        self.cancel_job_btn.setEnabled(False)
        for b in (
            self.norm_btn,
            self.segment_btn,
            self.all_in_one_btn,
            self.index_btn,
            self.export_corpus_btn,
        ):
            btn_row2.addWidget(b)
        btn_row2.addWidget(self.cancel_job_btn)
        btn_row2.addStretch()
        group_norm.setLayout(btn_row2)
        layout.addWidget(group_norm)

        group_recovery = QGroupBox("3. Reprise — Erreurs")
        group_recovery.setToolTip(
            "Liste les épisodes en statut ERROR, permet une relance ciblée et l'ouverture directe dans l'Inspecteur."
        )
        recovery_layout = QVBoxLayout(group_recovery)
        self.error_summary_label = QLabel("Épisodes en erreur: 0")
        recovery_layout.addWidget(self.error_summary_label)
        self.error_list = QListWidget()
        self.error_list.setMaximumHeight(110)
        self.error_list.currentRowChanged.connect(self._on_error_selection_changed)
        recovery_layout.addWidget(self.error_list)
        recovery_btn_row = QHBoxLayout()
        self.retry_selected_error_btn = QPushButton("Relancer épisode")
        self.retry_selected_error_btn.setToolTip("Relance l'épisode sélectionné (workflow complet).")
        self.retry_selected_error_btn.clicked.connect(self._retry_selected_error_episode)
        self.retry_selected_error_btn.setEnabled(False)
        self.retry_all_errors_btn = QPushButton("Relancer toutes les erreurs")
        self.retry_all_errors_btn.setToolTip("Relance tous les épisodes actuellement en erreur.")
        self.retry_all_errors_btn.clicked.connect(self._retry_error_episodes)
        self.retry_all_errors_btn.setEnabled(False)
        self.inspect_error_btn = QPushButton("Ouvrir dans Inspecteur")
        self.inspect_error_btn.setToolTip("Ouvre l'épisode sélectionné dans l'Inspecteur pour diagnostic.")
        self.inspect_error_btn.clicked.connect(self._open_selected_error_in_inspector)
        self.inspect_error_btn.setEnabled(False)
        self.refresh_errors_btn = QPushButton("Rafraîchir liste")
        self.refresh_errors_btn.clicked.connect(self._refresh_error_panel_from_ui)
        recovery_btn_row.addWidget(self.retry_selected_error_btn)
        recovery_btn_row.addWidget(self.retry_all_errors_btn)
        recovery_btn_row.addWidget(self.inspect_error_btn)
        recovery_btn_row.addWidget(self.refresh_errors_btn)
        recovery_btn_row.addStretch()
        recovery_layout.addLayout(recovery_btn_row)
        recovery_hint = QLabel("Astuce: pour les détails d'erreur complets, ouvrez le Journal d'exécution (menu Outils).")
        recovery_hint.setStyleSheet("color: gray; font-size: 0.9em;")
        recovery_hint.setWordWrap(True)
        recovery_layout.addWidget(recovery_hint)
        layout.addWidget(group_recovery)

        self.corpus_progress = QProgressBar()
        self.corpus_progress.setMaximum(100)
        self.corpus_progress.setValue(0)
        layout.addWidget(self.corpus_progress)
        self.corpus_status_label = QLabel("")
        self.corpus_status_label.setToolTip(
            "Workflow §14 (3 blocs) : Bloc 1 = Découverts → Téléchargés → SRT (import). "
            "Bloc 2 = Normalisés (CLEAN) → Segmentés (DB). "
            "Bloc 3 = Alignés/annotés (Validation & Annotation + Concordance)."
        )
        layout.addWidget(self.corpus_status_label)
        self.corpus_next_step_label = QLabel("")
        self.corpus_next_step_label.setStyleSheet("color: #505050;")
        self.corpus_next_step_label.setWordWrap(True)
        layout.addWidget(self.corpus_next_step_label)
        self.primary_action_row = QHBoxLayout()
        self.primary_action_row.addWidget(QLabel("Action recommandée:"))
        self.primary_action_btn = QPushButton("—")
        self.primary_action_btn.clicked.connect(self._run_primary_action)
        self.primary_action_btn.setEnabled(False)
        self.primary_action_row.addWidget(self.primary_action_btn)
        self.primary_action_row.addStretch()
        layout.addLayout(self.primary_action_row)
        scope_label = QLabel(
            "§14 — Bloc 1 (Import) : découverte, téléchargement, SRT (panneau Sous-titres dans Inspecteur). "
            "Bloc 2 (Normalisation / segmentation) : profil batch, Normaliser, Indexer DB. "
            "Périmètre via « Scope action » : épisode courant, sélection, saison filtrée ou tout le corpus."
        )
        scope_label.setStyleSheet("color: gray; font-size: 0.9em;")
        scope_label.setWordWrap(True)
        layout.addWidget(scope_label)

    def set_progress(self, value: int) -> None:
        self.corpus_progress.setValue(value)

    def set_cancel_btn_enabled(self, enabled: bool) -> None:
        self.cancel_job_btn.setEnabled(enabled)

    def _emit_cancel_job(self) -> None:
        self._on_cancel_job()

    def _set_primary_action(self, label: str, action: Callable[[], None] | None) -> None:
        self.primary_action_btn.setText(label)
        self._primary_action = action
        self.primary_action_btn.setEnabled(action is not None)

    def _run_primary_action(self) -> None:
        if self._primary_action is None:
            return
        self._primary_action()

    def _set_scope_mode(self, mode: str) -> None:
        idx = self.batch_scope_combo.findData(mode)
        if idx >= 0 and self.batch_scope_combo.currentIndex() != idx:
            self.batch_scope_combo.setCurrentIndex(idx)

    def _run_action_with_scope(self, mode: str, action: Callable[[str | None], None]) -> None:
        self._set_scope_mode(mode)
        action(scope_mode=mode)

    def refresh(self) -> None:
        """Recharge l'arbre et le statut depuis le store (appelé après ouverture projet / fin de job)."""
        store = self._get_store()
        db = self._get_db()
        if not store:
            self._cached_index = None
            self.season_filter_combo.clear()
            self.season_filter_combo.addItem("Toutes les saisons", None)
            self.corpus_status_label.setText("")
            self.corpus_next_step_label.setText("Prochaine action: ouvrez ou créez un projet dans la section Projet (Pilotage).")
            self.fetch_btn.setEnabled(False)
            self.norm_btn.setEnabled(False)
            self.segment_btn.setEnabled(False)
            self.all_in_one_btn.setEnabled(False)
            self.index_btn.setEnabled(False)
            self._refresh_error_panel(index=None, error_ids=[])
            self._set_primary_action("Ouvrez un projet", None)
            self._refresh_scope_preview(index=None)
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            self._cached_index = None
            self.season_filter_combo.clear()
            self.season_filter_combo.addItem("Toutes les saisons", None)
            self.corpus_status_label.setText("")
            self.corpus_next_step_label.setText("Prochaine action: cliquez sur « Découvrir épisodes » (ou ajoutez des épisodes en mode SRT only).")
            self.fetch_btn.setEnabled(False)
            self.norm_btn.setEnabled(False)
            self.segment_btn.setEnabled(False)
            self.all_in_one_btn.setEnabled(False)
            self.index_btn.setEnabled(False)
            self._refresh_error_panel(index=None, error_ids=[])
            self._set_primary_action("Découvrir épisodes", self._discover_episodes)
            self._refresh_scope_preview(index=None)
            return
        self._cached_index = index
        n_total = len(index.episodes)
        episode_ids = [e.episode_id for e in index.episodes]
        n_fetched = sum(1 for e in index.episodes if store.has_episode_raw(e.episode_id))
        n_norm = sum(1 for e in index.episodes if store.has_episode_clean(e.episode_id))
        n_segmented = 0
        n_indexed = 0
        if db and episode_ids:
            segmented_ids = set(db.get_episode_ids_with_segments(kind="sentence"))
            indexed_ids = set(db.get_episode_ids_indexed())
            n_segmented = len(set(episode_ids) & segmented_ids)
            n_indexed = len(set(episode_ids) & indexed_ids)
        error_ids = self._get_error_episode_ids(index)
        n_error = len(error_ids)
        n_with_srt = 0
        n_aligned = 0
        if db and episode_ids:
            tracks_by_ep = db.get_tracks_for_episodes(episode_ids)
            runs_by_ep = db.get_align_runs_for_episodes(episode_ids)
            n_with_srt = sum(1 for e in index.episodes if tracks_by_ep.get(e.episode_id))
            n_aligned = sum(1 for e in index.episodes if runs_by_ep.get(e.episode_id))
        self.corpus_status_label.setText(
            f"Workflow : Découverts {n_total} | Téléchargés {n_fetched} | Normalisés {n_norm} | Segmentés {n_segmented} | Indexés {n_indexed} | Erreurs {n_error} | SRT {n_with_srt} | Alignés {n_aligned}"
        )
        if n_error > 0:
            self.corpus_next_step_label.setText(
                "Prochaine action: relancer les épisodes en erreur avec « Relancer toutes les erreurs » (ou ciblé via « Relancer épisode »)."
            )
            self._set_primary_action("Relancer toutes les erreurs", self._retry_error_episodes)
        elif n_fetched < n_total:
            self.corpus_next_step_label.setText(
                "Prochaine action: importer les transcripts manquants avec « Télécharger » (scope « Tout le corpus »)."
            )
            self._set_primary_action(
                "Télécharger tout",
                lambda: self._run_action_with_scope("all", self._fetch_episodes),
            )
        elif n_norm < n_fetched:
            self.corpus_next_step_label.setText(
                "Prochaine action: normaliser les épisodes FETCHED avec « Normaliser » (scope « Tout le corpus »)."
            )
            self._set_primary_action(
                "Normaliser tout",
                lambda: self._run_action_with_scope("all", self._normalize_episodes),
            )
        elif n_segmented < n_norm:
            self.corpus_next_step_label.setText(
                "Prochaine action: segmenter et indexer les épisodes NORMALIZED (boutons Segmenter / Indexer DB)."
            )
            self._set_primary_action(
                "Segmenter + Indexer",
                lambda: self._run_action_with_scope("all", self._segment_and_index_scope),
            )
        elif n_indexed < n_segmented:
            self.corpus_next_step_label.setText(
                "Prochaine action: indexer les épisodes déjà segmentés avec « Indexer DB » (scope « Tout le corpus »)."
            )
            self._set_primary_action(
                "Indexer tout",
                lambda: self._run_action_with_scope("all", self._index_db),
            )
        elif n_with_srt == 0:
            self.corpus_next_step_label.setText(
                "Prochaine action: importer des sous-titres (SRT/VTT) dans l'Inspecteur pour préparer l'alignement."
            )
            if self._on_open_inspector:
                self._set_primary_action("Ouvrir Inspecteur (SRT)", self._open_selected_or_first_episode_in_inspector)
            else:
                self._set_primary_action("Importer SRT (Inspecteur)", None)
        elif n_aligned < n_with_srt:
            self.corpus_next_step_label.setText(
                "Prochaine action: lancer l'alignement des épisodes avec SRT dans Validation & Annotation, puis vérifier les personnages."
            )
            if self._on_open_alignment:
                self._set_primary_action("Aller à Validation", self._open_alignment_tab)
            else:
                self._set_primary_action("Passer à Validation", None)
        else:
            self.corpus_next_step_label.setText(
                "Corpus prêt: passez à Validation & Annotation puis Concordance pour l'analyse."
            )
            self._set_primary_action("Corpus prêt", None)
        self.fetch_btn.setEnabled(n_total > 0)
        self.norm_btn.setEnabled(n_fetched > 0)
        self.segment_btn.setEnabled(n_norm > 0)
        self.all_in_one_btn.setEnabled(n_total > 0)
        self.index_btn.setEnabled(n_norm > 0)
        self._refresh_error_panel(index=index, error_ids=error_ids)
        # Mise à jour de l'arbre : synchrone (refresh est déjà appelé après OK, pas au même moment que la boîte de dialogue)
        # Pas d'expandAll() : provoque segfault sur macOS ; déplier à la main (flèche à gauche de « Saison N »)
        self.episodes_tree_model.set_store(store)
        self.episodes_tree_model.set_db(db)
        self.episodes_tree_model.set_episodes(index.episodes)
        self._refresh_season_filter_combo()
        self._refresh_scope_preview(index)

    def refresh_profile_combo(self, profile_ids: list[str], current: str | None) -> None:
        """Met à jour le combo profil batch (après ouverture projet ou dialogue profils)."""
        current_batch = self.norm_batch_profile_combo.currentText()
        self.norm_batch_profile_combo.clear()
        self.norm_batch_profile_combo.addItems(profile_ids)
        if current_batch in profile_ids:
            self.norm_batch_profile_combo.setCurrentText(current_batch)
        elif current and current in profile_ids:
            self.norm_batch_profile_combo.setCurrentText(current)

    def _refresh_season_filter_combo(self) -> None:
        self.season_filter_combo.blockSignals(True)
        self.season_filter_combo.clear()
        self.season_filter_combo.addItem("Toutes les saisons", None)
        for sn in self.episodes_tree_model.get_season_numbers():
            self.season_filter_combo.addItem(f"Saison {sn}", sn)
        self.season_filter_combo.blockSignals(False)
        self._on_season_filter_changed()
        self._on_status_filter_changed()

    def _on_season_filter_changed(self) -> None:
        season = self.season_filter_combo.currentData()
        self.episodes_tree_proxy.set_season_filter(season)
        if season is not None and isinstance(self.episodes_tree, QTreeView):
            try:
                row = self.episodes_tree_model.get_season_numbers().index(season)
                source_ix = self.episodes_tree_model.index(row, 0, QModelIndex())
                proxy_ix = self.episodes_tree_proxy.mapFromSource(source_ix)
                if proxy_ix.isValid():
                    self.episodes_tree.expand(proxy_ix)
            except (ValueError, AttributeError):
                pass
        self._refresh_scope_preview_from_ui()

    def _on_status_filter_changed(self) -> None:
        status = self.status_filter_combo.currentData()
        self.episodes_tree_proxy.set_status_filter(status)

    def _check_all_episodes(self) -> None:
        self.episodes_tree_model.set_all_checked(True)
        self._refresh_scope_preview_from_ui()

    def _uncheck_all_episodes(self) -> None:
        self.episodes_tree_model.set_all_checked(False)
        self._refresh_scope_preview_from_ui()

    def _refresh_scope_preview_from_ui(self, *_args) -> None:
        self._refresh_scope_preview(self._cached_index)

    def _refresh_scope_preview(self, index: SeriesIndex | None) -> None:
        if index is None or not index.episodes:
            self.scope_preview_label.setText("Périmètre: 0 épisode")
            return
        mode = (self.batch_scope_combo.currentData() or "selection").lower()
        if mode == "all":
            n = len(index.episodes)
            self.scope_preview_label.setText(f"Périmètre: {n} épisode(s)")
            return
        if mode == "season":
            season = self.season_filter_combo.currentData()
            if season is None:
                self.scope_preview_label.setText("Périmètre: choisissez une saison")
                return
            n = len(self.episodes_tree_model.get_episode_ids_for_season(season))
            self.scope_preview_label.setText(f"Périmètre: {n} épisode(s)")
            return
        if mode == "current":
            n = 1 if self._resolve_current_episode_id() else 0
            if n == 0:
                self.scope_preview_label.setText("Périmètre: sélectionnez un épisode")
                return
            self.scope_preview_label.setText("Périmètre: 1 épisode")
            return
        n = len(self._resolve_selected_episode_ids())
        self.scope_preview_label.setText(f"Périmètre: {n} épisode(s)")

    def _on_episode_double_clicked(self, proxy_index: QModelIndex) -> None:
        """Double-clic sur un épisode : ouvrir l'Inspecteur sur cet épisode (comme Concordance)."""
        if not proxy_index.isValid() or not self._on_open_inspector:
            return
        source_index = self.episodes_tree_proxy.mapToSource(proxy_index)
        episode_id = self.episodes_tree_model.get_episode_id_for_index(source_index)
        if episode_id:
            self._on_open_inspector(episode_id)

    def _open_selected_or_first_episode_in_inspector(self) -> None:
        if not self._on_open_inspector:
            return
        selected_ids = self._resolve_selected_episode_ids()
        if selected_ids:
            self._on_open_inspector(selected_ids[0])
            return
        store = self._get_store()
        index = store.load_series_index() if store else None
        if index and index.episodes:
            self._on_open_inspector(index.episodes[0].episode_id)

    def _open_alignment_tab(self) -> None:
        if self._on_open_alignment:
            self._on_open_alignment()

    def _on_check_season_clicked(self) -> None:
        season = self.season_filter_combo.currentData()
        ids = self.episodes_tree_model.get_episode_ids_for_season(season)
        if not ids:
            return
        self.episodes_tree_model.set_checked(set(ids), True)
        self._refresh_scope_preview_from_ui()

    def _discover_episodes(self) -> None:
        resolved = self._resolve_project_context(require_db=True)
        if resolved is None:
            return
        _store, _db, context = resolved
        config = context["config"]
        step = FetchSeriesIndexStep(config.series_url, config.user_agent)
        self._run_job([step])

    def _discover_merge(self) -> None:
        resolved = self._resolve_project_context(require_db=True)
        if resolved is None:
            return
        _store, _db, context = resolved
        config = context["config"]
        dlg = QDialog(self)
        dlg.setWindowTitle("Découvrir (fusionner une autre source)")
        layout = QFormLayout(dlg)
        url_edit = QLineEdit()
        url_edit.setPlaceholderText("https://subslikescript.com/series/...")
        layout.addRow("URL série (autre source):", url_edit)
        source_combo = QComboBox()
        source_combo.addItems(AdapterRegistry.list_ids() or ["subslikescript"])
        layout.addRow("Source:", source_combo)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addRow(bbox)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        url = url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Corpus", "Indiquez l'URL de la série.")
            return
        source_id = source_combo.currentText() or "subslikescript"
        step = FetchAndMergeSeriesIndexStep(url, source_id, config.user_agent)
        self._run_job([step])

    def _add_episodes_manually(self) -> None:
        store = self._get_store()
        if not store:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Ajouter des épisodes")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Un episode_id par ligne (ex. S01E01, s01e02) :"))
        text_edit = QPlainTextEdit()
        text_edit.setPlaceholderText("S01E01\nS01E02\nS02E01")
        text_edit.setMinimumHeight(120)
        layout.addWidget(text_edit)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addWidget(bbox)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        lines = [ln.strip().upper() for ln in text_edit.toPlainText().strip().splitlines() if ln.strip()]
        if not lines:
            QMessageBox.information(self, "Corpus", "Aucun episode_id saisi.")
            return
        new_refs = []
        for ln in lines:
            mm = re.match(r"S(\d+)E(\d+)", ln, re.IGNORECASE)
            if not mm:
                continue
            ep_id = f"S{int(mm.group(1)):02d}E{int(mm.group(2)):02d}"
            new_refs.append(
                EpisodeRef(
                    episode_id=ep_id,
                    season=int(mm.group(1)),
                    episode=int(mm.group(2)),
                    title="",
                    url="",
                )
            )
        if not new_refs:
            QMessageBox.warning(self, "Corpus", "Aucun episode_id valide (format S01E01).")
            return
        index = store.load_series_index()
        existing_ids = {e.episode_id for e in (index.episodes or [])} if index else set()
        episodes = list(index.episodes or []) if index else []
        for ref in new_refs:
            if ref.episode_id not in existing_ids:
                episodes.append(ref)
                existing_ids.add(ref.episode_id)
        store.save_series_index(
            SeriesIndex(
                series_title=index.series_title if index else "",
                series_url=index.series_url if index else "",
                episodes=episodes,
            )
        )
        self.refresh()
        self._refresh_after_episodes_added()
        self._show_status(f"{len(new_refs)} épisode(s) ajouté(s).", 3000)

    def _resolve_selected_episode_ids(self) -> list[str]:
        """Résout les episode_id via cases cochées puis sélection de lignes."""
        ids = self.episodes_tree_model.get_checked_episode_ids()
        if ids:
            return ids
        selection_model = self.episodes_tree.selectionModel()
        if selection_model is None:
            return []
        proxy_indices = selection_model.selectedIndexes()
        source_indices = [self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices]
        return self.episodes_tree_model.get_episode_ids_selection(source_indices)

    def _resolve_current_episode_id(self) -> str | None:
        selection_model = self.episodes_tree.selectionModel()
        if selection_model is not None:
            proxy_indices = selection_model.selectedIndexes()
            source_indices = [self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices]
            selected_ids = self.episodes_tree_model.get_episode_ids_selection(source_indices)
            if selected_ids:
                return selected_ids[0]
        checked_ids = self.episodes_tree_model.get_checked_episode_ids()
        if checked_ids:
            return checked_ids[0]
        return None

    def _resolve_scope_and_ids(
        self,
        index: SeriesIndex,
        *,
        scope_mode: str | None = None,
    ) -> tuple[WorkflowScope, list[str]] | None:
        mode = (scope_mode or self.batch_scope_combo.currentData() or "selection").lower()
        if mode == "current":
            eid = self._resolve_current_episode_id()
            if not eid:
                warn_precondition(
                    self,
                    "Corpus",
                    "Scope « Épisode courant »: sélectionnez une ligne (ou cochez un épisode).",
                    next_step="Sélectionnez un épisode dans la liste ou cochez sa case.",
                )
                return None
            return WorkflowScope.current(eid), [eid]
        if mode == "selection":
            ids = self._resolve_selected_episode_ids()
            if not ids:
                warn_precondition(
                    self,
                    "Corpus",
                    "Scope « Sélection »: cochez au moins un épisode ou sélectionnez des lignes.",
                    next_step="Utilisez « Tout cocher » ou choisissez des épisodes manuellement.",
                )
                return None
            return WorkflowScope.selection(ids), ids
        if mode == "season":
            season = self.season_filter_combo.currentData()
            if season is None:
                warn_precondition(
                    self,
                    "Corpus",
                    "Scope « Saison filtrée »: choisissez d'abord une saison (pas « Toutes les saisons »).",
                    next_step="Choisissez une saison dans le filtre « Saison ».",
                )
                return None
            ids = self.episodes_tree_model.get_episode_ids_for_season(season)
            if not ids:
                warn_precondition(self, "Corpus", f"Aucun épisode trouvé pour la saison {season}.")
                return None
            return WorkflowScope.season_scope(int(season)), ids
        if mode == "all":
            return WorkflowScope.all(), [e.episode_id for e in index.episodes]
        warn_precondition(self, "Corpus", f"Scope inconnu: {mode}")
        return None

    def _build_profile_by_episode(
        self,
        *,
        store: Any,
        episode_refs: list[EpisodeRef],
        episode_ids: list[str],
        batch_profile: str,
    ) -> dict[str, str]:
        ref_by_id = {e.episode_id: e for e in episode_refs}
        episode_preferred = store.load_episode_preferred_profiles()
        source_defaults = store.load_source_profile_defaults()
        profile_by_episode: dict[str, str] = {}
        for eid in episode_ids:
            ref = ref_by_id.get(eid)
            profile = (
                episode_preferred.get(eid)
                or (source_defaults.get(ref.source_id or "") if ref else None)
                or batch_profile
            )
            profile_by_episode[eid] = profile
        return profile_by_episode

    @staticmethod
    def _resolve_lang_hint(context: dict[str, Any]) -> str:
        config = context.get("config")
        if config and getattr(config, "normalize_profile", None):
            return (
                (config.normalize_profile or "default_en_v1")
                .split("_")[0]
                .replace("default", "en")
                or "en"
            )
        return "en"

    def _build_plan_or_warn(
        self,
        *,
        action_id: WorkflowActionId,
        context: dict[str, Any],
        scope: WorkflowScope,
        episode_refs: list[EpisodeRef],
        options: dict[str, Any] | None = None,
    ):
        try:
            return self._workflow_service.build_plan(
                action_id=action_id,
                context=context,
                scope=scope,
                episode_refs=episode_refs,
                options=options,
            )
        except (WorkflowActionError, WorkflowScopeError, WorkflowOptionError) as exc:
            warn_precondition(self, "Corpus", str(exc))
            return None

    def _resolve_project_context(
        self,
        *,
        require_db: bool = False,
    ) -> tuple[Any, Any, dict[str, Any]] | None:
        store = self._get_store()
        db = self._get_db()
        context = self._get_context()
        if not context.get("config") or not store or (require_db and not db):
            warn_precondition(
                self,
                "Corpus",
                "Ouvrez un projet d'abord.",
                next_step="Pilotage > Projet: ouvrez ou initialisez un projet.",
            )
            return None
        return store, db, context

    def _load_index_or_warn(self, store: Any) -> SeriesIndex | None:
        index = store.load_series_index()
        if not index or not index.episodes:
            warn_precondition(
                self,
                "Corpus",
                "Découvrez d'abord les épisodes.",
                next_step="Pilotage > Corpus: cliquez sur « Découvrir épisodes ».",
            )
            return None
        return index

    def _resolve_scope_context(
        self,
        *,
        scope_mode: str | None = None,
        require_db: bool = False,
    ) -> tuple[Any, Any, dict[str, Any], SeriesIndex, WorkflowScope, list[str]] | None:
        resolved_context = self._resolve_project_context(require_db=require_db)
        if resolved_context is None:
            return None
        store, db, context = resolved_context
        index = self._load_index_or_warn(store)
        if index is None:
            return None
        resolved_scope = self._resolve_scope_and_ids(index, scope_mode=scope_mode)
        if resolved_scope is None:
            return None
        scope, ids = resolved_scope
        return store, db, context, index, scope, ids

    def _build_action_steps_or_warn(
        self,
        *,
        action_id: WorkflowActionId,
        context: dict[str, Any],
        scope: WorkflowScope,
        episode_refs: list[EpisodeRef],
        options: dict[str, Any] | None = None,
    ) -> list[Any] | None:
        plan = self._build_plan_or_warn(
            action_id=action_id,
            context=context,
            scope=scope,
            episode_refs=episode_refs,
            options=options,
        )
        if not plan:
            return None
        return list(plan.steps)

    def _run_action_for_scope(
        self,
        *,
        action_id: WorkflowActionId,
        context: dict[str, Any],
        scope: WorkflowScope,
        episode_refs: list[EpisodeRef],
        options: dict[str, Any] | None,
        empty_message: str,
    ) -> bool:
        steps = self._build_action_steps_or_warn(
            action_id=action_id,
            context=context,
            scope=scope,
            episode_refs=episode_refs,
            options=options,
        )
        if steps is None:
            return False
        if not steps:
            QMessageBox.information(self, "Corpus", empty_message)
            return False
        self._run_job(steps)
        return True

    def _get_episode_status_map(self, episode_ids: list[str]) -> dict[str, str]:
        db = self._get_db()
        if not db or not episode_ids:
            return {}
        try:
            return db.get_episode_statuses(episode_ids)
        except Exception:
            logger.exception("Failed to load episode statuses")
            return {}

    def _get_error_episode_ids(self, index: SeriesIndex) -> list[str]:
        episode_ids = [e.episode_id for e in index.episodes]
        statuses = self._get_episode_status_map(episode_ids)
        return [
            eid
            for eid in episode_ids
            if (statuses.get(eid) or "").lower() == EpisodeStatus.ERROR.value
        ]

    def _selected_error_episode_id(self) -> str | None:
        item = self.error_list.currentItem()
        if not item:
            return None
        eid = (item.text() or "").strip()
        return eid or None

    def _on_error_selection_changed(self) -> None:
        has_selection = self._selected_error_episode_id() is not None
        self.retry_selected_error_btn.setEnabled(has_selection)
        self.inspect_error_btn.setEnabled(has_selection and self._on_open_inspector is not None)
        self.retry_all_errors_btn.setEnabled(self.error_list.count() > 0)

    def _refresh_error_panel(
        self,
        *,
        index: SeriesIndex | None,
        error_ids: list[str] | None = None,
    ) -> None:
        previous = self._selected_error_episode_id()
        if error_ids is None:
            error_ids = self._get_error_episode_ids(index) if index else []
        self.error_list.blockSignals(True)
        self.error_list.clear()
        for eid in error_ids:
            self.error_list.addItem(eid)
        if previous and previous in error_ids:
            self.error_list.setCurrentRow(error_ids.index(previous))
        elif error_ids:
            self.error_list.setCurrentRow(0)
        self.error_list.blockSignals(False)
        self.error_summary_label.setText(f"Épisodes en erreur: {len(error_ids)}")
        self._on_error_selection_changed()

    def _refresh_error_panel_from_ui(self) -> None:
        store = self._get_store()
        if not store:
            self._refresh_error_panel(index=None, error_ids=[])
            return
        index = store.load_series_index()
        self._refresh_error_panel(index=index if index and index.episodes else None)

    def _run_all_for_episode_ids(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        context: dict[str, Any],
    ) -> None:
        if not ids:
            QMessageBox.warning(
                self, "Corpus", "Aucun épisode résolu pour le scope choisi."
            )
            return
        scope = WorkflowScope.selection(ids)
        batch_profile = self.norm_batch_profile_combo.currentText() or "default_en_v1"
        profile_by_episode = self._build_profile_by_episode(
            store=store,
            episode_refs=index.episodes,
            episode_ids=ids,
            batch_profile=batch_profile,
        )
        fetch_steps = self._build_action_steps_or_warn(
            action_id=WorkflowActionId.FETCH_EPISODES,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
            options={"episode_url_by_id": {ref.episode_id: ref.url for ref in index.episodes}},
        )
        if fetch_steps is None:
            return
        normalize_steps = self._build_action_steps_or_warn(
            action_id=WorkflowActionId.NORMALIZE_EPISODES,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
            options={
                "default_profile_id": batch_profile,
                "profile_by_episode": profile_by_episode,
            },
        )
        if normalize_steps is None:
            return
        segment_steps = self._build_action_steps_or_warn(
            action_id=WorkflowActionId.SEGMENT_EPISODES,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
            options={"lang_hint": self._resolve_lang_hint(context)},
        )
        if segment_steps is None:
            return
        index_steps = self._build_action_steps_or_warn(
            action_id=WorkflowActionId.BUILD_DB_INDEX,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
        )
        if index_steps is None:
            return
        steps = fetch_steps + normalize_steps + segment_steps + index_steps
        if not steps:
            QMessageBox.information(self, "Corpus", "Aucune opération à exécuter.")
            return
        self._run_job(steps)

    def _fetch_episodes(self, scope_mode: str | None = None) -> None:
        resolved = self._resolve_scope_context(scope_mode=scope_mode, require_db=True)
        if resolved is None:
            return
        _store, _db, context, index, scope, _ids = resolved
        self._run_action_for_scope(
            action_id=WorkflowActionId.FETCH_EPISODES,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
            options={
                "episode_url_by_id": {ref.episode_id: ref.url for ref in index.episodes}
            },
            empty_message="Aucun épisode à télécharger.",
        )

    def _normalize_episodes(self, scope_mode: str | None = None) -> None:
        resolved = self._resolve_scope_context(scope_mode=scope_mode)
        if resolved is None:
            return
        store, _db, context, index, scope, ids = resolved
        batch_profile = self.norm_batch_profile_combo.currentText() or "default_en_v1"
        profile_by_episode = self._build_profile_by_episode(
            store=store,
            episode_refs=index.episodes,
            episode_ids=ids,
            batch_profile=batch_profile,
        )
        self._run_action_for_scope(
            action_id=WorkflowActionId.NORMALIZE_EPISODES,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
            options={
                "default_profile_id": batch_profile,
                "profile_by_episode": profile_by_episode,
            },
            empty_message="Aucun épisode à normaliser.",
        )

    def _segment_episodes(self, scope_mode: str | None = None) -> None:
        """Bloc 2 — Segmente les épisodes du scope sélectionné ayant clean.txt."""
        resolved = self._resolve_scope_context(scope_mode=scope_mode)
        if resolved is None:
            return
        store, _db, context, index, _scope, ids = resolved
        eids_with_clean = [eid for eid in ids if store.has_episode_clean(eid)]
        if not eids_with_clean:
            QMessageBox.warning(
                self, "Corpus",
                "Aucun épisode du scope choisi n'a de fichier CLEAN. Normalisez d'abord ce scope."
            )
            return
        self._run_action_for_scope(
            action_id=WorkflowActionId.SEGMENT_EPISODES,
            context=context,
            scope=WorkflowScope.selection(eids_with_clean),
            episode_refs=index.episodes,
            options={"lang_hint": self._resolve_lang_hint(context)},
            empty_message="Aucun épisode à segmenter.",
        )

    def _run_all_for_scope(self) -> None:
        """§5 — Enchaînement : Télécharger → Normaliser → Segmenter → Indexer DB sur le scope choisi."""
        resolved = self._resolve_scope_context(require_db=True)
        if resolved is None:
            return
        store, _db, context, index, _scope, ids = resolved
        self._run_all_for_episode_ids(ids=ids, index=index, store=store, context=context)

    def _retry_selected_error_episode(self) -> None:
        resolved = self._resolve_project_context(require_db=True)
        if resolved is None:
            return
        store, _db, context = resolved
        index = self._load_index_or_warn(store)
        if index is None:
            return
        eid = self._selected_error_episode_id()
        if not eid:
            QMessageBox.information(self, "Corpus", "Sélectionnez un épisode en erreur à relancer.")
            return
        if eid not in {e.episode_id for e in index.episodes}:
            QMessageBox.warning(self, "Corpus", f"Épisode introuvable dans l'index: {eid}")
            return
        self._run_all_for_episode_ids(
            ids=[eid],
            index=index,
            store=store,
            context=context,
        )

    def _retry_error_episodes(self) -> None:
        """Relance les épisodes en erreur avec un enchaînement complet."""
        resolved = self._resolve_project_context(require_db=True)
        if resolved is None:
            return
        store, _db, context = resolved
        index = self._load_index_or_warn(store)
        if index is None:
            return
        error_ids = self._get_error_episode_ids(index)
        if not error_ids:
            QMessageBox.information(self, "Corpus", "Aucun épisode en erreur à relancer.")
            return
        self._run_all_for_episode_ids(
            ids=error_ids,
            index=index,
            store=store,
            context=context,
        )

    def _open_selected_error_in_inspector(self) -> None:
        if not self._on_open_inspector:
            return
        eid = self._selected_error_episode_id()
        if not eid:
            QMessageBox.information(self, "Corpus", "Sélectionnez un épisode à ouvrir.")
            return
        self._on_open_inspector(eid)

    def _index_db(self, scope_mode: str | None = None) -> None:
        resolved = self._resolve_scope_context(scope_mode=scope_mode, require_db=True)
        if resolved is None:
            return
        _store, _db, context, index, scope, _ids = resolved
        self._run_action_for_scope(
            action_id=WorkflowActionId.BUILD_DB_INDEX,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
            options=None,
            empty_message="Aucun épisode CLEAN à indexer pour ce scope.",
        )

    def _segment_and_index_scope(self, scope_mode: str | None = None) -> None:
        """Chaîne segmenter puis indexer pour les épisodes CLEAN du scope choisi."""
        resolved = self._resolve_scope_context(scope_mode=scope_mode, require_db=True)
        if resolved is None:
            return
        store, _db, context, index, _scope, ids = resolved
        ids_with_clean = [eid for eid in ids if store.has_episode_clean(eid)]
        if not ids_with_clean:
            QMessageBox.warning(self, "Corpus", "Aucun épisode CLEAN à segmenter/indexer pour ce scope.")
            return
        scope = WorkflowScope.selection(ids_with_clean)
        segment_steps = self._build_action_steps_or_warn(
            action_id=WorkflowActionId.SEGMENT_EPISODES,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
            options={"lang_hint": self._resolve_lang_hint(context)},
        )
        if segment_steps is None:
            return
        index_steps = self._build_action_steps_or_warn(
            action_id=WorkflowActionId.BUILD_DB_INDEX,
            context=context,
            scope=scope,
            episode_refs=index.episodes,
        )
        if index_steps is None:
            return
        steps = segment_steps + index_steps
        if not steps:
            QMessageBox.information(self, "Corpus", "Aucune opération à exécuter.")
            return
        self._run_job(steps)

    def _export_corpus(self) -> None:
        store = self._get_store()
        if not store:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        episodes_data: list[tuple[EpisodeRef, str]] = []
        for ref in index.episodes:
            if store.has_episode_clean(ref.episode_id):
                text = store.load_episode_text(ref.episode_id, kind="clean")
                episodes_data.append((ref, text))
        if not episodes_data:
            QMessageBox.warning(
                self, "Corpus", "Aucun épisode normalisé (CLEAN) à exporter."
            )
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter le corpus",
            "",
            "TXT (*.txt);;CSV (*.csv);;JSON (*.json);;Word (*.docx);;"
            "JSONL - Utterances (*.jsonl);;JSONL - Phrases (*.jsonl);;"
            "CSV - Utterances (*.csv);;CSV - Phrases (*.csv)",
        )
        if not path:
            return
        path = Path(path)
        selected_filter = selected_filter or ""
        path = normalize_export_path(
            path,
            selected_filter,
            allowed_suffixes=(".txt", ".csv", ".json", ".jsonl", ".docx"),
            default_suffix=".txt",
            filter_to_suffix={
                "TXT": ".txt",
                "CSV": ".csv",
                "JSON": ".json",
                "JSONL": ".jsonl",
                "WORD": ".docx",
            },
        )
        selected_upper = selected_filter.upper()
        try:
            if "JSONL - UTTERANCES" in selected_upper:
                export_corpus_utterances_jsonl(episodes_data, path)
            elif "JSONL - PHRASES" in selected_upper:
                export_corpus_phrases_jsonl(episodes_data, path)
            elif "CSV - UTTERANCES" in selected_upper:
                export_corpus_utterances_csv(episodes_data, path)
            elif "CSV - PHRASES" in selected_upper:
                export_corpus_phrases_csv(episodes_data, path)
            else:
                export_key = resolve_export_key(
                    path,
                    selected_filter,
                    suffix_to_key={
                        ".txt": "txt",
                        ".csv": "csv",
                        ".json": "json",
                        ".jsonl": "jsonl",
                        ".docx": "docx",
                    },
                    default_key="txt",
                )
                if export_key == "txt":
                    export_corpus_txt(episodes_data, path)
                elif export_key == "csv":
                    export_corpus_csv(episodes_data, path)
                elif export_key == "json":
                    export_corpus_json(episodes_data, path)
                elif export_key == "docx":
                    export_corpus_docx(episodes_data, path)
                elif export_key == "jsonl":
                    # JSONL direct sans variante explicite: valeur par défaut = utterances.
                    export_corpus_utterances_jsonl(episodes_data, path)
                else:
                    QMessageBox.warning(
                        self,
                        "Export",
                        "Format non reconnu. Utilisez .txt, .csv, .json, .jsonl ou .docx.",
                    )
                    return
            QMessageBox.information(
                self, "Export", f"Corpus exporté : {len(episodes_data)} épisode(s)."
            )
        except Exception as e:
            logger.exception("Export corpus")
            show_error(self, exc=e, context="Export corpus")
