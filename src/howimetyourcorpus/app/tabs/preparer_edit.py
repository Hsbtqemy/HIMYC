"""Contrôleur d'édition locale pour l'onglet Préparer."""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem

from howimetyourcorpus.app.undo_commands import CallbackUndoCommand
from howimetyourcorpus.core.segment import segmenter_utterances


class PreparerEditController:
    """Gère les mutations UI locales, undo d'édition et opérations de texte."""

    def __init__(self, tab: Any):
        self._tab = tab

    def apply_plain_text_value(self, text: str) -> None:
        tab = self._tab
        tab._updating_ui = True
        try:
            tab._set_text(text)
        finally:
            tab._updating_ui = False
        tab._set_dirty(True)

    def apply_table_column_values(self, table: QTableWidget, col: int, values: list[str]) -> None:
        tab = self._tab
        tab._updating_ui = True
        try:
            for row, value in enumerate(values):
                if row >= table.rowCount():
                    break
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(row, col, item)
                item.setText(value)
                item.setData(tab._edit_role, value)
        finally:
            tab._updating_ui = False
        tab._set_dirty(True)

    def apply_table_cell_value(self, table: QTableWidget, row: int, col: int, value: str) -> None:
        tab = self._tab
        tab._updating_ui = True
        try:
            if row >= table.rowCount():
                return
            item = table.item(row, col)
            if item is None:
                item = QTableWidgetItem("")
                table.setItem(row, col, item)
            item.setText(value)
            item.setData(tab._edit_role, value)
        finally:
            tab._updating_ui = False
        tab._set_dirty(True)

    def on_text_changed(self) -> None:
        tab = self._tab
        if tab._updating_ui:
            return
        tab._set_dirty(True)

    def on_table_item_changed(self, item: QTableWidgetItem) -> None:
        tab = self._tab
        if tab._updating_ui:
            return
        if item is None:
            return
        table = item.tableWidget()
        if table is None:
            return
        col = item.column()
        if table is tab.utterance_table:
            editable_cols = {1, 2}
        elif table is tab.cue_table:
            editable_cols = {1, 2, 3, 4}
        else:
            editable_cols = set()
        if col not in editable_cols:
            return

        new_value = item.text()
        old_value = item.data(tab._edit_role)
        if old_value is None:
            item.setData(tab._edit_role, new_value)
            tab._set_dirty(True)
            return
        old_value_str = str(old_value)
        if old_value_str == new_value:
            return

        row = item.row()
        item.setData(tab._edit_role, new_value)
        if tab.undo_stack:
            cmd = CallbackUndoCommand(
                f"Modifier cellule ({row + 1},{col + 1})",
                redo_callback=lambda t=table, r=row, c=col, v=new_value: self.apply_table_cell_value(t, r, c, v),
                undo_callback=lambda t=table, r=row, c=col, v=old_value_str: self.apply_table_cell_value(t, r, c, v),
                already_applied=True,
            )
            tab.undo_stack.push(cmd)
        tab._set_dirty(True)

    @staticmethod
    def replace_text(
        text: str,
        needle: str,
        repl: str,
        case_sensitive: bool,
        is_regex: bool,
    ) -> tuple[str, int]:
        if is_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.subn(needle, repl, text, flags=flags)
        if case_sensitive:
            return text.replace(needle, repl), text.count(needle)
        pattern = re.compile(re.escape(needle), re.IGNORECASE)
        return pattern.subn(repl, text)

    def search_replace_table(
        self,
        table: QTableWidget,
        needle: str,
        repl: str,
        case_sensitive: bool,
        is_regex: bool,
        *,
        text_col: int,
    ) -> int:
        tab = self._tab
        before_values: list[str] = []
        after_values: list[str] = []
        count_total = 0
        for row in range(table.rowCount()):
            item = table.item(row, text_col)
            old = item.text() if item is not None else ""
            new, count = self.replace_text(old, needle, repl, case_sensitive, is_regex)
            before_values.append(old)
            after_values.append(new)
            count_total += count
        if count_total <= 0:
            return 0
        if tab.undo_stack:
            cmd = CallbackUndoCommand(
                f"Rechercher/remplacer tableau ({count_total})",
                redo_callback=lambda t=table, c=text_col, v=after_values: self.apply_table_column_values(t, c, v),
                undo_callback=lambda t=table, c=text_col, v=before_values: self.apply_table_column_values(t, c, v),
            )
            tab.undo_stack.push(cmd)
        else:
            self.apply_table_column_values(table, text_col, after_values)
        return count_total

    def segment_to_utterances(self) -> None:
        tab = self._tab
        episode_id = tab.prep_episode_combo.currentData()
        if not episode_id:
            QMessageBox.warning(tab, "Préparer", "Sélectionnez un épisode.")
            return
        if tab._current_source_key != "transcript":
            QMessageBox.information(tab, "Préparer", "MVP: segmentation disponible sur Transcript.")
            return

        existing = tab.utterance_table.rowCount() > 0
        if existing:
            reply = QMessageBox.question(
                tab,
                "Préparer",
                "Des tours existent déjà pour cet épisode.\n\n"
                "Re-segmenter écrasera le découpage précédent. Continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        clean_text = tab.text_editor.toPlainText().strip()
        if not clean_text:
            QMessageBox.warning(tab, "Préparer", "Aucun transcript à segmenter.")
            return
        utterances = segmenter_utterances(clean_text)
        for seg in utterances:
            seg.episode_id = episode_id
        rows = [
            {
                "segment_id": u.segment_id,
                "n": u.n,
                "speaker_explicit": u.speaker_explicit,
                "text": u.text,
            }
            for u in utterances
        ]
        prev_rows = tab._export_utterance_rows()
        prev_widget_is_utterance = tab.stack.currentWidget() == tab.utterance_table

        def _redo() -> None:
            tab._updating_ui = True
            try:
                tab._set_utterances(rows)
                tab.stack.setCurrentWidget(tab.utterance_table)
            finally:
                tab._updating_ui = False
            tab._set_dirty(True)

        def _undo() -> None:
            tab._updating_ui = True
            try:
                tab._set_utterances(prev_rows)
                if prev_widget_is_utterance:
                    tab.stack.setCurrentWidget(tab.utterance_table)
                else:
                    tab.stack.setCurrentWidget(tab.text_editor)
            finally:
                tab._updating_ui = False
            tab._set_dirty(True)

        if tab.undo_stack:
            cmd = CallbackUndoCommand(
                f"Segmenter en tours ({len(rows)})",
                redo_callback=_redo,
                undo_callback=_undo,
            )
            tab.undo_stack.push(cmd)
        else:
            _redo()
        tab._show_status(f"{len(rows)} tour(s) généré(s).", 4000)
