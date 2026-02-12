"""Fenêtre principale : onglets Projet, Corpus, Inspecteur, Concordance, Logs."""

from __future__ import annotations

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
)
from PySide6.QtCore import Qt, QModelIndex

from corpusstudio.core.adapters.base import AdapterRegistry
from corpusstudio.core.models import ProjectConfig, EpisodeRef, SeriesIndex
from corpusstudio.core.normalize.profiles import PROFILES
from corpusstudio.core.pipeline.tasks import (
    FetchSeriesIndexStep,
    FetchEpisodeStep,
    NormalizeEpisodeStep,
    BuildDbIndexStep,
)
from corpusstudio.core.storage.project_store import ProjectStore
from corpusstudio.core.storage.db import CorpusDB
from corpusstudio.core.utils.logging import setup_logging, get_log_file_for_project
from corpusstudio.app.workers import JobRunner
from corpusstudio.app.models_qt import EpisodesTableModel, KwicTableModel

logger = logging.getLogger(__name__)

# Index des onglets (éviter les entiers magiques)
TAB_PROJET = 0
TAB_CORPUS = 1
TAB_INSPECTEUR = 2
TAB_CONCORDANCE = 3
TAB_LOGS = 4


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

        self._build_tab_projet()
        self._build_tab_corpus()
        self._build_tab_inspecteur()
        self._build_tab_concordance()
        self._build_tab_logs()
        self.tabs.setCurrentIndex(TAB_PROJET)

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
            QMessageBox.information(self, "Projet", "Projet initialisé.")
        except Exception as e:
            logger.exception("Init project failed")
            QMessageBox.critical(self, "Erreur", str(e))

    def _load_existing_project(self, root_path: Path):
        """Charge un projet existant (config.toml présent)."""
        from corpusstudio.core.storage.project_store import load_project_config
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
        QMessageBox.information(self, "Projet", "Projet ouvert.")

    def _setup_logging_for_project(self):
        corpus_logger = logging.getLogger("corpusstudio")
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
        self.cancel_job_btn = QPushButton("Annuler")
        self.cancel_job_btn.clicked.connect(self._cancel_job)
        self.cancel_job_btn.setEnabled(False)
        for b in (self.discover_btn, self.fetch_sel_btn, self.fetch_all_btn, self.norm_sel_btn, self.norm_all_btn, self.index_btn):
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

    def _run_job(self, steps: list):
        from corpusstudio.core.models import SeriesIndex
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
        layout.addLayout(row)
        split = QSplitter(Qt.Orientation.Vertical)
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setPlaceholderText("RAW")
        self.clean_edit = QPlainTextEdit()
        self.clean_edit.setPlaceholderText("CLEAN")
        split.addWidget(self.raw_edit)
        split.addWidget(self.clean_edit)
        layout.addWidget(split)
        self.inspect_stats_label = QLabel("Stats: —")
        layout.addWidget(self.inspect_stats_label)
        self.merge_examples_edit = QPlainTextEdit()
        self.merge_examples_edit.setReadOnly(True)
        self.merge_examples_edit.setMaximumHeight(120)
        layout.addWidget(QLabel("Exemples de fusions:"))
        layout.addWidget(self.merge_examples_edit)
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
        hits = self._db.query_kwic(term, season=season, episode=episode, window=45, limit=200)
        self.kwic_model.set_hits(hits)

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
        logging.getLogger("corpusstudio").addHandler(h)

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
