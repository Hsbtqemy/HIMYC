"""Fenêtre principale : onglets Projet, Corpus, Inspecteur, Préparer, Alignement, Concordance, Personnages, Logs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QMessageBox,
)
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence, QUndoStack
from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QDesktopServices

from howimetyourcorpus.core.models import ProjectConfig
from howimetyourcorpus.core.normalize.profiles import get_all_profile_ids
from howimetyourcorpus.core.pipeline.context import PipelineContext
from howimetyourcorpus.core.storage.project_store import ProjectStore
from howimetyourcorpus.core.storage.db import CorpusDB
from howimetyourcorpus.core.utils.logging import get_log_file_for_project
from howimetyourcorpus.app.dialogs import ProfilesDialog
from howimetyourcorpus.app.workers import JobRunner
from howimetyourcorpus.app.mainwindow_jobs import MainWindowJobsController
from howimetyourcorpus.app.mainwindow_tabs import MainWindowTabsController
from howimetyourcorpus import __version__

logger = logging.getLogger(__name__)

# Index des onglets (§15.4 + Préparer entre Inspecteur et Alignement)
TAB_PROJET = 0
TAB_CORPUS = 1
TAB_INSPECTEUR = 2
TAB_PREPARER = 3
TAB_ALIGNEMENT = 4
TAB_CONCORDANCE = 5
TAB_PERSONNAGES = 6
TAB_LOGS = 7


class MainWindow(QMainWindow):
    def __init__(self) -> None:
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
        self._jobs_controller = MainWindowJobsController(self, logger)
        self._tabs_controller = MainWindowTabsController(
            self,
            logger,
            tab_projet=TAB_PROJET,
            tab_corpus=TAB_CORPUS,
            tab_inspecteur=TAB_INSPECTEUR,
            tab_preparer=TAB_PREPARER,
            tab_alignement=TAB_ALIGNEMENT,
            tab_concordance=TAB_CONCORDANCE,
            tab_personnages=TAB_PERSONNAGES,
        )

        # Basse Priorité #3 : Undo/Redo stack global
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(50)  # Limite à 50 actions

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_menu_bar()
        self._build_tab_projet()
        self._build_tab_corpus()
        self._build_tab_inspecteur()
        self._build_tab_preparer()
        self._build_tab_alignement()
        self._build_tab_concordance()
        self._build_tab_personnages()
        self._build_tab_logs()
        self.tabs.setCurrentIndex(TAB_PROJET)
        self._previous_tab_index = TAB_PROJET
        self._reverting_tab_change = False
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _build_menu_bar(self) -> None:
        """Barre de menu : Édition (Undo/Redo), Aide (À propos, Mises à jour)."""
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # Basse Priorité #3 : Menu Édition avec Undo/Redo
        edit_menu = menu_bar.addMenu("É&dition")

        # Action Undo (Ctrl+Z)
        undo_action = self.undo_stack.createUndoAction(self, "Annuler")
        if not isinstance(undo_action, QAction):
            undo_action = QAction("Annuler", self)
            undo_action.triggered.connect(self.undo_stack.undo)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)
        self.undo_action = undo_action

        # Action Redo (Ctrl+Y ou Ctrl+Shift+Z)
        redo_action = self.undo_stack.createRedoAction(self, "Refaire")
        if not isinstance(redo_action, QAction):
            redo_action = QAction("Refaire", self)
            redo_action.triggered.connect(self.undo_stack.redo)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)
        self.redo_action = redo_action

        edit_menu.addSeparator()

        # Action Effacer historique
        clear_history_act = QAction("Effacer l'historique Undo/Redo", self)
        clear_history_act.setToolTip("Vide la pile d'annulation (libère mémoire)")
        clear_history_act.triggered.connect(self._clear_undo_history)
        edit_menu.addAction(clear_history_act)

        # Menu Aide
        aide = menu_bar.addMenu("&Aide")
        about_act = QAction("À propos", self)
        about_act.triggered.connect(self._show_about)
        aide.addAction(about_act)
        update_act = QAction("Vérifier les mises à jour", self)
        update_act.triggered.connect(self._open_releases_page)
        aide.addAction(update_act)

    def _clear_undo_history(self) -> None:
        """Efface l'historique Undo/Redo (Basse Priorité #3)."""
        count = self.undo_stack.count()
        if count == 0:
            QMessageBox.information(self, "Historique", "L'historique est déjà vide.")
            return

        reply = QMessageBox.question(
            self,
            "Effacer historique",
            f"Effacer {count} action(s) dans l'historique Undo/Redo ?\n\n"
            "Vous ne pourrez plus annuler ces actions.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.undo_stack.clear()
            QMessageBox.information(self, "Historique", "Historique effacé.")

    def _show_about(self) -> None:
        """Affiche la boîte À propos (version, lien mises à jour)."""
        QMessageBox.about(
            self,
            "À propos",
            f"<b>HowIMetYourCorpus</b><br>Version {__version__}<br><br>"
            "Pipeline de corpus + exploration + QA — transcriptions et sous-titres.<br><br>"
            "Mises à jour : Aide → Vérifier les mises à jour.",
        )

    def _open_releases_page(self) -> None:
        """Ouvre la page des releases GitHub (mise à jour optionnelle Phase 6)."""
        QDesktopServices.openUrl(QUrl("https://github.com/Hsbtqemy/HIMYC/releases"))

    def _build_tab_projet(self) -> None:
        self._tabs_controller.build_tab_projet()

    def _save_project_config(self) -> None:
        """Enregistre la configuration de l'onglet Projet dans config.toml (source, URL, etc.)."""
        if not self._config or not self._store or not (hasattr(self, "project_tab") and self.project_tab):
            return
        if not self._sync_config_from_project_tab(show_mismatch_status=True):
            return
        self.statusBar().showMessage("Configuration enregistrée (source, URL série, profil).", 3000)

    def _open_profiles_dialog(self) -> None:
        if not self._store:
            QMessageBox.warning(self, "Profils", "Ouvrez un projet d'abord.")
            return
        dlg = ProfilesDialog(self, self._store)
        dlg.exec()

    def _refresh_project_languages_list(self) -> None:
        if hasattr(self, "project_tab") and self.project_tab:
            self.project_tab.refresh_languages_list()

    def _refresh_language_combos(self) -> None:
        """Met à jour les listes de langues (Sous-titres, Concordance, Personnages) à partir du projet."""
        langs = self._store.load_project_languages() if self._store else ["en", "fr", "it"]
        if hasattr(self, "inspector_tab") and self.inspector_tab and hasattr(self.inspector_tab, "subtitles_tab"):
            self.inspector_tab.subtitles_tab.set_languages(langs)
        if hasattr(self, "concordance_tab") and hasattr(self.concordance_tab, "set_languages"):
            self.concordance_tab.set_languages(langs)
            # Pack Analyse C5: Refresh speakers
            self.concordance_tab.refresh_speakers()
        if hasattr(self, "personnages_tab") and self.personnages_tab:
            self.personnages_tab.refresh()

    def _validate_and_init_project_from_tab(self) -> None:
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
            self._refresh_preparer()
            self._refresh_subs_tracks()
            self._refresh_align_runs()
            self._refresh_personnages()
            QMessageBox.information(self, "Projet", "Projet initialisé.")
        except Exception as e:
            logger.exception("Init project failed")
            QMessageBox.critical(self, "Erreur", str(e))

    def _load_existing_project(self, root_path: Path) -> None:
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
            self._refresh_preparer()
            self._refresh_subs_tracks()
            self._refresh_align_runs()
            self._refresh_personnages()

        QTimer.singleShot(0, _deferred_refresh)

    def _setup_logging_for_project(self) -> None:
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
            # Mettre à jour le label chemin log dans l'onglet Logs
            if hasattr(self, "tabs") and self.tabs.count() > TAB_LOGS:
                log_widget = self.tabs.widget(TAB_LOGS)
                if hasattr(log_widget, "set_log_path"):
                    log_widget.set_log_path(str(log_file))

    def _build_tab_corpus(self) -> None:
        self._tabs_controller.build_tab_corpus()

    def _get_context(self) -> PipelineContext:
        custom_profiles = self._store.load_custom_profiles() if self._store else {}
        return {
            "config": self._config,
            "store": self._store,
            "db": self._db,
            "custom_profiles": custom_profiles,
        }

    def _run_job(self, steps: list[Any]) -> None:
        self._jobs_controller.run_job(steps, job_runner_cls=JobRunner)

    def _sync_config_from_project_tab(self, *, show_mismatch_status: bool = False) -> bool:
        """
        Synchronise la config en mémoire + config.toml depuis le formulaire Projet.

        Retourne True si la synchro est appliquée, False sinon (pas de projet ouvert, onglet absent,
        root du formulaire qui ne correspond pas au projet courant, etc.).
        """
        if not self._config or not self._store or not (hasattr(self, "project_tab") and self.project_tab):
            return False
        data = self.project_tab.get_form_data()
        root = data.get("root")
        if not root or Path(root).resolve() != self._config.root_dir.resolve():
            if show_mismatch_status:
                self.statusBar().showMessage("Ouvrez un projet puis modifiez le formulaire du projet ouvert.", 4000)
            return False
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
        return True

    def _on_job_progress(self, step_name: str, percent: float, message: str) -> None:
        self._jobs_controller.on_job_progress(step_name, percent, message)

    def _on_job_log(self, level: str, message: str) -> None:
        self._jobs_controller.on_job_log(level, message, tab_logs_index=TAB_LOGS)

    def _append_job_summary_to_log(self, summary: str) -> None:
        """Ajoute le résumé de fin de job dans l'onglet Logs."""
        self._jobs_controller.append_job_summary_to_log(summary, tab_logs_index=TAB_LOGS)

    def _build_job_summary_message(self, results: list) -> tuple[str, set[str], int]:
        """Construit le message de fin de job + la liste d'épisodes en échec."""
        return self._jobs_controller.build_job_summary_message(results)

    def _refresh_tabs_after_job(self) -> None:
        """Rafraîchit les onglets dépendants après exécution d'un job."""
        self._jobs_controller.refresh_tabs_after_job(message_box=QMessageBox)

    def _on_job_finished(self, results: list[Any]) -> None:
        self._jobs_controller.on_job_finished(
            results,
            message_box=QMessageBox,
            tab_logs_index=TAB_LOGS,
        )

    def _on_job_cancelled(self) -> None:
        self._jobs_controller.on_job_cancelled()

    def _on_job_error(self, step_name: str, exc: object) -> None:
        self._jobs_controller.on_job_error(step_name, exc, message_box=QMessageBox)

    def _cancel_job(self) -> None:
        self._jobs_controller.cancel_job()

    def _on_tab_changed(self, index: int) -> None:
        """Remplit le Corpus au passage sur l'onglet (évite segfault Qt/macOS au chargement du projet)."""
        if self._reverting_tab_change:
            return
        previous = getattr(self, "_previous_tab_index", TAB_PROJET)
        if previous == TAB_PREPARER and index != TAB_PREPARER:
            if hasattr(self, "preparer_tab") and self.preparer_tab:
                if not self.preparer_tab.prompt_save_if_dirty():
                    self._reverting_tab_change = True
                    self.tabs.setCurrentIndex(TAB_PREPARER)
                    self._reverting_tab_change = False
                    return
        self._previous_tab_index = index
        if index == TAB_CORPUS and self._store is not None:
            # Court délai pour que l'onglet soit actif et visible avant de remplir l'arbre
            QTimer.singleShot(50, self._refresh_episodes_from_store)

    def _refresh_episodes_from_store(self) -> None:
        self._tabs_controller.refresh_episodes_from_store()

    def _refresh_profile_combos(self) -> None:
        """Met à jour les listes de profils (prédéfinis + personnalisés projet) dans les combos."""
        custom = self._store.load_custom_profiles() if self._store else {}
        profile_ids = get_all_profile_ids(custom)
        current = self._config.normalize_profile if self._config else None
        if hasattr(self, "corpus_tab") and self.corpus_tab:
            self.corpus_tab.refresh_profile_combo(profile_ids, current)
        current_inspect = self._config.normalize_profile if self._config else None
        if hasattr(self, "inspector_tab") and self.inspector_tab:
            self.inspector_tab.refresh_profile_combo(profile_ids, current_inspect)

    def _build_tab_inspecteur(self) -> None:
        self._tabs_controller.build_tab_inspecteur()

    def _build_tab_preparer(self) -> None:
        self._tabs_controller.build_tab_preparer()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Sauvegarde les tailles des splitters et les notes Inspecteur à la fermeture."""
        if hasattr(self, "preparer_tab") and self.preparer_tab:
            if not self.preparer_tab.prompt_save_if_dirty():
                event.ignore()
                return
            self.preparer_tab.save_state()
        if hasattr(self, "inspector_tab") and self.inspector_tab:
            self.inspector_tab.save_state()
        if hasattr(self, "alignment_tab") and self.alignment_tab:
            self.alignment_tab.save_state()
        super().closeEvent(event)

    def _refresh_inspecteur_episodes(self) -> None:
        self._tabs_controller.refresh_inspecteur_episodes()

    def _refresh_subs_tracks(self) -> None:
        """Rafraîchit les pistes Sous-titres (§15.4 : même onglet que Inspecteur)."""
        self._tabs_controller.refresh_subs_tracks()

    def _refresh_preparer(self, *, force: bool = False) -> None:
        self._tabs_controller.refresh_preparer(force=force)

    def _build_tab_alignement(self) -> None:
        self._tabs_controller.build_tab_alignement()

    def _refresh_align_runs(self) -> None:
        self._tabs_controller.refresh_align_runs()

    def _build_tab_concordance(self) -> None:
        self._tabs_controller.build_tab_concordance()

    def _build_tab_personnages(self) -> None:
        self._tabs_controller.build_tab_personnages()

    def _refresh_personnages(self) -> None:
        self._tabs_controller.refresh_personnages()

    def _refresh_concordance(self) -> None:
        self._tabs_controller.refresh_concordance()

    def _kwic_open_inspector_impl(self, episode_id: str) -> None:
        """Passe à l'onglet Inspecteur et charge l'épisode (appelé depuis l'onglet Concordance)."""
        self._tabs_controller.kwic_open_inspector(episode_id)

    def open_preparer_for_episode(self, episode_id: str, source: str | None = None) -> None:
        """Ouvre l'onglet Préparer sur un épisode/source donnés."""
        self._tabs_controller.open_preparer_for_episode(episode_id, source=source)

    def open_alignement_for_episode(self, episode_id: str, segment_kind: str = "sentence") -> None:
        """Handoff explicite vers Alignement avec épisode + type de segments."""
        self._tabs_controller.open_alignement_for_episode(episode_id, segment_kind=segment_kind)

    def _build_tab_logs(self) -> None:
        self._tabs_controller.build_tab_logs()

    def _open_log_file(self) -> None:
        if not self._config:
            QMessageBox.information(self, "Logs", "Ouvrez un projet pour avoir un fichier log.")
            return
        log_path = get_log_file_for_project(self._config.root_dir)
        if not log_path.exists():
            QMessageBox.information(self, "Logs", "Aucun fichier log pour l'instant.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path))):
            QMessageBox.warning(self, "Logs", f"Impossible d'ouvrir le fichier:\n{log_path}")
