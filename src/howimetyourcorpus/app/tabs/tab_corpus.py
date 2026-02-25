"""Onglet Corpus : arbre épisodes, filtre saison, workflow (découvrir, télécharger, normaliser, indexer, exporter)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex
from howimetyourcorpus.core.normalize.profiles import PROFILES, get_all_profile_ids
from howimetyourcorpus.core.pipeline.tasks import (
    FetchSeriesIndexStep,
)
from howimetyourcorpus.app.models_qt import (
    EpisodesTreeModel,
    EpisodesTreeFilterProxyModel,
    EpisodesTableModel,
    EpisodesFilterProxyModel,
)
from howimetyourcorpus.app.tabs.corpus_export import (
    build_clean_episodes_data,
    export_corpus_by_filter,
)
from howimetyourcorpus.app.tabs.corpus_sources import CorpusSourcesController
from howimetyourcorpus.app.tabs.corpus_workflow import CorpusWorkflowController
from howimetyourcorpus.app.ui_utils import require_project, require_project_and_db

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
        self._failed_episode_ids: set[str] = set()  # Stocke les episode_id en échec
        self._sources_controller = CorpusSourcesController(self)
        self._workflow_controller = CorpusWorkflowController(self)

        layout = QVBoxLayout(self)
        self._build_filter_row(layout)
        self._build_episodes_view(layout)
        ribbon_layout = self._build_ribbon_container(layout)
        self._build_sources_group(ribbon_layout)
        self._build_normalization_group(ribbon_layout)
        self._build_status_block(ribbon_layout)
        self._on_corpus_ribbon_toggled(True)

    def _build_filter_row(self, layout: QVBoxLayout) -> None:
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Saison:"))
        self.season_filter_combo = QComboBox()
        self.season_filter_combo.setMinimumWidth(140)
        self.season_filter_combo.currentIndexChanged.connect(self._on_season_filter_changed)
        filter_row.addWidget(self.season_filter_combo)
        self.check_season_btn = QPushButton("Cocher la saison")
        self.check_season_btn.setToolTip(
            "Coche tous les épisodes de la saison choisie dans le filtre (ou tout si « Toutes les saisons »)."
        )
        self.check_season_btn.clicked.connect(self._on_check_season_clicked)
        filter_row.addWidget(self.check_season_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

    def _build_episodes_view(self, layout: QVBoxLayout) -> None:
        # Sur macOS, QTreeView + proxy provoque des segfaults ; on utilise une table plate (QTableView).
        # Fix : Windows a le même problème avec TVMaze (62 épisodes) → force TableView partout.
        _use_table = True
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
        layout.addWidget(self.episodes_tree)

    def _build_ribbon_container(self, layout: QVBoxLayout) -> QVBoxLayout:
        self.corpus_ribbon_toggle_btn = QToolButton()
        self.corpus_ribbon_toggle_btn.setCheckable(True)
        self.corpus_ribbon_toggle_btn.setChecked(True)
        self.corpus_ribbon_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.corpus_ribbon_toggle_btn.setArrowType(Qt.ArrowType.DownArrow)
        self.corpus_ribbon_toggle_btn.setText("Masquer le panneau d'actions")
        self.corpus_ribbon_toggle_btn.toggled.connect(self._on_corpus_ribbon_toggled)
        layout.addWidget(self.corpus_ribbon_toggle_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.corpus_ribbon_content = QWidget()
        ribbon_layout = QVBoxLayout(self.corpus_ribbon_content)
        ribbon_layout.setContentsMargins(0, 0, 0, 0)
        ribbon_layout.setSpacing(layout.spacing())
        layout.addWidget(self.corpus_ribbon_content)
        return ribbon_layout

    def _build_sources_group(self, ribbon_layout: QVBoxLayout) -> None:
        group_sources = QGroupBox("1. SOURCES — Constitution du corpus")
        group_sources.setToolTip(
            "Choisissez une ou deux sources pour constituer votre corpus. "
            "Les deux sources sont équivalentes et peuvent être utilisées indépendamment ou ensemble."
        )
        sources_main_layout = QVBoxLayout()

        global_btn_row = QHBoxLayout()
        self.check_all_btn = QPushButton("Tout cocher")
        self.check_all_btn.clicked.connect(lambda: self.episodes_tree_model.set_all_checked(True))
        self.uncheck_all_btn = QPushButton("Tout décocher")
        self.uncheck_all_btn.clicked.connect(lambda: self.episodes_tree_model.set_all_checked(False))
        global_btn_row.addWidget(self.check_all_btn)
        global_btn_row.addWidget(self.uncheck_all_btn)
        global_btn_row.addStretch()
        sources_main_layout.addLayout(global_btn_row)

        two_columns_layout = QHBoxLayout()
        two_columns_layout.addWidget(self._build_transcripts_group())
        two_columns_layout.addWidget(self._build_subtitles_group())
        sources_main_layout.addLayout(two_columns_layout)

        workflow_help = QLabel(
            "💡 <b>Workflows flexibles :</b> "
            "Transcripts seuls, Sous-titres seuls, ou les deux ensemble. "
            "Commencez par la source de votre choix !"
        )
        workflow_help.setWordWrap(True)
        workflow_help.setStyleSheet("background-color: #f0f8ff; padding: 8px; border-radius: 4px;")
        sources_main_layout.addWidget(workflow_help)

        group_sources.setLayout(sources_main_layout)
        ribbon_layout.addWidget(group_sources)

    def _build_transcripts_group(self) -> QGroupBox:
        transcripts_group = QGroupBox("📄 TRANSCRIPTS")
        transcripts_group.setToolTip(
            "Texte narratif complet récupéré depuis des sites web spécialisés (subslikescript, etc.). "
            "Récupération automatique via URL de la série."
        )
        transcripts_layout = QVBoxLayout()
        transcripts_layout.addWidget(QLabel("<b>Récupération automatique depuis le web</b>"))
        transcripts_layout.addWidget(QLabel("<i>Source configurée dans l'onglet Projet</i>"))

        self.discover_btn = QPushButton("🔍 Découvrir épisodes")
        self.discover_btn.setToolTip(
            "Récupère automatiquement la liste des épisodes depuis la source web configurée "
            "(URL série dans l'onglet Projet)."
        )
        self.discover_btn.clicked.connect(self._discover_episodes)
        transcripts_layout.addWidget(self.discover_btn)

        self.discover_merge_btn = QPushButton("🔀 Fusionner autre source...")
        self.discover_merge_btn.setToolTip(
            "Découvre une série depuis une autre source/URL et fusionne avec l'index existant "
            "(sans écraser les épisodes déjà présents)."
        )
        self.discover_merge_btn.clicked.connect(self._discover_merge)
        transcripts_layout.addWidget(self.discover_merge_btn)

        self.fetch_sel_btn = QPushButton("⬇️ Télécharger sélection")
        self.fetch_sel_btn.setToolTip(
            "Télécharge le texte narratif des épisodes cochés (ou des lignes sélectionnées au clic)."
        )
        self.fetch_sel_btn.clicked.connect(lambda: self._fetch_episodes(selection_only=True))
        transcripts_layout.addWidget(self.fetch_sel_btn)

        self.fetch_all_btn = QPushButton("⬇️ Télécharger tout")
        self.fetch_all_btn.setToolTip("Télécharge le texte narratif de tous les épisodes découverts.")
        self.fetch_all_btn.clicked.connect(lambda: self._fetch_episodes(selection_only=False))
        transcripts_layout.addWidget(self.fetch_all_btn)

        self.transcripts_status_label = QLabel("Status : 0/0 téléchargés")
        self.transcripts_status_label.setStyleSheet("color: gray; font-style: italic;")
        transcripts_layout.addWidget(self.transcripts_status_label)

        transcripts_layout.addStretch()
        transcripts_group.setLayout(transcripts_layout)
        return transcripts_group

    def _build_subtitles_group(self) -> QGroupBox:
        subtitles_group = QGroupBox("📺 SOUS-TITRES (SRT)")
        subtitles_group.setToolTip(
            "Fichiers de sous-titres (.srt) alignés précisément sur la vidéo avec timestamps. "
            "Import manuel depuis votre ordinateur."
        )
        subtitles_layout = QVBoxLayout()
        subtitles_layout.addWidget(QLabel("<b>Import manuel depuis votre ordinateur</b>"))
        subtitles_layout.addWidget(QLabel("<i>Fichiers .srt avec timestamps vidéo</i>"))

        self.add_episodes_btn = QPushButton("➕ Ajouter épisodes (liste)")
        self.add_episodes_btn.setToolTip(
            "Créer manuellement la liste des épisodes (ex: S01E01, S01E02...). "
            "Nécessaire avant d'importer les fichiers .srt si vous n'avez pas découvert via transcripts."
        )
        self.add_episodes_btn.clicked.connect(self._add_episodes_manually)
        subtitles_layout.addWidget(self.add_episodes_btn)

        self.import_srt_sel_btn = QPushButton("📥 Importer SRT sélection")
        self.import_srt_sel_btn.setToolTip(
            "Importer les fichiers .srt depuis votre ordinateur pour les épisodes sélectionnés. "
            "Vous serez invité à choisir les fichiers .srt un par un."
        )
        self.import_srt_sel_btn.clicked.connect(self._import_srt_selection)
        subtitles_layout.addWidget(self.import_srt_sel_btn)

        self.import_srt_batch_btn = QPushButton("📁 Import batch (dossier)")
        self.import_srt_batch_btn.setToolTip(
            "Importer automatiquement tous les fichiers .srt d'un dossier. "
            "Détection automatique des épisodes depuis les noms de fichiers (ex: S01E01.srt)."
        )
        self.import_srt_batch_btn.clicked.connect(self._import_srt_batch)
        subtitles_layout.addWidget(self.import_srt_batch_btn)

        self.manage_srt_btn = QPushButton("⚙️ Gérer sous-titres")
        self.manage_srt_btn.setToolTip(
            "Ouvre l'onglet Inspecteur pour gérer les pistes de sous-titres (voir, ajouter, supprimer)."
        )
        self.manage_srt_btn.clicked.connect(self._open_subtitles_manager)
        subtitles_layout.addWidget(self.manage_srt_btn)

        self.subtitles_status_label = QLabel("Status : 0/0 importés")
        self.subtitles_status_label.setStyleSheet("color: gray; font-style: italic;")
        subtitles_layout.addWidget(self.subtitles_status_label)

        subtitles_layout.addStretch()
        subtitles_group.setLayout(subtitles_layout)
        return subtitles_group

    def _build_normalization_group(self, ribbon_layout: QVBoxLayout) -> None:
        group_norm = QGroupBox("2. Normalisation / segmentation — Après import")
        group_norm.setToolTip(
            "Workflow §14 : Mise au propre des transcripts (RAW → CLEAN) et segmentation. "
            "Prérequis : au moins un épisode téléchargé (Bloc 1). L'alignement (Bloc 3) est dans les onglets Alignement, Concordance, Personnages."
        )
        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(QLabel("Profil (batch):"))
        self.norm_batch_profile_combo = QComboBox()
        self.norm_batch_profile_combo.addItems(list(PROFILES.keys()))
        self.norm_batch_profile_combo.setToolTip(
            "Profil par défaut pour « Normaliser sélection » et « Normaliser tout ». "
            "Priorité par épisode : 1) profil préféré (Inspecteur) 2) défaut de la source (Profils) 3) ce profil."
        )
        btn_row2.addWidget(self.norm_batch_profile_combo)

        self.manage_profiles_btn = QPushButton("⚙️ Gérer profils")
        self.manage_profiles_btn.setToolTip(
            "Ouvre le dialogue de gestion des profils de normalisation : "
            "créer, modifier, supprimer des profils personnalisés avec prévisualisation."
        )
        self.manage_profiles_btn.clicked.connect(self._open_profiles_dialog)
        btn_row2.addWidget(self.manage_profiles_btn)

        self.norm_sel_btn = QPushButton("Normaliser\nsélection")
        self.norm_sel_btn.setToolTip(
            "Bloc 2 — Normalise les épisodes cochés (ou les lignes sélectionnées). Prérequis : épisodes déjà téléchargés (RAW, Bloc 1)."
        )
        self.norm_sel_btn.clicked.connect(lambda: self._normalize_episodes(selection_only=True))
        self.norm_all_btn = QPushButton("Normaliser tout")
        self.norm_all_btn.setToolTip(
            "Bloc 2 — Normalise tout le corpus. Prérequis : épisodes déjà téléchargés (RAW, Bloc 1)."
        )
        self.norm_all_btn.clicked.connect(lambda: self._normalize_episodes(selection_only=False))
        self.segment_sel_btn = QPushButton("Segmenter\nsélection")
        self.segment_sel_btn.setToolTip(
            "Bloc 2 — Segmente les épisodes cochés (ou sélectionnés) ayant un fichier CLEAN."
        )
        self.segment_sel_btn.clicked.connect(lambda: self._segment_episodes(selection_only=True))
        self.segment_all_btn = QPushButton("Segmenter tout")
        self.segment_all_btn.setToolTip("Bloc 2 — Segmente tout le corpus (épisodes ayant CLEAN).")
        self.segment_all_btn.clicked.connect(lambda: self._segment_episodes(selection_only=False))
        self.all_in_one_btn = QPushButton("Tout faire\n(sélection)")
        self.all_in_one_btn.setToolTip(
            "§5 — Enchaînement pour les épisodes cochés : Télécharger → Normaliser → Segmenter → Indexer DB."
        )
        self.all_in_one_btn.clicked.connect(self._run_all_for_selection)
        self.index_btn = QPushButton("Indexer DB")
        self.index_btn.setToolTip(
            "Bloc 2 — Indexe en base tous les épisodes ayant un fichier CLEAN (segmentation). Tout le projet."
        )
        self.index_btn.clicked.connect(self._index_db)
        self.export_corpus_btn = QPushButton("Exporter corpus")
        self.export_corpus_btn.clicked.connect(self._export_corpus)
        self.cancel_job_btn = QPushButton("Annuler")
        self.cancel_job_btn.clicked.connect(self._emit_cancel_job)
        self.cancel_job_btn.setEnabled(False)
        self.resume_failed_btn = QPushButton("Reprendre les échecs")
        self.resume_failed_btn.setToolTip(
            "Relance uniquement les épisodes qui ont échoué lors du dernier job (téléchargement, normalisation, etc.)"
        )
        self.resume_failed_btn.clicked.connect(self._resume_failed_episodes)
        self.resume_failed_btn.setEnabled(False)

        for btn in (
            self.norm_sel_btn,
            self.norm_all_btn,
            self.segment_sel_btn,
            self.segment_all_btn,
            self.all_in_one_btn,
            self.index_btn,
            self.export_corpus_btn,
        ):
            btn_row2.addWidget(btn)
        btn_row2.addWidget(self.cancel_job_btn)
        btn_row2.addWidget(self.resume_failed_btn)
        btn_row2.addStretch()
        group_norm.setLayout(btn_row2)
        ribbon_layout.addWidget(group_norm)

    def _build_status_block(self, ribbon_layout: QVBoxLayout) -> None:
        self.corpus_progress = QProgressBar()
        self.corpus_progress.setMaximum(100)
        self.corpus_progress.setValue(0)
        ribbon_layout.addWidget(self.corpus_progress)
        self.corpus_status_label = QLabel("")
        self.corpus_status_label.setToolTip(
            "Workflow §14 (3 blocs) : Bloc 1 = Découverts → Téléchargés → SRT (import). "
            "Bloc 2 = Normalisés (CLEAN) → Segmentés (DB). Bloc 3 = Alignés (onglets Alignement, Concordance, Personnages)."
        )
        ribbon_layout.addWidget(self.corpus_status_label)
        scope_label = QLabel(
            "§14 — Bloc 1 (Import) : découverte, téléchargement, SRT (onglet Sous-titres). "
            "Bloc 2 (Normalisation / segmentation) : profil batch, Normaliser, Indexer DB. "
            "Périmètre : « sélection » = épisodes cochés ou lignes sélectionnées ; « tout » = tout le corpus."
        )
        scope_label.setStyleSheet("color: gray; font-size: 0.9em;")
        scope_label.setWordWrap(True)
        ribbon_layout.addWidget(scope_label)

    def _on_corpus_ribbon_toggled(self, expanded: bool) -> None:
        self.corpus_ribbon_content.setVisible(bool(expanded))
        if expanded:
            self.corpus_ribbon_toggle_btn.setArrowType(Qt.ArrowType.DownArrow)
            self.corpus_ribbon_toggle_btn.setText("Masquer le panneau d'actions")
        else:
            self.corpus_ribbon_toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
            self.corpus_ribbon_toggle_btn.setText("Afficher le panneau d'actions")

    def set_progress(self, value: int) -> None:
        self.corpus_progress.setValue(value)

    def set_cancel_btn_enabled(self, enabled: bool) -> None:
        self.cancel_job_btn.setEnabled(enabled)

    def set_resume_failed_btn_enabled(self, enabled: bool) -> None:
        """Active/désactive le bouton 'Reprendre les échecs'."""
        self.resume_failed_btn.setEnabled(enabled)

    def store_failed_episodes(self, failed_ids: set[str]) -> None:
        """Stocke les episode_id en échec pour la reprise."""
        self._failed_episode_ids = failed_ids
        self.set_resume_failed_btn_enabled(len(failed_ids) > 0)

    def _emit_cancel_job(self) -> None:
        self._on_cancel_job()

    def _get_selected_or_checked_episode_ids(self) -> list[str]:
        """Retourne les episode_id cochés, ou à défaut ceux des lignes sélectionnées."""
        ids = self.episodes_tree_model.get_checked_episode_ids()
        if not ids:
            proxy_indices = self.episodes_tree.selectionModel().selectedIndexes()
            source_indices = [
                self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices
            ]
            ids = self.episodes_tree_model.get_episode_ids_selection(source_indices)
        return ids

    def _get_project_index_context(self) -> tuple[Any, Any, SeriesIndex] | None:
        """Retourne (store, config, index) pour les actions batch, sinon affiche un warning."""
        store = self._get_store()
        context = self._get_context()
        if not context or not context.get("config") or not store:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return None
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return None
        return store, context["config"], index

    def _resolve_target_episode_ids(
        self,
        *,
        index: SeriesIndex,
        selection_only: bool,
    ) -> list[str] | None:
        """Résout la cible épisodes (sélection cochée/lignes ou tout le corpus)."""
        if selection_only:
            ids = self._get_selected_or_checked_episode_ids()
            if not ids:
                QMessageBox.warning(
                    self, "Corpus", "Cochez au moins un épisode ou sélectionnez des lignes."
                )
                return None
            return ids
        return [e.episode_id for e in index.episodes]

    @staticmethod
    def _resolve_episode_profile(
        *,
        episode_id: str,
        ref_by_id: dict[str, EpisodeRef],
        episode_preferred: dict[str, str],
        source_defaults: dict[str, str],
        batch_profile: str,
    ) -> str:
        ref = ref_by_id.get(episode_id)
        return (
            episode_preferred.get(episode_id)
            or (source_defaults.get(ref.source_id or "") if ref else None)
            or batch_profile
        )

    @staticmethod
    def _lang_hint_from_profile(profile_id: str | None) -> str:
        profile = (profile_id or "").strip()
        if not profile:
            return "en"
        token = profile.split("_")[0]
        hint = token.replace("default", "en")
        return hint or "en"

    def _set_no_project_state(self) -> None:
        """Met l'UI dans l'état « pas de projet » (labels vides, boutons désactivés)."""
        self.season_filter_combo.clear()
        self.season_filter_combo.addItem("Toutes les saisons", None)
        self.corpus_status_label.setText("")
        self.transcripts_status_label.setText("Status : 0/0 téléchargés")
        self.subtitles_status_label.setText("Status : 0/0 importés")
        self.norm_sel_btn.setEnabled(False)
        self.norm_all_btn.setEnabled(False)
        self.segment_sel_btn.setEnabled(False)
        self.segment_all_btn.setEnabled(False)
        self.all_in_one_btn.setEnabled(False)

    def _resume_failed_episodes(self) -> None:
        """Relance les opérations sur les épisodes en échec (téléchargement, normalisation, etc.)."""
        if not self._failed_episode_ids:
            QMessageBox.information(
                self, "Reprendre échecs", "Aucun échec récent à reprendre."
            )
            return
        # Cocher les épisodes en échec
        self.episodes_tree_model.set_checked(self._failed_episode_ids, True)
        # Message de confirmation
        reply = QMessageBox.question(
            self,
            "Reprendre les échecs",
            f"{len(self._failed_episode_ids)} épisode(s) en échec cochés.\n\n"
            "Relancer maintenant le même type d'opération ?\n"
            "(Télécharger/Normaliser/Segmenter selon ce qui a échoué)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # L'utilisateur doit cliquer sur le bouton approprié (Télécharger/Normaliser/etc.)
            QMessageBox.information(
                self,
                "Reprendre",
                f"{len(self._failed_episode_ids)} épisode(s) cochés. Cliquez sur le bouton d'action approprié (Télécharger, Normaliser, etc.).",
            )

    def refresh(self) -> None:
        """Recharge l'arbre et le statut depuis le store (appelé après ouverture projet / fin de job)."""
        try:
            store = self._get_store()
            db = self._get_db()
            if not store:
                self._set_no_project_state()
                return
            index = store.load_series_index()
            if not index or not index.episodes:
                self._set_no_project_state()
                return
            n_total = len(index.episodes)
            n_fetched = sum(1 for e in index.episodes if store.has_episode_raw(e.episode_id))
            n_norm = sum(1 for e in index.episodes if store.has_episode_clean(e.episode_id))
            n_indexed = len(db.get_episode_ids_indexed()) if db else 0
            n_with_srt = 0
            n_aligned = 0
            if db and index.episodes:
                episode_ids = [e.episode_id for e in index.episodes]
                tracks_by_ep = db.get_tracks_for_episodes(episode_ids)
                runs_by_ep = db.get_align_runs_for_episodes(episode_ids)
                n_with_srt = sum(1 for e in index.episodes if tracks_by_ep.get(e.episode_id))
                n_aligned = sum(1 for e in index.episodes if runs_by_ep.get(e.episode_id))
            
            # Status global
            self.corpus_status_label.setText(
                f"Workflow : Découverts {n_total} | Téléchargés {n_fetched} | Normalisés {n_norm} | Segmentés {n_indexed} | SRT {n_with_srt} | Alignés {n_aligned}"
            )
            
            # Status colonne Transcripts
            missing_transcripts = n_total - n_fetched
            if missing_transcripts > 0:
                self.transcripts_status_label.setText(f"Status : {n_fetched}/{n_total} téléchargés ⚠️ ({missing_transcripts} manquants)")
                self.transcripts_status_label.setStyleSheet("color: orange; font-style: italic;")
            else:
                self.transcripts_status_label.setText(f"Status : {n_fetched}/{n_total} téléchargés ✅")
                self.transcripts_status_label.setStyleSheet("color: green; font-style: italic;")
            
            # Status colonne Sous-titres
            missing_srt = n_total - n_with_srt
            if missing_srt > 0:
                self.subtitles_status_label.setText(f"Status : {n_with_srt}/{n_total} importés ⚠️ ({missing_srt} manquants)")
                self.subtitles_status_label.setStyleSheet("color: orange; font-style: italic;")
            else:
                self.subtitles_status_label.setText(f"Status : {n_with_srt}/{n_total} importés ✅")
                self.subtitles_status_label.setStyleSheet("color: green; font-style: italic;")
            
            self.norm_sel_btn.setEnabled(n_fetched > 0 or n_with_srt > 0)  # Normaliser si transcripts OU sous-titres
            self.norm_all_btn.setEnabled(n_fetched > 0 or n_with_srt > 0)
            self.segment_sel_btn.setEnabled(n_norm > 0)
            self.segment_all_btn.setEnabled(n_norm > 0)
            self.all_in_one_btn.setEnabled(n_total > 0)
            
            # Mise à jour de l'arbre : synchrone (refresh est déjà appelé après OK, pas au même moment que la boîte de dialogue)
            # Pas d'expandAll() : provoque segfault sur macOS ; déplier à la main (flèche à gauche de « Saison N »)
            logger.debug(f"Corpus refresh: updating tree model with {len(index.episodes)} episodes")
            self.episodes_tree_model.set_store(store)
            self.episodes_tree_model.set_db(db)
            self.episodes_tree_model.set_episodes(index.episodes)
            self._refresh_season_filter_combo()
            logger.debug("Corpus refresh completed successfully")
        except Exception as e:
            logger.exception("Error in corpus_tab.refresh()")
            QMessageBox.critical(self, "Erreur Corpus", f"Erreur lors du rafraîchissement du corpus:\n\n{type(e).__name__}: {e}\n\nVoir l'onglet Logs pour plus de détails.")

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
            except (ValueError, AttributeError) as exc:
                logger.debug("Season expand skipped for %r: %s", season, exc)

    def _on_episode_double_clicked(self, proxy_index: QModelIndex) -> None:
        """Double-clic sur un épisode : ouvrir l'Inspecteur sur cet épisode (comme Concordance)."""
        if not proxy_index.isValid() or not self._on_open_inspector:
            return
        source_index = self.episodes_tree_proxy.mapToSource(proxy_index)
        episode_id = self.episodes_tree_model.get_episode_id_for_index(source_index)
        if episode_id:
            self._on_open_inspector(episode_id)

    def _on_check_season_clicked(self) -> None:
        season = self.season_filter_combo.currentData()
        ids = self.episodes_tree_model.get_episode_ids_for_season(season)
        if not ids:
            return
        self.episodes_tree_model.set_checked(set(ids), True)

    @require_project_and_db
    def _discover_episodes(self) -> None:
        context = self._get_context()
        if not context or not context.get("config"):
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        config = context["config"]
        step = FetchSeriesIndexStep(config.series_url, config.user_agent)
        self._run_job([step])
    
    @require_project
    def _open_profiles_dialog(self) -> None:
        """Ouvre le dialogue de gestion des profils de normalisation."""
        store = self._get_store()
        assert store is not None  # garanti par @require_project
        from howimetyourcorpus.app.dialogs import ProfilesDialog
        dlg = ProfilesDialog(self, store)
        dlg.exec()
        custom_profiles = store.load_custom_profiles()
        self.refresh_profile_combo(
            get_all_profile_ids(custom_profiles),
            self.norm_batch_profile_combo.currentText(),
        )

    @require_project_and_db
    def _discover_merge(self) -> None:
        self._sources_controller.discover_merge()

    @require_project
    def _add_episodes_manually(self) -> None:
        self._sources_controller.add_episodes_manually()
    
    @require_project_and_db
    def _import_srt_selection(self) -> None:
        self._sources_controller.import_srt_selection()
    
    @require_project_and_db
    def _import_srt_batch(self) -> None:
        self._sources_controller.import_srt_batch()
    
    @require_project
    def _open_subtitles_manager(self) -> None:
        self._sources_controller.open_subtitles_manager()


    @require_project_and_db
    def _fetch_episodes(self, selection_only: bool) -> None:
        self._workflow_controller.fetch_episodes(selection_only)

    @require_project
    def _normalize_episodes(self, selection_only: bool) -> None:
        self._workflow_controller.normalize_episodes(selection_only)

    @require_project
    def _segment_episodes(self, selection_only: bool) -> None:
        """Bloc 2 — Segmente les épisodes (sélection ou tout) ayant clean.txt."""
        self._workflow_controller.segment_episodes(selection_only)

    @require_project_and_db
    def _run_all_for_selection(self) -> None:
        """§5 — Enchaînement : Télécharger → Normaliser → Segmenter → Indexer DB pour les épisodes cochés."""
        self._workflow_controller.run_all_for_selection()

    @require_project_and_db
    def _index_db(self) -> None:
        self._workflow_controller.index_db()

    @require_project
    def _export_corpus(self) -> None:
        store = self._get_store()
        assert store is not None  # garanti par @require_project
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        
        # Demander si on exporte tout ou seulement la sélection
        selected_ids = self._get_selected_or_checked_episode_ids()
        export_selection_only = False
        if selected_ids:
            reply = QMessageBox.question(
                self,
                "Export corpus",
                f"Exporter uniquement la sélection ({len(selected_ids)} épisode(s) cochés) ?\n\n"
                f"Oui = sélection uniquement\nNon = tout le corpus normalisé",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            export_selection_only = (reply == QMessageBox.StandardButton.Yes)

        selected_set = set(selected_ids) if export_selection_only else None
        episodes_data = build_clean_episodes_data(
            store=store,
            episodes=index.episodes,
            selected_ids=selected_set,
        )
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
        output_path = Path(path)
        selected_filter = selected_filter or ""
        try:
            if not export_corpus_by_filter(episodes_data, output_path, selected_filter):
                QMessageBox.warning(
                    self,
                    "Export",
                    "Format non reconnu. Utilisez .txt, .csv, .json ou .jsonl (segmenté).",
                )
                return
            QMessageBox.information(self, "Export", f"Corpus exporté : {len(episodes_data)} épisode(s).")
        except Exception as e:
            logger.exception("Export corpus")
            QMessageBox.critical(self, "Erreur", str(e))
