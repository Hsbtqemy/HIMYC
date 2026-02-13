"""Onglet Projet : dossier, source, URL série, profils, langues."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from howimetyourcorpus.core.adapters.base import AdapterRegistry
from howimetyourcorpus.core.normalize.profiles import PROFILES


class ProjectTabWidget(QWidget):
    """Widget de l'onglet Projet : formulaire dossier/source/URL, profils, langues."""

    def __init__(
        self,
        get_store: Callable[[], Any],
        on_validate_clicked: Callable[[], None],
        on_save_config: Callable[[], None] | None,
        on_open_profiles_dialog: Callable[[], None],
        on_refresh_language_combos: Callable[[], None],
        show_status: Callable[[str, int], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._validate_callback = on_validate_clicked
        self._save_config_callback = on_save_config
        self._open_profiles_callback = on_open_profiles_dialog
        self._refresh_language_combos_callback = on_refresh_language_combos
        self._show_status = show_status

        layout = QFormLayout(self)
        self.proj_root_edit = QLineEdit()
        self.proj_root_edit.setPlaceholderText("C:\\...\\projects\\MonProjet")
        browse_btn = QPushButton("Parcourir...")
        browse_btn.clicked.connect(self._browse)
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
        self.srt_only_cb.setToolTip(
            "Cochez si vous partez des SRT sans transcriptions. "
            "Si vous laissez l'URL série vide, le projet est considéré SRT only automatiquement."
        )
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
        validate_btn.clicked.connect(self._emit_validate)
        save_config_btn = QPushButton("Enregistrer la configuration")
        save_config_btn.setToolTip(
            "Sauvegarde la source, l'URL série, le profil, etc. dans config.toml (projet déjà ouvert)."
        )
        save_config_btn.clicked.connect(self._save_config)
        layout.addRow("", validate_btn)
        layout.addRow("", save_config_btn)
        profiles_btn = QPushButton("Gérer les profils de normalisation...")
        profiles_btn.setToolTip(
            "Créer, modifier ou supprimer les profils personnalisés (fichier profiles.json du projet)."
        )
        profiles_btn.clicked.connect(self._emit_open_profiles)
        layout.addRow("", profiles_btn)

        layout.addRow("", QLabel("Langues du projet (sous-titres, personnages, KWIC) :"))
        self.languages_list = QListWidget()
        self.languages_list.setMaximumHeight(80)
        self.languages_list.currentRowChanged.connect(self._on_languages_selection_changed)
        layout.addRow("", self.languages_list)
        lang_btn_row = QHBoxLayout()
        self.add_lang_btn = QPushButton("Ajouter une langue...")
        self.add_lang_btn.setToolTip(
            "Ajoute un code langue (ex. de, es) utilisé dans les sous-titres et personnages."
        )
        self.add_lang_btn.clicked.connect(self._add_language)
        self.remove_lang_btn = QPushButton("Supprimer la langue")
        self.remove_lang_btn.setToolTip(
            "Retire la langue sélectionnée de la liste (n'affecte pas les fichiers déjà importés)."
        )
        self.remove_lang_btn.clicked.connect(self._remove_language)
        lang_btn_row.addWidget(self.add_lang_btn)
        lang_btn_row.addWidget(self.remove_lang_btn)
        lang_btn_row.addStretch()
        layout.addRow("", lang_btn_row)

    def get_form_data(self) -> dict[str, Any]:
        """Retourne les données du formulaire pour init/charger le projet."""
        root = self.proj_root_edit.text().strip()
        source_id = self.source_id_combo.currentText() or "subslikescript"
        series_url = self.series_url_edit.text().strip()
        srt_only = self.srt_only_cb.isChecked() or not series_url
        if not series_url:
            series_url = ""
        rate_limit = self.rate_limit_spin.value()
        normalize_profile = self.normalize_profile_combo.currentText() or "default_en_v1"
        return {
            "root": root,
            "source_id": source_id,
            "series_url": series_url,
            "srt_only": srt_only,
            "rate_limit": rate_limit,
            "normalize_profile": normalize_profile,
        }

    def _save_config(self) -> None:
        """Enregistre la configuration du formulaire (source, URL, etc.) si un projet est ouvert."""
        if self._save_config_callback:
            self._save_config_callback()

    def set_project_state(self, root_path: Path, config: Any) -> None:
        """Remplit le formulaire après chargement d'un projet existant."""
        self.proj_root_edit.setText(str(root_path))
        self.series_url_edit.setText(config.series_url)
        self.srt_only_cb.setChecked(not (config.series_url or "").strip())
        self.normalize_profile_combo.setCurrentText(config.normalize_profile)
        self.rate_limit_spin.setValue(int(config.rate_limit_s))
        self.source_id_combo.setCurrentText(config.source_id)

    def refresh_languages_list(self) -> None:
        """Remplit la liste des langues depuis le store (appelé après ouverture projet)."""
        self.languages_list.clear()
        store = self._get_store()
        if store:
            for lang in store.load_project_languages():
                self.languages_list.addItem(lang)
        self.add_lang_btn.setEnabled(bool(store))
        self._on_languages_selection_changed()

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choisir le dossier projet")
        if d:
            self.proj_root_edit.setText(d)

    def _emit_validate(self) -> None:
        self._validate_callback()

    def _emit_open_profiles(self) -> None:
        self._open_profiles_callback()

    def _on_languages_selection_changed(self) -> None:
        store = self._get_store()
        self.remove_lang_btn.setEnabled(
            bool(store)
            and self.languages_list.count() > 0
            and self.languages_list.currentRow() >= 0
        )

    def _add_language(self) -> None:
        store = self._get_store()
        if not store:
            QMessageBox.warning(self, "Langues", "Ouvrez un projet d'abord.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Ajouter une langue")
        form = QFormLayout(dlg)
        code_edit = QLineEdit()
        code_edit.setPlaceholderText("ex. de, es, pt")
        code_edit.setMaxLength(10)
        form.addRow("Code langue (2–10 caractères):", code_edit)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        form.addRow(bbox)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        code = (code_edit.text() or "").strip().lower()
        if not code or len(code) < 2:
            QMessageBox.warning(
                self, "Langues", "Indiquez un code langue (au moins 2 caractères)."
            )
            return
        langs = store.load_project_languages()
        if code in langs:
            QMessageBox.information(
                self, "Langues", f"La langue « {code} » est déjà dans la liste."
            )
            return
        langs.append(code)
        langs.sort()
        store.save_project_languages(langs)
        self.refresh_languages_list()
        self._refresh_language_combos_callback()
        self._show_status(f"Langue « {code} » ajoutée.", 3000)

    def _remove_language(self) -> None:
        store = self._get_store()
        if not store:
            return
        row = self.languages_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "Langues", "Sélectionnez une langue à supprimer.")
            return
        code = self.languages_list.item(row).text()
        if (
            QMessageBox.question(
                self,
                "Supprimer la langue",
                f"Retirer « {code} » de la liste ? (Les pistes/cues déjà importés ne sont pas supprimés.)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        langs = store.load_project_languages()
        langs = [x for x in langs if x != code]
        store.save_project_languages(langs)
        self.refresh_languages_list()
        self._refresh_language_combos_callback()
        self._show_status(f"Langue « {code} » retirée de la liste.", 3000)
