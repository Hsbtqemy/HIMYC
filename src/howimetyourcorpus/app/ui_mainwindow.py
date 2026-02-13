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
    QListWidgetItem,
    QMenu,
    QDialog,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QModelIndex, QPoint, QUrl, QSettings
from PySide6.QtGui import QTextCursor, QAction, QIcon
from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QDesktopServices

from howimetyourcorpus.core.adapters.base import AdapterRegistry
from howimetyourcorpus.core.models import ProjectConfig, EpisodeRef, SeriesIndex
from howimetyourcorpus.core.normalize.profiles import PROFILES, get_all_profile_ids
from howimetyourcorpus.core.pipeline.tasks import (
    FetchAndMergeSeriesIndexStep,
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
    export_segments_txt,
    export_segments_csv,
    export_segments_tsv,
)
from howimetyourcorpus.app.workers import JobRunner
from howimetyourcorpus.app.models_qt import (
    EpisodesTreeModel,
    EpisodesTreeFilterProxyModel,
    KwicTableModel,
    AlignLinksTableModel,
)
from howimetyourcorpus import __version__

logger = logging.getLogger(__name__)

# Index des onglets (éviter les entiers magiques)
TAB_PROJET = 0
TAB_CORPUS = 1
TAB_INSPECTEUR = 2
TAB_SOUS_TITRES = 3
TAB_ALIGNEMENT = 4
TAB_CONCORDANCE = 5
TAB_PERSONNAGES = 6
TAB_LOGS = 7


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


def _parse_subtitle_filename(path: Path) -> tuple[str | None, str | None]:
    """Extrait (episode_id, lang) du nom de fichier. Ex. S01E01_en.srt -> (S01E01, en)."""
    name = path.name
    m = re.match(r"(?i)(S\d+E\d+)[_\-\.]?(\w{2})\.(srt|vtt)$", name)
    if not m:
        return (None, None)
    ep = m.group(1).upper()
    lang = m.group(2).lower()
    return (ep, lang)


class SubtitleBatchImportDialog(QDialog):
    """Dialogue pour mapper fichiers SRT/VTT → épisode + langue puis lancer l'import en masse."""

    def __init__(
        self,
        parent: QWidget | None,
        episode_ids: list[str],
        rows: list[tuple[str, str | None, str | None]],
        languages: list[str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Importer SRT en masse")
        self.episode_ids = episode_ids
        self.rows = rows  # (path, episode_id_guess, lang_guess)
        self.result: list[tuple[str, str, str]] = []  # (path, episode_id, lang) après validation
        langs = languages if languages else ["en", "fr", "it"]
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Vérifiez ou corrigez l'épisode et la langue pour chaque fichier, puis cliquez Importer."))
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Fichier", "Épisode", "Langue"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, (path_str, ep_guess, lang_guess) in enumerate(rows):
            self.table.insertRow(i)
            item = QTableWidgetItem(Path(path_str).name)
            item.setData(Qt.ItemDataRole.UserRole, path_str)
            item.setToolTip(path_str)
            self.table.setItem(i, 0, item)
            combo_ep = QComboBox()
            combo_ep.addItem("—", "")
            for eid in episode_ids:
                combo_ep.addItem(eid, eid)
            if ep_guess and ep_guess in episode_ids:
                idx = combo_ep.findData(ep_guess)
                if idx >= 0:
                    combo_ep.setCurrentIndex(idx)
            self.table.setCellWidget(i, 1, combo_ep)
            combo_lang = QComboBox()
            for lang in langs:
                combo_lang.addItem(lang, lang)
            if lang_guess and lang_guess in langs:
                combo_lang.setCurrentText(lang_guess)
            self.table.setCellWidget(i, 2, combo_lang)
        layout.addWidget(self.table)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self._accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _accept(self):
        self.result = []
        for i in range(self.table.rowCount()):
            path_item = self.table.item(i, 0)
            path_str = (path_item.data(Qt.ItemDataRole.UserRole) or path_item.text() or "").strip() if path_item else ""
            combo_ep = self.table.cellWidget(i, 1)
            combo_lang = self.table.cellWidget(i, 2)
            if not isinstance(combo_ep, QComboBox) or not isinstance(combo_lang, QComboBox):
                continue
            ep = (combo_ep.currentData() or "").strip()
            lang = (combo_lang.currentData() or combo_lang.currentText() or "").strip()
            if path_str and ep and lang:
                self.result.append((path_str, ep, lang))
        if not self.result:
            QMessageBox.warning(self, "Import", "Indiquez au moins un fichier avec épisode et langue.")
            return
        self.accept()


class ProfilesDialog(QDialog):
    """Dialogue pour gérer les profils de normalisation (liste, nouvel / modifier / supprimer pour les personnalisés)."""

    def __init__(self, parent: QWidget | None, store: ProjectStore | None):
        super().__init__(parent)
        self.setWindowTitle("Profils de normalisation")
        self._store = store
        self._custom_list: list[dict[str, Any]] = []  # list of {"id", "merge_subtitle_breaks", "max_merge_examples_in_debug"}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Profils prédéfinis (lecture seule) et personnalisés (éditables)."))
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)
        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("Nouveau")
        self.new_btn.clicked.connect(self._new_profile)
        self.edit_btn = QPushButton("Modifier")
        self.edit_btn.clicked.connect(self._edit_profile)
        self.delete_btn = QPushButton("Supprimer")
        self.delete_btn.clicked.connect(self._delete_profile)
        btn_row.addWidget(self.new_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addWidget(QLabel("Profil par défaut par source (pour normalisation batch / Inspecteur):"))
        self.source_profile_table = QTableWidget()
        self.source_profile_table.setColumnCount(2)
        self.source_profile_table.setHorizontalHeaderLabels(["Source", "Profil"])
        self.source_profile_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.source_profile_table)
        src_btn_row = QHBoxLayout()
        add_src_btn = QPushButton("Ajouter lien source→profil")
        add_src_btn.clicked.connect(self._add_source_profile_row)
        remove_src_btn = QPushButton("Supprimer la ligne")
        remove_src_btn.clicked.connect(self._remove_source_profile_row)
        src_btn_row.addWidget(add_src_btn)
        src_btn_row.addWidget(remove_src_btn)
        src_btn_row.addStretch()
        layout.addLayout(src_btn_row)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bbox.rejected.connect(self._close_profiles_dialog)
        layout.addWidget(bbox)
        self._load_list()
        self._load_source_profile_table()
        self._on_selection_changed()

    def _load_list(self):
        self.list_widget.clear()
        self._custom_list = []
        if self._store:
            custom = self._store.load_custom_profiles()
            self._custom_list = [
                {"id": p.id, "merge_subtitle_breaks": p.merge_subtitle_breaks, "max_merge_examples_in_debug": p.max_merge_examples_in_debug}
                for p in custom.values()
            ]
        for pid in PROFILES.keys():
            item = QListWidgetItem(f"{pid} (prédéfini)")
            item.setData(Qt.ItemDataRole.UserRole, ("builtin", pid))
            self.list_widget.addItem(item)
        for d in self._custom_list:
            pid = d.get("id") or ""
            if pid:
                item = QListWidgetItem(f"{pid} (personnalisé)")
                item.setData(Qt.ItemDataRole.UserRole, ("custom", pid))
                self.list_widget.addItem(item)

    def _on_selection_changed(self):
        item = self.list_widget.currentItem()
        is_custom = False
        if item:
            kind, _ = item.data(Qt.ItemDataRole.UserRole) or ("", "")
            is_custom = kind == "custom"
        self.edit_btn.setEnabled(is_custom)
        self.delete_btn.setEnabled(is_custom)

    def _save_custom(self):
        if self._store:
            self._store.save_custom_profiles(self._custom_list)
        self._load_list()
        if self.parent() and hasattr(self.parent(), "_refresh_profile_combos"):
            self.parent()._refresh_profile_combos()

    def _new_profile(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nouveau profil")
        form = QFormLayout(dlg)
        id_edit = QLineEdit()
        id_edit.setPlaceholderText("ex: mon_profil")
        form.addRow("Id:", id_edit)
        merge_cb = QCheckBox()
        merge_cb.setChecked(True)
        form.addRow("Fusionner césures:", merge_cb)
        max_spin = QSpinBox()
        max_spin.setRange(0, 100)
        max_spin.setValue(20)
        form.addRow("Max exemples debug:", max_spin)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        form.addRow(bbox)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        pid = (id_edit.text() or "").strip()
        if not pid:
            QMessageBox.warning(self, "Profil", "Indiquez un id.")
            return
        if pid in PROFILES or any(p.get("id") == pid for p in self._custom_list):
            QMessageBox.warning(self, "Profil", "Cet id existe déjà.")
            return
        self._custom_list.append({
            "id": pid,
            "merge_subtitle_breaks": merge_cb.isChecked(),
            "max_merge_examples_in_debug": max_spin.value(),
        })
        self._save_custom()

    def _edit_profile(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        kind, pid = item.data(Qt.ItemDataRole.UserRole) or ("", "")
        if kind != "custom":
            return
        custom = next((p for p in self._custom_list if p.get("id") == pid), None)
        if not custom:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Modifier le profil")
        form = QFormLayout(dlg)
        id_edit = QLineEdit()
        id_edit.setText(pid)
        id_edit.setReadOnly(True)
        form.addRow("Id:", id_edit)
        merge_cb = QCheckBox()
        merge_cb.setChecked(custom.get("merge_subtitle_breaks", True))
        form.addRow("Fusionner césures:", merge_cb)
        max_spin = QSpinBox()
        max_spin.setRange(0, 100)
        max_spin.setValue(custom.get("max_merge_examples_in_debug", 20))
        form.addRow("Max exemples debug:", max_spin)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        form.addRow(bbox)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        custom["merge_subtitle_breaks"] = merge_cb.isChecked()
        custom["max_merge_examples_in_debug"] = max_spin.value()
        self._save_custom()

    def _delete_profile(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        kind, pid = item.data(Qt.ItemDataRole.UserRole) or ("", "")
        if kind != "custom":
            return
        if QMessageBox.question(
            self, "Supprimer",
            f"Supprimer le profil « {pid} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._custom_list = [p for p in self._custom_list if p.get("id") != pid]
        self._save_custom()

    def _load_source_profile_table(self):
        """Remplit la table source → profil depuis le store."""
        self.source_profile_table.setRowCount(0)
        if not self._store:
            return
        defaults = self._store.load_source_profile_defaults()
        source_ids = AdapterRegistry.list_ids() or ["subslikescript"]
        profile_ids = list(get_all_profile_ids())
        for source_id, profile_id in defaults.items():
            row = self.source_profile_table.rowCount()
            self.source_profile_table.insertRow(row)
            src_combo = QComboBox()
            src_combo.addItems(source_ids)
            idx = src_combo.findText(source_id)
            if idx >= 0:
                src_combo.setCurrentIndex(idx)
            self.source_profile_table.setCellWidget(row, 0, src_combo)
            prof_combo = QComboBox()
            prof_combo.addItems(profile_ids)
            idx = prof_combo.findText(profile_id)
            if idx >= 0:
                prof_combo.setCurrentIndex(idx)
            self.source_profile_table.setCellWidget(row, 1, prof_combo)

    def _add_source_profile_row(self):
        """Ajoute une ligne (source, profil) à la table."""
        source_ids = AdapterRegistry.list_ids() or ["subslikescript"]
        profile_ids = list(get_all_profile_ids())
        row = self.source_profile_table.rowCount()
        self.source_profile_table.insertRow(row)
        src_combo = QComboBox()
        src_combo.addItems(source_ids)
        self.source_profile_table.setCellWidget(row, 0, src_combo)
        prof_combo = QComboBox()
        prof_combo.addItems(profile_ids)
        self.source_profile_table.setCellWidget(row, 1, prof_combo)

    def _remove_source_profile_row(self):
        """Supprime la ligne sélectionnée de la table source→profil."""
        row = self.source_profile_table.currentRow()
        if row >= 0:
            self.source_profile_table.removeRow(row)

    def _save_source_profile_defaults(self):
        """Enregistre la table source→profil dans le store."""
        if not self._store:
            return
        defaults: dict[str, str] = {}
        for row in range(self.source_profile_table.rowCount()):
            src_w = self.source_profile_table.cellWidget(row, 0)
            prof_w = self.source_profile_table.cellWidget(row, 1)
            if src_w and prof_w:
                src = (src_w.currentText() or "").strip()
                prof = (prof_w.currentText() or "").strip()
                if src and prof:
                    defaults[src] = prof
        self._store.save_source_profile_defaults(defaults)

    def _close_profiles_dialog(self):
        """Sauvegarde les liens source→profil puis ferme le dialogue."""
        self._save_source_profile_defaults()
        self.reject()


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
        self._build_tab_sous_titres()
        self._build_tab_alignement()
        self._build_tab_concordance()
        self._build_tab_personnages()
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
        self.srt_only_cb = QCheckBox("Projet SRT uniquement (sans transcriptions)")
        self.srt_only_cb.setToolTip("Cochez pour créer un projet sans Découvrir/Télécharger ; vous pourrez ajouter des épisodes à la main et importer des SRT.")
        layout.addRow("", self.srt_only_cb)

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
        profiles_btn = QPushButton("Gérer les profils de normalisation...")
        profiles_btn.setToolTip("Créer, modifier ou supprimer les profils personnalisés (fichier profiles.json du projet).")
        profiles_btn.clicked.connect(self._open_profiles_dialog)
        layout.addRow("", profiles_btn)

        layout.addRow("", QLabel("Langues du projet (sous-titres, personnages, KWIC) :"))
        self.languages_list = QListWidget()
        self.languages_list.setMaximumHeight(80)
        self.languages_list.currentRowChanged.connect(self._on_languages_list_selection_changed)
        layout.addRow("", self.languages_list)
        lang_btn_row = QHBoxLayout()
        self.add_lang_btn = QPushButton("Ajouter une langue...")
        self.add_lang_btn.setToolTip("Ajoute un code langue (ex. de, es) utilisé dans les sous-titres et personnages.")
        self.add_lang_btn.clicked.connect(self._add_project_language)
        self.remove_lang_btn = QPushButton("Supprimer la langue")
        self.remove_lang_btn.setToolTip("Retire la langue sélectionnée de la liste (n'affecte pas les fichiers déjà importés).")
        self.remove_lang_btn.clicked.connect(self._remove_project_language)
        lang_btn_row.addWidget(self.add_lang_btn)
        lang_btn_row.addWidget(self.remove_lang_btn)
        lang_btn_row.addStretch()
        layout.addRow("", lang_btn_row)

        self.tabs.addTab(w, "Projet")

    def _browse_project(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir le dossier projet")
        if d:
            self.proj_root_edit.setText(d)

    def _open_profiles_dialog(self):
        if not self._store:
            QMessageBox.warning(self, "Profils", "Ouvrez un projet d'abord.")
            return
        dlg = ProfilesDialog(self, self._store)
        dlg.exec()

    def _refresh_project_languages_list(self):
        """Remplit la liste des langues du projet (onglet Projet)."""
        self.languages_list.clear()
        if self._store:
            for lang in self._store.load_project_languages():
                self.languages_list.addItem(lang)
        self.add_lang_btn.setEnabled(bool(self._store))
        self._on_languages_list_selection_changed()

    def _on_languages_list_selection_changed(self):
        self.remove_lang_btn.setEnabled(
            bool(self._store) and self.languages_list.count() > 0 and self.languages_list.currentRow() >= 0
        )

    def _add_project_language(self):
        if not self._store:
            QMessageBox.warning(self, "Langues", "Ouvrez un projet d'abord.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Ajouter une langue")
        form = QFormLayout(dlg)
        code_edit = QLineEdit()
        code_edit.setPlaceholderText("ex. de, es, pt")
        code_edit.setMaxLength(10)
        form.addRow("Code langue (2–10 caractères):", code_edit)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        form.addRow(bbox)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        code = (code_edit.text() or "").strip().lower()
        if not code or len(code) < 2:
            QMessageBox.warning(self, "Langues", "Indiquez un code langue (au moins 2 caractères).")
            return
        langs = self._store.load_project_languages()
        if code in langs:
            QMessageBox.information(self, "Langues", f"La langue « {code} » est déjà dans la liste.")
            return
        langs.append(code)
        langs.sort()
        self._store.save_project_languages(langs)
        self._refresh_project_languages_list()
        self._refresh_language_combos()
        self.statusBar().showMessage(f"Langue « {code} » ajoutée.", 3000)

    def _remove_project_language(self):
        if not self._store:
            return
        row = self.languages_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "Langues", "Sélectionnez une langue à supprimer.")
            return
        code = self.languages_list.item(row).text()
        if QMessageBox.question(
            self, "Supprimer la langue",
            f"Retirer « {code} » de la liste ? (Les pistes/cues déjà importés ne sont pas supprimés.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        langs = self._store.load_project_languages()
        langs = [x for x in langs if x != code]
        self._store.save_project_languages(langs)
        self._refresh_project_languages_list()
        self._refresh_language_combos()
        self.statusBar().showMessage(f"Langue « {code} » retirée de la liste.", 3000)

    def _refresh_language_combos(self):
        """Met à jour les listes de langues (Sous-titres, Personnages, KWIC, etc.) à partir du projet."""
        langs = self._store.load_project_languages() if self._store else ["en", "fr", "it"]
        self.subs_lang_combo.clear()
        self.subs_lang_combo.addItems(langs)
        self.kwic_lang_combo.clear()
        self.kwic_lang_combo.addItem("—", "")
        for lang in langs:
            self.kwic_lang_combo.addItem(lang, lang)
        self._refresh_personnages_headers_and_sources()

    def _refresh_personnages_headers_and_sources(self):
        """Met à jour les colonnes de la table personnages (Id, Canonique + une par langue) et le combo Source."""
        langs = self._store.load_project_languages() if self._store else ["en", "fr", "it"]
        self.personnages_table.setColumnCount(2 + len(langs))
        self.personnages_table.setHorizontalHeaderLabels(["Id", "Canonique"] + [lang.upper() for lang in langs])
        self.personnages_source_combo.clear()
        self.personnages_source_combo.addItem("Segments", "segments")
        for lang in langs:
            self.personnages_source_combo.addItem(f"Cues {lang.upper()}", f"cues_{lang}")

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
            srt_only = self.srt_only_cb.isChecked()
            if not srt_only and not series_url:
                QMessageBox.warning(self, "Projet", "Indiquez l'URL de la série (ou cochez « Projet SRT uniquement »).")
                return
            if srt_only and not series_url:
                series_url = ""
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
            if srt_only:
                from howimetyourcorpus.core.models import SeriesIndex
                self._store.save_series_index(SeriesIndex(series_title="", series_url="", episodes=[]))
            self._refresh_profile_combos()
            self.norm_batch_profile_combo.setCurrentText(config.normalize_profile)
            self.inspect_profile_combo.setCurrentText(config.normalize_profile)
            self._refresh_project_languages_list()
            self._refresh_language_combos()
            self._refresh_episodes_from_store()
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
        self.proj_root_edit.setText(str(root_path))
        self.series_url_edit.setText(config.series_url)
        self.srt_only_cb.setChecked(not (config.series_url or "").strip())
        self.normalize_profile_combo.setCurrentText(config.normalize_profile)
        self.rate_limit_spin.setValue(int(config.rate_limit_s))
        self.source_id_combo.setCurrentText(config.source_id)
        self.norm_batch_profile_combo.setCurrentText(config.normalize_profile)
        self.inspect_profile_combo.setCurrentText(config.normalize_profile)
        self._refresh_project_languages_list()
        self._refresh_language_combos()
        self._refresh_episodes_from_store()
        self._refresh_inspecteur_episodes()
        self._refresh_subs_tracks()
        self._refresh_align_runs()
        self._refresh_personnages()
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
        # Filtre par saison + Cocher la saison
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Saison:"))
        self.season_filter_combo = QComboBox()
        self.season_filter_combo.setMinimumWidth(140)
        self.season_filter_combo.currentIndexChanged.connect(self._on_season_filter_changed)
        filter_row.addWidget(self.season_filter_combo)
        self.check_season_btn = QPushButton("Cocher la saison")
        self.check_season_btn.setToolTip("Coche tous les épisodes de la saison choisie dans le filtre (ou tout si « Toutes les saisons »).")
        self.check_season_btn.clicked.connect(self._on_check_season_clicked)
        filter_row.addWidget(self.check_season_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)
        self.episodes_tree = QTreeView()
        self.episodes_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.episodes_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.episodes_tree.setRootIsDecorated(True)
        self.episodes_tree.setAlternatingRowColors(True)
        self.episodes_tree_model = EpisodesTreeModel()
        self.episodes_tree_proxy = EpisodesTreeFilterProxyModel()
        self.episodes_tree_proxy.setSourceModel(self.episodes_tree_model)
        self.episodes_tree.setModel(self.episodes_tree_proxy)
        self.episodes_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.episodes_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.episodes_tree.setColumnWidth(0, 32)
        layout.addWidget(self.episodes_tree)

        btn_row = QHBoxLayout()
        self.check_all_btn = QPushButton("Tout cocher")
        self.check_all_btn.clicked.connect(lambda: self.episodes_tree_model.set_all_checked(True))
        self.uncheck_all_btn = QPushButton("Tout décocher")
        self.uncheck_all_btn.clicked.connect(lambda: self.episodes_tree_model.set_all_checked(False))
        btn_row.addWidget(self.check_all_btn)
        btn_row.addWidget(self.uncheck_all_btn)
        btn_row.addWidget(QLabel("Profil (batch):"))
        self.norm_batch_profile_combo = QComboBox()
        self.norm_batch_profile_combo.addItems(list(PROFILES.keys()))
        self.norm_batch_profile_combo.setToolTip("Profil de normalisation utilisé pour « Normaliser sélection » et « Normaliser tout ». Profils prédéfinis + projet (profiles.json).")
        btn_row.addWidget(self.norm_batch_profile_combo)
        self.discover_btn = QPushButton("Découvrir épisodes")
        self.discover_btn.setToolTip("Récupère la liste des épisodes depuis la source (tout le projet).")
        self.discover_btn.clicked.connect(self._discover_episodes)
        self.add_episodes_btn = QPushButton("Ajouter épisodes (SRT only)")
        self.add_episodes_btn.setToolTip("Ajoute des épisodes à la main (un par ligne, ex. S01E01). Pour projet SRT uniquement.")
        self.add_episodes_btn.clicked.connect(self._add_episodes_manually)
        self.discover_merge_btn = QPushButton("Découvrir (fusionner une autre source)...")
        self.discover_merge_btn.setToolTip("Découvre une série depuis une autre source/URL et fusionne avec l'index existant (sans écraser les épisodes déjà présents).")
        self.discover_merge_btn.clicked.connect(self._discover_merge)
        self.fetch_sel_btn = QPushButton("Télécharger sélection")
        self.fetch_sel_btn.setToolTip("Télécharge les épisodes cochés (ou les lignes sélectionnées au clic).")
        self.fetch_sel_btn.clicked.connect(lambda: self._fetch_episodes(selection_only=True))
        self.fetch_all_btn = QPushButton("Télécharger tout")
        self.fetch_all_btn.setToolTip("Télécharge tout le corpus (tous les épisodes découverts).")
        self.fetch_all_btn.clicked.connect(lambda: self._fetch_episodes(selection_only=False))
        self.norm_sel_btn = QPushButton("Normaliser sélection")
        self.norm_sel_btn.setToolTip(
            "Normalise les épisodes cochés (ou les lignes sélectionnées). Prérequis : épisodes déjà téléchargés (RAW)."
        )
        self.norm_sel_btn.clicked.connect(lambda: self._normalize_episodes(selection_only=True))
        self.norm_all_btn = QPushButton("Normaliser tout")
        self.norm_all_btn.setToolTip(
            "Normalise tout le corpus. Prérequis : épisodes déjà téléchargés (RAW)."
        )
        self.norm_all_btn.clicked.connect(lambda: self._normalize_episodes(selection_only=False))
        self.index_btn = QPushButton("Indexer DB")
        self.index_btn.setToolTip("Indexe en base tous les épisodes ayant un fichier CLEAN (tout le projet).")
        self.index_btn.clicked.connect(self._index_db)
        self.export_corpus_btn = QPushButton("Exporter corpus")
        self.export_corpus_btn.clicked.connect(self._export_corpus)
        self.cancel_job_btn = QPushButton("Annuler")
        self.cancel_job_btn.clicked.connect(self._cancel_job)
        self.cancel_job_btn.setEnabled(False)
        for b in (self.discover_btn, self.add_episodes_btn, self.discover_merge_btn, self.fetch_sel_btn, self.fetch_all_btn, self.norm_sel_btn, self.norm_all_btn, self.index_btn, self.export_corpus_btn):
            btn_row.addWidget(b)
        btn_row.addWidget(self.cancel_job_btn)
        layout.addLayout(btn_row)

        self.corpus_progress = QProgressBar()
        self.corpus_progress.setMaximum(100)
        self.corpus_progress.setValue(0)
        layout.addWidget(self.corpus_progress)
        self.corpus_status_label = QLabel("")
        self.corpus_status_label.setToolTip("Résumé : épisodes découverts, normalisés (CLEAN), indexés en DB.")
        layout.addWidget(self.corpus_status_label)
        scope_label = QLabel("Périmètre : « sélection » = épisodes cochés ou lignes sélectionnées ; « tout » = tout le corpus.")
        scope_label.setStyleSheet("color: gray; font-size: 0.9em;")
        layout.addWidget(scope_label)
        self.tabs.addTab(w, "Corpus")

    def _get_context(self) -> dict[str, Any]:
        custom_profiles = self._store.load_custom_profiles() if self._store else {}
        return {
            "config": self._config,
            "store": self._store,
            "db": self._db,
            "custom_profiles": custom_profiles,
        }

    def _discover_episodes(self):
        if not self._config or not self._store or not self._db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        step = FetchSeriesIndexStep(self._config.series_url, self._config.user_agent)
        self._run_job([step])

    def _discover_merge(self):
        """Découvre une série depuis une autre source/URL et fusionne avec l'index existant."""
        if not self._config or not self._store or not self._db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Découvrir (fusionner une autre source)")
        layout = QFormLayout(dlg)
        url_edit = QLineEdit()
        url_edit.setPlaceholderText("https://subslikescript.com/series/...")
        layout.addRow("URL série (autre source):", url_edit)
        source_combo = QComboBox()
        source_combo.addItems(AdapterRegistry.list_ids() or ["subslikescript"])
        layout.addRow("Source:", source_combo)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
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
        step = FetchAndMergeSeriesIndexStep(url, source_id, self._config.user_agent)
        self._run_job([step])

    def _add_episodes_manually(self):
        """Ajoute des épisodes à la main (projet SRT only) : un episode_id par ligne (ex. S01E01)."""
        if not self._store:
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
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addWidget(bbox)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        lines = [ln.strip().upper() for ln in text_edit.toPlainText().strip().splitlines() if ln.strip()]
        if not lines:
            QMessageBox.information(self, "Corpus", "Aucun episode_id saisi.")
            return
        m = re.match(r"S(\d+)E(\d+)", lines[0])
        new_refs = []
        for ln in lines:
            mm = re.match(r"S(\d+)E(\d+)", ln, re.IGNORECASE)
            if not mm:
                continue
            ep_id = f"S{int(mm.group(1)):02d}E{int(mm.group(2)):02d}"
            new_refs.append(EpisodeRef(episode_id=ep_id, season=int(mm.group(1)), episode=int(mm.group(2)), title="", url=""))
        if not new_refs:
            QMessageBox.warning(self, "Corpus", "Aucun episode_id valide (format S01E01).")
            return
        index = self._store.load_series_index()
        existing_ids = {e.episode_id for e in (index.episodes or [])} if index else set()
        episodes = list(index.episodes or []) if index else []
        for ref in new_refs:
            if ref.episode_id not in existing_ids:
                episodes.append(ref)
                existing_ids.add(ref.episode_id)
        self._store.save_series_index(SeriesIndex(
            series_title=index.series_title if index else "",
            series_url=index.series_url if index else "",
            episodes=episodes,
        ))
        self._refresh_episodes_from_store()
        self._refresh_inspecteur_episodes()
        self._refresh_personnages()
        self.statusBar().showMessage(f"{len(new_refs)} épisode(s) ajouté(s).", 3000)

    def _fetch_episodes(self, selection_only: bool):
        if not self._config or not self._store or not self._db:
            QMessageBox.warning(self, "Corpus", "Ouvrez un projet d'abord.")
            return
        index = self._store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        if selection_only:
            ids = self.episodes_tree_model.get_checked_episode_ids()
            if not ids:
                proxy_indices = self.episodes_tree.selectionModel().selectedIndexes()
                source_indices = [self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices]
                ids = self.episodes_tree_model.get_episode_ids_selection(source_indices)
            if not ids:
                QMessageBox.warning(
                    self, "Corpus", "Cochez au moins un épisode ou sélectionnez des lignes."
                )
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
        index = self._store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Corpus", "Découvrez d'abord les épisodes.")
            return
        if selection_only:
            ids = self.episodes_tree_model.get_checked_episode_ids()
            if not ids:
                proxy_indices = self.episodes_tree.selectionModel().selectedIndexes()
                source_indices = [self.episodes_tree_proxy.mapToSource(ix) for ix in proxy_indices]
                ids = self.episodes_tree_model.get_episode_ids_selection(source_indices)
            if not ids:
                QMessageBox.warning(
                    self, "Corpus", "Cochez au moins un épisode ou sélectionnez des lignes."
                )
                return
        else:
            ids = [e.episode_id for e in index.episodes]
        ref_by_id = {e.episode_id: e for e in index.episodes}
        episode_preferred = self._store.load_episode_preferred_profiles()
        source_defaults = self._store.load_source_profile_defaults()
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
        ok = sum(1 for r in results if getattr(r, "success", True))
        fail = len(results) - ok
        if fail:
            first_fail_msg = ""
            for r in results:
                if not getattr(r, "success", True):
                    first_fail_msg = (getattr(r, "message", None) or str(r))[:80]
                    if len(getattr(r, "message", "") or "") > 80:
                        first_fail_msg += "…"
                    break
            msg = f"Terminé : {ok} réussie(s), {fail} échec(s)."
            if first_fail_msg:
                msg += f" Premier échec : {first_fail_msg}"
            self.statusBar().showMessage(msg, 10000)
        else:
            self.statusBar().showMessage(
                f"Terminé : {len(results)} étape(s) exécutée(s) avec succès.",
                5000,
            )
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

    def _refresh_episodes_from_store(self):
        if not self._store:
            return
        index = self._store.load_series_index()
        if index and index.episodes:
            self.episodes_tree_model.set_store(self._store)
            self.episodes_tree_model.set_db(self._db)
            self.episodes_tree_model.set_episodes(index.episodes)
            self.episodes_tree.expandAll()
            self._refresh_season_filter_combo()
            n_norm = sum(1 for e in index.episodes if self._store.has_episode_clean(e.episode_id))
            n_indexed = len(self._db.get_episode_ids_indexed()) if self._db else 0
            n_with_srt = 0
            n_aligned = 0
            if self._db:
                for e in index.episodes:
                    if self._db.get_tracks_for_episode(e.episode_id):
                        n_with_srt += 1
                    if self._db.get_align_runs_for_episode(e.episode_id):
                        n_aligned += 1
            self.corpus_status_label.setText(
                f"Corpus : {len(index.episodes)} épisode(s), {n_norm} normalisé(s), {n_indexed} indexé(s) ; {n_with_srt} avec SRT, {n_aligned} aligné(s)."
            )
        else:
            self.season_filter_combo.clear()
            self.season_filter_combo.addItem("Toutes les saisons", None)
            self.corpus_status_label.setText("")

    def _refresh_season_filter_combo(self):
        """Met à jour le combo filtre saison (Toutes + Saison 1, 2, …)."""
        self.season_filter_combo.blockSignals(True)
        self.season_filter_combo.clear()
        self.season_filter_combo.addItem("Toutes les saisons", None)
        for sn in self.episodes_tree_model.get_season_numbers():
            self.season_filter_combo.addItem(f"Saison {sn}", sn)
        self.season_filter_combo.blockSignals(False)
        self._on_season_filter_changed()

    def _on_season_filter_changed(self):
        season = self.season_filter_combo.currentData()
        self.episodes_tree_proxy.set_season_filter(season)
        if season is not None:
            try:
                row = self.episodes_tree_model.get_season_numbers().index(season)
                source_ix = self.episodes_tree_model.index(row, 0, QModelIndex())
                proxy_ix = self.episodes_tree_proxy.mapFromSource(source_ix)
                if proxy_ix.isValid():
                    self.episodes_tree.expand(proxy_ix)
            except (ValueError, AttributeError):
                pass

    def _on_check_season_clicked(self):
        season = self.season_filter_combo.currentData()
        ids = self.episodes_tree_model.get_episode_ids_for_season(season)
        if not ids:
            return
        self.episodes_tree_model.set_checked(set(ids), True)

    def _refresh_profile_combos(self):
        """Met à jour les listes de profils (prédéfinis + personnalisés projet) dans les combos."""
        custom = self._store.load_custom_profiles() if self._store else {}
        profile_ids = get_all_profile_ids(custom)
        current_batch = self.norm_batch_profile_combo.currentText()
        current_inspect = self.inspect_profile_combo.currentText()
        self.norm_batch_profile_combo.clear()
        self.norm_batch_profile_combo.addItems(profile_ids)
        self.inspect_profile_combo.clear()
        self.inspect_profile_combo.addItems(profile_ids)
        if current_batch in profile_ids:
            self.norm_batch_profile_combo.setCurrentText(current_batch)
        elif self._config and self._config.normalize_profile in profile_ids:
            self.norm_batch_profile_combo.setCurrentText(self._config.normalize_profile)
        if current_inspect in profile_ids:
            self.inspect_profile_combo.setCurrentText(current_inspect)
        elif self._config and self._config.normalize_profile in profile_ids:
            self.inspect_profile_combo.setCurrentText(self._config.normalize_profile)

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
        row.addWidget(QLabel("Profil:"))
        self.inspect_profile_combo = QComboBox()
        self.inspect_profile_combo.addItems(list(PROFILES.keys()))
        self.inspect_profile_combo.setToolTip("Profil de normalisation pour « Normaliser cet épisode ». Profils prédéfinis + projet (profiles.json).")
        row.addWidget(self.inspect_profile_combo)
        self.inspect_norm_btn = QPushButton("Normaliser cet épisode")
        self.inspect_norm_btn.setToolTip("Applique la normalisation (RAW → CLEAN) à l'épisode affiché, avec le profil choisi.")
        self.inspect_norm_btn.clicked.connect(self._run_normalize_inspect_episode)
        row.addWidget(self.inspect_norm_btn)
        self.inspect_set_preferred_profile_btn = QPushButton("Définir comme préféré pour cet épisode")
        self.inspect_set_preferred_profile_btn.setToolTip("Mémorise le profil choisi comme préféré pour cet épisode (batch et Inspecteur).")
        self.inspect_set_preferred_profile_btn.clicked.connect(self._set_episode_preferred_profile)
        row.addWidget(self.inspect_set_preferred_profile_btn)
        self.inspect_segment_btn = QPushButton("Segmente l'épisode")
        self.inspect_segment_btn.clicked.connect(self._run_segment_episode)
        row.addWidget(self.inspect_segment_btn)
        self.inspect_export_segments_btn = QPushButton("Exporter les segments")
        self.inspect_export_segments_btn.clicked.connect(self._export_inspect_segments)
        row.addWidget(self.inspect_export_segments_btn)
        layout.addLayout(row)
        # Splitter horizontal : liste segments | zone RAW/CLEAN
        self.inspect_main_split = QSplitter(Qt.Orientation.Horizontal)
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setPlaceholderText("RAW")
        self.clean_edit = QPlainTextEdit()
        self.clean_edit.setPlaceholderText("CLEAN")
        self.inspect_segments_list = QListWidget()
        self.inspect_segments_list.setMinimumWidth(80)
        self.inspect_segments_list.currentItemChanged.connect(self._inspect_on_segment_selected)
        self.inspect_main_split.addWidget(self.inspect_segments_list)
        # Splitter vertical à droite : RAW | CLEAN (redimensionnable)
        self.inspect_right_split = QSplitter(Qt.Orientation.Vertical)
        self.inspect_right_split.addWidget(self.raw_edit)
        self.inspect_right_split.addWidget(self.clean_edit)
        self.inspect_main_split.addWidget(self.inspect_right_split)
        layout.addWidget(self.inspect_main_split)
        self._inspect_restore_splitter_sizes()
        self.inspect_stats_label = QLabel("Stats: —")
        layout.addWidget(self.inspect_stats_label)
        self.merge_examples_edit = QPlainTextEdit()
        self.merge_examples_edit.setReadOnly(True)
        self.merge_examples_edit.setMaximumHeight(120)
        layout.addWidget(QLabel("Exemples de fusions:"))
        layout.addWidget(self.merge_examples_edit)
        layout.addWidget(QLabel("Notes — à vérifier / à affiner (sauvegardé par épisode) :"))
        self.inspect_notes_edit = QPlainTextEdit()
        self.inspect_notes_edit.setPlaceholderText("Points à vérifier, à changer, à affiner pour cet épisode…")
        self.inspect_notes_edit.setMaximumHeight(100)
        layout.addWidget(self.inspect_notes_edit)
        self._inspect_current_episode_id: str | None = None
        self.inspect_segments_list.setVisible(False)
        self.tabs.addTab(w, "Inspecteur")

    def _inspect_restore_splitter_sizes(self) -> None:
        """Restaure les proportions des splitters de l'Inspecteur (QSettings)."""
        def to_sizes(val) -> list[int] | None:
            if val is None:
                return None
            if isinstance(val, (list, tuple)):
                try:
                    return [int(x) for x in val][:10]
                except (TypeError, ValueError):
                    return None
            if isinstance(val, str):
                try:
                    return [int(x) for x in val.split(",") if x.strip()][:10]
                except ValueError:
                    return None
            return None

        settings = QSettings()
        main = to_sizes(settings.value("inspecteur/mainSplitter"))
        right = to_sizes(settings.value("inspecteur/rightSplitter"))
        if main is not None and len(main) >= 2:
            self.inspect_main_split.setSizes(main)
        if right is not None and len(right) >= 2:
            self.inspect_right_split.setSizes(right)

    def _inspect_save_splitter_sizes(self) -> None:
        """Sauvegarde les proportions des splitters de l'Inspecteur (QSettings)."""
        settings = QSettings()
        settings.setValue("inspecteur/mainSplitter", self.inspect_main_split.sizes())
        settings.setValue("inspecteur/rightSplitter", self.inspect_right_split.sizes())

    def closeEvent(self, event):
        """Sauvegarde les tailles des splitters et les notes Inspecteur à la fermeture."""
        self._inspect_save_splitter_sizes()
        if self._inspect_current_episode_id and self._store:
            self._store.save_episode_notes(
                self._inspect_current_episode_id,
                self.inspect_notes_edit.toPlainText(),
            )
        super().closeEvent(event)

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
            self._inspect_current_episode_id = None
            self.raw_edit.clear()
            self.clean_edit.clear()
            self.inspect_stats_label.setText("Stats: —")
            self.merge_examples_edit.clear()
            self.inspect_notes_edit.clear()
            self.inspect_segments_list.clear()
            return
        if self._inspect_current_episode_id and self._inspect_current_episode_id != eid:
            self._store.save_episode_notes(
                self._inspect_current_episode_id,
                self.inspect_notes_edit.toPlainText(),
            )
        self._inspect_current_episode_id = eid
        self.inspect_notes_edit.setPlainText(self._store.load_episode_notes(eid))
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
        # Profil : préféré épisode > défaut source > config
        episode_preferred = self._store.load_episode_preferred_profiles()
        source_defaults = self._store.load_source_profile_defaults()
        index = self._store.load_series_index()
        ref = next((e for e in (index.episodes or []) if e.episode_id == eid), None) if index else None
        profile = (
            episode_preferred.get(eid)
            or (source_defaults.get(ref.source_id or "") if ref else None)
            or (self._config.normalize_profile if self._config else "default_en_v1")
        )
        if profile and profile in get_all_profile_ids():
            self.inspect_profile_combo.setCurrentText(profile)
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

    def _run_normalize_inspect_episode(self):
        eid = self.inspect_episode_combo.currentData()
        if not eid or not self._store:
            QMessageBox.warning(self, "Normalisation", "Sélectionnez un épisode et ouvrez un projet.")
            return
        if not self._store.has_episode_raw(eid):
            QMessageBox.warning(self, "Normalisation", "L'épisode doit d'abord être téléchargé (RAW).")
            return
        profile = self.inspect_profile_combo.currentText() or "default_en_v1"
        self._run_job([NormalizeEpisodeStep(eid, profile)])

    def _set_episode_preferred_profile(self):
        """Mémorise le profil choisi comme préféré pour l'épisode courant (Inspecteur)."""
        eid = self.inspect_episode_combo.currentData()
        if not eid or not self._store:
            QMessageBox.warning(self, "Profil préféré", "Sélectionnez un épisode et ouvrez un projet.")
            return
        profile = self.inspect_profile_combo.currentText() or "default_en_v1"
        preferred = self._store.load_episode_preferred_profiles()
        preferred[eid] = profile
        self._store.save_episode_preferred_profiles(preferred)
        self.statusBar().showMessage(f"Profil « {profile} » défini comme préféré pour {eid}.", 3000)

    def _run_segment_episode(self):
        eid = self.inspect_episode_combo.currentData()
        if not eid or not self._store or not self._db:
            QMessageBox.warning(self, "Segmentation", "Sélectionnez un épisode et ouvrez un projet.")
            return
        if not self._store.has_episode_clean(eid):
            QMessageBox.warning(self, "Segmentation", "L'épisode doit d'abord être normalisé (clean.txt).")
            return
        self._run_job([SegmentEpisodeStep(eid, lang_hint="en")])

    def _export_inspect_segments(self):
        """Exporte les segments de l'épisode affiché dans l'Inspecteur (TXT, CSV, TSV)."""
        eid = self.inspect_episode_combo.currentData()
        if not eid or not self._db:
            QMessageBox.warning(self, "Export segments", "Sélectionnez un épisode et ouvrez un projet.")
            return
        segments = self._db.get_segments_for_episode(eid)
        if not segments:
            QMessageBox.warning(
                self, "Export segments",
                "Aucun segment pour cet épisode. Lancez d'abord « Segmente l'épisode ».",
            )
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter les segments",
            "",
            "TXT — un segment par ligne (*.txt);;CSV (*.csv);;TSV (*.tsv)",
        )
        if not path:
            return
        path = Path(path)
        try:
            if path.suffix.lower() == ".txt" or "TXT" in (selected_filter or ""):
                export_segments_txt(segments, path)
            elif path.suffix.lower() == ".tsv" or "TSV" in (selected_filter or ""):
                export_segments_tsv(segments, path)
            else:
                export_segments_csv(segments, path)
            QMessageBox.information(
                self, "Export", f"Segments exportés : {len(segments)} segment(s).",
            )
        except Exception as e:
            logger.exception("Export segments Inspecteur")
            QMessageBox.critical(self, "Erreur", str(e))

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
        self.subs_import_batch_btn = QPushButton("Importer SRT en masse...")
        self.subs_import_batch_btn.setToolTip("Choisir un dossier, associer chaque fichier SRT/VTT à un épisode et une langue, puis lancer l'import.")
        self.subs_import_batch_btn.clicked.connect(self._subs_import_batch)
        row.addWidget(self.subs_import_batch_btn)
        layout.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Pistes pour l'épisode:"))
        layout.addLayout(row2)
        self.subs_tracks_list = QListWidget()
        self.subs_tracks_list.currentItemChanged.connect(self._subs_on_track_selected)
        layout.addWidget(self.subs_tracks_list)
        layout.addWidget(QLabel("Contenu SRT/VTT (modifiable) :"))
        self.subs_content_edit = QPlainTextEdit()
        self.subs_content_edit.setPlaceholderText("Sélectionnez une piste ci-dessus pour afficher et modifier le contenu…")
        self.subs_content_edit.setMinimumHeight(120)
        layout.addWidget(self.subs_content_edit)
        self.subs_save_btn = QPushButton("Sauvegarder et ré-importer")
        self.subs_save_btn.clicked.connect(self._subs_save_content)
        self.subs_save_btn.setEnabled(False)
        layout.addWidget(self.subs_save_btn)
        self._subs_editing_lang: str | None = None
        self._subs_editing_fmt: str | None = None
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
        self.subs_content_edit.clear()
        self.subs_save_btn.setEnabled(False)
        self._subs_editing_lang = None
        self._subs_editing_fmt = None
        eid = self.subs_episode_combo.currentData()
        if not eid or not self._db:
            return
        tracks = self._db.get_tracks_for_episode(eid)
        for t in tracks:
            lang = t.get("lang", "")
            fmt = t.get("format", "")
            nb = t.get("nb_cues", 0)
            item = QListWidgetItem(f"{lang} | {fmt} | {nb} cues")
            item.setData(Qt.ItemDataRole.UserRole, {"lang": lang, "format": fmt})
            self.subs_tracks_list.addItem(item)

    def _subs_on_track_selected(self, current: QListWidgetItem | None):
        self.subs_content_edit.clear()
        self.subs_save_btn.setEnabled(False)
        self._subs_editing_lang = None
        self._subs_editing_fmt = None
        if not current or not self._store:
            return
        eid = self.subs_episode_combo.currentData()
        if not eid:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return
        lang = data.get("lang", "")
        fmt = data.get("format", "srt")
        content_fmt = self._store.load_episode_subtitle_content(eid, lang)
        if not content_fmt:
            return
        content, detected_fmt = content_fmt
        self._subs_editing_lang = lang
        self._subs_editing_fmt = detected_fmt
        self.subs_content_edit.setPlainText(content)
        self.subs_save_btn.setEnabled(True)

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

    def _subs_import_batch(self):
        """Ouvre un dossier, scanne les SRT/VTT, affiche le dialogue de mapping puis lance l'import en masse."""
        if not self._store or not self._db:
            QMessageBox.warning(self, "Sous-titres", "Ouvrez un projet d'abord.")
            return
        index = self._store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Sous-titres", "Découvrez d'abord les épisodes (onglet Corpus).")
            return
        folder = QFileDialog.getExistingDirectory(self, "Choisir un dossier contenant des SRT/VTT")
        if not folder:
            return
        folder_path = Path(folder)
        rows: list[tuple[str, str | None, str | None]] = []
        for p in folder_path.glob("*.srt"):
            ep, lang = _parse_subtitle_filename(p)
            rows.append((str(p.resolve()), ep, lang))
        for p in folder_path.glob("*.vtt"):
            ep, lang = _parse_subtitle_filename(p)
            rows.append((str(p.resolve()), ep, lang))
        if not rows:
            QMessageBox.information(self, "Import", "Aucun fichier .srt ou .vtt trouvé dans ce dossier.")
            return
        episode_ids = [e.episode_id for e in index.episodes]
        langs = self._store.load_project_languages() if self._store else None
        dlg = SubtitleBatchImportDialog(self, episode_ids, rows, languages=langs)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result:
            return
        steps = [ImportSubtitlesStep(ep, lang, path) for path, ep, lang in dlg.result]
        self._run_job(steps)
        self._refresh_subs_tracks()
        self._refresh_episodes_from_store()
        self.statusBar().showMessage(f"Import en masse lancé : {len(steps)} fichier(s).", 5000)

    def _subs_save_content(self):
        """Sauvegarde le contenu SRT/VTT modifié et ré-importe pour mettre à jour la DB."""
        eid = self.subs_episode_combo.currentData()
        if not eid or not self._store or not self._db:
            return
        if not self._subs_editing_lang or not self._subs_editing_fmt:
            QMessageBox.warning(self, "Sous-titres", "Sélectionnez une piste à modifier.")
            return
        content = self.subs_content_edit.toPlainText()
        try:
            path = self._store.save_episode_subtitle_content(
                eid, self._subs_editing_lang, content, self._subs_editing_fmt
            )
            self._run_job([ImportSubtitlesStep(eid, self._subs_editing_lang, str(path))])
            self._refresh_subs_tracks()
        except Exception as e:
            logger.exception("Sauvegarde SRT/VTT")
            QMessageBox.critical(self, "Erreur", str(e))

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
        self.align_accepted_only_cb = QCheckBox("Liens acceptés uniquement")
        self.align_accepted_only_cb.setToolTip("Export concordancier, rapport HTML et stats : ne considérer que les liens acceptés")
        row.addWidget(self.align_accepted_only_cb)
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
        self._run_job([AlignEpisodeStep(eid, pivot_lang="en", target_langs=["fr"])])

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
        """Exporte le concordancier parallèle (segment + EN + FR) en CSV, TSV ou JSONL."""
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
            status_filter = "accepted" if self.align_accepted_only_cb.isChecked() else None
            rows = self._db.get_parallel_concordance(eid, run_id, status_filter=status_filter)
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
            status_filter = "accepted" if self.align_accepted_only_cb.isChecked() else None
            stats = self._db.get_align_stats_for_run(eid, run_id, status_filter=status_filter)
            sample = self._db.get_parallel_concordance(eid, run_id, status_filter=status_filter)
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
            status_filter = "accepted" if self.align_accepted_only_cb.isChecked() else None
            stats = self._db.get_align_stats_for_run(eid, run_id, status_filter=status_filter)
            by_status = stats.get("by_status") or {}
            msg = (
                f"Épisode: {stats.get('episode_id', '')}\n"
                f"Run: {stats.get('run_id', '')}\n\n"
                f"Liens totaux: {stats.get('nb_links', 0)}\n"
                f"Liens pivot (segment↔EN): {stats.get('nb_pivot', 0)}\n"
                f"Liens target (EN↔FR): {stats.get('nb_target', 0)}\n"
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

    def _build_tab_personnages(self):
        """Onglet Personnages : liste des noms canoniques + noms par langue (pour assignation et propagation)."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "Liste des personnages du projet (noms canoniques et par langue). "
            "Utilisée pour l’assignation et la propagation des noms (backlog §8)."
        ))
        self.personnages_table = QTableWidget()
        self.personnages_table.setColumnCount(4)
        self.personnages_table.setHorizontalHeaderLabels(["Id", "Canonique", "EN", "FR"])
        self.personnages_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.personnages_table)
        btn_row = QHBoxLayout()
        self.personnages_add_btn = QPushButton("Nouveau")
        self.personnages_add_btn.clicked.connect(self._personnages_add_row)
        self.personnages_remove_btn = QPushButton("Supprimer")
        self.personnages_remove_btn.clicked.connect(self._personnages_remove_row)
        self.personnages_save_btn = QPushButton("Enregistrer")
        self.personnages_save_btn.clicked.connect(self._personnages_save)
        btn_row.addWidget(self.personnages_add_btn)
        btn_row.addWidget(self.personnages_remove_btn)
        btn_row.addWidget(self.personnages_save_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addWidget(QLabel("Assignation (segment ou cue → personnage) :"))
        assign_row = QHBoxLayout()
        assign_row.addWidget(QLabel("Épisode:"))
        self.personnages_episode_combo = QComboBox()
        self.personnages_episode_combo.setMinimumWidth(200)
        assign_row.addWidget(self.personnages_episode_combo)
        assign_row.addWidget(QLabel("Source:"))
        self.personnages_source_combo = QComboBox()
        self.personnages_source_combo.addItem("Segments (phrases)", "segments")
        self.personnages_source_combo.addItem("Cues EN", "cues_en")
        self.personnages_source_combo.addItem("Cues FR", "cues_fr")
        self.personnages_source_combo.addItem("Cues IT", "cues_it")
        assign_row.addWidget(self.personnages_source_combo)
        self.personnages_load_assign_btn = QPushButton("Charger")
        self.personnages_load_assign_btn.clicked.connect(self._personnages_load_assignments)
        assign_row.addWidget(self.personnages_load_assign_btn)
        layout.addLayout(assign_row)
        self.personnages_assign_table = QTableWidget()
        self.personnages_assign_table.setColumnCount(3)
        self.personnages_assign_table.setHorizontalHeaderLabels(["ID", "Texte", "Personnage"])
        self.personnages_assign_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.personnages_assign_table)
        self.personnages_save_assign_btn = QPushButton("Enregistrer assignations")
        self.personnages_save_assign_btn.clicked.connect(self._personnages_save_assignments)
        layout.addWidget(self.personnages_save_assign_btn)
        self.personnages_propagate_btn = QPushButton("Propager vers les autres fichiers")
        self.personnages_propagate_btn.setToolTip("Utilise les liens d'alignement pour propager les noms de personnages vers les positions alignées (fichiers cibles).")
        self.personnages_propagate_btn.clicked.connect(self._personnages_propagate)
        layout.addWidget(self.personnages_propagate_btn)
        self.tabs.addTab(w, "Personnages")

    def _personnages_add_row(self):
        row = self.personnages_table.rowCount()
        self.personnages_table.insertRow(row)
        for c in range(self.personnages_table.columnCount()):
            self.personnages_table.setItem(row, c, QTableWidgetItem(""))

    def _personnages_remove_row(self):
        row = self.personnages_table.currentRow()
        if row >= 0:
            self.personnages_table.removeRow(row)

    def _personnages_save(self):
        if not self._store:
            QMessageBox.warning(self, "Personnages", "Ouvrez un projet d'abord.")
            return
        langs = self._store.load_project_languages()
        characters = []
        for row in range(self.personnages_table.rowCount()):
            id_item = self.personnages_table.item(row, 0)
            canon_item = self.personnages_table.item(row, 1)
            cid = (id_item.text() or "").strip() if id_item else ""
            canon = (canon_item.text() or "").strip() if canon_item else ""
            if not cid and not canon:
                continue
            names_by_lang = {}
            for i, lang in enumerate(langs):
                if 2 + i < self.personnages_table.columnCount():
                    item = self.personnages_table.item(row, 2 + i)
                    if item and (item.text() or "").strip():
                        names_by_lang[lang] = (item.text() or "").strip()
            characters.append({
                "id": cid or canon.lower().replace(" ", "_"),
                "canonical": canon or cid,
                "names_by_lang": names_by_lang,
            })
        self._store.save_character_names(characters)
        self.statusBar().showMessage("Personnages enregistrés.", 3000)

    def _refresh_personnages(self):
        """Charge la liste des personnages depuis le projet et remplit la table + combo épisodes assignation."""
        self.personnages_table.setRowCount(0)
        self.personnages_episode_combo.clear()
        if not self._store:
            return
        langs = self._store.load_project_languages()
        self.personnages_table.setColumnCount(2 + len(langs))
        self.personnages_table.setHorizontalHeaderLabels(["Id", "Canonique"] + [lang.upper() for lang in langs])
        self.personnages_source_combo.clear()
        self.personnages_source_combo.addItem("Segments", "segments")
        for lang in langs:
            self.personnages_source_combo.addItem(f"Cues {lang.upper()}", f"cues_{lang}")
        characters = self._store.load_character_names()
        for ch in characters:
            row = self.personnages_table.rowCount()
            self.personnages_table.insertRow(row)
            names = ch.get("names_by_lang") or {}
            self.personnages_table.setItem(row, 0, QTableWidgetItem(ch.get("id") or ""))
            self.personnages_table.setItem(row, 1, QTableWidgetItem(ch.get("canonical") or ""))
            for i, lang in enumerate(langs):
                self.personnages_table.setItem(row, 2 + i, QTableWidgetItem(names.get(lang, "")))
        index = self._store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.personnages_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)

    def _personnages_load_assignments(self):
        """Charge les segments ou cues de l'épisode/source et remplit la table d'assignation."""
        eid = self.personnages_episode_combo.currentData()
        source_key = self.personnages_source_combo.currentData() or "segments"
        if not eid or not self._db or not self._store:
            QMessageBox.warning(self, "Personnages", "Ouvrez un projet et sélectionnez un épisode.")
            return
        character_ids = [ch.get("id") or ch.get("canonical", "") for ch in self._store.load_character_names() if ch.get("id") or ch.get("canonical")]
        assignments = self._store.load_character_assignments()
        source_type = "segment" if source_key == "segments" else "cue"
        assign_map = {a["source_id"]: a.get("character_id") or "" for a in assignments if a.get("episode_id") == eid and a.get("source_type") == source_type}
        self.personnages_assign_table.setRowCount(0)
        if source_key == "segments":
            segments = self._db.get_segments_for_episode(eid, kind="sentence")
            for s in segments:
                sid = s.get("segment_id") or ""
                text = (s.get("text") or "")[:80]
                if len((s.get("text") or "")) > 80:
                    text += "…"
                row = self.personnages_assign_table.rowCount()
                self.personnages_assign_table.insertRow(row)
                self.personnages_assign_table.setItem(row, 0, QTableWidgetItem(sid))
                self.personnages_assign_table.setItem(row, 1, QTableWidgetItem(text))
                combo = QComboBox()
                combo.addItem("—", "")
                for cid in character_ids:
                    combo.addItem(cid, cid)
                idx = combo.findData(assign_map.get(sid, ""))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                self.personnages_assign_table.setCellWidget(row, 2, combo)
        else:
            lang = source_key.replace("cues_", "")
            cues = self._db.get_cues_for_episode_lang(eid, lang)
            for c in cues:
                cid = c.get("cue_id") or ""
                text = (c.get("text_clean") or c.get("text_raw") or "")[:80]
                if len((c.get("text_clean") or c.get("text_raw") or "")) > 80:
                    text += "…"
                row = self.personnages_assign_table.rowCount()
                self.personnages_assign_table.insertRow(row)
                self.personnages_assign_table.setItem(row, 0, QTableWidgetItem(cid))
                self.personnages_assign_table.setItem(row, 1, QTableWidgetItem(text))
                combo = QComboBox()
                combo.addItem("—", "")
                for char_id in character_ids:
                    combo.addItem(char_id, char_id)
                idx = combo.findData(assign_map.get(cid, ""))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                self.personnages_assign_table.setCellWidget(row, 2, combo)

    def _personnages_save_assignments(self):
        """Enregistre les assignations (table) dans character_assignments.json."""
        eid = self.personnages_episode_combo.currentData()
        source_key = self.personnages_source_combo.currentData() or "segments"
        if not eid or not self._store:
            QMessageBox.warning(self, "Personnages", "Ouvrez un projet et sélectionnez un épisode.")
            return
        source_type = "segment" if source_key == "segments" else "cue"
        new_assignments = []
        for row in range(self.personnages_assign_table.rowCount()):
            id_item = self.personnages_assign_table.item(row, 0)
            source_id = (id_item.text() or "").strip() if id_item else ""
            combo = self.personnages_assign_table.cellWidget(row, 2)
            if not isinstance(combo, QComboBox):
                continue
            character_id = (combo.currentData() or combo.currentText() or "").strip()
            if source_id and character_id:
                new_assignments.append({"episode_id": eid, "source_type": source_type, "source_id": source_id, "character_id": character_id})
        all_assignments = self._store.load_character_assignments()
        all_assignments = [a for a in all_assignments if not (a.get("episode_id") == eid and a.get("source_type") == source_type)]
        all_assignments.extend(new_assignments)
        self._store.save_character_assignments(all_assignments)
        self.statusBar().showMessage(f"Assignations enregistrées : {len(new_assignments)}.", 3000)

    def _personnages_propagate(self):
        """Propagation des noms de personnages via les liens d'alignement (stub : à compléter avec écriture vers fichiers/DB)."""
        if not self._store or not self._db:
            QMessageBox.warning(self, "Personnages", "Ouvrez un projet d'abord.")
            return
        eid = self.personnages_episode_combo.currentData()
        if not eid:
            QMessageBox.warning(self, "Personnages", "Sélectionnez un épisode (section Assignation).")
            return
        assignments = self._store.load_character_assignments()
        episode_assignments = [a for a in assignments if a.get("episode_id") == eid]
        if not episode_assignments:
            QMessageBox.information(self, "Propagation", "Aucune assignation pour cet épisode. Enregistrez des assignations d'abord.")
            return
        runs = self._db.get_align_runs_for_episode(eid)
        if not runs:
            QMessageBox.information(self, "Propagation", "Aucun run d'alignement pour cet épisode. Lancez l'alignement (onglet Alignement) d'abord.")
            return
        assign_map = {(a.get("source_type"), a.get("source_id")): a.get("character_id") for a in episode_assignments if a.get("source_id") and a.get("character_id")}
        run_id = runs[0].get("align_run_id")
        links = self._db.query_alignment_for_episode(eid, run_id=run_id)
        for link in links:
            segment_id = link.get("segment_id")
            cue_id = link.get("cue_id")
            char_id = assign_map.get(("segment", segment_id)) or assign_map.get(("cue", cue_id))
            if not char_id:
                continue
        self.statusBar().showMessage(
            f"Propagation : {len(episode_assignments)} assignation(s), {len(links)} lien(s) ; écriture vers fichiers cibles à implémenter (backlog §8).",
            6000,
        )

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
