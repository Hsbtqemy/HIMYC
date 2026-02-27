"""Onglet Inspecteur : RAW/CLEAN, segments, normalisation, export segments, notes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.normalize.profiles import (
    get_all_profile_ids,
    get_profile,
    format_profile_rules_summary,
)
from howimetyourcorpus.core.pipeline.tasks import NormalizeEpisodeStep, SegmentEpisodeStep
from howimetyourcorpus.core.export_utils import (
    export_segments_txt,
    export_segments_csv,
    export_segments_tsv,
    export_segments_docx,
    export_segments_srt_like,
)
from howimetyourcorpus.core.normalize.profiles import PROFILES
from howimetyourcorpus.app.ui_utils import require_project, require_project_and_db

logger = logging.getLogger(__name__)


class InspectorTabWidget(QWidget):
    """Widget de l'onglet Inspecteur : épisode, RAW/CLEAN, segments, normaliser, segmenter, export, notes."""

    def __init__(
        self,
        get_store: Callable[[], object],
        get_db: Callable[[], object],
        get_config: Callable[[], object],
        run_job: Callable[[list], None],
        show_status: Callable[[str, int], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._get_config = get_config
        self._run_job = run_job
        self._show_status = show_status
        self._current_episode_id: str | None = None

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self._inspect_episode_label = QLabel("Épisode:")
        row.addWidget(self._inspect_episode_label)
        self.inspect_episode_combo = QComboBox()
        self.inspect_episode_combo.currentIndexChanged.connect(self._load_episode)
        row.addWidget(self.inspect_episode_combo)
        row.addWidget(QLabel("Vue:"))
        self.inspect_view_combo = QComboBox()
        self.inspect_view_combo.addItem("Épisode", "episode")
        self.inspect_view_combo.addItem("Segments", "segments")
        self.inspect_view_combo.currentIndexChanged.connect(self._switch_view)
        row.addWidget(self.inspect_view_combo)
        row.addWidget(QLabel("Kind:"))
        self.inspect_kind_combo = QComboBox()
        self.inspect_kind_combo.addItem("Tous", "")
        self.inspect_kind_combo.addItem("Phrases", "sentence")
        self.inspect_kind_combo.addItem("Tours", "utterance")
        self.inspect_kind_combo.setToolTip("Filtre la liste segments par type (phrases/tours de parole)")
        self.inspect_kind_combo.currentIndexChanged.connect(self._on_kind_filter_changed)
        row.addWidget(self.inspect_kind_combo)
        # §15.5 — Navigation segments (Aller au segment #N)
        row.addWidget(QLabel("Aller à:"))
        self.segment_goto_edit = QLineEdit()
        self.segment_goto_edit.setPlaceholderText("#N")
        self.segment_goto_edit.setMaximumWidth(60)
        self.segment_goto_edit.setToolTip("Entrez le numéro de segment (ex: 42) et appuyez sur Entrée")
        self.segment_goto_edit.returnPressed.connect(self._goto_segment)
        row.addWidget(self.segment_goto_edit)
        self.segment_goto_btn = QPushButton("→")
        self.segment_goto_btn.setMaximumWidth(40)
        self.segment_goto_btn.setToolTip("Aller au segment #N")
        self.segment_goto_btn.clicked.connect(self._goto_segment)
        row.addWidget(self.segment_goto_btn)
        self.inspect_segment_btn = QPushButton("Segmente l'épisode")
        self.inspect_segment_btn.clicked.connect(self._run_segment)
        row.addWidget(self.inspect_segment_btn)
        self.inspect_export_segments_btn = QPushButton("Exporter les segments")
        self.inspect_export_segments_btn.setToolTip(
            "Exporte les segments de l'épisode affiché : TXT (une ligne par segment), CSV/TSV (colonnes détaillées), "
            "SRT-like (blocs numérotés), Word (.docx)."
        )
        self.inspect_export_segments_btn.clicked.connect(self._export_segments)
        row.addWidget(self.inspect_export_segments_btn)
        layout.addLayout(row)

        # §15.5 — Normalisation (transcript) : regrouper profil + actions + lien Gérer les profils + aperçu des règles
        norm_group = QGroupBox("Normalisation (transcript)")
        norm_group.setToolTip(
            "Profil appliqué à RAW → CLEAN. Priorité : préféré épisode > défaut source (Profils) > config projet."
        )
        norm_layout = QVBoxLayout(norm_group)
        norm_row = QHBoxLayout()
        norm_row.addWidget(QLabel("Profil:"))
        self.inspect_profile_combo = QComboBox()
        self.inspect_profile_combo.addItems(list(PROFILES.keys()))
        self.inspect_profile_combo.setToolTip(
            "Profil pour « Normaliser cet épisode ». Priorité : préféré épisode > défaut source (Profils) > config projet."
        )
        self.inspect_profile_combo.currentTextChanged.connect(self._update_profile_rules_preview)
        norm_row.addWidget(self.inspect_profile_combo)
        self.inspect_norm_btn = QPushButton("Normaliser cet épisode")
        self.inspect_norm_btn.setToolTip(
            "Applique la normalisation (RAW → CLEAN) à l'épisode affiché, avec le profil choisi."
        )
        self.inspect_norm_btn.clicked.connect(self._run_normalize)
        norm_row.addWidget(self.inspect_norm_btn)
        self.inspect_set_preferred_profile_btn = QPushButton("Définir comme préféré pour cet épisode")
        self.inspect_set_preferred_profile_btn.setToolTip(
            "Mémorise ce profil pour cet épisode. Utilisé en priorité lors du batch (Corpus) et ici."
        )
        self.inspect_set_preferred_profile_btn.clicked.connect(self._set_episode_preferred_profile)
        norm_row.addWidget(self.inspect_set_preferred_profile_btn)
        self.inspect_manage_profiles_btn = QPushButton("Gérer les profils…")
        self.inspect_manage_profiles_btn.setToolTip(
            "Ouvre le dialogue de gestion des profils : créer, modifier, supprimer les profils personnalisés (profiles.json)."
        )
        self.inspect_manage_profiles_btn.clicked.connect(self._open_profiles_dialog)
        norm_row.addWidget(self.inspect_manage_profiles_btn)
        norm_layout.addLayout(norm_row)
        norm_layout.addWidget(QLabel("Aperçu des règles du profil :"))
        self.inspect_profile_rules_preview = QPlainTextEdit()
        self.inspect_profile_rules_preview.setReadOnly(True)
        self.inspect_profile_rules_preview.setMaximumHeight(140)
        self.inspect_profile_rules_preview.setPlaceholderText("Sélectionnez un profil…")
        self.inspect_profile_rules_preview.setToolTip("Résumé des options du profil sélectionné (lecture seule).")
        norm_layout.addWidget(self.inspect_profile_rules_preview)
        layout.addWidget(norm_group)
        self._update_profile_rules_preview()

        self.inspect_main_split = QSplitter(Qt.Orientation.Horizontal)
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setPlaceholderText("RAW")
        self.clean_edit = QPlainTextEdit()
        self.clean_edit.setPlaceholderText("CLEAN")
        self.inspect_segments_list = QListWidget()
        self.inspect_segments_list.setMinimumWidth(80)
        self.inspect_segments_list.currentItemChanged.connect(self._on_segment_selected)
        self.inspect_main_split.addWidget(self.inspect_segments_list)
        self.inspect_right_split = QSplitter(Qt.Orientation.Vertical)
        self.inspect_right_split.addWidget(self.raw_edit)
        self.inspect_right_split.addWidget(self.clean_edit)
        self.inspect_main_split.addWidget(self.inspect_right_split)
        self.raw_edit.setMinimumHeight(60)
        self.clean_edit.setMinimumHeight(60)
        layout.addWidget(self.inspect_main_split)
        self._restore_splitter_sizes()

        self.inspect_stats_label = QLabel("Stats: —")
        layout.addWidget(self.inspect_stats_label)
        self.merge_examples_edit = QPlainTextEdit()
        self.merge_examples_edit.setReadOnly(True)
        self.merge_examples_edit.setMaximumHeight(120)
        layout.addWidget(QLabel("Exemples de fusions:"))
        layout.addWidget(self.merge_examples_edit)
        layout.addWidget(QLabel("Notes — à vérifier / à affiner (sauvegardé par épisode) :"))
        self.inspect_notes_edit = QPlainTextEdit()
        self.inspect_notes_edit.setPlaceholderText(
            "Points à vérifier, à changer, à affiner pour cet épisode…"
        )
        self.inspect_notes_edit.setMaximumHeight(100)
        layout.addWidget(self.inspect_notes_edit)
        self.inspect_segments_list.setVisible(False)
        self.inspect_kind_combo.setVisible(False)

    def _restore_splitter_sizes(self) -> None:
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

    def save_state(self) -> None:
        """Sauvegarde les proportions des splitters et les notes de l'épisode courant (appelé à la fermeture)."""
        settings = QSettings()
        settings.setValue("inspecteur/mainSplitter", self.inspect_main_split.sizes())
        settings.setValue("inspecteur/rightSplitter", self.inspect_right_split.sizes())
        store = self._get_store()
        if self._current_episode_id and store:
            store.save_episode_notes(
                self._current_episode_id,
                self.inspect_notes_edit.toPlainText(),
            )

    def refresh(self) -> None:
        """Recharge la liste des épisodes et l'épisode courant (préserve la sélection si possible)."""
        current_episode_id = self.inspect_episode_combo.currentData()
        self.inspect_episode_combo.clear()
        store = self._get_store()
        if not store:
            return
        index = store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.inspect_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
            # Restaurer la sélection d'épisode (évite le retour à S01E01 après enregistrement)
            if current_episode_id:
                for i in range(self.inspect_episode_combo.count()):
                    if self.inspect_episode_combo.itemData(i) == current_episode_id:
                        self.inspect_episode_combo.setCurrentIndex(i)
                        break
        self._load_episode()

    def refresh_profile_combo(self, profile_ids: list[str], current: str | None) -> None:
        """Met à jour la liste des profils (après ouverture projet ou dialogue profils)."""
        current_inspect = self.inspect_profile_combo.currentText()
        self.inspect_profile_combo.clear()
        self.inspect_profile_combo.addItems(profile_ids)
        if current_inspect and current_inspect in profile_ids:
            self.inspect_profile_combo.setCurrentText(current_inspect)
        elif current and current in profile_ids:
            self.inspect_profile_combo.setCurrentText(current)

    def set_episode_selector_visible(self, visible: bool) -> None:
        """§15.4 — Masque ou affiche le sélecteur d'épisode (quand intégré dans l'onglet fusionné)."""
        self._inspect_episode_label.setVisible(visible)
        self.inspect_episode_combo.setVisible(visible)

    def set_episode_and_load(self, episode_id: str) -> None:
        """Sélectionne l'épisode donné et charge son contenu (ex. depuis Concordance « Ouvrir dans Inspecteur »)."""
        for i in range(self.inspect_episode_combo.count()):
            if self.inspect_episode_combo.itemData(i) == episode_id:
                self.inspect_episode_combo.setCurrentIndex(i)
                break
        self._load_episode()

    def _load_episode(self) -> None:
        eid = self.inspect_episode_combo.currentData()
        store = self._get_store()
        if not eid or not store:
            self._current_episode_id = None
            self.raw_edit.clear()
            self.clean_edit.clear()
            self.inspect_stats_label.setText("Stats: —")
            self.merge_examples_edit.clear()
            self.inspect_notes_edit.clear()
            self.inspect_segments_list.clear()
            return
        if self._current_episode_id and self._current_episode_id != eid:
            store.save_episode_notes(
                self._current_episode_id,
                self.inspect_notes_edit.toPlainText(),
            )
        self._current_episode_id = eid
        self.inspect_notes_edit.setPlainText(store.load_episode_notes(eid))
        raw = store.load_episode_text(eid, kind="raw")
        clean = store.load_episode_text(eid, kind="clean")
        self.raw_edit.setPlainText(raw)
        self.clean_edit.setPlainText(clean)
        meta = store.load_episode_transform_meta(eid)
        if meta is not None:
            stats = meta.get("raw_lines", 0), meta.get("clean_lines", 0), meta.get("merges", 0)
            self.inspect_stats_label.setText(
                f"Stats: raw_lines={stats[0]}, clean_lines={stats[1]}, merges={stats[2]}"
            )
            examples = meta.get("debug", {}).get("merge_examples", [])
            self.merge_examples_edit.setPlainText(
                "\n".join(
                    f"{x.get('before', '')} | {x.get('after', '')}" for x in examples[:15]
                )
            )
        else:
            self.inspect_stats_label.setText("Stats: —")
            self.merge_examples_edit.clear()
        config = self._get_config()
        episode_preferred = store.load_episode_preferred_profiles()
        source_defaults = store.load_source_profile_defaults()
        index = store.load_series_index()
        ref = (
            next((e for e in (index.episodes or []) if e.episode_id == eid), None)
            if index
            else None
        )
        profile = (
            episode_preferred.get(eid)
            or (source_defaults.get(ref.source_id or "") if ref else None)
            or (config.normalize_profile if config else "default_en_v1")
        )
        all_ids = get_all_profile_ids(store.load_custom_profiles() if store else None)
        if profile and profile in all_ids:
            self.inspect_profile_combo.setCurrentText(profile)
        self._fill_segments(eid)

    def _switch_view(self) -> None:
        is_segments = self.inspect_view_combo.currentData() == "segments"
        self.inspect_segments_list.setVisible(is_segments)
        self.inspect_kind_combo.setVisible(is_segments)
        eid = self.inspect_episode_combo.currentData()
        if eid:
            self._fill_segments(eid)

    def _on_kind_filter_changed(self) -> None:
        """Filtre les segments par kind (appelé par le combo Kind)."""
        eid = self.inspect_episode_combo.currentData()
        if eid:
            self._fill_segments(eid)
    
    def _goto_segment(self) -> None:
        """Moyenne Priorité #3 : Navigation rapide vers segment #N."""
        segment_num_str = self.segment_goto_edit.text().strip()
        if not segment_num_str:
            return
        
        try:
            segment_num = int(segment_num_str)
        except ValueError:
            QMessageBox.warning(self, "Navigation", "Entrez un numéro de segment valide (ex: 42).")
            return
        
        # Rechercher le segment dans la liste
        for i in range(self.inspect_segments_list.count()):
            item = self.inspect_segments_list.item(i)
            seg = item.data(Qt.ItemDataRole.UserRole) if item else None
            if seg and seg.get("n") == segment_num:
                self.inspect_segments_list.setCurrentItem(item)
                self.inspect_segments_list.scrollToItem(item)
                self._on_segment_selected(item)
                self.segment_goto_edit.clear()
                return
        
        QMessageBox.information(
            self,
            "Navigation",
            f"Segment #{segment_num} introuvable.\n\n"
            f"Vérifiez que l'épisode est segmenté et que le numéro existe."
        )

    def _fill_segments(self, episode_id: str) -> None:
        self.inspect_segments_list.clear()
        if self.inspect_view_combo.currentData() != "segments":
            return
        db = self._get_db()
        if not db:
            return
        kind_filter = self.inspect_kind_combo.currentData() or ""
        segments = db.get_segments_for_episode(episode_id, kind=kind_filter if kind_filter else None)
        for s in segments:
            kind = s.get("kind", "")
            n = s.get("n", 0)
            speaker = s.get("speaker_explicit") or ""
            text = (s.get("text") or "")[:60]
            if len((s.get("text") or "")) > 60:
                text += "…"
            if speaker:
                label = f"[{kind}] {n} {speaker}: {text}"
            else:
                label = f"[{kind}] {n}: {text}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.inspect_segments_list.addItem(item)

    def _on_segment_selected(self, current: QListWidgetItem | None) -> None:
        if not current:
            return
        seg = current.data(Qt.ItemDataRole.UserRole)
        if not seg:
            return
        start_char = seg.get("start_char", 0)
        end_char = seg.get("end_char", 0)
        text = self.clean_edit.toPlainText()
        cursor = self.clean_edit.textCursor()
        cursor.setPosition(min(start_char, len(text)))
        cursor.setPosition(min(end_char, len(text)), QTextCursor.MoveMode.KeepAnchor)
        self.clean_edit.setTextCursor(cursor)
        self.clean_edit.ensureCursorVisible()

    @require_project
    def _run_normalize(self) -> None:
        eid = self.inspect_episode_combo.currentData()
        store = self._get_store()
        assert store is not None  # garanti par @require_project
        if not eid:
            QMessageBox.warning(self, "Normalisation", "Sélectionnez un épisode.")
            return
        if not store.has_episode_raw(eid):
            QMessageBox.warning(self, "Normalisation", "L'épisode doit d'abord être téléchargé (RAW).")
            return
        profile = self.inspect_profile_combo.currentText() or "default_en_v1"
        self._run_job([NormalizeEpisodeStep(eid, profile)])

    @require_project
    def _set_episode_preferred_profile(self) -> None:
        eid = self.inspect_episode_combo.currentData()
        store = self._get_store()
        assert store is not None  # garanti par @require_project
        if not eid:
            QMessageBox.warning(self, "Profil préféré", "Sélectionnez un épisode.")
            return
        profile = self.inspect_profile_combo.currentText() or "default_en_v1"
        preferred = store.load_episode_preferred_profiles()
        preferred[eid] = profile
        store.save_episode_preferred_profiles(preferred)
        self._show_status(f"Profil « {profile} » défini comme préféré pour {eid}.", 3000)

    def _update_profile_rules_preview(self) -> None:
        """§15.5 — Met à jour la zone « Aperçu des règles du profil » selon le profil sélectionné."""
        profile_id = (self.inspect_profile_combo.currentText() or "").strip()
        if not profile_id:
            self.inspect_profile_rules_preview.clear()
            return
        store = self._get_store()
        custom = store.load_custom_profiles() if store else None
        profile = get_profile(profile_id, custom)
        if profile:
            self.inspect_profile_rules_preview.setPlainText(format_profile_rules_summary(profile))
        else:
            self.inspect_profile_rules_preview.setPlainText(f"Profil « {profile_id} » non trouvé.")

    @require_project
    def _open_profiles_dialog(self) -> None:
        """§15.5 — Ouvre le dialogue de gestion des profils de normalisation."""
        store = self._get_store()
        assert store is not None  # garanti par @require_project
        from howimetyourcorpus.app.dialogs import ProfilesDialog
        dlg = ProfilesDialog(self, store)
        dlg.exec()
        custom = store.load_custom_profiles()
        self.refresh_profile_combo(
            get_all_profile_ids(custom),
            self.inspect_profile_combo.currentText(),
        )
        self._update_profile_rules_preview()

    @require_project_and_db
    def _run_segment(self) -> None:
        eid = self.inspect_episode_combo.currentData()
        store = self._get_store()
        assert store is not None  # garanti par @require_project_and_db
        if not eid:
            QMessageBox.warning(self, "Segmentation", "Sélectionnez un épisode.")
            return
        if not store.has_episode_clean(eid):
            QMessageBox.warning(self, "Segmentation", "L'épisode doit d'abord être normalisé (clean.txt).")
            return
        self._run_job([SegmentEpisodeStep(eid, lang_hint="en")])

    @require_project_and_db
    def _export_segments(self) -> None:
        eid = self.inspect_episode_combo.currentData()
        db = self._get_db()
        if not eid:
            QMessageBox.warning(self, "Export segments", "Sélectionnez un épisode.")
            return
        segments = db.get_segments_for_episode(eid)
        if not segments:
            QMessageBox.warning(
                self,
                "Export segments",
                "Aucun segment pour cet épisode. Lancez d'abord « Segmente l'épisode ».",
            )
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter les segments",
            "",
            "TXT — un segment par ligne (*.txt);;CSV (*.csv);;TSV (*.tsv);;SRT-like (*.srt);;Word (*.docx)",
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != ".docx" and "Word" in (selected_filter or ""):
            path = path.with_suffix(".docx")
        if path.suffix.lower() != ".srt" and "SRT" in (selected_filter or ""):
            path = path.with_suffix(".srt")
        try:
            if path.suffix.lower() == ".txt" or "TXT" in (selected_filter or ""):
                export_segments_txt(segments, path)
            elif path.suffix.lower() == ".tsv" or "TSV" in (selected_filter or ""):
                export_segments_tsv(segments, path)
            elif path.suffix.lower() == ".srt" or "SRT" in (selected_filter or ""):
                export_segments_srt_like(segments, path)
            elif path.suffix.lower() == ".docx" or "Word" in (selected_filter or ""):
                export_segments_docx(segments, path)
            else:
                export_segments_csv(segments, path)
            QMessageBox.information(
                self, "Export", f"Segments exportés : {len(segments)} segment(s)."
            )
        except Exception as e:
            logger.exception("Export segments Inspecteur")
            QMessageBox.critical(
                self,
                "Erreur export",
                f"Erreur lors de l'export : {e}\n\n"
                "Vérifiez les droits d'écriture, que le fichier n'est pas ouvert ailleurs et l'encodage (UTF-8)."
            )
