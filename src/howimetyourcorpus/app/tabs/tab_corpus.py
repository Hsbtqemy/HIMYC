"""Onglet Corpus : arbre épisodes, filtre saison, workflow (découvrir, télécharger, normaliser, indexer, exporter)."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QModelIndex, Qt
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
from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex
from howimetyourcorpus.core.normalize.profiles import PROFILES
from howimetyourcorpus.core.pipeline.tasks import (
    FetchSeriesIndexStep,
    FetchAndMergeSeriesIndexStep,
    FetchEpisodeStep,
    NormalizeEpisodeStep,
    SegmentEpisodeStep,
    BuildDbIndexStep,
)
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

        layout = QVBoxLayout(self)
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
        layout.addWidget(self.episodes_tree)

        # Bloc 1 — Import (constitution du corpus) §14
        group_import = QGroupBox("1. Import — Constitution du corpus")
        group_import.setToolTip(
            "Workflow §14 : Découvrir les épisodes, télécharger les transcripts (RAW), importer les SRT (onglet Sous-titres). "
            "Pas de normalisation ni d'alignement ici."
        )
        btn_row1 = QHBoxLayout()
        self.check_all_btn = QPushButton("Tout cocher")
        self.check_all_btn.clicked.connect(lambda: self.episodes_tree_model.set_all_checked(True))
        self.uncheck_all_btn = QPushButton("Tout décocher")
        self.uncheck_all_btn.clicked.connect(lambda: self.episodes_tree_model.set_all_checked(False))
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
        self.fetch_sel_btn = QPushButton("Télécharger\nsélection")
        self.fetch_sel_btn.setToolTip("Télécharge les épisodes cochés (ou les lignes sélectionnées au clic).")
        self.fetch_sel_btn.clicked.connect(lambda: self._fetch_episodes(selection_only=True))
        self.fetch_all_btn = QPushButton("Télécharger tout")
        self.fetch_all_btn.setToolTip("Télécharge tout le corpus (tous les épisodes découverts).")
        self.fetch_all_btn.clicked.connect(lambda: self._fetch_episodes(selection_only=False))
        for b in (self.discover_btn, self.add_episodes_btn, self.discover_merge_btn, self.fetch_sel_btn, self.fetch_all_btn):
            btn_row1.addWidget(b)
        btn_row1.addStretch()
        group_import.setLayout(btn_row1)
        layout.addWidget(group_import)

        # Bloc 2 — Normalisation / segmentation (après import) §14
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
        self.segment_all_btn.setToolTip(
            "Bloc 2 — Segmente tout le corpus (épisodes ayant CLEAN)."
        )
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
        for b in (self.norm_sel_btn, self.norm_all_btn, self.segment_sel_btn, self.segment_all_btn, self.all_in_one_btn, self.index_btn, self.export_corpus_btn):
            btn_row2.addWidget(b)
        btn_row2.addWidget(self.cancel_job_btn)
        btn_row2.addStretch()
        group_norm.setLayout(btn_row2)
        layout.addWidget(group_norm)

        self.corpus_progress = QProgressBar()
        self.corpus_progress.setMaximum(100)
        self.corpus_progress.setValue(0)
        layout.addWidget(self.corpus_progress)
        self.corpus_status_label = QLabel("")
        self.corpus_status_label.setToolTip(
            "Workflow §14 (3 blocs) : Bloc 1 = Découverts → Téléchargés → SRT (import). "
            "Bloc 2 = Normalisés (CLEAN) → Segmentés (DB). Bloc 3 = Alignés (onglets Alignement, Concordance, Personnages)."
        )
        layout.addWidget(self.corpus_status_label)
        scope_label = QLabel(
            "§14 — Bloc 1 (Import) : découverte, téléchargement, SRT (onglet Sous-titres). "
            "Bloc 2 (Normalisation / segmentation) : profil batch, Normaliser, Indexer DB. "
            "Périmètre : « sélection » = épisodes cochés ou lignes sélectionnées ; « tout » = tout le corpus."
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

    def refresh(self) -> None:
        """Recharge l'arbre et le statut depuis le store (appelé après ouverture projet / fin de job)."""
        store = self._get_store()
        db = self._get_db()
        if not store:
            self.season_filter_combo.clear()
            self.season_filter_combo.addItem("Toutes les saisons", None)
            self.corpus_status_label.setText("")
            self.norm_sel_btn.setEnabled(False)
            self.norm_all_btn.setEnabled(False)
            self.segment_sel_btn.setEnabled(False)
            self.segment_all_btn.setEnabled(False)
            self.all_in_one_btn.setEnabled(False)
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            self.season_filter_combo.clear()
            self.season_filter_combo.addItem("Toutes les saisons", None)
            self.corpus_status_label.setText("")
            self.norm_sel_btn.setEnabled(False)
            self.norm_all_btn.setEnabled(False)
            self.segment_sel_btn.setEnabled(False)
            self.segment_all_btn.setEnabled(False)
            self.all_in_one_btn.setEnabled(False)
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
        self.corpus_status_label.setText(
            f"Workflow : Découverts {n_total} | Téléchargés {n_fetched} | Normalisés {n_norm} | Segmentés {n_indexed} | SRT {n_with_srt} | Alignés {n_aligned}"
        )
        self.norm_sel_btn.setEnabled(n_fetched > 0)
        self.norm_all_btn.setEnabled(n_fetched > 0)
        self.segment_sel_btn.setEnabled(n_norm > 0)
        self.segment_all_btn.setEnabled(n_norm > 0)
        self.all_in_one_btn.setEnabled(n_total > 0)
        # Mise à jour de l'arbre : synchrone (refresh est déjà appelé après OK, pas au même moment que la boîte de dialogue)
        # Pas d'expandAll() : provoque segfault sur macOS ; déplier à la main (flèche à gauche de « Saison N »)
        self.episodes_tree_model.set_store(store)
        self.episodes_tree_model.set_db(db)
        self.episodes_tree_model.set_episodes(index.episodes)
        self._refresh_season_filter_combo()

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
            except (ValueError, AttributeError):
                pass

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

    def _discover_episodes(self) -> None:
        context = self._get_context()
        if not context.get("config") or not context.get("store") or not context.get("db"):
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        config = context["config"]
        step = FetchSeriesIndexStep(config.series_url, config.user_agent)
        self._run_job([step])

    def _discover_merge(self) -> None:
        context = self._get_context()
        if not context.get("config") or not context.get("store") or not context.get("db"):
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
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

    def _fetch_episodes(self, selection_only: bool) -> None:
        store = self._get_store()
        db = self._get_db()
        context = self._get_context()
        if not context.get("config") or not store or not db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        if selection_only:
            ids = self.episodes_tree_model.get_checked_episode_ids()
            if not ids:
                proxy_indices = self.episodes_tree.selectionModel().selectedIndexes()
                source_indices = [
                    self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices
                ]
                ids = self.episodes_tree_model.get_episode_ids_selection(source_indices)
            if not ids:
                QMessageBox.warning(
                    self, "Corpus", "Cochez au moins un épisode ou sélectionnez des lignes."
                )
                return
        else:
            ids = [e.episode_id for e in index.episodes]
        steps = [
            FetchEpisodeStep(ref.episode_id, ref.url)
            for ref in index.episodes
            if ref.episode_id in ids
        ]
        if not steps:
            return
        self._run_job(steps)

    def _normalize_episodes(self, selection_only: bool) -> None:
        store = self._get_store()
        context = self._get_context()
        if not context.get("config") or not store:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        if selection_only:
            ids = self.episodes_tree_model.get_checked_episode_ids()
            if not ids:
                proxy_indices = self.episodes_tree.selectionModel().selectedIndexes()
                source_indices = [
                    self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices
                ]
                ids = self.episodes_tree_model.get_episode_ids_selection(source_indices)
            if not ids:
                QMessageBox.warning(
                    self, "Corpus", "Cochez au moins un épisode ou sélectionnez des lignes."
                )
                return
        else:
            ids = [e.episode_id for e in index.episodes]
        ref_by_id = {e.episode_id: e for e in index.episodes}
        episode_preferred = store.load_episode_preferred_profiles()
        source_defaults = store.load_source_profile_defaults()
        batch_profile = self.norm_batch_profile_combo.currentText() or "default_en_v1"
        steps = []
        for eid in ids:
            ref = ref_by_id.get(eid)
            profile = (
                episode_preferred.get(eid)
                or (source_defaults.get(ref.source_id or "") if ref else None)
                or batch_profile
            )
            steps.append(NormalizeEpisodeStep(eid, profile))
        self._run_job(steps)

    def _segment_episodes(self, selection_only: bool) -> None:
        """Bloc 2 — Segmente les épisodes (sélection ou tout) ayant clean.txt."""
        store = self._get_store()
        context = self._get_context()
        if not context.get("config") or not store:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        if selection_only:
            ids = self.episodes_tree_model.get_checked_episode_ids()
            if not ids:
                proxy_indices = self.episodes_tree.selectionModel().selectedIndexes()
                source_indices = [
                    self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices
                ]
                ids = self.episodes_tree_model.get_episode_ids_selection(source_indices)
            if not ids:
                QMessageBox.warning(
                    self, "Corpus", "Cochez au moins un épisode ou sélectionnez des lignes."
                )
                return
        else:
            ids = [e.episode_id for e in index.episodes]
        eids_with_clean = [eid for eid in ids if store.has_episode_clean(eid)]
        if not eids_with_clean:
            QMessageBox.warning(
                self, "Corpus",
                "Aucun épisode sélectionné n'a de fichier CLEAN. Normalisez d'abord la sélection."
            )
            return
        config = context.get("config")
        lang_hint = "en"
        if config and getattr(config, "normalize_profile", None):
            lang_hint = (config.normalize_profile or "default_en_v1").split("_")[0].replace("default", "en") or "en"
        steps = [SegmentEpisodeStep(eid, lang_hint=lang_hint) for eid in eids_with_clean]
        self._run_job(steps)

    def _run_all_for_selection(self) -> None:
        """§5 — Enchaînement : Télécharger → Normaliser → Segmenter → Indexer DB pour les épisodes cochés."""
        store = self._get_store()
        db = self._get_db()
        context = self._get_context()
        if not context.get("config") or not store or not db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        ids = self.episodes_tree_model.get_checked_episode_ids()
        if not ids:
            proxy_indices = self.episodes_tree.selectionModel().selectedIndexes()
            source_indices = [
                self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices
            ]
            ids = self.episodes_tree_model.get_episode_ids_selection(source_indices)
        if not ids:
            QMessageBox.warning(
                self, "Corpus", "Cochez au moins un épisode ou sélectionnez des lignes."
            )
            return
        ref_by_id = {e.episode_id: e for e in index.episodes}
        episode_preferred = store.load_episode_preferred_profiles()
        source_defaults = store.load_source_profile_defaults()
        batch_profile = self.norm_batch_profile_combo.currentText() or "default_en_v1"
        config = context.get("config")
        lang_hint = "en"
        if config and getattr(config, "normalize_profile", None):
            lang_hint = (config.normalize_profile or "default_en_v1").split("_")[0].replace("default", "en") or "en"
        fetch_steps = [
            FetchEpisodeStep(ref_by_id[eid].episode_id, ref_by_id[eid].url)
            for eid in ids if eid in ref_by_id
        ]
        norm_steps = []
        for eid in ids:
            ref = ref_by_id.get(eid)
            profile = (
                episode_preferred.get(eid)
                or (source_defaults.get(ref.source_id or "") if ref else None)
                or batch_profile
            )
            norm_steps.append(NormalizeEpisodeStep(eid, profile))
        segment_steps = [SegmentEpisodeStep(eid, lang_hint=lang_hint) for eid in ids]
        steps = fetch_steps + norm_steps + segment_steps + [BuildDbIndexStep()]
        self._run_job(steps)

    def _index_db(self) -> None:
        store = self._get_store()
        db = self._get_db()
        if not store or not db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        self._run_job([BuildDbIndexStep()])

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
        try:
            if path.suffix.lower() == ".txt" or selected_filter.startswith("TXT"):
                export_corpus_txt(episodes_data, path)
            elif "JSONL - Utterances" in selected_filter:
                export_corpus_utterances_jsonl(episodes_data, path)
            elif "JSONL - Phrases" in selected_filter:
                export_corpus_phrases_jsonl(episodes_data, path)
            elif "CSV - Utterances" in selected_filter:
                export_corpus_utterances_csv(episodes_data, path)
            elif "CSV - Phrases" in selected_filter:
                export_corpus_phrases_csv(episodes_data, path)
            elif path.suffix.lower() == ".csv" or selected_filter.startswith("CSV"):
                export_corpus_csv(episodes_data, path)
            elif path.suffix.lower() == ".json" or "JSON" in selected_filter:
                export_corpus_json(episodes_data, path)
            elif path.suffix.lower() == ".docx" or "Word" in selected_filter:
                export_corpus_docx(episodes_data, path)
            else:
                QMessageBox.warning(
                    self,
                    "Export",
                    "Format non reconnu. Utilisez .txt, .csv, .json ou .jsonl (segmenté).",
                )
                return
            QMessageBox.information(
                self, "Export", f"Corpus exporté : {len(episodes_data)} épisode(s)."
            )
        except Exception as e:
            logger.exception("Export corpus")
            QMessageBox.critical(self, "Erreur", str(e))
