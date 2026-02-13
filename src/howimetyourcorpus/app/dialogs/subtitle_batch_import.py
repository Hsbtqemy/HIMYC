"""Dialogue pour mapper fichiers SRT/VTT → épisode + langue puis lancer l'import en masse."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)


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
