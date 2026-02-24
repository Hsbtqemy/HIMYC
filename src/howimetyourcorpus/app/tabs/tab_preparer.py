"""Onglet Préparer : édition transcript fichier par fichier avant alignement."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.app.dialogs import NormalizeOptionsDialog, SegmentationOptionsDialog
from howimetyourcorpus.app.tabs.preparer_context import PreparerContextController
from howimetyourcorpus.app.tabs.preparer_edit import PreparerEditController
from howimetyourcorpus.app.tabs.preparer_save import PreparerSaveController
from howimetyourcorpus.app.tabs.preparer_state import PreparerStateController
from howimetyourcorpus.app.tabs.preparer_views import CueWidgets, TranscriptWidgets
from howimetyourcorpus.app.undo_commands import CallbackUndoCommand
from howimetyourcorpus.core.models import TransformStats
from howimetyourcorpus.core.preparer import (
    DEFAULT_SEGMENTATION_OPTIONS,
    PREP_STATUS_CHOICES,
    PREP_STATUS_VALUES,
    PreparerService,
    format_ms_to_srt_time as _format_ms_to_srt_time,
    normalize_segmentation_options,
    parse_srt_time_to_ms as _parse_srt_time_to_ms,
)

logger = logging.getLogger(__name__)


def parse_srt_time_to_ms(value: str) -> int:
    """Compat tests/modules: réexport local des utilitaires timecodes."""
    return _parse_srt_time_to_ms(value)


def format_ms_to_srt_time(ms: int) -> str:
    """Compat tests/modules: réexport local des utilitaires timecodes."""
    return _format_ms_to_srt_time(ms)


class SearchReplaceDialog(QDialog):
    """Dialogue simple de recherche/remplacement."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Rechercher / Remplacer")
        layout = QVBoxLayout(self)

        row_find = QHBoxLayout()
        row_find.addWidget(QLabel("Rechercher:"))
        self.find_edit = QLineEdit()
        row_find.addWidget(self.find_edit)
        layout.addLayout(row_find)

        row_replace = QHBoxLayout()
        row_replace.addWidget(QLabel("Remplacer par:"))
        self.replace_edit = QLineEdit()
        row_replace.addWidget(self.replace_edit)
        layout.addLayout(row_replace)

        opts = QHBoxLayout()
        self.case_sensitive_cb = QCheckBox("Respecter la casse")
        self.regex_cb = QCheckBox("Regex")
        opts.addWidget(self.case_sensitive_cb)
        opts.addWidget(self.regex_cb)
        opts.addStretch()
        layout.addLayout(opts)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_params(self) -> tuple[str, str, bool, bool]:
        return (
            self.find_edit.text(),
            self.replace_edit.text(),
            self.case_sensitive_cb.isChecked(),
            self.regex_cb.isChecked(),
        )


class PreparerTabWidget(QWidget):
    """Préparation d'un fichier: normalisation, édition, segmentation tours, sauvegarde."""

    def __init__(
        self,
        *,
        get_store: Callable[[], Any],
        get_db: Callable[[], Any],
        show_status: Callable[[str, int], None],
        on_go_alignement: Callable[[str, str], None],
        undo_stack: QUndoStack | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._show_status = show_status
        self._on_go_alignement = on_go_alignement
        self.undo_stack = undo_stack
        self._service: PreparerService | None = None
        self._dirty = False
        self._current_episode_id: str | None = None
        self._current_source_key = "transcript"
        self._current_status_value = "raw"
        self._force_save_transcript_rows = False
        self._updating_ui = False
        self._edit_role = int(Qt.ItemDataRole.UserRole) + 1
        self._context_controller = PreparerContextController(self, logger)
        self._edit_controller = PreparerEditController(self)
        self._state_controller = PreparerStateController(self, valid_status_values=PREP_STATUS_VALUES)
        self._save_controller = PreparerSaveController(
            get_store=self._get_store,
            get_db=self._get_db,
            build_service=self._build_service,
            normalize_cue_timecodes_display=self._normalize_cue_timecodes_display,
            undo_stack=self.undo_stack,
        )

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Épisode:"))
        self.prep_episode_combo = QComboBox()
        self.prep_episode_combo.currentIndexChanged.connect(self._on_episode_changed)
        top.addWidget(self.prep_episode_combo)

        top.addWidget(QLabel("Fichier:"))
        self.prep_source_combo = QComboBox()
        self._refresh_source_combo_items()
        self.prep_source_combo.currentIndexChanged.connect(self._on_source_changed)
        top.addWidget(self.prep_source_combo)

        top.addWidget(QLabel("Statut:"))
        self.prep_status_combo = QComboBox()
        for label, value in PREP_STATUS_CHOICES:
            self.prep_status_combo.addItem(label, value)
        self.prep_status_combo.currentIndexChanged.connect(self._on_status_changed)
        top.addWidget(self.prep_status_combo)

        self.dirty_label = QLabel("")
        self.dirty_label.setStyleSheet("color: #b00020; font-weight: bold;")
        top.addWidget(self.dirty_label)
        top.addStretch()
        layout.addLayout(top)

        actions = QHBoxLayout()
        self.prep_normalize_btn = QPushButton("Nettoyer")
        self.prep_normalize_btn.clicked.connect(self._normalize_transcript)
        actions.addWidget(self.prep_normalize_btn)

        self.prep_search_replace_btn = QPushButton("Rechercher / Remplacer")
        self.prep_search_replace_btn.clicked.connect(self._search_replace)
        actions.addWidget(self.prep_search_replace_btn)

        self.prep_segment_btn = QPushButton("Segmenter en tours")
        self.prep_segment_btn.clicked.connect(self._segment_to_utterances)
        actions.addWidget(self.prep_segment_btn)

        self.prep_segment_options_btn = QPushButton("Paramètres segmentation")
        self.prep_segment_options_btn.clicked.connect(self._open_segmentation_options)
        actions.addWidget(self.prep_segment_options_btn)

        self.prep_edit_timecodes_cb = QCheckBox("Éditer timecodes")
        self.prep_edit_timecodes_cb.setToolTip(
            "Autorise l'édition des colonnes Début/Fin sur les cues SRT."
        )
        self.prep_edit_timecodes_cb.toggled.connect(self._on_edit_timecodes_toggled)
        self.prep_edit_timecodes_cb.setEnabled(False)
        actions.addWidget(self.prep_edit_timecodes_cb)

        self.prep_strict_timecodes_cb = QCheckBox("Validation stricte")
        self.prep_strict_timecodes_cb.setToolTip(
            "En mode édition timecodes, refuse les chevauchements entre cues adjacentes."
        )
        self.prep_strict_timecodes_cb.setEnabled(False)
        actions.addWidget(self.prep_strict_timecodes_cb)

        self.prep_save_btn = QPushButton("Enregistrer")
        self.prep_save_btn.clicked.connect(self.save_current)
        actions.addWidget(self.prep_save_btn)

        self.prep_go_align_btn = QPushButton("Aller à l'alignement")
        self.prep_go_align_btn.clicked.connect(self._go_to_alignement)
        actions.addWidget(self.prep_go_align_btn)
        actions.addStretch()
        layout.addLayout(actions)

        utterance_actions = QHBoxLayout()
        self.prep_add_utt_btn = QPushButton("Ajouter ligne")
        self.prep_add_utt_btn.clicked.connect(self._add_utterance_row_below)
        utterance_actions.addWidget(self.prep_add_utt_btn)

        self.prep_delete_utt_btn = QPushButton("Supprimer ligne")
        self.prep_delete_utt_btn.clicked.connect(self._delete_selected_utterance_rows)
        utterance_actions.addWidget(self.prep_delete_utt_btn)

        self.prep_merge_utt_btn = QPushButton("Fusionner")
        self.prep_merge_utt_btn.clicked.connect(self._merge_selected_utterances)
        utterance_actions.addWidget(self.prep_merge_utt_btn)

        self.prep_split_utt_btn = QPushButton("Scinder au curseur")
        self.prep_split_utt_btn.clicked.connect(self._split_selected_utterance_at_cursor)
        utterance_actions.addWidget(self.prep_split_utt_btn)

        self.prep_group_utt_btn = QPushButton("Regrouper par assignations")
        self.prep_group_utt_btn.clicked.connect(self._group_utterances_by_assignments)
        utterance_actions.addWidget(self.prep_group_utt_btn)

        self.prep_renumber_utt_btn = QPushButton("Renuméroter")
        self.prep_renumber_utt_btn.clicked.connect(self._renumber_utterances)
        utterance_actions.addWidget(self.prep_renumber_utt_btn)

        self.prep_reset_utt_btn = QPushButton("Revenir au texte")
        self.prep_reset_utt_btn.clicked.connect(self._reset_utterances_to_text)
        utterance_actions.addWidget(self.prep_reset_utt_btn)
        utterance_actions.addStretch()
        layout.addLayout(utterance_actions)

        self.help_label = QLabel(
            "Transcript: normaliser, segmenter (règles paramétrables), éditer les tours.\n"
            "SRT: éditer personnage/texte des cues, timecodes éditables via « Éditer timecodes »."
        )
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet("color: #666;")
        layout.addWidget(self.help_label)

        self._transcript_widgets = TranscriptWidgets(
            edit_role=self._edit_role,
            on_text_changed=self._on_text_changed,
            on_table_item_changed=self._on_table_item_changed,
        )
        self._cue_widgets = CueWidgets(
            edit_role=self._edit_role,
            on_table_item_changed=self._on_table_item_changed,
        )
        # Attributs publics conservés pour compatibilité (tests et intégrations).
        self.text_editor = self._transcript_widgets.text_editor
        self.utterance_table = self._transcript_widgets.utterance_table
        self.cue_table = self._cue_widgets.cue_table

        self.stack = QStackedWidget()
        self.stack.addWidget(self.text_editor)
        self.stack.addWidget(self.utterance_table)
        self.stack.addWidget(self.cue_table)
        layout.addWidget(self.stack)
        self._update_utterance_action_states()

    def _build_service(self) -> PreparerService | None:
        store = self._get_store()
        db = self._get_db()
        if not store or not db:
            self._service = None
            return None
        if (
            self._service is None
            or self._service.store is not store
            or self._service.db is not db
        ):
            self._service = PreparerService(store, db)
        return self._service

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def current_episode_id(self) -> str | None:
        return self._current_episode_id

    def refresh(self) -> None:
        self._context_controller.refresh()

    def set_episode_and_load(self, episode_id: str, source_key: str | None = None) -> None:
        self._context_controller.set_episode_and_load(episode_id, source_key)

    def _refresh_source_combo_items(self) -> None:
        """Synchronise les sources Préparer avec les langues projet (Transcript + SRT <lang>)."""
        current_key = (
            self.prep_source_combo.currentData()
            or self._current_source_key
            or "transcript"
        )
        store = self._get_store()
        langs_raw = store.load_project_languages() if store else ["en", "fr", "it"]
        langs: list[str] = []
        seen: set[str] = set()
        for lang in langs_raw or []:
            key = str(lang or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            langs.append(key)
        if not langs:
            langs = ["en", "fr", "it"]

        self.prep_source_combo.blockSignals(True)
        self.prep_source_combo.clear()
        self.prep_source_combo.addItem("Transcript", "transcript")
        for lang in langs:
            self.prep_source_combo.addItem(f"SRT {lang.upper()}", f"srt_{lang}")
        idx = self.prep_source_combo.findData(current_key)
        self.prep_source_combo.setCurrentIndex(idx if idx >= 0 else 0)

        source_model = self.prep_source_combo.model()
        for i in range(1, self.prep_source_combo.count()):
            item = source_model.item(i) if hasattr(source_model, "item") else None
            if item is not None:
                item.setEnabled(False)
        self.prep_source_combo.blockSignals(False)

        source_key = self.prep_source_combo.currentData() or "transcript"
        self._current_source_key = str(source_key)

    def save_state(self) -> None:
        """Méthode symétrique aux autres onglets (pas d'état persistant spécifique pour l'instant)."""
        return

    def prompt_save_if_dirty(self) -> bool:
        if not self._dirty:
            return True
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Préparer")
        msg.setText("Modifications non enregistrées.")
        msg.setInformativeText("Voulez-vous enregistrer avant de continuer ?")
        btn_save = msg.addButton("Enregistrer", QMessageBox.ButtonRole.AcceptRole)
        btn_discard = msg.addButton("Ignorer", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_save)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == btn_save:
            return self.save_current()
        if clicked == btn_discard:
            # Recharger l'état persistant pour réellement abandonner le brouillon.
            self._load_selected_context(force=True)
            self._set_dirty(False)
            return True
        return clicked != btn_cancel

    def _on_episode_changed(self) -> None:
        self._context_controller.on_episode_changed()

    def _on_source_changed(self) -> None:
        self._context_controller.on_source_changed()

    def _restore_episode_combo(self) -> None:
        self._context_controller.restore_episode_combo()

    def _restore_source_combo(self) -> None:
        self._context_controller.restore_source_combo()

    def _default_status_for_loaded_data(self, source_key: str, data: dict[str, Any]) -> str:
        return self._context_controller.default_status_for_loaded_data(source_key, data)

    def _apply_status_value(self, status: str, *, persist: bool, mark_dirty: bool) -> None:
        st = (status or "raw").strip().lower()
        if st not in PREP_STATUS_VALUES:
            st = "raw"
        idx = self.prep_status_combo.findData(st)
        if idx < 0:
            idx = 0
            st = self.prep_status_combo.itemData(0) or "raw"
        self.prep_status_combo.blockSignals(True)
        self.prep_status_combo.setCurrentIndex(idx)
        self.prep_status_combo.blockSignals(False)
        self._current_status_value = st
        if persist:
            store = self._get_store()
            if store and self._current_episode_id and self._current_source_key:
                store.set_episode_prep_status(self._current_episode_id, self._current_source_key, st)
        self._set_dirty(mark_dirty)

    def _on_status_changed(self) -> None:
        if self._updating_ui:
            return
        new_status = (self.prep_status_combo.currentData() or "raw").strip().lower()
        old_status = (getattr(self, "_current_status_value", "") or new_status).strip().lower()
        if new_status == old_status:
            return

        # Changement utilisateur : persistance immédiate.
        self._apply_status_value(new_status, persist=True, mark_dirty=False)
        if self.undo_stack:
            cmd = CallbackUndoCommand(
                "Changer statut préparation",
                redo_callback=lambda s=new_status: self._apply_status_value(s, persist=True, mark_dirty=False),
                undo_callback=lambda s=old_status: self._apply_status_value(s, persist=True, mark_dirty=False),
                already_applied=True,
            )
            self.undo_stack.push(cmd)
        self._show_status(f"Statut: {new_status}.", 2500)

    def _reset_empty_context(self) -> None:
        self._context_controller.reset_empty_context()

    def _load_selected_context(self, force: bool = False) -> None:
        self._context_controller.load_selected_context(force=force)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = bool(dirty)
        self.dirty_label.setText("* brouillon" if self._dirty else "")

    def _set_text(self, text: str) -> None:
        self._transcript_widgets.set_text(text)

    def _set_utterances(self, utterances: list[dict[str, Any]]) -> None:
        self._transcript_widgets.set_utterances(
            utterances,
            character_options=self._character_choices(),
        )
        self._update_utterance_action_states()

    def _set_cues(
        self,
        cues: list[dict[str, Any]],
        *,
        episode_id: str | None = None,
        lang: str | None = None,
    ) -> None:
        episode_for_assign = episode_id or self._current_episode_id
        assign_map = self._load_assignment_map(
            source_type="cue",
            episode_id=episode_for_assign,
            prefix=f"{episode_for_assign}:{(lang or '').strip().lower()}:",
        )
        self._cue_widgets.set_cues(
            cues,
            assign_map,
            character_options=self._character_choices(),
        )
        self._apply_cue_timecode_editability()
        self._update_utterance_action_states()

    def _refresh_source_availability(self, episode_id: str | None) -> None:
        self._context_controller.refresh_source_availability(episode_id)

    def _on_edit_timecodes_toggled(self, checked: bool) -> None:
        self.prep_strict_timecodes_cb.setEnabled(bool(checked) and self.prep_edit_timecodes_cb.isEnabled())
        self._apply_cue_timecode_editability()

    def _apply_cue_timecode_editability(self) -> None:
        editable = self.prep_edit_timecodes_cb.isChecked() and self.prep_edit_timecodes_cb.isEnabled()
        self._cue_widgets.apply_timecode_editability(editable)

    def _normalize_cue_timecodes_display(self) -> None:
        self._cue_widgets.normalize_timecodes_display()

    def _apply_plain_text_value(self, text: str) -> None:
        self._edit_controller.apply_plain_text_value(text)

    def _apply_table_column_values(self, table: QTableWidget, col: int, values: list[str]) -> None:
        self._edit_controller.apply_table_column_values(table, col, values)

    def _apply_table_cell_value(self, table: QTableWidget, row: int, col: int, value: str) -> None:
        self._edit_controller.apply_table_cell_value(table, row, col, value)

    def _on_text_changed(self) -> None:
        self._edit_controller.on_text_changed()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        self._edit_controller.on_table_item_changed(item)

    def _normalize_transcript(self) -> None:
        episode_id = self.prep_episode_combo.currentData()
        store = self._get_store()
        service = self._build_service()
        if not episode_id or not store or service is None:
            QMessageBox.warning(self, "Préparer", "Ouvrez un projet et sélectionnez un épisode.")
            return
        if self._current_source_key != "transcript":
            QMessageBox.information(self, "Préparer", "MVP: normalisation explicite disponible sur Transcript.")
            return
        dlg = NormalizeOptionsDialog(self, store=store)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        options = dlg.get_options()
        options["input_text"] = self.text_editor.toPlainText()
        try:
            result = service.apply_normalization(episode_id, "transcript", options)
            clean_text = result.get("clean_text") or ""
            stats = result.get("stats")
            debug = result.get("debug")
            self._set_text(clean_text)
            self.save_clean_text_with_meta(episode_id, clean_text, stats=stats, debug=debug)
            self._apply_status_value("normalized", persist=True, mark_dirty=False)
            merges = int(getattr(stats, "merges", 0)) if stats else 0
            self._show_status(f"Normalisation appliquée ({merges} fusion(s)).", 4000)
        except Exception as exc:
            logger.exception("Normalize transcript preparer")
            QMessageBox.critical(self, "Préparer", f"Erreur normalisation: {exc}")

    def _search_replace(self) -> None:
        dlg = SearchReplaceDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        needle, repl, case_sensitive, is_regex = dlg.get_params()
        if not needle:
            QMessageBox.warning(self, "Préparer", "Le texte à rechercher est vide.")
            return

        try:
            if self.stack.currentWidget() == self.utterance_table and self.utterance_table.rowCount() > 0:
                count = self._search_replace_table(
                    self.utterance_table,
                    needle,
                    repl,
                    case_sensitive,
                    is_regex,
                    text_col=2,
                )
            elif self.stack.currentWidget() == self.cue_table and self.cue_table.rowCount() > 0:
                count = self._search_replace_table(
                    self.cue_table,
                    needle,
                    repl,
                    case_sensitive,
                    is_regex,
                    text_col=4,
                )
            else:
                before = self.text_editor.toPlainText()
                after, count = self._replace_text(before, needle, repl, case_sensitive, is_regex)
                if count > 0:
                    if self.undo_stack:
                        cmd = CallbackUndoCommand(
                            f"Rechercher/remplacer ({count})",
                            redo_callback=lambda v=after: self._apply_plain_text_value(v),
                            undo_callback=lambda v=before: self._apply_plain_text_value(v),
                        )
                        self.undo_stack.push(cmd)
                    else:
                        self._apply_plain_text_value(after)
            if count > 0:
                self._show_status(f"{count} remplacement(s).", 3000)
            else:
                QMessageBox.information(self, "Préparer", "Aucune occurrence trouvée.")
        except re.error as exc:
            QMessageBox.warning(self, "Préparer", f"Regex invalide: {exc}")

    def _search_replace_table(
        self,
        table: QTableWidget,
        needle: str,
        repl: str,
        case_sensitive: bool,
        is_regex: bool,
        *,
        text_col: int,
    ) -> int:
        return self._edit_controller.search_replace_table(
            table,
            needle,
            repl,
            case_sensitive,
            is_regex,
            text_col=text_col,
        )

    @staticmethod
    def _replace_text(
        text: str,
        needle: str,
        repl: str,
        case_sensitive: bool,
        is_regex: bool,
    ) -> tuple[str, int]:
        return PreparerEditController.replace_text(text, needle, repl, case_sensitive, is_regex)

    def _export_utterance_rows(self) -> list[dict[str, Any]]:
        return self._transcript_widgets.export_utterance_rows()

    def _load_segmentation_options(self, episode_id: str, source_key: str) -> dict[str, Any]:
        store = self._get_store()
        if not store:
            return dict(DEFAULT_SEGMENTATION_OPTIONS)
        try:
            return store.get_episode_segmentation_options(
                episode_id,
                source_key,
                default=DEFAULT_SEGMENTATION_OPTIONS,
            )
        except Exception:
            logger.exception("Load segmentation options")
            return dict(DEFAULT_SEGMENTATION_OPTIONS)

    def _open_segmentation_options(self) -> None:
        episode_id = self.prep_episode_combo.currentData()
        if not episode_id:
            QMessageBox.warning(self, "Préparer", "Sélectionnez un épisode.")
            return
        if self._current_source_key != "transcript":
            QMessageBox.information(
                self,
                "Préparer",
                "Les paramètres de segmentation sont disponibles sur la source Transcript.",
            )
            return
        store = self._get_store()
        if not store:
            QMessageBox.warning(self, "Préparer", "Projet indisponible.")
            return

        initial = self._load_segmentation_options(episode_id, self._current_source_key)
        dlg = SegmentationOptionsDialog(self, initial_options=initial)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        options = normalize_segmentation_options(dlg.get_options())
        try:
            store.set_episode_segmentation_options(episode_id, self._current_source_key, options)
        except Exception as exc:
            logger.exception("Save segmentation options")
            QMessageBox.critical(self, "Préparer", f"Impossible d'enregistrer les paramètres: {exc}")
            return
        self._show_status("Paramètres segmentation enregistrés.", 3000)

    def _segment_to_utterances(self) -> None:
        self._edit_controller.segment_to_utterances()

    def _add_utterance_row_below(self) -> None:
        self._edit_controller.add_utterance_row_below()

    def _delete_selected_utterance_rows(self) -> None:
        self._edit_controller.delete_selected_utterance_rows()

    def _merge_selected_utterances(self) -> None:
        self._edit_controller.merge_selected_utterances()

    def _split_selected_utterance_at_cursor(self) -> None:
        self._edit_controller.split_selected_utterance_at_cursor()

    def _group_utterances_by_assignments(self) -> None:
        self._edit_controller.group_utterances_by_assignments(tolerant=True)

    def _renumber_utterances(self) -> None:
        self._edit_controller.renumber_utterances()

    def _reset_utterances_to_text(self) -> None:
        self._edit_controller.reset_utterances_to_text()

    def _update_utterance_action_states(self) -> None:
        is_transcript = self._current_source_key == "transcript"
        has_episode = bool(self.prep_episode_combo.currentData())
        has_rows = self.utterance_table.rowCount() > 0

        self.prep_segment_options_btn.setEnabled(is_transcript and has_episode)
        self.prep_add_utt_btn.setEnabled(is_transcript and has_episode)
        self.prep_delete_utt_btn.setEnabled(is_transcript and has_rows)
        self.prep_merge_utt_btn.setEnabled(is_transcript and self.utterance_table.rowCount() >= 2)
        self.prep_split_utt_btn.setEnabled(is_transcript and has_rows)
        self.prep_group_utt_btn.setEnabled(is_transcript and has_rows)
        self.prep_renumber_utt_btn.setEnabled(is_transcript and has_rows)
        self.prep_reset_utt_btn.setEnabled(is_transcript and has_rows)

    def save_clean_text_with_meta(
        self,
        episode_id: str,
        clean_text: str,
        *,
        stats: TransformStats | None = None,
        debug: dict[str, Any] | None = None,
    ) -> bool:
        """Sauvegarde clean.txt avec une méta minimale (contrat save_episode_clean complet)."""
        store = self._get_store()
        if not store:
            return False
        try:
            if stats is None:
                raw = store.load_episode_text(episode_id, kind="raw")
                stats = TransformStats(
                    raw_lines=len(raw.splitlines()) if raw else len(clean_text.splitlines()),
                    clean_lines=len(clean_text.splitlines()),
                    merges=0,
                    kept_breaks=0,
                    duration_ms=0,
                )
            store.save_episode_clean(
                episode_id,
                clean_text,
                stats,
                debug or {"source": "preparer", "mode": "manual_save"},
            )
            return True
        except Exception:
            logger.exception("Save clean text with meta")
            return False

    def _capture_prep_status_scope(self, episode_id: str, source_key: str) -> dict[str, Any]:
        return self._state_controller.capture_prep_status_scope(episode_id, source_key)

    def _restore_prep_status_scope(self, scope: dict[str, Any]) -> None:
        self._state_controller.restore_prep_status_scope(scope)

    def _restore_prep_status_snapshot(self, episode_id: str, state: dict[str, Any]) -> None:
        self._state_controller.restore_prep_status_snapshot(episode_id, state)

    def _restore_assignment_snapshot(
        self,
        state: dict[str, Any],
        scoped_restore: Callable[[list[dict[str, Any]]], None],
    ) -> None:
        self._state_controller.restore_assignment_snapshot(state, scoped_restore)

    @staticmethod
    def _is_utterance_assignment(assignment: dict[str, Any], episode_id: str) -> bool:
        return PreparerStateController.is_utterance_assignment(assignment, episode_id)

    def _capture_utterance_assignments_scope(self, episode_id: str) -> list[dict[str, Any]]:
        return self._state_controller.capture_utterance_assignments_scope(episode_id)

    def _restore_utterance_assignments_scope(self, episode_id: str, scoped_assignments: list[dict[str, Any]]) -> None:
        self._state_controller.restore_utterance_assignments_scope(episode_id, scoped_assignments)

    @staticmethod
    def _is_cue_assignment_for_lang(assignment: dict[str, Any], episode_id: str, lang: str) -> bool:
        return PreparerStateController.is_cue_assignment_for_lang(assignment, episode_id, lang)

    def _capture_cue_assignments_scope(self, episode_id: str, lang: str) -> list[dict[str, Any]]:
        return self._state_controller.capture_cue_assignments_scope(episode_id, lang)

    def _restore_cue_assignments_scope(
        self,
        episode_id: str,
        lang: str,
        scoped_assignments: list[dict[str, Any]],
    ) -> None:
        self._state_controller.restore_cue_assignments_scope(episode_id, lang, scoped_assignments)

    def _capture_clean_file_state(self, episode_id: str, source_key: str) -> dict[str, Any]:
        return self._state_controller.capture_clean_file_state(episode_id, source_key)

    def _apply_clean_file_state(self, episode_id: str, state: dict[str, Any], *, mark_dirty: bool) -> None:
        self._state_controller.apply_clean_file_state(episode_id, state, mark_dirty=mark_dirty)

    def _capture_utterance_persistence_state(self, episode_id: str, source_key: str) -> dict[str, Any]:
        return self._state_controller.capture_utterance_persistence_state(episode_id, source_key)

    def _apply_utterance_persistence_state(
        self,
        episode_id: str,
        state: dict[str, Any],
        *,
        mark_dirty: bool,
    ) -> None:
        self._state_controller.apply_utterance_persistence_state(episode_id, state, mark_dirty=mark_dirty)

    def _capture_cue_persistence_state(self, episode_id: str, lang: str, source_key: str) -> dict[str, Any]:
        return self._state_controller.capture_cue_persistence_state(episode_id, lang, source_key)

    def _apply_cue_persistence_state(
        self,
        episode_id: str,
        lang: str,
        state: dict[str, Any],
        *,
        mark_dirty: bool,
    ) -> None:
        self._state_controller.apply_cue_persistence_state(episode_id, lang, state, mark_dirty=mark_dirty)

    def _save_transcript_rows(self, episode_id: str) -> bool:
        return self._save_controller.save_transcript_rows(
            owner=self,
            episode_id=episode_id,
            utterance_table=self.utterance_table,
            text_value=self.text_editor.toPlainText(),
        )

    def _save_cue_rows(self, episode_id: str, lang: str) -> bool:
        strict = self.prep_edit_timecodes_cb.isChecked() and self.prep_strict_timecodes_cb.isChecked()
        return self._save_controller.save_cue_rows(
            owner=self,
            episode_id=episode_id,
            lang=lang,
            cue_table=self.cue_table,
            strict=strict,
        )

    def _auto_update_status_after_save(self) -> None:
        current = (self.prep_status_combo.currentData() or "raw").strip().lower()
        if current in ("raw", "normalized"):
            self._apply_status_value("edited", persist=True, mark_dirty=False)

    def _run_save_with_snapshot_undo(
        self,
        *,
        capture_before: Callable[[], dict[str, Any]],
        save_action: Callable[[], bool],
        capture_after: Callable[[], dict[str, Any]],
        undo_title: str,
        redo_callback: Callable[[dict[str, Any]], None],
        undo_callback: Callable[[dict[str, Any]], None],
        success_status: str,
    ) -> bool:
        before_state = capture_before() if self.undo_stack else {}
        ok = save_action()
        if not ok:
            return False
        self._auto_update_status_after_save()
        if self.undo_stack:
            after_state = capture_after()
            self._save_controller.push_snapshot_undo(
                title=undo_title,
                redo_callback=lambda st=after_state: redo_callback(st),
                undo_callback=lambda st=before_state: undo_callback(st),
            )
        self._show_status(success_status, 3000)
        return True

    def save_current(self) -> bool:
        episode_id = self.prep_episode_combo.currentData()
        if not episode_id:
            return True
        try:
            if self._current_source_key.startswith("srt_"):
                lang = self._current_source_key.replace("srt_", "", 1)
                ok = self._run_save_with_snapshot_undo(
                    capture_before=lambda ep=episode_id, ln=lang: self._capture_cue_persistence_state(
                        ep, ln, self._current_source_key
                    ),
                    save_action=lambda ep=episode_id, ln=lang: self._save_cue_rows(ep, ln),
                    capture_after=lambda ep=episode_id, ln=lang: self._capture_cue_persistence_state(
                        ep, ln, self._current_source_key
                    ),
                    undo_title=f"Enregistrer cues {lang.upper()}",
                    redo_callback=lambda st, ep=episode_id, ln=lang: self._apply_cue_persistence_state(
                        ep, ln, st, mark_dirty=False
                    ),
                    undo_callback=lambda st, ep=episode_id, ln=lang: self._apply_cue_persistence_state(
                        ep, ln, st, mark_dirty=True
                    ),
                    success_status=f"Cues {lang.upper()} enregistrées et piste réécrite.",
                )
            elif self.stack.currentWidget() == self.utterance_table or (
                self._current_source_key == "transcript" and self._force_save_transcript_rows
            ):
                ok = self._run_save_with_snapshot_undo(
                    capture_before=lambda ep=episode_id: self._capture_utterance_persistence_state(
                        ep, self._current_source_key
                    ),
                    save_action=lambda ep=episode_id: self._save_transcript_rows(ep),
                    capture_after=lambda ep=episode_id: self._capture_utterance_persistence_state(
                        ep, self._current_source_key
                    ),
                    undo_title="Enregistrer tours",
                    redo_callback=lambda st, ep=episode_id: self._apply_utterance_persistence_state(
                        ep, st, mark_dirty=False
                    ),
                    undo_callback=lambda st, ep=episode_id: self._apply_utterance_persistence_state(
                        ep, st, mark_dirty=True
                    ),
                    success_status="Tours enregistrés.",
                )
            else:
                text = self.text_editor.toPlainText()
                ok = self._run_save_with_snapshot_undo(
                    capture_before=lambda ep=episode_id: self._capture_clean_file_state(ep, self._current_source_key),
                    save_action=lambda ep=episode_id, txt=text: self.save_clean_text_with_meta(ep, txt),
                    capture_after=lambda ep=episode_id: self._capture_clean_file_state(ep, self._current_source_key),
                    undo_title="Enregistrer transcript clean",
                    redo_callback=lambda st, ep=episode_id: self._apply_clean_file_state(ep, st, mark_dirty=False),
                    undo_callback=lambda st, ep=episode_id: self._apply_clean_file_state(ep, st, mark_dirty=True),
                    success_status="Transcript clean enregistré.",
                )
            if not ok:
                abort_reason = self._save_controller.pop_abort_reason()
                if abort_reason == "align_runs_invalidation_cancelled":
                    self._show_status("Enregistrement annulé (alignements préservés).", 3500)
                    return False
                QMessageBox.critical(self, "Préparer", "Échec de sauvegarde.")
                return False
            self._force_save_transcript_rows = False
            self._set_dirty(False)
            return True
        except Exception as exc:
            logger.exception("Save preparer")
            QMessageBox.critical(self, "Préparer", f"Erreur sauvegarde: {exc}")
            return False

    def _go_to_alignement(self) -> None:
        episode_id = self.prep_episode_combo.currentData()
        if not episode_id:
            QMessageBox.warning(self, "Préparer", "Sélectionnez un épisode.")
            return
        if self._dirty and not self.prompt_save_if_dirty():
            return
        if self._current_source_key == "transcript":
            segment_kind = "utterance" if self.utterance_table.rowCount() > 0 else "sentence"
        else:
            segment_kind = "sentence"
        self._on_go_alignement(episode_id, segment_kind)

    def _load_assignment_map(
        self,
        *,
        source_type: str,
        episode_id: str | None,
        prefix: str,
    ) -> dict[str, str]:
        store = self._get_store()
        if not store or not episode_id:
            return {}
        out: dict[str, str] = {}
        for a in store.load_character_assignments():
            if a.get("episode_id") != episode_id:
                continue
            if a.get("source_type") != source_type:
                continue
            source_id = (a.get("source_id") or "").strip()
            if prefix and not source_id.startswith(prefix):
                continue
            out[source_id] = (a.get("character_id") or "").strip()
        return out

    def _character_choices(self) -> list[str]:
        """Valeurs proposées dans les combos Personnage (id/canonique/noms par langue)."""
        store = self._get_store()
        if not store:
            return []
        seen: set[str] = set()
        out: list[str] = []
        for ch in store.load_character_names():
            raw_values: list[str] = [
                (ch.get("id") or "").strip(),
                (ch.get("canonical") or "").strip(),
            ]
            names = ch.get("names_by_lang") or {}
            if isinstance(names, dict):
                raw_values.extend((str(v or "").strip() for v in names.values()))
            for value in raw_values:
                key = value.lower()
                if not value or key in seen:
                    continue
                seen.add(key)
                out.append(value)
        return out
