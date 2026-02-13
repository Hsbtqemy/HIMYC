"""Fenêtre principale : onglets Projet, Corpus, Inspecteur, Concordance, Logs."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QTreeView,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QPlainTextEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QProgressBar,
    QFormLayout,
    QMessageBox,
    QAbstractItemView,
    QHeaderView,
    QSplitter,
    QListWidget,
    QMenu,
    QDialog,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QModelIndex, QPoint, QTimer, QUrl, QSettings
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QDesktopServices

from howimetyourcorpus.core.models import ProjectConfig, SeriesIndex
from howimetyourcorpus.core.normalize.profiles import get_all_profile_ids
from howimetyourcorpus.core.pipeline.context import PipelineContext
from howimetyourcorpus.core.storage.project_store import ProjectStore
from howimetyourcorpus.core.storage.db import CorpusDB
from howimetyourcorpus.core.utils.logging import setup_logging, get_log_file_for_project
from howimetyourcorpus.core.export_utils import (
    export_segments_txt,
    export_segments_csv,
    export_segments_tsv,
)
from howimetyourcorpus.app.dialogs import ProfilesDialog
from howimetyourcorpus.app.tabs import (
    AlignmentTabWidget,
    ConcordanceTabWidget,
    CorpusTabWidget,
    InspecteurEtSousTitresTabWidget,
    LogsTabWidget,
    PersonnagesTabWidget,
    ProjectTabWidget,
)
from howimetyourcorpus.app.workers import JobRunner
from howimetyourcorpus.app.models_qt import AlignLinksTableModel
from howimetyourcorpus import __version__

logger = logging.getLogger(__name__)

# Index des onglets (§15.4 : Inspecteur + Sous-titres fusionnés → 7 onglets)
TAB_PROJET = 0
TAB_CORPUS = 1
TAB_INSPECTEUR = 2
TAB_ALIGNEMENT = 3
TAB_CONCORDANCE = 4
TAB_PERSONNAGES = 5
TAB_LOGS = 6


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HowIMetYourCorpus")
        self.setMinimumSize(800, 500)
        screen = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if screen:
            w = min(1000, screen.width())
            h = min(700, screen.height())
            self.resize(w, h)
        else:
            self.resize(1000, 700)
        # Icône fenêtre (depuis la source ou cwd)
        for icon_path in (
            Path.cwd() / "resources" / "icons" / "icon_512.png",
            Path(__file__).resolve().parent.parent.parent.parent / "resources" / "icons" / "icon_512.png",
        ):
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                break
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
        self._build_tab_alignement()
        self._build_tab_concordance()
        self._build_tab_personnages()
        self._build_tab_logs()
        self.tabs.setCurrentIndex(TAB_PROJET)
        self.tabs.currentChanged.connect(self._on_tab_changed)

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
        self.project_tab = ProjectTabWidget(
            get_store=lambda: self._store,
            on_validate_clicked=self._validate_and_init_project_from_tab,
            on_save_config=self._save_project_config,
            on_open_profiles_dialog=self._open_profiles_dialog,
            on_refresh_language_combos=self._refresh_language_combos,
            show_status=lambda msg, timeout=3000: self.statusBar().showMessage(msg, timeout),
        )
        self.tabs.addTab(self.project_tab, "Projet")

    def _save_project_config(self) -> None:
        """Enregistre la configuration de l'onglet Projet dans config.toml (source, URL, etc.)."""
        if not self._config or not self._store or not (hasattr(self, "project_tab") and self.project_tab):
            return
        data = self.project_tab.get_form_data()
        root = data.get("root")
        if not root or Path(root).resolve() != self._config.root_dir.resolve():
            self.statusBar().showMessage("Ouvrez un projet puis modifiez le formulaire du projet ouvert.", 4000)
            return
        self._store.save_config_main(
            series_url=data.get("series_url", ""),
            source_id=data.get("source_id"),
            rate_limit_s=float(data.get("rate_limit", 2)),
            normalize_profile=data.get("normalize_profile"),
        )
        self._config = ProjectConfig(
            project_name=self._config.project_name,
            root_dir=self._config.root_dir,
            source_id=data.get("source_id", self._config.source_id),
            series_url=data.get("series_url", self._config.series_url),
            rate_limit_s=float(data.get("rate_limit", self._config.rate_limit_s)),
            user_agent=self._config.user_agent,
            normalize_profile=data.get("normalize_profile", self._config.normalize_profile),
        )
        self.statusBar().showMessage("Configuration enregistrée (source, URL série, profil).", 3000)

    def _open_profiles_dialog(self):
        if not self._store:
            QMessageBox.warning(self, "Profils", "Ouvrez un projet d'abord.")
            return
        dlg = ProfilesDialog(self, self._store)
        dlg.exec()

    def _refresh_project_languages_list(self):
        if hasattr(self, "project_tab") and self.project_tab:
            self.project_tab.refresh_languages_list()

    def _refresh_language_combos(self):
        """Met à jour les listes de langues (Sous-titres, Concordance, Personnages) à partir du projet."""
        langs = self._store.load_project_languages() if self._store else ["en", "fr", "it"]
        if hasattr(self, "inspector_tab") and self.inspector_tab and hasattr(self.inspector_tab, "subtitles_tab"):
            self.inspector_tab.subtitles_tab.set_languages(langs)
        if hasattr(self, "concordance_tab") and hasattr(self.concordance_tab, "set_languages"):
            self.concordance_tab.set_languages(langs)
        if hasattr(self, "personnages_tab") and self.personnages_tab:
            self.personnages_tab.refresh()

    def _validate_and_init_project_from_tab(self):
        data = self.project_tab.get_form_data()
        root = data["root"]
        if not root:
            QMessageBox.warning(self, "Projet", "Indiquez un dossier projet.")
            return
        root_path = Path(root)
        config_toml = root_path / "config.toml"
        try:
            if config_toml.exists():
                self._load_existing_project(root_path)
                return
            config = ProjectConfig(
                project_name=root_path.name,
                root_dir=root_path,
                source_id=data["source_id"],
                series_url=data["series_url"],
                rate_limit_s=float(data["rate_limit"]),
                user_agent="HowIMetYourCorpus/0.1 (research)",
                normalize_profile=data["normalize_profile"],
            )
            ProjectStore.init_project(config)
            self._config = config
            self._store = ProjectStore(config.root_dir)
            self._db = CorpusDB(self._store.get_db_path())
            self._db.init()
            self._setup_logging_for_project()
            if data["srt_only"]:
                from howimetyourcorpus.core.models import SeriesIndex
                self._store.save_series_index(SeriesIndex(series_title="", series_url="", episodes=[]))
            self.project_tab.set_project_state(root_path, config)
            self.project_tab.refresh_languages_list()
            self._refresh_profile_combos()
            self._refresh_language_combos()
            self._refresh_inspecteur_episodes()
            self._refresh_subs_tracks()
            self._refresh_align_runs()
            self._refresh_personnages()
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
        else:
            self._db.ensure_migrated()
        self._setup_logging_for_project()
        self.project_tab.set_project_state(root_path, config)
        self.project_tab.refresh_languages_list()
        self._refresh_profile_combos()
        self._refresh_language_combos()
        QMessageBox.information(self, "Projet", "Projet ouvert.")
        # Ne pas remplir le Corpus ici : provoque segfault Qt/macOS. Le Corpus se remplit au clic sur l'onglet.
        def _deferred_refresh() -> None:
            self._refresh_inspecteur_episodes()
            self._refresh_subs_tracks()
            self._refresh_align_runs()
            self._refresh_personnages()

        QTimer.singleShot(0, _deferred_refresh)

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
        self.corpus_tab = CorpusTabWidget(
            get_store=lambda: self._store,
            get_db=lambda: self._db,
            get_context=self._get_context,
            run_job=self._run_job,
            show_status=lambda msg, timeout=3000: self.statusBar().showMessage(msg, timeout),
            refresh_after_episodes_added=lambda: (
                self._refresh_episodes_from_store(),
                self._refresh_inspecteur_episodes(),
                self._refresh_personnages(),
            ),
            on_cancel_job=self._cancel_job,
            on_open_inspector=self._kwic_open_inspector_impl,
        )
        self.tabs.addTab(self.corpus_tab, "Corpus")
        self.tabs.setTabToolTip(TAB_CORPUS, "Workflow §14 — Bloc 1 (Import) + Bloc 2 (Normalisation / segmentation) : découverte, téléchargement, normaliser, indexer.")
        # §15.3 — Projet = lieu du téléchargement : connecter les boutons Projet à la logique Corpus
        self.project_tab.set_acquisition_callbacks(
            on_discover_episodes=lambda: self.corpus_tab._discover_episodes(),
            on_fetch_all=lambda: self.corpus_tab._fetch_episodes(False),
        )

    def _get_context(self) -> PipelineContext:
        custom_profiles = self._store.load_custom_profiles() if self._store else {}
        return {
            "config": self._config,
            "store": self._store,
            "db": self._db,
            "custom_profiles": custom_profiles,
        }

    def _run_job(self, steps: list):
        # Synchroniser la config depuis l'onglet Projet (URL série, etc.) avant tout job
        if self._config and self._store and hasattr(self, "project_tab") and self.project_tab:
            data = self.project_tab.get_form_data()
            if data.get("root") and Path(data["root"]).resolve() == self._config.root_dir.resolve():
                self._store.save_config_main(
                    series_url=data.get("series_url", ""),
                    source_id=data.get("source_id"),
                    rate_limit_s=float(data.get("rate_limit", 2)),
                    normalize_profile=data.get("normalize_profile"),
                )
                self._config = ProjectConfig(
                    project_name=self._config.project_name,
                    root_dir=self._config.root_dir,
                    source_id=data.get("source_id", self._config.source_id),
                    series_url=data.get("series_url", self._config.series_url),
                    rate_limit_s=float(data.get("rate_limit", self._config.rate_limit_s)),
                    user_agent=self._config.user_agent,
                    normalize_profile=data.get("normalize_profile", self._config.normalize_profile),
                )
        context = self._get_context()
        if not context.get("config"):
            return
        self._job_runner = JobRunner(steps, context, force=False)
        self._job_runner.progress.connect(self._on_job_progress)
        self._job_runner.log.connect(self._on_job_log)
        self._job_runner.error.connect(self._on_job_error)
        self._job_runner.finished.connect(self._on_job_finished)
        self._job_runner.cancelled.connect(self._on_job_cancelled)
        if hasattr(self, "corpus_tab") and self.corpus_tab:
            self.corpus_tab.set_cancel_btn_enabled(True)
            self.corpus_tab.set_progress(0)
        self._job_runner.run_async()

    def _on_job_progress(self, step_name: str, percent: float, message: str):
        if hasattr(self, "corpus_tab") and self.corpus_tab:
            self.corpus_tab.set_progress(int(percent * 100))

    def _on_job_log(self, level: str, message: str):
        if self.tabs.count() > TAB_LOGS:
            log_widget = self.tabs.widget(TAB_LOGS)
            if isinstance(log_widget, QWidget) and log_widget.layout() and log_widget.layout().itemAt(0):
                te = log_widget.findChild(QPlainTextEdit)
                if te:
                    te.appendPlainText(f"[{level}] {message}")

    def _append_job_summary_to_log(self, summary: str) -> None:
        """Ajoute le résumé de fin de job dans l'onglet Logs."""
        if self.tabs.count() > TAB_LOGS:
            log_widget = self.tabs.widget(TAB_LOGS)
            if isinstance(log_widget, QWidget):
                te = log_widget.findChild(QPlainTextEdit)
                if te:
                    te.appendPlainText(f"[info] {summary}")

    def _on_job_finished(self, results: list):
        if hasattr(self, "corpus_tab") and self.corpus_tab:
            self.corpus_tab.set_cancel_btn_enabled(False)
            self.corpus_tab.set_progress(100)
        ok = sum(1 for r in results if getattr(r, "success", True))
        fail = len(results) - ok
        # Résumé unifié : X réussis, Y échecs (toujours affiché)
        msg = f"Terminé : {ok} réussie(s), {fail} échec(s)."
        if fail:
            failed_episode_ids = []
            first_fail_msg = ""
            for r in results:
                if not getattr(r, "success", True):
                    m = (getattr(r, "message", None) or str(r)) or ""
                    if not first_fail_msg:
                        first_fail_msg = m[:80] + ("…" if len(m) > 80 else "")
                    # Extraire episode_id (ex. S01E01) du message pour reprise ciblée
                    ep_match = re.search(r"S\d+E\d+", m, re.IGNORECASE)
                    if ep_match and ep_match.group(0).upper() not in {e.upper() for e in failed_episode_ids}:
                        failed_episode_ids.append(ep_match.group(0).upper())
            if failed_episode_ids:
                msg += f" Échec(s) : {', '.join(sorted(set(failed_episode_ids)))}."
            elif first_fail_msg:
                msg += f" Premier échec : {first_fail_msg}"
            self.statusBar().showMessage(msg, 10000)
        else:
            self.statusBar().showMessage(msg, 5000)
        self._append_job_summary_to_log(msg)
        self._refresh_episodes_from_store()
        self._refresh_inspecteur_episodes()
        self._refresh_subs_tracks()
        self._refresh_align_runs()
        self._job_runner = None

    def _on_job_cancelled(self):
        if hasattr(self, "corpus_tab") and self.corpus_tab:
            self.corpus_tab.set_cancel_btn_enabled(False)
        self._job_runner = None

    def _on_job_error(self, step_name: str, exc: object):
        if hasattr(self, "corpus_tab") and self.corpus_tab:
            self.corpus_tab.set_cancel_btn_enabled(False)
        try:
            msg = str(exc) if exc is not None else "Erreur inconnue"
        except Exception:
            msg = "Erreur inconnue"
        if len(msg) > 500:
            msg = msg[:497] + "..."
        QMessageBox.critical(self, "Erreur", f"{step_name}: {msg}")

    def _cancel_job(self):
        if self._job_runner:
            self._job_runner.cancel()

    def _on_tab_changed(self, index: int) -> None:
        """Remplit le Corpus au passage sur l'onglet (évite segfault Qt/macOS au chargement du projet)."""
        if index == TAB_CORPUS and self._store is not None:
            # Court délai pour que l'onglet soit actif et visible avant de remplir l'arbre
            QTimer.singleShot(50, self._refresh_episodes_from_store)

    def _refresh_episodes_from_store(self):
        if hasattr(self, "corpus_tab") and self.corpus_tab:
            self.corpus_tab.refresh()

    def _refresh_profile_combos(self):
        """Met à jour les listes de profils (prédéfinis + personnalisés projet) dans les combos."""
        custom = self._store.load_custom_profiles() if self._store else {}
        profile_ids = get_all_profile_ids(custom)
        current = self._config.normalize_profile if self._config else None
        if hasattr(self, "corpus_tab") and self.corpus_tab:
            self.corpus_tab.refresh_profile_combo(profile_ids, current)
        current_inspect = self._config.normalize_profile if self._config else None
        if hasattr(self, "inspector_tab") and self.inspector_tab:
            self.inspector_tab.refresh_profile_combo(profile_ids, current_inspect)

    def _build_tab_inspecteur(self):
        """§15.4 — Onglet Inspecteur fusionné avec Sous-titres (un épisode, deux panneaux)."""
        self.inspector_tab = InspecteurEtSousTitresTabWidget(
            get_store=lambda: self._store,
            get_db=lambda: self._db,
            get_config=lambda: self._config,
            run_job=self._run_job,
            refresh_episodes=self._refresh_episodes_from_store,
            show_status=lambda msg, timeout=3000: self.statusBar().showMessage(msg, timeout),
        )
        self.tabs.addTab(self.inspector_tab, "Inspecteur")
        self.tabs.setTabToolTip(TAB_INSPECTEUR, "§15.4 — Transcript (RAW/CLEAN, segments) + Sous-titres (pistes, import, normaliser) pour l'épisode courant.")

    def closeEvent(self, event):
        """Sauvegarde les tailles des splitters et les notes Inspecteur à la fermeture."""
        if hasattr(self, "inspector_tab") and self.inspector_tab:
            self.inspector_tab.save_state()
        super().closeEvent(event)

    def _refresh_inspecteur_episodes(self):
        if hasattr(self, "inspector_tab") and self.inspector_tab:
            self.inspector_tab.refresh()

    def _refresh_subs_tracks(self):
        """Rafraîchit les pistes Sous-titres (§15.4 : même onglet que Inspecteur)."""
        if hasattr(self, "inspector_tab") and self.inspector_tab:
            self.inspector_tab.refresh()

    def _build_tab_alignement(self):
        self.alignment_tab = AlignmentTabWidget(
            get_store=lambda: self._store,
            get_db=lambda: self._db,
            run_job=self._run_job,
        )
        self.tabs.addTab(self.alignment_tab, "Alignement")
        self.tabs.setTabToolTip(TAB_ALIGNEMENT, "Workflow §14 — Bloc 3 : Alignement transcript↔cues, liens, export concordancier.")

    def _refresh_align_runs(self):
        if hasattr(self, "alignment_tab") and self.alignment_tab:
            self.alignment_tab.refresh()

    def _build_tab_concordance(self):
        self.concordance_tab = ConcordanceTabWidget(
            get_db=lambda: self._db,
            on_open_inspector=self._kwic_open_inspector_impl,
        )
        self.tabs.addTab(self.concordance_tab, "Concordance")
        self.tabs.setTabToolTip(TAB_CONCORDANCE, "Workflow §14 — Bloc 3 : Concordancier parallèle (segment | EN | FR…), export KWIC.")

    def _build_tab_personnages(self):
        self.personnages_tab = PersonnagesTabWidget(
            get_store=lambda: self._store,
            get_db=lambda: self._db,
            show_status=lambda msg, timeout=3000: self.statusBar().showMessage(msg, timeout),
        )
        self.tabs.addTab(self.personnages_tab, "Personnages")
        self.tabs.setTabToolTip(TAB_PERSONNAGES, "Workflow §14 — Bloc 3 : Assignation segment/cue→personnage, propagation (après alignement).")

    def _refresh_personnages(self):
        if hasattr(self, "personnages_tab") and self.personnages_tab:
            self.personnages_tab.refresh()

    def _kwic_open_inspector_impl(self, episode_id: str) -> None:
        """Passe à l'onglet Inspecteur et charge l'épisode (appelé depuis l'onglet Concordance)."""
        self.tabs.setCurrentIndex(TAB_INSPECTEUR)
        if hasattr(self, "inspector_tab") and self.inspector_tab:
            self.inspector_tab.set_episode_and_load(episode_id)

    def _build_tab_logs(self):
        w = LogsTabWidget(on_open_log=self._open_log_file)
        self.tabs.addTab(w, "Logs")

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
