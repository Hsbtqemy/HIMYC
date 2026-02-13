"""Onglet Sous-titres : pistes par épisode, import SRT/VTT, édition contenu."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.pipeline.tasks import DownloadOpenSubtitlesStep, ImportSubtitlesStep
from howimetyourcorpus.app.dialogs import OpenSubtitlesDownloadDialog, SubtitleBatchImportDialog

logger = logging.getLogger(__name__)


def _parse_subtitle_filename(path: Path) -> tuple[str | None, str | None]:
    """Extrait (episode_id, lang) du nom de fichier. Ex. S01E01_en.srt -> (S01E01, en)."""
    name = path.name
    m = re.match(r"(?i)(S\d+E\d+)[_\-\.]?(\w{2})\.(srt|vtt)$", name)
    if not m:
        return (None, None)
    ep = m.group(1).upper()
    lang = m.group(2).lower()
    return (ep, lang)


class SubtitleTabWidget(QWidget):
    """Widget de l'onglet Sous-titres : épisode, pistes, import fichier/masse, édition contenu."""

    def __init__(
        self,
        get_store: Callable[[], object],
        get_db: Callable[[], object],
        run_job: Callable[[list], None],
        refresh_episodes: Callable[[], None],
        show_status: Callable[[str, int], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._run_job = run_job
        self._refresh_episodes = refresh_episodes
        self._show_status = show_status

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Épisode:"))
        self.subs_episode_combo = QComboBox()
        self.subs_episode_combo.currentIndexChanged.connect(self._on_episode_changed)
        row.addWidget(self.subs_episode_combo)
        row.addWidget(QLabel("Langue:"))
        self.subs_lang_combo = QComboBox()
        self.subs_lang_combo.addItems(["en", "fr", "it"])
        self.subs_lang_combo.setToolTip(
            "Le format SRT ne contient pas de langue. Choisissez ici la langue de ce fichier (EN, FR, etc.)."
        )
        row.addWidget(self.subs_lang_combo)
        self.subs_import_btn = QPushButton("Importer SRT/VTT...")
        self.subs_import_btn.clicked.connect(self._import_file)
        row.addWidget(self.subs_import_btn)
        self.subs_import_batch_btn = QPushButton("Importer SRT en masse...")
        self.subs_import_batch_btn.setToolTip(
            "Choisir un dossier. Épisode et langue sont devinés d'après le nom (ex. S01E01_fr.srt → S01E01, fr). "
            "Vérifiez ou corrigez dans le tableau avant d'importer."
        )
        self.subs_import_batch_btn.clicked.connect(self._import_batch)
        row.addWidget(self.subs_import_batch_btn)
        self.subs_opensubtitles_btn = QPushButton("Télécharger depuis OpenSubtitles…")
        self.subs_opensubtitles_btn.setToolTip(
            "Télécharger des sous-titres depuis OpenSubtitles (clé API requise)."
        )
        self.subs_opensubtitles_btn.clicked.connect(self._import_opensubtitles)
        row.addWidget(self.subs_opensubtitles_btn)
        layout.addLayout(row)
        help_subs = QLabel(
            "Les fichiers SRT/VTT ne déclarent pas leur langue. À l'import : choisir la langue ci-dessus (ou nommer en masse S01E01_fr.srt). "
            "Ces pistes (EN, FR, …) servent de pivot et cible dans l'onglet Alignement après segmentation (Inspecteur)."
        )
        help_subs.setStyleSheet("color: gray; font-size: 0.9em;")
        help_subs.setWordWrap(True)
        layout.addWidget(help_subs)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Pistes pour l'épisode:"))
        self.subs_delete_track_btn = QPushButton("Supprimer la piste sélectionnée")
        self.subs_delete_track_btn.setToolTip("Supprime la piste (ex. mauvaise langue) en base et le fichier sur disque.")
        self.subs_delete_track_btn.clicked.connect(self._delete_selected_track)
        self.subs_delete_track_btn.setEnabled(False)
        row2.addStretch()
        row2.addWidget(self.subs_delete_track_btn)
        layout.addLayout(row2)
        self.subs_tracks_list = QListWidget()
        self.subs_tracks_list.currentItemChanged.connect(self._on_track_selected)
        layout.addWidget(self.subs_tracks_list)
        layout.addWidget(QLabel("Contenu SRT/VTT (modifiable) :"))
        self.subs_content_edit = QPlainTextEdit()
        self.subs_content_edit.setPlaceholderText(
            "Sélectionnez une piste ci-dessus pour afficher et modifier le contenu…"
        )
        self.subs_content_edit.setMinimumHeight(120)
        layout.addWidget(self.subs_content_edit)
        self.subs_save_btn = QPushButton("Sauvegarder et ré-importer")
        self.subs_save_btn.clicked.connect(self._save_content)
        self.subs_save_btn.setEnabled(False)
        layout.addWidget(self.subs_save_btn)
        self._editing_lang: str | None = None
        self._editing_fmt: str | None = None

    def set_languages(self, langs: list[str]) -> None:
        """Met à jour la liste des langues (appelé quand les langues du projet changent)."""
        self.subs_lang_combo.clear()
        self.subs_lang_combo.addItems(langs)

    def refresh(self) -> None:
        """Recharge la liste des épisodes et les pistes (appelé après ouverture projet / import)."""
        self.subs_episode_combo.clear()
        store = self._get_store()
        if not store:
            return
        index = store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.subs_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
        self._on_episode_changed()

    def _on_episode_changed(self) -> None:
        self.subs_tracks_list.clear()
        self.subs_content_edit.clear()
        self.subs_save_btn.setEnabled(False)
        self.subs_delete_track_btn.setEnabled(False)
        self._editing_lang = None
        self._editing_fmt = None
        eid = self.subs_episode_combo.currentData()
        db = self._get_db()
        if not eid or not db:
            return
        tracks = db.get_tracks_for_episode(eid)
        for t in tracks:
            lang = t.get("lang", "")
            fmt = t.get("format", "")
            nb = t.get("nb_cues", 0)
            item = QListWidgetItem(f"{lang} | {fmt} | {nb} cues")
            item.setData(Qt.ItemDataRole.UserRole, {"lang": lang, "format": fmt})
            self.subs_tracks_list.addItem(item)

    def _on_track_selected(self, current: QListWidgetItem | None) -> None:
        self.subs_content_edit.clear()
        self.subs_save_btn.setEnabled(False)
        self.subs_delete_track_btn.setEnabled(bool(current))
        self._editing_lang = None
        self._editing_fmt = None
        if not current:
            return
        store = self._get_store()
        if not store:
            return
        eid = self.subs_episode_combo.currentData()
        if not eid:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return
        lang = data.get("lang", "")
        fmt = data.get("format", "srt")
        content_fmt = store.load_episode_subtitle_content(eid, lang)
        if not content_fmt:
            return
        content, detected_fmt = content_fmt
        self._editing_lang = lang
        self._editing_fmt = detected_fmt
        self.subs_content_edit.setPlainText(content)
        self.subs_save_btn.setEnabled(True)

    def _delete_selected_track(self) -> None:
        current = self.subs_tracks_list.currentItem()
        store = self._get_store()
        db = self._get_db()
        if not current or not store or not db:
            return
        eid = self.subs_episode_combo.currentData()
        data = current.data(Qt.ItemDataRole.UserRole)
        if not eid or not data or not isinstance(data, dict):
            return
        lang = data.get("lang", "")
        if not lang:
            return
        reply = QMessageBox.question(
            self,
            "Supprimer la piste",
            f"Supprimer la piste {lang} pour cet épisode ? (base de données et fichier sur disque, irréversible)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        db.delete_subtitle_track(eid, lang)
        store.remove_episode_subtitle(eid, lang)
        self._on_episode_changed()
        self._refresh_episodes()
        self._show_status(f"Piste {lang} supprimée.", 3000)

    def _import_file(self) -> None:
        eid = self.subs_episode_combo.currentData()
        store = self._get_store()
        db = self._get_db()
        if not eid or not store or not db:
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
        self.refresh()

    def _import_batch(self) -> None:
        store = self._get_store()
        db = self._get_db()
        if not store or not db:
            QMessageBox.warning(self, "Sous-titres", "Ouvrez un projet d'abord.")
            return
        index = store.load_series_index()
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
        langs = store.load_project_languages() if store else None
        dlg = SubtitleBatchImportDialog(self, episode_ids, rows, languages=langs)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result:
            return
        steps = [ImportSubtitlesStep(ep, lang, path) for path, ep, lang in dlg.result]
        self._run_job(steps)
        self.refresh()
        self._refresh_episodes()
        self._show_status(f"Import en masse lancé : {len(steps)} fichier(s).", 5000)

    def _import_opensubtitles(self) -> None:
        store = self._get_store()
        if not store:
            QMessageBox.warning(self, "Sous-titres", "Ouvrez un projet d'abord.")
            return
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(self, "Sous-titres", "Découvrez d'abord les épisodes (onglet Corpus).")
            return
        config_extra = store.load_config_extra()
        api_key = config_extra.get("opensubtitles_api_key") or ""
        series_imdb_id = config_extra.get("series_imdb_id") or ""
        episode_refs = [(e.episode_id, e.season, e.episode) for e in index.episodes]
        langs = store.load_project_languages()
        dlg = OpenSubtitlesDownloadDialog(
            self,
            episode_refs=episode_refs,
            api_key=api_key if isinstance(api_key, str) else "",
            series_imdb_id=series_imdb_id if isinstance(series_imdb_id, str) else "",
            languages=langs,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result:
            return
        api_key_val, imdb_id, lang, selected = dlg.result
        store.save_config_extra({
            "opensubtitles_api_key": api_key_val,
            "series_imdb_id": imdb_id,
        })
        steps = [
            DownloadOpenSubtitlesStep(ep_id, season, episode, lang, api_key_val, imdb_id)
            for ep_id, season, episode in selected
        ]
        self._run_job(steps)
        self.refresh()
        self._refresh_episodes()
        self._show_status(f"Téléchargement OpenSubtitles lancé : {len(steps)} épisode(s).", 5000)

    def _save_content(self) -> None:
        eid = self.subs_episode_combo.currentData()
        store = self._get_store()
        db = self._get_db()
        if not eid or not store or not db:
            return
        if not self._editing_lang or not self._editing_fmt:
            QMessageBox.warning(self, "Sous-titres", "Sélectionnez une piste à modifier.")
            return
        content = self.subs_content_edit.toPlainText()
        try:
            path = store.save_episode_subtitle_content(
                eid, self._editing_lang, content, self._editing_fmt
            )
            self._run_job([ImportSubtitlesStep(eid, self._editing_lang, str(path))])
            self.refresh()
        except Exception as e:
            logger.exception("Sauvegarde SRT/VTT")
            QMessageBox.critical(self, "Erreur", str(e))
