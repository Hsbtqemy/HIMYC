"""Fenêtre principale : onglets Projet, Corpus, Inspecteur, Concordance, Logs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QTableView,
    QPlainTextEdit,
    QComboBox,
    QSpinBox,
    QProgressBar,
    QFormLayout,
    QMessageBox,
    QAbstractItemView,
    QHeaderView,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QMenu,
)
from PySide6.QtCore import Qt, QModelIndex, QPoint, QUrl
from PySide6.QtGui import QTextCursor, QAction
from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QDesktopServices

from howimetyourcorpus.core.adapters.base import AdapterRegistry
from howimetyourcorpus.core.models import ProjectConfig, EpisodeRef, SeriesIndex
from howimetyourcorpus.core.normalize.profiles import PROFILES
from howimetyourcorpus.core.pipeline.tasks import (
    FetchSeriesIndexStep,
    FetchEpisodeStep,
    NormalizeEpisodeStep,
    BuildDbIndexStep,
    SegmentEpisodeStep,
    ImportSubtitlesStep,
    AlignEpisodeStep,
)
from howimetyourcorpus.core.storage.project_store import ProjectStore
from howimetyourcorpus.core.storage.db import CorpusDB
from howimetyourcorpus.core.utils.logging import setup_logging, get_log_file_for_project
from howimetyourcorpus.core.export_utils import (
    export_corpus_txt,
    export_corpus_csv,
    export_corpus_json,
    export_corpus_docx,
    export_corpus_utterances_jsonl,
    export_corpus_utterances_csv,
    export_corpus_phrases_jsonl,
    export_corpus_phrases_csv,
    export_kwic_csv,
    export_kwic_json,
    export_kwic_tsv,
    export_kwic_jsonl,
    export_parallel_concordance_csv,
    export_parallel_concordance_tsv,
    export_parallel_concordance_jsonl,
    export_align_report_html,
)
from howimetyourcorpus.app.workers import JobRunner
from howimetyourcorpus.app.models_qt import EpisodesTableModel, KwicTableModel, AlignLinksTableModel
from howimetyourcorpus import __version__

logger = logging.getLogger(__name__)

# Index des onglets (éviter les entiers magiques)
TAB_PROJET = 0
TAB_CORPUS = 1
TAB_INSPECTEUR = 2
TAB_SOUS_TITRES = 3
TAB_ALIGNEMENT = 4
TAB_CONCORDANCE = 5
TAB_LOGS = 6


class TextEditHandler(logging.Handler):
    """Redirige les logs vers un QPlainTextEdit."""

    def __init__(self, widget: QPlainTextEdit):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        try:
            msg = self.format(record)
            self.widget.appendPlainText(msg)
        except Exception:
            logger.exception("TextEditHandler.emit")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HowIMetYourCorpus")
        self.resize(1000, 700)
        self._config: ProjectConfig | None = None
        self._store: ProjectStore | None = None
        self._db: CorpusDB | None = None
        self._job_runner: JobRunner | None = None
        self._log_handler: logging.Handler | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_menu_bar()
        self._build_tab_projet()
        self._build_tab_corpus()
        self._build_tab_inspecteur()
        self._build_tab_sous_titres()
        self._build_tab_alignement()
        self._build_tab_concordance()
        self._build_tab_logs()
        self.tabs.setCurrentIndex(TAB_PROJET)

    def _build_menu_bar(self):
        """Barre de menu : Aide > À propos, Vérifier les mises à jour (Phase 6)."""
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        aide = menu_bar.addMenu("&Aide")
        about_act = QAction("À propos", self)
        about_act.triggered.connect(self._show_about)
        aide.addAction(about_act)
        update_act = QAction("Vérifier les mises à jour", self)
        update_act.triggered.connect(self._open_releases_page)
        aide.addAction(update_act)

    def _show_about(self):
        """Affiche la boîte À propos (version, lien mises à jour)."""
        QMessageBox.about(
            self,
            "À propos",
            f"<b>HowIMetYourCorpus</b><br>Version {__version__}<br><br>"
            "Pipeline de corpus + exploration + QA — transcriptions et sous-titres.<br><br>"
            "Mises à jour : Aide → Vérifier les mises à jour.",
        )

    def _open_releases_page(self):
        """Ouvre la page des releases GitHub (mise à jour optionnelle Phase 6)."""
        QDesktopServices.openUrl(QUrl("https://github.com/Hsbtqemy/HIMYC/releases"))

    def _build_tab_projet(self):
        w = QWidget()
        layout = QFormLayout(w)
        self.proj_root_edit = QLineEdit()
        self.proj_root_edit.setPlaceholderText("C:\\...\\projects\\MonProjet")
        browse_btn = QPushButton("Parcourir...")
        browse_btn.clicked.connect(self._browse_project)
        row = QHBoxLayout()
        row.addWidget(self.proj_root_edit)
        row.addWidget(browse_btn)
        layout.addRow("Dossier projet:", row)

        self.source_id_combo = QComboBox()
        self.source_id_combo.addItems(AdapterRegistry.list_ids() or ["subslikescript"])
        layout.addRow("Source:", self.source_id_combo)

        self.series_url_edit = QLineEdit()
        self.series_url_edit.setPlaceholderText("https://subslikescript.com/series/...")
        layout.addRow("URL série:", self.series_url_edit)

        self.rate_limit_spin = QSpinBox()
        self.rate_limit_spin.setRange(1, 60)
        self.rate_limit_spin.setValue(2)
        self.rate_limit_spin.setSuffix(" s")
        layout.addRow("Rate limit:", self.rate_limit_spin)

        self.normalize_profile_combo = QComboBox()
        self.normalize_profile_combo.addItems(list(PROFILES.keys()))
        layout.addRow("Profil normalisation:", self.normalize_profile_combo)

        validate_btn = QPushButton("Valider & initialiser")
        validate_btn.clicked.connect(self._validate_and_init_project)
        layout.addRow("", validate_btn)

        self.tabs.addTab(w, "Projet")

    def _browse_project(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir le dossier projet")
        if d:
            self.proj_root_edit.setText(d)

    def _validate_and_init_project(self):
        root = self.proj_root_edit.text().strip()
        if not root:
            QMessageBox.warning(self, "Projet", "Indiquez un dossier projet.")
            return
        root_path = Path(root)
        config_toml = root_path / "config.toml"
        try:
            if config_toml.exists():
                self._load_existing_project(root_path)
                return
            source_id = self.source_id_combo.currentText() or "subslikescript"
            series_url = self.series_url_edit.text().strip()
            if not series_url:
                QMessageBox.warning(self, "Projet", "Indiquez l'URL de la série.")
                return
            rate_limit = self.rate_limit_spin.value()
            profile = self.normalize_profile_combo.currentText() or "default_en_v1"
            config = ProjectConfig(
                project_name=root_path.name,
                root_dir=root_path,
                source_id=source_id,
                series_url=series_url,
                rate_limit_s=float(rate_limit),
                user_agent="HowIMetYourCorpus/0.1 (research)",
                normalize_profile=profile,
            )
            ProjectStore.init_project(config)
            self._config = config
            self._store = ProjectStore(config.root_dir)
            self._db = CorpusDB(self._store.get_db_path())
            self._db.init()
            self._setup_logging_for_project()
        self._refresh_episodes_from_store()
        self._refresh_inspecteur_episodes()
        self._refresh_subs_tracks()
        self._refresh_align_runs()
        QMessageBox.information(self, "Projet", "Projet initialisé.")
        except Exception as e:
            logger.exception("Init project failed")
            QMessageBox.critical(self, "Erreur", str(e))

    def _load_existing_project(self, root_path: Path):
        """Charge un projet existant (config.toml présent)."""
        from howimetyourcorpus.core.storage.project_store import load_project_config
        data = load_project_config(root_path / "config.toml")
        config = ProjectConfig(
            project_name=data.get("project_name", root_path.name),
            root_dir=root_path,
            source_id=data.get("source_id", "subslikescript"),
            series_url=data.get("series_url", ""),
            rate_limit_s=float(data.get("rate_limit_s", 2)),
            user_agent=data.get("user_agent", "HowIMetYourCorpus/0.1 (research)"),
            normalize_profile=data.get("normalize_profile", "default_en_v1"),
        )
        self._config = config
        self._store = ProjectStore(config.root_dir)
        self._db = CorpusDB(self._store.get_db_path())
        if not self._db.db_path.exists():
            self._db.init()
        self._setup_logging_for_project()
        self.proj_root_edit.setText(str(root_path))
        self.series_url_edit.setText(config.series_url)
        self.normalize_profile_combo.setCurrentText(config.normalize_profile)
        self.rate_limit_spin.setValue(int(config.rate_limit_s))
        self.source_id_combo.setCurrentText(config.source_id)
        self._refresh_episodes_from_store()
        self._refresh_inspecteur_episodes()
        self._refresh_subs_tracks()
        self._refresh_align_runs()
        QMessageBox.information(self, "Projet", "Projet ouvert.")

    def _setup_logging_for_project(self):
        corpus_logger = logging.getLogger("howimetyourcorpus")
        if self._log_handler:
            corpus_logger.removeHandler(self._log_handler)
        if self._config:
            log_file = get_log_file_for_project(self._config.root_dir)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            corpus_logger.addHandler(file_handler)
            self._log_handler = file_handler

    def _build_tab_corpus(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.episodes_table = QTableView()
        self.episodes_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.episodes_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.episodes_model = EpisodesTableModel()
        self.episodes_table.setModel(self.episodes_model)
        self.episodes_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.episodes_table)

        btn_row = QHBoxLayout()
        self.discover_btn = QPushButton("Découvrir épisodes")
        self.discover_btn.clicked.connect(self._discover_episodes)
        self.fetch_sel_btn = QPushButton("Télécharger sélection")
        self.fetch_sel_btn.clicked.connect(lambda: self._fetch_episodes(selection_only=True))
        self.fetch_all_btn = QPushButton("Télécharger tout")
        self.fetch_all_btn.clicked.connect(lambda: self._fetch_episodes(selection_only=False))
        self.norm_sel_btn = QPushButton("Normaliser sélection")
        self.norm_sel_btn.clicked.connect(lambda: self._normalize_episodes(selection_only=True))
        self.norm_all_btn = QPushButton("Normaliser tout")
        self.norm_all_btn.clicked.connect(lambda: self._normalize_episodes(selection_only=False))
        self.index_btn = QPushButton("Indexer DB")
        self.index_btn.clicked.connect(self._index_db)
        self.export_corpus_btn = QPushButton("Exporter corpus")
        self.export_corpus_btn.clicked.connect(self._export_corpus)
        self.cancel_job_btn = QPushButton("Annuler")
        self.cancel_job_btn.clicked.connect(self._cancel_job)
        self.cancel_job_btn.setEnabled(False)
        for b in (self.discover_btn, self.fetch_sel_btn, self.fetch_all_btn, self.norm_sel_btn, self.norm_all_btn, self.index_btn, self.export_corpus_btn):
            btn_row.addWidget(b)
        btn_row.addWidget(self.cancel_job_btn)
        layout.addLayout(btn_row)

        self.corpus_progress = QProgressBar()
        self.corpus_progress.setMaximum(100)
        self.corpus_progress.setValue(0)
        layout.addWidget(self.corpus_progress)
        self.tabs.addTab(w, "Corpus")

    def _get_context(self) -> dict[str, Any]:
        return {
            "config": self._config,
            "store": self._store,
            "db": self._db,
        }

    def _discover_episodes(self):
        if not self._config or not self._store or not self._db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        step = FetchSeriesIndexStep(self._config.series_url, self._config.user_agent)
        self._run_job([step])

    def _fetch_episodes(self, selection_only: bool):
        if not self._config or not self._store or not self._db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        index = self._store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        if selection_only:
            ids = self.episodes_model.get_episode_ids_selection(self.episodes_table.selectionModel().selectedIndexes())
            if not ids:
                QMessageBox.warning(self, "Corpus", "Sélectionnez au moins un épisode.")
                return
        else:
            ids = [e.episode_id for e in index.episodes]
        steps = []
        for ref in (e for e in index.episodes if e.episode_id in ids):
            steps.append(FetchEpisodeStep(ref.episode_id, ref.url))
        if not steps:
            return
        self._run_job(steps)

    def _normalize_episodes(self, selection_only: bool):
        if not self._config or not self._store:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        if selection_only:
            ids = self.episodes_model.get_episode_ids_selection(self.episodes_table.selectionModel().selectedIndexes())
            if not ids:
                QMessageBox.warning(self, "Corpus", "Sélectionnez au moins un épisode.")
                return
        else:
            index = self._store.load_series_index()
            if not index:
                return
            ids = [e.episode_id for e in index.episodes]
        profile = self._config.normalize_profile if self._config else "default_en_v1"
        steps = [NormalizeEpisodeStep(eid, profile) for eid in ids]
        self._run_job(steps)

    def _index_db(self):
        if not self._store or not self._db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        steps = [BuildDbIndexStep()]
        self._run_job(steps)

    def _export_corpus(self):
        if not self._store:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        index = self._store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        episodes_data: list[tuple[EpisodeRef, str]] = []
        for ref in index.episodes:
            if self._store.has_episode_clean(ref.episode_id):
                text = self._store.load_episode_text(ref.episode_id, kind="clean")
                episodes_data.append((ref, text))
        if not episodes_data:
            QMessageBox.warning(self, "Corpus", "Aucun épisode normalisé (CLEAN) à exporter.")
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
                    self, "Export",
                    "Format non reconnu. Utilisez .txt, .csv, .json ou .jsonl (segmenté).",
                )
                return
            QMessageBox.information(self, "Export", f"Corpus exporté : {len(episodes_data)} épisode(s).")
        except Exception as e:
            logger.exception("Export corpus")
            QMessageBox.critical(self, "Erreur", str(e))

    def _run_job(self, steps: list):
        from howimetyourcorpus.core.models import SeriesIndex
        context = self._get_context()
        if not context.get("config"):
            return
        self._job_runner = JobRunner(steps, context, force=False)
        self._job_runner.progress.connect(self._on_job_progress)
        self._job_runner.log.connect(self._on_job_log)
        self._job_runner.error.connect(self._on_job_error)
        self._job_runner.finished.connect(self._on_job_finished)
        self._job_runner.cancelled.connect(self._on_job_cancelled)
        self.cancel_job_btn.setEnabled(True)
        self.corpus_progress.setValue(0)
        self._job_runner.run_async()

    def _on_job_progress(self, step_name: str, percent: float, message: str):
        self.corpus_progress.setValue(int(percent * 100))

    def _on_job_log(self, level: str, message: str):
        if self.tabs.count() > TAB_LOGS:
            log_widget = self.tabs.widget(TAB_LOGS)
            if isinstance(log_widget, QWidget) and log_widget.layout() and log_widget.layout().itemAt(0):
                te = log_widget.findChild(QPlainTextEdit)
                if te:
                    te.appendPlainText(f"[{level}] {message}")

    def _on_job_finished(self, results: list):
        self.cancel_job_btn.setEnabled(False)
        self.corpus_progress.setValue(100)
        self._refresh_episodes_from_store()
        self._refresh_inspecteur_episodes()
        self._refresh_subs_tracks()
        self._refresh_align_runs()
        eid = self.inspect_episode_combo.currentData()
        if eid:
            self._inspect_fill_segments(eid)
        self._job_runner = None

    def _on_job_cancelled(self):
        self.cancel_job_btn.setEnabled(False)
        self._job_runner = None

    def _on_job_error(self, step_name: str, exc: object):
        self.cancel_job_btn.setEnabled(False)
        QMessageBox.critical(self, "Erreur", f"{step_name}: {exc}")

    def _cancel_job(self):
        if self._job_runner:
            self._job_runner.cancel()

    def _refresh_episodes_from_store(self):
        if not self._store:
            return
        index = self._store.load_series_index()
        if index and index.episodes:
            self.episodes_model.set_store(self._store)
            self.episodes_model.set_db(self._db)
            self.episodes_model.set_episodes(index.episodes)

    def _build_tab_inspecteur(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("Épisode:"))
        self.inspect_episode_combo = QComboBox()
        self.inspect_episode_combo.currentIndexChanged.connect(self._inspect_load_episode)
        row.addWidget(self.inspect_episode_combo)
        row.addWidget(QLabel("Vue:"))
        self.inspect_view_combo = QComboBox()
        self.inspect_view_combo.addItem("Épisode", "episode")
        self.inspect_view_combo.addItem("Segments", "segments")
        self.inspect_view_combo.currentIndexChanged.connect(self._inspect_switch_view)
        row.addWidget(self.inspect_view_combo)
        self.inspect_segment_btn = QPushButton("Segmente l'épisode")
        self.inspect_segment_btn.clicked.connect(self._run_segment_episode)
        row.addWidget(self.inspect_segment_btn)
        layout.addLayout(row)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setPlaceholderText("RAW")
        self.clean_edit = QPlainTextEdit()
        self.clean_edit.setPlaceholderText("CLEAN")
        self.inspect_segments_list = QListWidget()
        self.inspect_segments_list.setMaximumWidth(320)
        self.inspect_segments_list.currentItemChanged.connect(self._inspect_on_segment_selected)
        split.addWidget(self.inspect_segments_list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.raw_edit)
        right_layout.addWidget(self.clean_edit)
        split.addWidget(right)
        layout.addWidget(split)
        self.inspect_stats_label = QLabel("Stats: —")
        layout.addWidget(self.inspect_stats_label)
        self.merge_examples_edit = QPlainTextEdit()
        self.merge_examples_edit.setReadOnly(True)
        self.merge_examples_edit.setMaximumHeight(120)
        layout.addWidget(QLabel("Exemples de fusions:"))
        layout.addWidget(self.merge_examples_edit)
        self.inspect_segments_list.setVisible(False)
        self.tabs.addTab(w, "Inspecteur")

    def _refresh_inspecteur_episodes(self):
        self.inspect_episode_combo.clear()
        if not self._store:
            return
        index = self._store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.inspect_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
        self._inspect_load_episode()

    def _inspect_load_episode(self):
        eid = self.inspect_episode_combo.currentData()
        if not eid or not self._store:
            self.raw_edit.clear()
            self.clean_edit.clear()
            self.inspect_stats_label.setText("Stats: —")
            self.merge_examples_edit.clear()
            self.inspect_segments_list.clear()
            return
        raw = self._store.load_episode_text(eid, kind="raw")
        clean = self._store.load_episode_text(eid, kind="clean")
        self.raw_edit.setPlainText(raw)
        self.clean_edit.setPlainText(clean)
        meta = self._store.load_episode_transform_meta(eid)
        if meta is not None:
            stats = meta.get("raw_lines", 0), meta.get("clean_lines", 0), meta.get("merges", 0)
            self.inspect_stats_label.setText(f"Stats: raw_lines={stats[0]}, clean_lines={stats[1]}, merges={stats[2]}")
            examples = meta.get("debug", {}).get("merge_examples", [])
            self.merge_examples_edit.setPlainText("\n".join(
                f"{x.get('before', '')} | {x.get('after', '')}" for x in examples[:15]
            ))
        else:
            self.inspect_stats_label.setText("Stats: —")
            self.merge_examples_edit.clear()
        self._inspect_fill_segments(eid)

    def _inspect_switch_view(self):
        is_segments = self.inspect_view_combo.currentData() == "segments"
        self.inspect_segments_list.setVisible(is_segments)
        eid = self.inspect_episode_combo.currentData()
        if eid:
            self._inspect_fill_segments(eid)

    def _inspect_fill_segments(self, episode_id: str):
        self.inspect_segments_list.clear()
        if self.inspect_view_combo.currentData() != "segments" or not self._db:
            return
        segments = self._db.get_segments_for_episode(episode_id)
        for s in segments:
            kind = s.get("kind", "")
            n = s.get("n", 0)
            text = (s.get("text") or "")[:60]
            if len((s.get("text") or "")) > 60:
                text += "…"
            item = QListWidgetItem(f"[{kind}] {n}: {text}")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.inspect_segments_list.addItem(item)

    def _inspect_on_segment_selected(self, current: QListWidgetItem | None):
        if not current:
            return
        seg = current.data(Qt.ItemDataRole.UserRole)
        if not seg:
            return
        start_char = seg.get("start_char", 0)
        end_char = seg.get("end_char", 0)
        cursor = self.clean_edit.textCursor()
        cursor.setPosition(min(start_char, len(self.clean_edit.toPlainText())))
        cursor.setPosition(min(end_char, len(self.clean_edit.toPlainText())), QTextCursor.MoveMode.KeepAnchor)
        self.clean_edit.setTextCursor(cursor)
        self.clean_edit.ensureCursorVisible()

    def _run_segment_episode(self):
        eid = self.inspect_episode_combo.currentData()
        if not eid or not self._store or not self._db:
            QMessageBox.warning(self, "Segmentation", "Sélectionnez un épisode et ouvrez un projet.")
            return
        if not self._store.has_episode_clean(eid):
            QMessageBox.warning(self, "Segmentation", "L'épisode doit d'abord être normalisé (clean.txt).")
            return
        self._run_job([SegmentEpisodeStep(eid, lang_hint="en")])

    def _build_tab_sous_titres(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("Épisode:"))
        self.subs_episode_combo = QComboBox()
        self.subs_episode_combo.currentIndexChanged.connect(self._subs_on_episode_changed)
        row.addWidget(self.subs_episode_combo)
        row.addWidget(QLabel("Langue:"))
        self.subs_lang_combo = QComboBox()
        self.subs_lang_combo.addItems(["en", "fr", "it"])
        row.addWidget(self.subs_lang_combo)
        self.subs_import_btn = QPushButton("Importer SRT/VTT...")
        self.subs_import_btn.clicked.connect(self._subs_import_file)
        row.addWidget(self.subs_import_btn)
        layout.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Pistes pour l'épisode:"))
        layout.addLayout(row2)
        self.subs_tracks_list = QListWidget()
        layout.addWidget(self.subs_tracks_list)
        self.tabs.addTab(w, "Sous-titres")

    def _refresh_subs_tracks(self):
        self.subs_episode_combo.clear()
        if not self._store:
            return
        index = self._store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.subs_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
        self._subs_on_episode_changed()

    def _subs_on_episode_changed(self):
        self.subs_tracks_list.clear()
        eid = self.subs_episode_combo.currentData()
        if not eid or not self._db:
            return
        tracks = self._db.get_tracks_for_episode(eid)
        for t in tracks:
            lang = t.get("lang", "")
            fmt = t.get("format", "")
            nb = t.get("nb_cues", 0)
            self.subs_tracks_list.addItem(f"{lang} | {fmt} | {nb} cues")

    def _subs_import_file(self):
        eid = self.subs_episode_combo.currentData()
        if not eid or not self._store or not self._db:
            QMessageBox.warning(self, "Sous-titres", "Sélectionnez un épisode et ouvrez un projet.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer sous-titres SRT/VTT",
            "",
            "Sous-titres (*.srt *.vtt);;Tous (*.*)",
        )
        if not path:
            return
        lang = self.subs_lang_combo.currentText() or "en"
        self._run_job([ImportSubtitlesStep(eid, lang, path)])
        self._refresh_subs_tracks()

    def _build_tab_alignement(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("Épisode:"))
        self.align_episode_combo = QComboBox()
        self.align_episode_combo.currentIndexChanged.connect(self._align_on_episode_changed)
        row.addWidget(self.align_episode_combo)
        row.addWidget(QLabel("Run:"))
        self.align_run_combo = QComboBox()
        self.align_run_combo.currentIndexChanged.connect(self._align_on_run_changed)
        row.addWidget(self.align_run_combo)
        self.align_run_btn = QPushButton("Lancer alignement")
        self.align_run_btn.clicked.connect(self._run_align_episode)
        row.addWidget(self.align_run_btn)
        self.export_align_btn = QPushButton("Exporter aligné")
        self.export_align_btn.clicked.connect(self._export_alignment)
        row.addWidget(self.export_align_btn)
        self.export_parallel_btn = QPushButton("Exporter concordancier parallèle")
        self.export_parallel_btn.clicked.connect(self._export_parallel_concordance)
        row.addWidget(self.export_parallel_btn)
        self.align_report_btn = QPushButton("Rapport HTML")
        self.align_report_btn.clicked.connect(self._export_align_report)
        row.addWidget(self.align_report_btn)
        self.align_stats_btn = QPushButton("Stats")
        self.align_stats_btn.clicked.connect(self._show_align_stats)
        row.addWidget(self.align_stats_btn)
        layout.addLayout(row)
        self.align_table = QTableView()
        self.align_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.align_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.align_table.customContextMenuRequested.connect(self._align_table_context_menu)
        layout.addWidget(self.align_table)
        self.tabs.addTab(w, "Alignement")

    def _refresh_align_runs(self):
        self.align_episode_combo.clear()
        if not self._store:
            return
        index = self._store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.align_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
        self._align_on_episode_changed()

    def _align_on_episode_changed(self):
        self.align_run_combo.clear()
        eid = self.align_episode_combo.currentData()
        if not eid or not self._db:
            self._align_fill_links()
            return
        runs = self._db.get_align_runs_for_episode(eid)
        for r in runs:
            run_id = r.get("align_run_id", "")
            created = r.get("created_at", "")[:19] if r.get("created_at") else ""
            self.align_run_combo.addItem(f"{run_id} ({created})", run_id)
        self._align_on_run_changed()

    def _align_on_run_changed(self):
        self._align_fill_links()

    def _align_fill_links(self):
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        model = AlignLinksTableModel()
        if not self._db or not eid:
            self.align_table.setModel(model)
            return
        links = self._db.query_alignment_for_episode(eid, run_id=run_id)
        model.set_links(links, self._db)
        self.align_table.setModel(model)

    def _align_table_context_menu(self, pos: QPoint):
        """Menu contextuel sur la table des liens : Accepter / Rejeter le lien sélectionné."""
        idx = self.align_table.indexAt(pos)
        if not idx.isValid() or not self._db:
            return
        model = self.align_table.model()
        if not isinstance(model, AlignLinksTableModel):
            return
        link = model.get_link_at(idx.row())
        if not link or not link.get("link_id"):
            return
        link_id = link["link_id"]
        menu = QMenu(self)
        accept_act = menu.addAction("Accepter")
        reject_act = menu.addAction("Rejeter")
        action = menu.exec(self.align_table.viewport().mapToGlobal(pos))
        if action == accept_act:
            self._db.set_align_status(link_id, "accepted")
            self._align_fill_links()
        elif action == reject_act:
            self._db.set_align_status(link_id, "rejected")
            self._align_fill_links()

    def _run_align_episode(self):
        eid = self.align_episode_combo.currentData()
        if not eid or not self._store or not self._db:
            QMessageBox.warning(self, "Alignement", "Sélectionnez un épisode et ouvrez un projet.")
            return
        self._run_job([AlignEpisodeStep(eid, pivot_lang="en", target_langs=["fr", "it"])])

    def _export_alignment(self):
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        if not eid or not run_id or not self._db:
            QMessageBox.warning(self, "Alignement", "Sélectionnez un épisode et un run.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter alignement", "", "CSV (*.csv);;JSONL (*.jsonl)")
        if not path:
            return
        path = Path(path)
        links = self._db.query_alignment_for_episode(eid, run_id=run_id)
        try:
            if path.suffix.lower() == ".jsonl":
                with path.open("w", encoding="utf-8") as f:
                    for row in links:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
            else:
                import csv
                with path.open("w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["link_id", "segment_id", "cue_id", "cue_id_target", "lang", "role", "confidence", "status", "meta"])
                    for row in links:
                        meta = row.get("meta")
                        meta_str = json.dumps(meta, ensure_ascii=False) if meta else ""
                        w.writerow([row.get("link_id"), row.get("segment_id"), row.get("cue_id"), row.get("cue_id_target"), row.get("lang"), row.get("role"), row.get("confidence"), row.get("status"), meta_str])
            QMessageBox.information(self, "Export", f"Alignement exporté : {len(links)} lien(s).")
        except Exception as e:
            logger.exception("Export alignement")
            QMessageBox.critical(self, "Erreur", str(e))

    def _export_parallel_concordance(self):
        """Exporte le concordancier parallèle (segment + EN + FR + IT) en CSV, TSV ou JSONL."""
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        if not eid or not run_id or not self._db:
            QMessageBox.warning(self, "Concordancier parallèle", "Sélectionnez un épisode et un run.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter concordancier parallèle", "",
            "CSV (*.csv);;TSV (*.tsv);;JSONL (*.jsonl)"
        )
        if not path:
            return
        path = Path(path)
        try:
            rows = self._db.get_parallel_concordance(eid, run_id)
            if path.suffix.lower() == ".jsonl":
                export_parallel_concordance_jsonl(rows, path)
            elif path.suffix.lower() == ".tsv":
                export_parallel_concordance_tsv(rows, path)
            else:
                export_parallel_concordance_csv(rows, path)
            QMessageBox.information(self, "Export", f"Concordancier parallèle exporté : {len(rows)} ligne(s).")
        except Exception as e:
            logger.exception("Export concordancier parallèle")
            QMessageBox.critical(self, "Erreur", str(e))

    def _export_align_report(self):
        """Génère un rapport HTML (stats + échantillon concordancier parallèle)."""
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        if not eid or not run_id or not self._db:
            QMessageBox.warning(self, "Rapport", "Sélectionnez un épisode et un run.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Rapport alignement", "", "HTML (*.html)")
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != ".html":
            path = path.with_suffix(".html")
        try:
            stats = self._db.get_align_stats_for_run(eid, run_id)
            sample = self._db.get_parallel_concordance(eid, run_id)
            export_align_report_html(stats, sample, eid, run_id, path)
            QMessageBox.information(self, "Rapport", f"Rapport enregistré : {path.name}")
        except Exception as e:
            logger.exception("Rapport alignement")
            QMessageBox.critical(self, "Erreur", str(e))

    def _show_align_stats(self):
        """Affiche les statistiques d'alignement du run sélectionné."""
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        if not eid or not run_id or not self._db:
            QMessageBox.warning(self, "Stats", "Sélectionnez un épisode et un run.")
            return
        try:
            stats = self._db.get_align_stats_for_run(eid, run_id)
            by_status = stats.get("by_status") or {}
            msg = (
                f"Épisode: {stats.get('episode_id', '')}\n"
                f"Run: {stats.get('run_id', '')}\n\n"
                f"Liens totaux: {stats.get('nb_links', 0)}\n"
                f"Liens pivot (segment↔EN): {stats.get('nb_pivot', 0)}\n"
                f"Liens target (EN↔FR/IT): {stats.get('nb_target', 0)}\n"
                f"Confiance moyenne: {stats.get('avg_confidence', '—')}\n"
                f"Par statut: {', '.join(f'{k}={v}' for k, v in sorted(by_status.items()))}"
            )
            QMessageBox.information(self, "Statistiques alignement", msg)
        except Exception as e:
            logger.exception("Stats alignement")
            QMessageBox.critical(self, "Erreur", str(e))

    def _build_tab_concordance(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("Recherche:"))
        self.kwic_search_edit = QLineEdit()
        self.kwic_search_edit.setPlaceholderText("Terme...")
        self.kwic_search_edit.returnPressed.connect(self._run_kwic)
        row.addWidget(self.kwic_search_edit)
        self.kwic_go_btn = QPushButton("Rechercher")
        self.kwic_go_btn.clicked.connect(self._run_kwic)
        row.addWidget(self.kwic_go_btn)
        self.export_kwic_btn = QPushButton("Exporter résultats")
        self.export_kwic_btn.clicked.connect(self._export_kwic)
        row.addWidget(self.export_kwic_btn)
        row.addWidget(QLabel("Scope:"))
        self.kwic_scope_combo = QComboBox()
        self.kwic_scope_combo.addItem("Épisodes (texte)", "episodes")
        self.kwic_scope_combo.addItem("Segments", "segments")
        self.kwic_scope_combo.addItem("Cues (sous-titres)", "cues")
        row.addWidget(self.kwic_scope_combo)
        row.addWidget(QLabel("Kind:"))
        self.kwic_kind_combo = QComboBox()
        self.kwic_kind_combo.addItem("—", "")
        self.kwic_kind_combo.addItem("Phrases", "sentence")
        self.kwic_kind_combo.addItem("Tours", "utterance")
        row.addWidget(self.kwic_kind_combo)
        row.addWidget(QLabel("Langue:"))
        self.kwic_lang_combo = QComboBox()
        self.kwic_lang_combo.addItem("—", "")
        self.kwic_lang_combo.addItem("en", "en")
        self.kwic_lang_combo.addItem("fr", "fr")
        self.kwic_lang_combo.addItem("it", "it")
        row.addWidget(self.kwic_lang_combo)
        row.addWidget(QLabel("Saison:"))
        self.kwic_season_spin = QSpinBox()
        self.kwic_season_spin.setMinimum(0)
        self.kwic_season_spin.setMaximum(99)
        self.kwic_season_spin.setSpecialValueText("—")
        row.addWidget(self.kwic_season_spin)
        row.addWidget(QLabel("Épisode:"))
        self.kwic_episode_spin = QSpinBox()
        self.kwic_episode_spin.setMinimum(0)
        self.kwic_episode_spin.setMaximum(999)
        self.kwic_episode_spin.setSpecialValueText("—")
        row.addWidget(self.kwic_episode_spin)
        layout.addLayout(row)
        self.kwic_table = QTableView()
        self.kwic_model = KwicTableModel()
        self.kwic_table.setModel(self.kwic_model)
        self.kwic_table.doubleClicked.connect(self._kwic_open_inspector)
        self.kwic_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.kwic_table)
        self.tabs.addTab(w, "Concordance")

    def _run_kwic(self):
        term = self.kwic_search_edit.text().strip()
        if not term or not self._db:
            return
        season = self.kwic_season_spin.value() if self.kwic_season_spin.value() > 0 else None
        episode = self.kwic_episode_spin.value() if self.kwic_episode_spin.value() > 0 else None
        scope = self.kwic_scope_combo.currentData() or "episodes"
        if scope == "segments":
            kind = self.kwic_kind_combo.currentData() or None
            hits = self._db.query_kwic_segments(term, kind=kind, season=season, episode=episode, window=45, limit=200)
        elif scope == "cues":
            lang = self.kwic_lang_combo.currentData() or None
            hits = self._db.query_kwic_cues(term, lang=lang, season=season, episode=episode, window=45, limit=200)
        else:
            hits = self._db.query_kwic(term, season=season, episode=episode, window=45, limit=200)
        self.kwic_model.set_hits(hits)

    def _export_kwic(self):
        hits = self.kwic_model.get_all_hits()
        if not hits:
            QMessageBox.warning(self, "Concordance", "Effectuez d'abord une recherche ou aucun résultat à exporter.")
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter les résultats KWIC",
            "",
            "CSV (*.csv);;TSV (*.tsv);;JSON (*.json);;JSONL (*.jsonl)",
        )
        if not path:
            return
        path = Path(path)
        try:
            if path.suffix.lower() == ".csv" or "CSV" in (selected_filter or ""):
                export_kwic_csv(hits, path)
            elif path.suffix.lower() == ".tsv" or "TSV" in (selected_filter or ""):
                export_kwic_tsv(hits, path)
            elif path.suffix.lower() == ".json" or "JSON" in (selected_filter or ""):
                export_kwic_json(hits, path)
            elif path.suffix.lower() == ".jsonl" or "JSONL" in (selected_filter or ""):
                export_kwic_jsonl(hits, path)
            else:
                QMessageBox.warning(self, "Export", "Format non reconnu. Utilisez .csv, .tsv, .json ou .jsonl")
                return
            QMessageBox.information(self, "Export", f"Résultats exportés : {len(hits)} occurrence(s).")
        except Exception as e:
            logger.exception("Export KWIC")
            QMessageBox.critical(self, "Erreur", str(e))

    def _kwic_open_inspector(self, index: QModelIndex):
        hit = self.kwic_model.get_hit_at(index.row())
        if not hit:
            return
        self.tabs.setCurrentIndex(TAB_INSPECTEUR)
        for i in range(self.inspect_episode_combo.count()):
            if self.inspect_episode_combo.itemData(i) == hit.episode_id:
                self.inspect_episode_combo.setCurrentIndex(i)
                break
        self._inspect_load_episode()

    def _build_tab_logs(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.logs_edit = QPlainTextEdit()
        self.logs_edit.setReadOnly(True)
        layout.addWidget(self.logs_edit)
        row = QHBoxLayout()
        open_log_btn = QPushButton("Ouvrir fichier log")
        open_log_btn.clicked.connect(self._open_log_file)
        row.addWidget(open_log_btn)
        layout.addLayout(row)
        self.tabs.addTab(w, "Logs")
        # Connect app logger to this widget
        h = TextEditHandler(self.logs_edit)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger("howimetyourcorpus").addHandler(h)

    def _open_log_file(self):
        if not self._config:
            QMessageBox.information(self, "Logs", "Ouvrez un projet pour avoir un fichier log.")
            return
        log_path = get_log_file_for_project(self._config.root_dir)
        if not log_path.exists():
            QMessageBox.information(self, "Logs", "Aucun fichier log pour l'instant.")
            return
        import os
        os.startfile(str(log_path))
