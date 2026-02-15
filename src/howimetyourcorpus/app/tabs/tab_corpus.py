"""Onglet Corpus : arbre épisodes, filtre saison, workflow (découvrir, télécharger, normaliser, indexer, exporter)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QModelIndex, QSettings, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.adapters.base import AdapterRegistry
from howimetyourcorpus.core.models import EpisodeStatus, SeriesIndex
from howimetyourcorpus.core.normalize.profiles import PROFILES, resolve_lang_hint_from_profile_id
from howimetyourcorpus.core.workflow import (
    WorkflowScope,
    WorkflowService,
)
from howimetyourcorpus.app.feedback import show_error, show_info, warn_precondition
from howimetyourcorpus.app.corpus_controller import CorpusWorkflowController
from howimetyourcorpus.app.export_dialog import build_export_success_message
from howimetyourcorpus.app.corpus_scope import (
    build_episode_scope_capabilities,
    normalize_scope_mode,
    resolve_scope_ids,
    resolve_episode_scope_capabilities_cache,
)
from howimetyourcorpus.app.models_qt import (
    EpisodesTreeModel,
    EpisodesTreeFilterProxyModel,
    EpisodesTableModel,
    EpisodesFilterProxyModel,
)

logger = logging.getLogger(__name__)

_CORPUS_FORCE_REPROCESS_KEY = "corpus/forceReprocess"


class CorpusTabWidget(QWidget):
    """Widget de l'onglet Corpus : arbre épisodes, saison, cases à cocher, boutons workflow, progression."""

    def __init__(
        self,
        get_store: Callable[[], Any],
        get_db: Callable[[], Any],
        get_context: Callable[[], Any],
        run_job: Callable[..., None],
        show_status: Callable[[str, int], None],
        refresh_after_episodes_added: Callable[[], None],
        on_cancel_job: Callable[[], None],
        on_open_inspector: Callable[[str], None] | None = None,
        on_open_alignment: Callable[[], None] | None = None,
        on_open_concordance: Callable[[], None] | None = None,
        on_open_logs_for_episode: Callable[[str], None] | None = None,
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
        self._on_open_concordance = on_open_concordance
        self._on_open_logs_for_episode = on_open_logs_for_episode
        self._workflow_controller = CorpusWorkflowController(
            workflow_service=WorkflowService(),
            run_steps=lambda steps: self._run_job_with_force(steps),
            warn_user=self._warn_corpus_precondition,
        )
        self._primary_action: Callable[[], None] | None = None
        self._cached_index: SeriesIndex | None = None
        self._episode_scope_capabilities: dict[str, tuple[bool, bool, bool, bool]] = {}
        self._workflow_busy = False
        self._sidebar_sections_detached = False

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        self._content_layout = layout
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        view_filter_row = QHBoxLayout()
        view_filter_row.setContentsMargins(0, 0, 0, 0)
        view_filter_row.setSpacing(8)
        view_filter_row.addWidget(QLabel("Saison:"))
        self.season_filter_combo = QComboBox()
        self.season_filter_combo.setMinimumWidth(140)
        self.season_filter_combo.currentIndexChanged.connect(self._on_season_filter_changed)
        view_filter_row.addWidget(self.season_filter_combo)
        view_filter_row.addWidget(QLabel("Statut:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.setMinimumWidth(160)
        self.status_filter_combo.addItem("Tous", None)
        self.status_filter_combo.addItem("Nouveaux", EpisodeStatus.NEW.value)
        self.status_filter_combo.addItem("Téléchargés", EpisodeStatus.FETCHED.value)
        self.status_filter_combo.addItem("Normalisés", EpisodeStatus.NORMALIZED.value)
        self.status_filter_combo.addItem("Indexés", EpisodeStatus.INDEXED.value)
        self.status_filter_combo.addItem("En erreur", EpisodeStatus.ERROR.value)
        self.status_filter_combo.currentIndexChanged.connect(self._on_status_filter_changed)
        view_filter_row.addWidget(self.status_filter_combo)
        self.check_season_btn = QPushButton("Cocher la saison")
        self.check_season_btn.setToolTip(
            "Coche tous les épisodes de la saison choisie dans le filtre (ou tout si « Toutes les saisons »)."
        )
        self.check_season_btn.clicked.connect(self._on_check_season_clicked)
        view_filter_row.addWidget(self.check_season_btn)
        view_filter_row.addStretch()
        layout.addLayout(view_filter_row)

        scope_row = QHBoxLayout()
        scope_row.setContentsMargins(0, 0, 0, 0)
        scope_row.setSpacing(8)
        scope_row.addWidget(QLabel("Périmètre action:"))
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
        scope_row.addWidget(self.batch_scope_combo)
        self.scope_preview_label = QLabel("Périmètre: 0 épisode")
        self.scope_preview_label.setStyleSheet("color: #666;")
        scope_row.addWidget(self.scope_preview_label)
        scope_row.addStretch()
        layout.addLayout(scope_row)

        self.primary_action_row = QHBoxLayout()
        self.primary_action_row.setContentsMargins(0, 0, 0, 2)
        self.primary_action_row.setSpacing(8)
        primary_action_title = QLabel("Action recommandée:")
        primary_action_title.setStyleSheet("font-weight: 600;")
        self.primary_action_row.addWidget(primary_action_title)
        self.primary_action_btn = QPushButton("—")
        self.primary_action_btn.clicked.connect(self._run_primary_action)
        self.primary_action_btn.setEnabled(False)
        self.primary_action_btn.setMinimumWidth(240)
        self.primary_action_btn.setMinimumHeight(32)
        self.primary_action_btn.setStyleSheet("font-weight: 600;")
        self.primary_action_btn.setToolTip(
            "Exécute l'action suggérée selon l'état actuel du workflow."
        )
        self.primary_action_row.addWidget(self.primary_action_btn)
        self.primary_action_row.addStretch()
        layout.addLayout(self.primary_action_row)

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
        self.episodes_tree.setMinimumHeight(340)
        self.episodes_tree.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        if _use_table:
            _header = self.episodes_tree.horizontalHeader()
            _header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            _header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            _header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            _header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            _header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            _header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            _header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
            _header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
            self.episodes_tree.setColumnWidth(0, 32)
            self.episodes_tree.setColumnWidth(1, 94)
            self.episodes_tree.setColumnWidth(2, 74)
            self.episodes_tree.setColumnWidth(3, 74)
            self.episodes_tree.setColumnWidth(5, 115)
            self.episodes_tree.setColumnWidth(6, 125)
            self.episodes_tree.setColumnWidth(7, 92)
            self.episodes_tree.setSortingEnabled(True)
        else:
            _header = self.episodes_tree.header()
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
        layout.addWidget(self.episodes_tree, 1)
        self.episodes_empty_label = QLabel("")
        self.episodes_empty_label.setStyleSheet("color: #666; font-style: italic;")
        self.episodes_empty_label.setWordWrap(True)
        self.episodes_empty_label.setVisible(False)
        layout.addWidget(self.episodes_empty_label)

        # Bloc 1 — Import (constitution du corpus) §14
        self.group_import = QGroupBox("1. Importer — Constituer le corpus")
        self.group_import.setToolTip(
            "Workflow §14 : Découvrir les épisodes, télécharger les transcripts (RAW), importer les SRT (panneau Sous-titres de l'Inspecteur). "
            "Pas de normalisation ni d'alignement ici."
        )
        import_layout = QVBoxLayout(self.group_import)
        import_layout.setContentsMargins(8, 8, 8, 8)
        import_layout.setSpacing(6)
        import_primary_row = QHBoxLayout()
        import_primary_row.setContentsMargins(0, 0, 0, 0)
        import_primary_row.setSpacing(6)
        import_primary_row.addWidget(QLabel("Actions principales:"))
        self.discover_btn = QPushButton("Découvrir épisodes")
        self.discover_btn.setToolTip("Récupère la liste des épisodes depuis la source (tout le projet).")
        self.discover_btn.clicked.connect(self._discover_episodes)
        self.discover_btn.setMinimumHeight(30)
        self.discover_btn.setStyleSheet("font-weight: 600;")
        self.fetch_btn = QPushButton("Télécharger")
        self.fetch_btn.setToolTip(
            "Télécharge selon le scope sélectionné (épisode courant, sélection, saison ou tout)."
        )
        self.fetch_btn.clicked.connect(self._fetch_episodes)
        self.fetch_btn.setMinimumHeight(30)
        self.fetch_btn.setStyleSheet("font-weight: 600;")
        import_primary_row.addWidget(self.discover_btn)
        import_primary_row.addWidget(self.fetch_btn)
        import_primary_row.addStretch()
        import_layout.addLayout(import_primary_row)

        import_secondary_row = QHBoxLayout()
        import_secondary_row.setContentsMargins(0, 0, 0, 0)
        import_secondary_row.setSpacing(6)
        secondary_import_label = QLabel("Actions secondaires:")
        secondary_import_label.setStyleSheet("color: #666;")
        import_secondary_row.addWidget(secondary_import_label)
        self.check_all_btn = QPushButton("Tout cocher")
        self.check_all_btn.setMinimumHeight(28)
        self.check_all_btn.clicked.connect(self._check_all_episodes)
        self.uncheck_all_btn = QPushButton("Tout décocher")
        self.uncheck_all_btn.setMinimumHeight(28)
        self.uncheck_all_btn.clicked.connect(self._uncheck_all_episodes)
        import_secondary_row.addWidget(self.check_all_btn)
        import_secondary_row.addWidget(self.uncheck_all_btn)
        self.add_episodes_btn = QPushButton("Ajouter épisodes (SRT only)")
        self.add_episodes_btn.setMinimumHeight(28)
        self.add_episodes_btn.setToolTip(
            "Ajoute des épisodes à la main (un par ligne, ex. S01E01). Pour projet SRT uniquement."
        )
        self.add_episodes_btn.clicked.connect(self._add_episodes_manually)
        self.discover_merge_btn = QPushButton("Découvrir + fusionner une source...")
        self.discover_merge_btn.setMinimumHeight(28)
        self.discover_merge_btn.setToolTip(
            "Découvre une série depuis une autre source/URL et fusionne avec l'index existant (sans écraser les épisodes déjà présents)."
        )
        self.discover_merge_btn.clicked.connect(self._discover_merge)
        import_secondary_row.addWidget(self.add_episodes_btn)
        import_secondary_row.addWidget(self.discover_merge_btn)
        import_secondary_row.addStretch()
        import_layout.addLayout(import_secondary_row)
        import_outputs_label = QLabel(
            "Sorties du bloc 1: index d'épisodes + transcripts RAW (et fusion d'index si « Découvrir (fusionner) »)."
        )
        import_outputs_label.setStyleSheet("color: #666; font-size: 0.9em;")
        import_outputs_label.setWordWrap(True)
        import_layout.addWidget(import_outputs_label)
        layout.addWidget(self.group_import)

        # Bloc 2 — Normalisation / segmentation (après import) §14
        self.group_norm = QGroupBox("2. Transformer / Indexer — Après import")
        self.group_norm.setToolTip(
            "Workflow §14 : Mise au propre des transcripts (RAW → CLEAN) et segmentation. "
            "Prérequis : au moins un épisode téléchargé (Bloc 1). "
            "Le Bloc 3 se fait dans Validation & Annotation (alignement/personnages) et Concordance."
        )
        norm_layout = QVBoxLayout(self.group_norm)
        norm_layout.setContentsMargins(8, 8, 8, 8)
        norm_layout.setSpacing(6)
        norm_settings_row = QHBoxLayout()
        norm_settings_row.setContentsMargins(0, 0, 0, 0)
        norm_settings_row.setSpacing(6)
        norm_settings_row.addWidget(QLabel("Profil (batch):"))
        self.norm_batch_profile_combo = QComboBox()
        self.norm_batch_profile_combo.addItems(list(PROFILES.keys()))
        self.norm_batch_profile_combo.setToolTip(
            "Profil par défaut pour « Normaliser » (scope courant). "
            "Priorité par épisode : 1) profil préféré (Inspecteur) 2) défaut de la source (Profils) 3) ce profil."
        )
        norm_settings_row.addWidget(self.norm_batch_profile_combo)
        self.force_reprocess_check = QCheckBox("Forcer re-traitement")
        self.force_reprocess_check.setToolTip(
            "Relance les étapes idempotentes même si les artefacts existent déjà (CLEAN, segments, index DB)."
        )
        self.force_reprocess_check.toggled.connect(self._save_force_reprocess_state)
        norm_settings_row.addWidget(self.force_reprocess_check)
        norm_settings_row.addStretch()
        norm_layout.addLayout(norm_settings_row)

        norm_primary_row = QHBoxLayout()
        norm_primary_row.setContentsMargins(0, 0, 0, 0)
        norm_primary_row.setSpacing(6)
        norm_primary_row.addWidget(QLabel("Actions principales:"))
        self.norm_btn = QPushButton("Normaliser")
        self.norm_btn.setToolTip(
            "Bloc 2 — Normalise selon le scope sélectionné. Prérequis : épisodes déjà téléchargés (RAW, Bloc 1)."
        )
        self.norm_btn.clicked.connect(self._normalize_episodes)
        self.norm_btn.setMinimumHeight(30)
        self.norm_btn.setStyleSheet("font-weight: 600;")
        self.segment_btn = QPushButton("Segmenter")
        self.segment_btn.setToolTip(
            "Bloc 2 — Segmente selon le scope sélectionné (épisodes ayant un fichier CLEAN)."
        )
        self.segment_btn.clicked.connect(self._segment_episodes)
        self.segment_btn.setMinimumHeight(30)
        self.segment_btn.setStyleSheet("font-weight: 600;")
        self.index_btn = QPushButton("Indexer DB")
        self.index_btn.setToolTip(
            "Bloc 2 — Indexe en base selon le scope sélectionné (épisodes ayant CLEAN)."
        )
        self.index_btn.clicked.connect(self._index_db)
        self.index_btn.setMinimumHeight(30)
        self.index_btn.setStyleSheet("font-weight: 600;")
        norm_primary_row.addWidget(self.norm_btn)
        norm_primary_row.addWidget(self.segment_btn)
        norm_primary_row.addWidget(self.index_btn)
        norm_primary_row.addStretch()
        norm_layout.addLayout(norm_primary_row)

        norm_secondary_row = QHBoxLayout()
        norm_secondary_row.setContentsMargins(0, 0, 0, 0)
        norm_secondary_row.setSpacing(6)
        secondary_norm_label = QLabel("Actions secondaires:")
        secondary_norm_label.setStyleSheet("color: #666;")
        norm_secondary_row.addWidget(secondary_norm_label)
        self.all_in_one_btn = QPushButton("Tout faire")
        self.all_in_one_btn.setMinimumHeight(28)
        self.all_in_one_btn.setToolTip(
            "§5 — Enchaînement selon le scope : Télécharger → Normaliser → Segmenter → Indexer DB."
        )
        self.all_in_one_btn.clicked.connect(self._run_all_for_scope)
        self._fetch_btn_tooltip_default = self.fetch_btn.toolTip()
        self._norm_btn_tooltip_default = self.norm_btn.toolTip()
        self._segment_btn_tooltip_default = self.segment_btn.toolTip()
        self._all_in_one_btn_tooltip_default = self.all_in_one_btn.toolTip()
        self._index_btn_tooltip_default = self.index_btn.toolTip()
        self.export_corpus_btn = QPushButton("Exporter corpus")
        self.export_corpus_btn.setMinimumHeight(28)
        self.export_corpus_btn.clicked.connect(self._export_corpus)
        self.cancel_job_btn = QPushButton("Annuler")
        self.cancel_job_btn.setMinimumHeight(28)
        self.cancel_job_btn.clicked.connect(self._emit_cancel_job)
        self.cancel_job_btn.setEnabled(False)
        norm_secondary_row.addWidget(self.all_in_one_btn)
        norm_secondary_row.addWidget(self.export_corpus_btn)
        norm_secondary_row.addWidget(self.cancel_job_btn)
        norm_secondary_row.addStretch()
        norm_layout.addLayout(norm_secondary_row)
        norm_outputs_label = QLabel(
            "Sorties du bloc 2: fichiers CLEAN, segments et index DB (selon l'action lancée)."
        )
        norm_outputs_label.setStyleSheet("color: #666; font-size: 0.9em;")
        norm_outputs_label.setWordWrap(True)
        norm_layout.addWidget(norm_outputs_label)
        layout.addWidget(self.group_norm)

        self.group_recovery = QGroupBox("3. Reprise — Erreurs")
        self.group_recovery.setToolTip(
            "Liste les épisodes en statut ERROR, permet une relance ciblée et l'ouverture directe dans l'Inspecteur."
        )
        recovery_layout = QVBoxLayout(self.group_recovery)
        recovery_layout.setContentsMargins(8, 8, 8, 8)
        recovery_layout.setSpacing(6)
        self.error_summary_label = QLabel("Épisodes en erreur: 0")
        recovery_layout.addWidget(self.error_summary_label)
        self.error_list = QListWidget()
        self.error_list.setMaximumHeight(110)
        self.error_list.currentRowChanged.connect(self._on_error_selection_changed)
        recovery_layout.addWidget(self.error_list)
        recovery_btn_row = QHBoxLayout()
        recovery_btn_row.setContentsMargins(0, 0, 0, 0)
        recovery_btn_row.setSpacing(6)
        self.retry_selected_error_btn = QPushButton("Relancer épisode")
        self.retry_selected_error_btn.setMinimumHeight(28)
        self.retry_selected_error_btn.setToolTip("Relance l'épisode sélectionné (workflow complet).")
        self.retry_selected_error_btn.clicked.connect(self._retry_selected_error_episode)
        self.retry_selected_error_btn.setEnabled(False)
        self.retry_all_errors_btn = QPushButton("Relancer toutes les erreurs")
        self.retry_all_errors_btn.setMinimumHeight(28)
        self.retry_all_errors_btn.setToolTip("Relance tous les épisodes actuellement en erreur.")
        self.retry_all_errors_btn.clicked.connect(self._retry_error_episodes)
        self.retry_all_errors_btn.setEnabled(False)
        self.inspect_error_btn = QPushButton("Ouvrir dans Inspecteur")
        self.inspect_error_btn.setMinimumHeight(28)
        self.inspect_error_btn.setToolTip("Ouvre l'épisode sélectionné dans l'Inspecteur pour diagnostic.")
        self.inspect_error_btn.clicked.connect(self._open_selected_error_in_inspector)
        self.inspect_error_btn.setEnabled(False)
        self.logs_error_btn = QPushButton("Ouvrir logs épisode")
        self.logs_error_btn.setMinimumHeight(28)
        self.logs_error_btn.setToolTip(
            "Ouvre le panneau Logs et filtre automatiquement sur l'épisode sélectionné."
        )
        self.logs_error_btn.clicked.connect(self._open_selected_error_in_logs)
        self.logs_error_btn.setEnabled(False)
        self.refresh_errors_btn = QPushButton("Rafraîchir liste")
        self.refresh_errors_btn.setMinimumHeight(28)
        self.refresh_errors_btn.clicked.connect(self._refresh_error_panel_from_ui)
        recovery_btn_row.addWidget(self.retry_selected_error_btn)
        recovery_btn_row.addWidget(self.retry_all_errors_btn)
        recovery_btn_row.addWidget(self.inspect_error_btn)
        recovery_btn_row.addWidget(self.logs_error_btn)
        recovery_btn_row.addWidget(self.refresh_errors_btn)
        recovery_btn_row.addStretch()
        recovery_layout.addLayout(recovery_btn_row)
        recovery_hint = QLabel("Astuce: pour les détails d'erreur complets, ouvrez le Journal d'exécution (menu Outils).")
        recovery_hint.setStyleSheet("color: gray; font-size: 0.9em;")
        recovery_hint.setWordWrap(True)
        recovery_layout.addWidget(recovery_hint)
        layout.addWidget(self.group_recovery)

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
        self.acquisition_runtime_label = QLabel("")
        self.acquisition_runtime_label.setStyleSheet("color: #505050; font-size: 0.9em;")
        self.acquisition_runtime_label.setWordWrap(True)
        self.acquisition_runtime_label.setToolTip(
            "Paramètres d'acquisition HTTP effectivement appliqués au dernier job."
        )
        layout.addWidget(self.acquisition_runtime_label)
        scope_label = QLabel(
            "§14 — Bloc 1 (Import) : découverte, téléchargement, SRT (panneau Sous-titres dans Inspecteur). "
            "Bloc 2 (Normalisation / segmentation) : profil batch, Normaliser, Indexer DB. "
            "Périmètre via « Scope action » : épisode courant, sélection, saison filtrée ou tout le corpus. "
            "Option « Forcer re-traitement » : rejoue les étapes même si des artefacts existent."
        )
        scope_label.setStyleSheet("color: gray; font-size: 0.9em;")
        scope_label.setWordWrap(True)
        layout.addWidget(scope_label)
        self._restore_force_reprocess_state()
        self._update_episodes_empty_state()
        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)
        self._configure_tab_order()

    def _configure_tab_order(self) -> None:
        """Ordre clavier explicite pour les actions principales du corpus."""
        chain = [
            self.season_filter_combo,
            self.status_filter_combo,
            self.check_season_btn,
            self.batch_scope_combo,
            self.primary_action_btn,
            self.episodes_tree,
            self.discover_btn,
            self.fetch_btn,
            self.check_all_btn,
            self.uncheck_all_btn,
            self.add_episodes_btn,
            self.discover_merge_btn,
            self.norm_batch_profile_combo,
            self.force_reprocess_check,
            self.norm_btn,
            self.segment_btn,
            self.index_btn,
            self.all_in_one_btn,
            self.export_corpus_btn,
            self.cancel_job_btn,
            self.error_list,
            self.retry_selected_error_btn,
            self.retry_all_errors_btn,
            self.inspect_error_btn,
            self.logs_error_btn,
            self.refresh_errors_btn,
        ]
        for current, nxt in zip(chain, chain[1:]):
            self.setTabOrder(current, nxt)

    def first_focus_widget(self) -> QWidget:
        """Point d'entrée focus (Pilotage)."""
        return self.season_filter_combo

    def last_focus_widget(self) -> QWidget:
        """Point de sortie focus (Pilotage)."""
        return self.refresh_errors_btn

    def take_right_column_sections(self) -> list[QWidget]:
        """Détache les blocs secondaires pour les réutiliser dans la colonne droite du Pilotage."""
        sections = [self.group_norm, self.group_recovery]
        if self._sidebar_sections_detached:
            return sections
        parent_layout = getattr(self, "_content_layout", None)
        if parent_layout is not None:
            for widget in sections:
                parent_layout.removeWidget(widget)
                widget.setParent(None)
        self._sidebar_sections_detached = True
        return sections

    def _save_force_reprocess_state(self, checked: bool) -> None:
        settings = QSettings()
        settings.setValue(_CORPUS_FORCE_REPROCESS_KEY, bool(checked))

    def _restore_force_reprocess_state(self) -> None:
        settings = QSettings()
        checked = bool(settings.value(_CORPUS_FORCE_REPROCESS_KEY, False))
        self.force_reprocess_check.setChecked(checked)

    def set_progress(self, value: int) -> None:
        self.corpus_progress.setValue(value)

    def set_acquisition_runtime_info(self, text: str) -> None:
        """Affiche un diagnostic runtime des options d'acquisition (profil/rate-limit/timeout/retry)."""
        self.acquisition_runtime_label.setText(text or "")

    def set_cancel_btn_enabled(self, enabled: bool) -> None:
        self.cancel_job_btn.setEnabled(enabled)

    def _set_scope_action_buttons_enabled(
        self,
        *,
        fetch: bool,
        normalize: bool,
        segment: bool,
        run_all: bool,
        index: bool,
    ) -> None:
        self.fetch_btn.setEnabled(fetch)
        self.norm_btn.setEnabled(normalize)
        self.segment_btn.setEnabled(segment)
        self.all_in_one_btn.setEnabled(run_all)
        self.index_btn.setEnabled(index)

    def _set_scope_action_tooltips(
        self,
        *,
        fetch_reason: str | None,
        normalize_reason: str | None,
        segment_reason: str | None,
        run_all_reason: str | None,
        index_reason: str | None,
    ) -> None:
        self.fetch_btn.setToolTip(fetch_reason or self._fetch_btn_tooltip_default)
        self.norm_btn.setToolTip(normalize_reason or self._norm_btn_tooltip_default)
        self.segment_btn.setToolTip(segment_reason or self._segment_btn_tooltip_default)
        self.all_in_one_btn.setToolTip(run_all_reason or self._all_in_one_btn_tooltip_default)
        self.index_btn.setToolTip(index_reason or self._index_btn_tooltip_default)

    def _set_scope_actions_unavailable(self, reason: str) -> None:
        self._set_scope_action_buttons_enabled(
            fetch=False,
            normalize=False,
            segment=False,
            run_all=False,
            index=False,
        )
        self._set_scope_action_tooltips(
            fetch_reason=reason,
            normalize_reason=reason,
            segment_reason=reason,
            run_all_reason=reason,
            index_reason=reason,
        )

    def set_workflow_busy(self, busy: bool) -> None:
        """Active/désactive les contrôles de pilotage pendant l'exécution d'un job."""
        self._workflow_busy = busy
        enabled = not busy
        controls = (
            self.season_filter_combo,
            self.status_filter_combo,
            self.check_season_btn,
            self.batch_scope_combo,
            self.check_all_btn,
            self.uncheck_all_btn,
            self.discover_btn,
            self.add_episodes_btn,
            self.discover_merge_btn,
            self.fetch_btn,
            self.norm_batch_profile_combo,
            self.force_reprocess_check,
            self.norm_btn,
            self.segment_btn,
            self.all_in_one_btn,
            self.index_btn,
            self.export_corpus_btn,
            self.retry_selected_error_btn,
            self.retry_all_errors_btn,
            self.inspect_error_btn,
            self.logs_error_btn,
            self.refresh_errors_btn,
            self.primary_action_btn,
        )
        for widget in controls:
            widget.setEnabled(enabled)
        self.cancel_job_btn.setEnabled(busy)
        if not busy:
            self._refresh_scope_action_states(self._cached_index)

    def _emit_cancel_job(self) -> None:
        self._on_cancel_job()

    def _run_job_with_force(self, steps: list[Any], *, force: bool | None = None) -> None:
        """Exécute le job en propageant le mode force si le callback le supporte."""
        force_flag = self.force_reprocess_check.isChecked() if force is None else bool(force)
        try:
            self._run_job(steps, force=force_flag)
        except TypeError:
            self._run_job(steps)

    def _set_primary_action(self, label: str, action: Callable[[], None] | None) -> None:
        self.primary_action_btn.setText(label)
        self._primary_action = action
        self.primary_action_btn.setEnabled(action is not None)
        if action is None:
            self.primary_action_btn.setToolTip(
                "Aucune action recommandée disponible pour l'état courant."
            )
        else:
            self.primary_action_btn.setToolTip(
                "Exécute l'action suggérée selon l'état actuel du workflow."
            )

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

    def _apply_empty_corpus_state(
        self,
        *,
        next_step_message: str,
        primary_label: str,
        primary_action: Callable[[], None] | None,
    ) -> None:
        self._cached_index = None
        self._episode_scope_capabilities = {}
        self.episodes_tree_model.set_store(None)
        self.episodes_tree_model.set_db(None)
        self.episodes_tree_model.set_episodes([])
        self.season_filter_combo.clear()
        self.season_filter_combo.addItem("Toutes les saisons", None)
        self.corpus_status_label.setText("")
        self.corpus_next_step_label.setText(next_step_message)
        self.acquisition_runtime_label.setText("")
        self._set_scope_action_buttons_enabled(
            fetch=False,
            normalize=False,
            segment=False,
            run_all=False,
            index=False,
        )
        self._set_scope_action_tooltips(
            fetch_reason="Action indisponible: initialisez d'abord le corpus.",
            normalize_reason="Action indisponible: initialisez d'abord le corpus.",
            segment_reason="Action indisponible: initialisez d'abord le corpus.",
            run_all_reason="Action indisponible: initialisez d'abord le corpus.",
            index_reason="Action indisponible: initialisez d'abord le corpus.",
        )
        self._refresh_error_panel(index=None, error_ids=[])
        self._set_primary_action(primary_label, primary_action)
        self._refresh_scope_preview(index=None)
        self._update_episodes_empty_state()

    def _apply_workflow_advice(self, action_id: str, label: str) -> None:
        if action_id == "retry_errors":
            self._set_primary_action(label, self._retry_error_episodes)
            return
        if action_id == "open_concordance_cues":
            if self._on_open_concordance:
                self._set_primary_action(label, self._open_concordance_tab)
            else:
                self._set_primary_action("Concordance (Cues)", None)
            return
        scope_actions: dict[str, Callable[[str | None], None]] = {
            "fetch_all": self._fetch_episodes,
            "normalize_all": self._normalize_episodes,
            "segment_and_index": self._segment_and_index_scope,
            "index_all": self._index_db,
        }
        scoped_action = scope_actions.get(action_id)
        if scoped_action is not None:
            self._set_primary_action(
                label,
                lambda: self._run_action_with_scope("all", scoped_action),
            )
            return
        if action_id == "open_inspector_srt":
            if self._on_open_inspector:
                self._set_primary_action(label, self._open_selected_or_first_episode_in_inspector)
            else:
                self._set_primary_action("Importer SRT (Inspecteur)", None)
            return
        if action_id == "open_validation_alignment":
            if self._on_open_alignment:
                self._set_primary_action(label, self._open_alignment_tab)
            else:
                self._set_primary_action("Passer à Validation", None)
            return
        self._set_primary_action(label, None)

    def refresh(self) -> None:
        """Recharge l'arbre et le statut depuis le store (appelé après ouverture projet / fin de job)."""
        store = self._get_store()
        db = self._get_db()
        if not store:
            self._apply_empty_corpus_state(
                next_step_message="Prochaine action: ouvrez ou créez un projet dans la section Projet (Pilotage).",
                primary_label="Ouvrez un projet",
                primary_action=None,
            )
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            self._apply_empty_corpus_state(
                next_step_message=(
                    "Prochaine action: cliquez sur « Découvrir épisodes » "
                    "(ou ajoutez des épisodes en mode SRT only)."
                ),
                primary_label="Découvrir épisodes",
                primary_action=self._discover_episodes,
            )
            return
        self._cached_index = index
        self._episode_scope_capabilities = build_episode_scope_capabilities(
            index=index,
            has_episode_raw=store.has_episode_raw,
            has_episode_clean=store.has_episode_clean,
            log=logger,
        )
        counts, error_ids, advice = self._workflow_controller.resolve_workflow_snapshot(
            index=index,
            store=store,
            db=db,
        )
        self.corpus_status_label.setText(
            self._workflow_controller.build_workflow_status_line(counts)
        )
        self.corpus_next_step_label.setText(advice.message)
        self._apply_workflow_advice(advice.action_id, advice.label)
        default_enabled = self._workflow_controller.resolve_default_scope_action_enabled_from_counts(counts)
        self._set_scope_action_buttons_enabled(
            fetch=default_enabled["fetch"],
            normalize=default_enabled["normalize"],
            segment=default_enabled["segment"],
            run_all=default_enabled["run_all"],
            index=default_enabled["index"],
        )
        self._refresh_error_panel(index=index, error_ids=error_ids)
        # Mise à jour de l'arbre : synchrone (refresh est déjà appelé après OK, pas au même moment que la boîte de dialogue)
        # Pas d'expandAll() : provoque segfault sur macOS ; déplier à la main (flèche à gauche de « Saison N »)
        self.episodes_tree_model.set_store(store)
        self.episodes_tree_model.set_db(db)
        self.episodes_tree_model.set_episodes(index.episodes)
        self._refresh_season_filter_combo()
        self._refresh_scope_preview(index)
        self._refresh_scope_action_states(index)
        self._update_episodes_empty_state()
        if self._workflow_busy:
            self.set_workflow_busy(True)

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
        self._refresh_scope_preview_from_ui()

    def _check_all_episodes(self) -> None:
        self.episodes_tree_model.set_all_checked(True)
        self._refresh_scope_preview_from_ui()

    def _uncheck_all_episodes(self) -> None:
        self.episodes_tree_model.set_all_checked(False)
        self._refresh_scope_preview_from_ui()

    def _refresh_scope_preview_from_ui(self, *_args) -> None:
        self._refresh_scope_preview(self._cached_index)
        self._refresh_scope_action_states(self._cached_index)
        self._update_episodes_empty_state()

    def _update_episodes_empty_state(self, *_args) -> None:
        total = len(self._cached_index.episodes) if self._cached_index and self._cached_index.episodes else 0
        visible = int(self.episodes_tree_proxy.rowCount()) if self.episodes_tree_proxy else 0
        if total <= 0:
            self.episodes_empty_label.setText(
                "Aucun épisode dans le corpus. Cliquez sur « Découvrir épisodes » pour démarrer."
            )
            self.episodes_empty_label.setVisible(True)
            return
        if visible <= 0:
            self.episodes_empty_label.setText(
                "Aucun épisode visible avec les filtres actuels. Ajustez Saison/Statut."
            )
            self.episodes_empty_label.setVisible(True)
            return
        self.episodes_empty_label.setVisible(False)

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

    def _open_concordance_tab(self) -> None:
        if self._on_open_concordance:
            self._on_open_concordance()

    def _on_check_season_clicked(self) -> None:
        season = self.season_filter_combo.currentData()
        ids = self.episodes_tree_model.get_episode_ids_for_season(season)
        if not ids:
            return
        self.episodes_tree_model.set_checked(set(ids), True)
        self._refresh_scope_preview_from_ui()

    def _discover_episodes(self) -> None:
        resolved = self._workflow_controller.resolve_project_context_or_warn(
            store=self._get_store(),
            db=self._get_db(),
            context=self._get_context(),
            require_db=True,
        )
        if resolved is None:
            return
        _store, _db, context = resolved
        self._run_job_with_force(
            self._workflow_controller.build_discover_series_steps(context=context),
            force=False,
        )

    def _discover_merge(self) -> None:
        resolved = self._workflow_controller.resolve_project_context_or_warn(
            store=self._get_store(),
            db=self._get_db(),
            context=self._get_context(),
            require_db=True,
        )
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
        steps = self._workflow_controller.build_discover_merge_steps_or_warn(
            context=context,
            series_url=url_edit.text(),
            source_id=source_combo.currentText(),
        )
        if steps is None:
            return
        self._run_job_with_force(steps, force=False)

    def _add_episodes_manually(self) -> None:
        resolved = self._workflow_controller.resolve_project_context_or_warn(
            store=self._get_store(),
            db=self._get_db(),
            context=self._get_context(),
            require_db=False,
        )
        if resolved is None:
            return
        store, _db, _context = resolved
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
        parsed = self._workflow_controller.resolve_manual_episode_refs_or_warn(
            raw_text=text_edit.toPlainText(),
        )
        if parsed is None:
            return
        new_refs, invalid_count = parsed
        merged = self._workflow_controller.merge_manual_episode_refs_or_warn(
            index=store.load_series_index(),
            new_refs=new_refs,
        )
        if merged is None:
            return
        merged_index, added_count, skipped_existing = merged
        store.save_series_index(merged_index)
        self.refresh()
        self._refresh_after_episodes_added()
        self._show_status(
            self._workflow_controller.build_manual_add_status_message(
                added_count=added_count,
                skipped_existing=skipped_existing,
                invalid_count=invalid_count,
            ),
            5000,
        )

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

    def _warn_corpus_precondition(self, message: str, next_step: str | None = None) -> None:
        warn_precondition(self, "Corpus", message, next_step=next_step)

    def _get_episode_scope_capabilities(
        self,
        *,
        index: SeriesIndex,
        store: Any,
    ) -> dict[str, tuple[bool, bool, bool, bool]]:
        self._episode_scope_capabilities = resolve_episode_scope_capabilities_cache(
            cache=self._episode_scope_capabilities,
            index=index,
            has_episode_raw=store.has_episode_raw,
            has_episode_clean=store.has_episode_clean,
            log=logger,
        )
        return self._episode_scope_capabilities

    def _resolve_scope_ids_silent(
        self,
        index: SeriesIndex,
        *,
        scope_mode: str | None = None,
    ) -> list[str]:
        mode = normalize_scope_mode(scope_mode or self.batch_scope_combo.currentData())
        return resolve_scope_ids(
            scope_mode=mode,
            all_episode_ids=[e.episode_id for e in index.episodes],
            current_episode_id=self._resolve_current_episode_id(),
            selected_episode_ids=self._resolve_selected_episode_ids(),
            season=self.season_filter_combo.currentData(),
            get_episode_ids_for_season=self.episodes_tree_model.get_episode_ids_for_season,
        )

    def _refresh_scope_action_states(self, index: SeriesIndex | None) -> None:
        if self._workflow_busy:
            return
        store = self._get_store()
        has_index = bool(index and index.episodes)
        ids = self._resolve_scope_ids_silent(index) if has_index else []
        capabilities = self._get_episode_scope_capabilities(index=index, store=store) if (has_index and store) else {}
        enabled, reasons, unavailable_reason = self._workflow_controller.resolve_scope_action_ui_state(
            has_index=has_index,
            has_store=bool(store),
            ids=ids,
            capabilities=capabilities,
        )
        if unavailable_reason is not None:
            self._set_scope_actions_unavailable(unavailable_reason)
            return
        self._set_scope_action_buttons_enabled(
            fetch=enabled["fetch"],
            normalize=enabled["normalize"],
            segment=enabled["segment"],
            run_all=enabled["run_all"],
            index=enabled["index"],
        )
        self._set_scope_action_tooltips(
            fetch_reason=reasons["fetch"],
            normalize_reason=reasons["normalize"],
            segment_reason=reasons["segment"],
            run_all_reason=reasons["run_all"],
            index_reason=reasons["index"],
        )

    @staticmethod
    def _resolve_lang_hint(context: dict[str, Any]) -> str:
        config = context.get("config")
        profile_id = getattr(config, "normalize_profile", None) if config else None
        return resolve_lang_hint_from_profile_id(profile_id, fallback="en")

    def _resolve_scope_context(
        self,
        *,
        scope_mode: str | None = None,
        require_db: bool = False,
    ) -> tuple[Any, Any, dict[str, Any], SeriesIndex, WorkflowScope, list[str]] | None:
        store = self._get_store()
        db = self._get_db()
        context = self._get_context()
        index = store.load_series_index() if store else None
        return self._workflow_controller.resolve_scope_context_or_warn(
            store=store,
            db=db,
            context=context,
            index=index,
            require_db=require_db,
            scope_mode=scope_mode or self.batch_scope_combo.currentData(),
            all_episode_ids=[e.episode_id for e in index.episodes] if index and index.episodes else [],
            current_episode_id=self._resolve_current_episode_id(),
            selected_episode_ids=self._resolve_selected_episode_ids(),
            season=self.season_filter_combo.currentData(),
            get_episode_ids_for_season=self.episodes_tree_model.get_episode_ids_for_season,
        )

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
        self.logs_error_btn.setEnabled(has_selection and self._on_open_logs_for_episode is not None)
        self.retry_all_errors_btn.setEnabled(self.error_list.count() > 0)

    def _refresh_error_panel(
        self,
        *,
        index: SeriesIndex | None,
        error_ids: list[str] | None = None,
    ) -> None:
        previous = self._selected_error_episode_id()
        if error_ids is None:
            error_ids = self._workflow_controller.resolve_error_episode_ids_from_index(
                index=index,
                db=self._get_db(),
            )
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

    def _fetch_episodes(self, scope_mode: str | None = None) -> None:
        resolved = self._resolve_scope_context(scope_mode=scope_mode, require_db=True)
        if resolved is None:
            return
        _store, _db, context, index, _scope, ids = resolved
        skipped_message = self._workflow_controller.run_fetch_scope_or_warn(
            ids=ids,
            index=index,
            context=context,
            empty_message="Aucun épisode à télécharger.",
            empty_next_step="Vérifiez que les épisodes du scope ont une URL source valide.",
        )
        if skipped_message:
            self._show_status(skipped_message, 4000)

    def _normalize_episodes(self, scope_mode: str | None = None) -> None:
        resolved = self._resolve_scope_context(scope_mode=scope_mode)
        if resolved is None:
            return
        store, _db, context, index, _scope, ids = resolved
        skipped_message = self._workflow_controller.run_normalize_scope_or_warn(
            ids=ids,
            index=index,
            store=store,
            context=context,
            batch_profile=self.norm_batch_profile_combo.currentText() or "default_en_v1",
            empty_message="Aucun épisode à normaliser.",
            empty_next_step="Téléchargez d'abord des transcripts RAW pour ce scope.",
        )
        if skipped_message:
            self._show_status(skipped_message, 4000)

    def _segment_episodes(self, scope_mode: str | None = None) -> None:
        """Bloc 2 — Segmente les épisodes du scope sélectionné ayant clean.txt."""
        resolved = self._resolve_scope_context(scope_mode=scope_mode)
        if resolved is None:
            return
        store, _db, context, index, _scope, ids = resolved
        skipped_message = self._workflow_controller.run_segment_scope_or_warn(
            ids=ids,
            index=index,
            store=store,
            context=context,
            lang_hint=self._resolve_lang_hint(context),
            clean_empty_message="Aucun épisode du scope choisi n'a de fichier CLEAN. Normalisez d'abord ce scope.",
            clean_empty_next_step="Lancez « Normaliser » sur ce scope puis relancez la segmentation.",
            empty_message="Aucun épisode à segmenter.",
            empty_next_step="Normalisez d'abord les épisodes du scope pour produire des fichiers CLEAN.",
        )
        if skipped_message:
            self._show_status(skipped_message, 4000)

    def _run_all_for_scope(self) -> None:
        """§5 — Enchaînement : Télécharger → Normaliser → Segmenter → Indexer DB sur le scope choisi."""
        resolved = self._resolve_scope_context(require_db=True)
        if resolved is None:
            return
        store, _db, context, index, _scope, ids = resolved
        skipped_message = self._workflow_controller.run_full_workflow_scope_or_warn(
            ids=ids,
            index=index,
            store=store,
            context=context,
            batch_profile=self.norm_batch_profile_combo.currentText() or "default_en_v1",
            lang_hint=self._resolve_lang_hint(context),
            empty_message="Aucune opération à exécuter.",
            empty_next_step="Ajustez le scope ou préparez des épisodes (URL/RAW/CLEAN) avant relance.",
        )
        if skipped_message:
            self._show_status(skipped_message, 4000)

    def _retry_selected_error_episode(self) -> None:
        context = self._get_context()
        skipped_message = self._workflow_controller.run_retry_selected_error_or_warn(
            store=self._get_store(),
            db=self._get_db(),
            context=context,
            selected_episode_id=self._selected_error_episode_id(),
            batch_profile=self.norm_batch_profile_combo.currentText() or "default_en_v1",
            lang_hint=self._resolve_lang_hint(context),
        )
        if skipped_message:
            self._show_status(skipped_message, 4000)

    def _retry_error_episodes(self) -> None:
        """Relance les épisodes en erreur avec un enchaînement complet."""
        context = self._get_context()
        skipped_message = self._workflow_controller.run_retry_all_errors_or_warn(
            store=self._get_store(),
            db=self._get_db(),
            context=context,
            batch_profile=self.norm_batch_profile_combo.currentText() or "default_en_v1",
            lang_hint=self._resolve_lang_hint(context),
        )
        if skipped_message:
            self._show_status(skipped_message, 4000)

    def _open_selected_error_in_inspector(self) -> None:
        if not self._on_open_inspector:
            return
        self._workflow_controller.run_selected_error_callback_or_warn(
            selected_episode_id=self._selected_error_episode_id(),
            callback=self._on_open_inspector,
            empty_message="Sélectionnez un épisode à ouvrir.",
            empty_next_step="Cliquez une ligne dans le panneau erreurs, puis réessayez.",
        )

    def _open_selected_error_in_logs(self) -> None:
        if not self._on_open_logs_for_episode:
            return
        self._workflow_controller.run_selected_error_callback_or_warn(
            selected_episode_id=self._selected_error_episode_id(),
            callback=self._on_open_logs_for_episode,
            empty_message="Sélectionnez un épisode à filtrer dans les logs.",
            empty_next_step="Cliquez une ligne dans le panneau erreurs, puis relancez.",
        )

    def _index_db(self, scope_mode: str | None = None) -> None:
        resolved = self._resolve_scope_context(scope_mode=scope_mode, require_db=True)
        if resolved is None:
            return
        store, _db, context, index, _scope, ids = resolved
        skipped_message = self._workflow_controller.run_index_scope_or_warn(
            ids=ids,
            index=index,
            store=store,
            context=context,
            clean_empty_message="Aucun épisode CLEAN à indexer pour ce scope.",
            clean_empty_next_step="Lancez « Normaliser » sur ce scope puis réessayez.",
            empty_message="Aucun épisode CLEAN à indexer pour ce scope.",
            empty_next_step="Vérifiez que le scope contient des épisodes normalisés (CLEAN).",
        )
        if skipped_message:
            self._show_status(skipped_message, 4000)

    def _segment_and_index_scope(self, scope_mode: str | None = None) -> None:
        """Chaîne segmenter puis indexer pour les épisodes CLEAN du scope choisi."""
        resolved = self._resolve_scope_context(scope_mode=scope_mode, require_db=True)
        if resolved is None:
            return
        store, _db, context, index, _scope, ids = resolved
        skipped_message = self._workflow_controller.run_segment_and_index_scope_or_warn(
            ids=ids,
            index=index,
            store=store,
            context=context,
            lang_hint=self._resolve_lang_hint(context),
            clean_empty_message="Aucun épisode CLEAN à segmenter/indexer pour ce scope.",
            clean_empty_next_step="Lancez « Normaliser » sur ce scope puis réessayez.",
            empty_message="Aucune opération à exécuter.",
            empty_next_step="Préparez d'abord des épisodes CLEAN dans le scope courant.",
        )
        if skipped_message:
            self._show_status(skipped_message, 4000)

    def _export_corpus(self) -> None:
        store = self._get_store()
        episodes_data = self._workflow_controller.resolve_clean_episodes_for_export_or_warn(
            store=store,
        )
        if not episodes_data:
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
        try:
            output_path = self._workflow_controller.export_episodes_data_or_warn(
                episodes_data=episodes_data,
                path=Path(path),
                selected_filter=selected_filter or "",
            )
            if output_path is None:
                return
            show_info(
                self,
                "Export",
                build_export_success_message(
                    subject="Corpus exporté",
                    count=len(episodes_data),
                    count_label="épisode(s)",
                    path=output_path,
                ),
                status_callback=self._show_status,
            )
        except Exception as e:
            logger.exception("Export corpus")
            show_error(self, exc=e, context="Export corpus")
