"""Onglet Sous-titres : pistes par épisode, import SRT/VTT, édition contenu."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
from howimetyourcorpus.core.normalize.profiles import get_all_profile_ids
from howimetyourcorpus.core.subtitles.parsers import cues_to_srt
from howimetyourcorpus.app.feedback import show_error, warn_precondition
from howimetyourcorpus.app.export_dialog import normalize_export_path
from howimetyourcorpus.app.dialogs import OpenSubtitlesDownloadDialog, SubtitleBatchImportDialog
from howimetyourcorpus.app.qt_helpers import refill_combo_preserve_selection

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
        self._job_busy = False

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self._subs_episode_label = QLabel("Épisode:")
        row.addWidget(self._subs_episode_label)
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
        self.subs_export_final_btn = QPushButton("Exporter SRT final…")
        self.subs_export_final_btn.setToolTip(
            "§15.2 — Exporte la piste sélectionnée en SRT (timecodes + text_clean, avec noms personnages si propagation faite)."
        )
        self.subs_export_final_btn.clicked.connect(self._export_srt_final)
        self.subs_export_final_btn.setEnabled(False)
        row2.addWidget(self.subs_export_final_btn)
        self.subs_delete_track_btn = QPushButton("Supprimer la piste sélectionnée")
        self.subs_delete_track_btn.setToolTip("Supprime la piste (ex. mauvaise langue) en base et le fichier sur disque.")
        self.subs_delete_track_btn.clicked.connect(self._delete_selected_track)
        self.subs_delete_track_btn.setEnabled(False)
        row2.addStretch()
        row2.addWidget(self.subs_delete_track_btn)
        layout.addLayout(row2)
        row_norm = QHBoxLayout()
        row_norm.addWidget(QLabel("§11 Profil (piste):"))
        self.subs_norm_profile_combo = QComboBox()
        self.subs_norm_profile_combo.setToolTip(
            "Profil de normalisation pour « Normaliser la piste » (fusion césures, espaces). Même moteur que les transcripts."
        )
        row_norm.addWidget(self.subs_norm_profile_combo)
        self.subs_norm_btn = QPushButton("Normaliser la piste")
        self.subs_norm_btn.setToolTip(
            "Applique le profil aux sous-titres de la piste sélectionnée : text_clean mis à jour en base (text_raw inchangé)."
        )
        self.subs_norm_btn.clicked.connect(self._normalize_track)
        self.subs_norm_btn.setEnabled(False)
        row_norm.addWidget(self.subs_norm_btn)
        self.subs_rewrite_srt_check = QCheckBox("Réécrire le fichier SRT après normalisation")
        self.subs_rewrite_srt_check.setToolTip(
            "Si coché, le fichier SRT sur disque est réécrit à partir de text_clean (écrase l'original)."
        )
        self.subs_rewrite_srt_check.setChecked(False)
        row_norm.addWidget(self.subs_rewrite_srt_check)
        row_norm.addStretch()
        layout.addLayout(row_norm)
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
        self._refresh_action_buttons()

    def set_languages(self, langs: list[str]) -> None:
        """Met à jour la liste des langues (appelé quand les langues du projet changent)."""
        self.subs_lang_combo.clear()
        self.subs_lang_combo.addItems(langs)

    def set_episode_selector_visible(self, visible: bool) -> None:
        """§15.4 — Masque ou affiche le sélecteur d'épisode (quand intégré dans l'onglet fusionné)."""
        self._subs_episode_label.setVisible(visible)
        self.subs_episode_combo.setVisible(visible)

    def set_episode_and_load(self, episode_id: str) -> None:
        """§15.4 — Sélectionne l'épisode donné et charge ses pistes (synchro avec Inspecteur)."""
        for i in range(self.subs_episode_combo.count()):
            if self.subs_episode_combo.itemData(i) == episode_id:
                if self.subs_episode_combo.currentIndex() != i:
                    self.subs_episode_combo.setCurrentIndex(i)
                else:
                    self._on_episode_changed()
                return
        self._on_episode_changed()

    def refresh(self) -> None:
        """Recharge la liste des épisodes et les pistes (appelé après ouverture projet / import)."""
        store = self._get_store()
        if not store:
            refill_combo_preserve_selection(
                self.subs_episode_combo,
                items=[],
                current_data=None,
            )
            self._refresh_action_buttons()
            return
        index = store.load_series_index()
        current_episode = self.subs_episode_combo.currentData()
        items: list[tuple[str, str]] = []
        if index and index.episodes:
            items = [(f"{e.episode_id} - {e.title}", e.episode_id) for e in index.episodes]
        refill_combo_preserve_selection(
            self.subs_episode_combo,
            items=items,
            current_data=current_episode,
        )
        self._on_episode_changed()

    def _on_episode_changed(self) -> None:
        current_track_data = None
        current_track_item = self.subs_tracks_list.currentItem()
        if current_track_item:
            data = current_track_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                current_track_data = data
        self.subs_tracks_list.clear()
        self.subs_content_edit.clear()
        self._editing_lang = None
        self._editing_fmt = None
        store = self._get_store()
        custom = store.load_custom_profiles() if store else {}
        profile_ids = get_all_profile_ids(custom)
        current = self.subs_norm_profile_combo.currentText()
        self.subs_norm_profile_combo.clear()
        self.subs_norm_profile_combo.addItems(profile_ids)
        if current in profile_ids:
            self.subs_norm_profile_combo.setCurrentText(current)
        eid = self.subs_episode_combo.currentData()
        db = self._get_db()
        if not eid or not db:
            self._refresh_action_buttons()
            return
        try:
            tracks = db.get_tracks_for_episode(eid)
        except Exception as e:
            logger.exception("Chargement pistes sous-titres")
            show_error(self, exc=e, context="Chargement pistes sous-titres")
            self._refresh_action_buttons()
            return
        selected_item: QListWidgetItem | None = None
        for t in tracks:
            lang = t.get("lang", "")
            fmt = t.get("format", "")
            nb = t.get("nb_cues", 0)
            item = QListWidgetItem(f"{lang} | {fmt} | {nb} cues")
            item.setData(Qt.ItemDataRole.UserRole, {"lang": lang, "format": fmt})
            self.subs_tracks_list.addItem(item)
            if (
                isinstance(current_track_data, dict)
                and lang == current_track_data.get("lang")
                and fmt == current_track_data.get("format")
            ):
                selected_item = item
        if selected_item is not None:
            self.subs_tracks_list.setCurrentItem(selected_item)
        self._refresh_action_buttons()

    def _on_track_selected(self, current: QListWidgetItem | None) -> None:
        self.subs_content_edit.clear()
        self._editing_lang = None
        self._editing_fmt = None
        if not current:
            self._refresh_action_buttons()
            return
        store = self._get_store()
        if not store:
            self._refresh_action_buttons()
            return
        eid = self.subs_episode_combo.currentData()
        if not eid:
            self._refresh_action_buttons()
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            self._refresh_action_buttons()
            return
        lang = data.get("lang", "")
        fmt = data.get("format", "srt")
        try:
            content_fmt = store.load_episode_subtitle_content(eid, lang)
        except Exception as e:
            logger.exception("Chargement contenu sous-titres")
            show_error(self, exc=e, context="Chargement sous-titres")
            self._refresh_action_buttons()
            return
        if not content_fmt:
            self._refresh_action_buttons()
            return
        content, detected_fmt = content_fmt
        self._editing_lang = lang
        self._editing_fmt = detected_fmt
        self.subs_content_edit.setPlainText(content)
        self._refresh_action_buttons()

    def _refresh_action_buttons(self) -> None:
        has_project = bool(self._get_store() and self._get_db())
        has_episode = bool(self.subs_episode_combo.currentData())
        has_track = self.subs_tracks_list.currentItem() is not None
        editable = bool(self._editing_lang and self._editing_fmt)
        controls_enabled = not self._job_busy
        self.subs_episode_combo.setEnabled(has_project and controls_enabled)
        self.subs_lang_combo.setEnabled(has_project and controls_enabled)
        self.subs_import_btn.setEnabled(has_project and has_episode and controls_enabled)
        self.subs_import_batch_btn.setEnabled(has_project and controls_enabled)
        self.subs_opensubtitles_btn.setEnabled(has_project and controls_enabled)
        self.subs_delete_track_btn.setEnabled(has_track and controls_enabled)
        self.subs_export_final_btn.setEnabled(has_track and controls_enabled)
        self.subs_norm_btn.setEnabled(has_track and controls_enabled)
        self.subs_norm_profile_combo.setEnabled(has_track and controls_enabled)
        self.subs_rewrite_srt_check.setEnabled(has_track and controls_enabled)
        self.subs_save_btn.setEnabled(editable and controls_enabled)

    def set_job_busy(self, busy: bool) -> None:
        """Désactive les actions de mutation pendant un job de fond."""
        self._job_busy = busy
        self._refresh_action_buttons()

    def _delete_selected_track(self) -> None:
        resolved = self._resolve_selected_track_or_warn(title="Suppression piste")
        if resolved is None:
            return
        eid, lang, store, db = resolved
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
        db.delete_align_runs_for_episode(eid)
        store.remove_episode_subtitle(eid, lang)
        self._on_episode_changed()
        self._refresh_episodes()
        self._show_status(f"Piste {lang} supprimée.", 3000)

    def _resolve_store_db_or_warn(self, *, title: str = "Sous-titres") -> tuple[object, object] | None:
        store = self._get_store()
        db = self._get_db()
        if not store or not db:
            warn_precondition(
                self,
                title,
                "Ouvrez un projet d'abord.",
                next_step="Pilotage: ouvrez/créez un projet puis revenez dans l'Inspecteur.",
            )
            return None
        return store, db

    def _resolve_index_or_warn(self, store: object, *, title: str = "Sous-titres"):
        index = store.load_series_index()
        if not index or not index.episodes:
            warn_precondition(
                self,
                title,
                "Découvrez d'abord les épisodes.",
                next_step="Pilotage > Corpus: cliquez sur « Découvrir épisodes ».",
            )
            return None
        return index

    def _resolve_episode_context_or_warn(self, *, title: str = "Sous-titres") -> tuple[str, object, object] | None:
        resolved = self._resolve_store_db_or_warn(title=title)
        if resolved is None:
            return None
        store, db = resolved
        eid = self.subs_episode_combo.currentData()
        if not eid:
            warn_precondition(
                self,
                title,
                "Sélectionnez un épisode.",
                next_step="Inspecteur: choisissez un épisode dans le sélecteur.",
            )
            return None
        return str(eid), store, db

    def _resolve_selected_track_or_warn(
        self,
        *,
        title: str = "Sous-titres",
    ) -> tuple[str, str, object, object] | None:
        resolved = self._resolve_episode_context_or_warn(title=title)
        if resolved is None:
            return None
        eid, store, db = resolved
        current = self.subs_tracks_list.currentItem()
        if current is None:
            warn_precondition(
                self,
                title,
                "Sélectionnez une piste.",
                next_step="Choisissez une piste dans la liste des sous-titres de l'épisode.",
            )
            return None
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            warn_precondition(
                self,
                title,
                "La piste sélectionnée est invalide.",
                next_step="Rafraîchissez l'onglet puis re-sélectionnez une piste.",
            )
            return None
        lang = str(data.get("lang", "")).strip()
        if not lang:
            warn_precondition(
                self,
                title,
                "La piste sélectionnée n'a pas de langue valide.",
                next_step="Rafraîchissez l'onglet puis re-sélectionnez une piste.",
            )
            return None
        return eid, lang, store, db

    def _normalize_track(self) -> None:
        """§11 — Applique le profil de normalisation aux cues de la piste sélectionnée."""
        resolved = self._resolve_selected_track_or_warn(title="Normalisation piste")
        if resolved is None:
            return
        eid, lang, store, db = resolved
        profile_id = self.subs_norm_profile_combo.currentText() or "default_en_v1"
        rewrite_srt = self.subs_rewrite_srt_check.isChecked()
        nb = store.normalize_subtitle_track(db, eid, lang, profile_id, rewrite_srt=rewrite_srt)
        self._on_episode_changed()
        self._refresh_episodes()
        if nb > 0:
            msg = f"Piste {lang} : {nb} cue(s) normalisée(s)."
            if rewrite_srt:
                msg += " Fichier SRT réécrit."
            self._show_status(msg, 4000)
        else:
            self._show_status("Aucune cue à normaliser ou profil introuvable.", 3000)

    def _export_srt_final(self) -> None:
        """§15.2 — Exporte la piste sélectionnée en SRT final (timecodes + text_clean)."""
        resolved = self._resolve_selected_track_or_warn(title="Export SRT")
        if resolved is None:
            return
        eid, lang, _store, db = resolved
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Exporter SRT final", "", "SRT (*.srt);;Tous (*.*)"
        )
        if not path:
            return
        path = normalize_export_path(
            Path(path),
            selected_filter,
            allowed_suffixes=(".srt",),
            default_suffix=".srt",
            filter_to_suffix={"SRT": ".srt"},
        )
        try:
            cues = db.get_cues_for_episode_lang(eid, lang)
            if not cues:
                warn_precondition(
                    self,
                    "Export SRT",
                    "Aucune cue pour cette piste.",
                    next_step="Réimportez la piste sous-titres puis relancez l'export.",
                )
                return
            srt_content = cues_to_srt(cues)
            path.write_text(srt_content, encoding="utf-8")
            self._show_status(f"SRT final exporté : {path.name}", 4000)
        except Exception as e:
            logger.exception("Export SRT final")
            show_error(self, exc=e, context="Export SRT final")

    def _import_file(self) -> None:
        resolved = self._resolve_episode_context_or_warn()
        if resolved is None:
            return
        eid, _store, _db = resolved
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
        resolved = self._resolve_store_db_or_warn()
        if resolved is None:
            return
        store, _db = resolved
        index = self._resolve_index_or_warn(store)
        if index is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "Choisir un dossier contenant des SRT/VTT")
        if not folder:
            return
        folder_path = Path(folder)
        rows: list[tuple[str, str | None, str | None]] = []
        for p in sorted(folder_path.iterdir()):
            if not p.is_file() or p.suffix.lower() not in {".srt", ".vtt"}:
                continue
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
        resolved = self._resolve_store_db_or_warn()
        if resolved is None:
            return
        store, _db = resolved
        index = self._resolve_index_or_warn(store)
        if index is None:
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
        resolved = self._resolve_episode_context_or_warn(title="Sauvegarde sous-titres")
        if resolved is None:
            return
        eid, store, _db = resolved
        if not self._editing_lang or not self._editing_fmt:
            warn_precondition(
                self,
                "Sauvegarde sous-titres",
                "Sélectionnez une piste à modifier.",
                next_step="Choisissez une piste dans la liste puis éditez son contenu.",
            )
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
            show_error(self, exc=e, context="Sauvegarde sous-titres")
