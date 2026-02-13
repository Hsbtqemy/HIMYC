"""Dialogue pour gérer les profils de normalisation (liste, nouvel / modifier / supprimer)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.adapters.base import AdapterRegistry
from howimetyourcorpus.core.normalize.profiles import PROFILES, get_all_profile_ids
from howimetyourcorpus.core.storage.project_store import ProjectStore


class ProfilesDialog(QDialog):
    """Dialogue pour gérer les profils de normalisation (liste, nouvel / modifier / supprimer pour les personnalisés)."""

    def __init__(self, parent: QWidget | None, store: ProjectStore | None):
        super().__init__(parent)
        self.setWindowTitle("Profils de normalisation")
        self._store = store
        self._custom_list: list[dict[str, Any]] = []
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
        layout.addWidget(QLabel(
            "Profil par défaut par source (pour normalisation batch / Inspecteur) :\n"
            "Si un épisode n'a pas de « profil préféré », le profil de sa source est utilisé."
        ))
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

    def _load_list(self) -> None:
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

    def _on_selection_changed(self) -> None:
        item = self.list_widget.currentItem()
        is_custom = False
        if item:
            kind, _ = item.data(Qt.ItemDataRole.UserRole) or ("", "")
            is_custom = kind == "custom"
        self.edit_btn.setEnabled(is_custom)
        self.delete_btn.setEnabled(is_custom)

    def _save_custom(self) -> None:
        if self._store:
            self._store.save_custom_profiles(self._custom_list)
        self._load_list()
        if self.parent() and hasattr(self.parent(), "_refresh_profile_combos"):
            self.parent()._refresh_profile_combos()

    def _new_profile(self) -> None:
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

    def _edit_profile(self) -> None:
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

    def _delete_profile(self) -> None:
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

    def _load_source_profile_table(self) -> None:
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

    def _add_source_profile_row(self) -> None:
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

    def _remove_source_profile_row(self) -> None:
        row = self.source_profile_table.currentRow()
        if row >= 0:
            self.source_profile_table.removeRow(row)

    def _save_source_profile_defaults(self) -> None:
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

    def _close_profiles_dialog(self) -> None:
        self._save_source_profile_defaults()
        self.reject()
