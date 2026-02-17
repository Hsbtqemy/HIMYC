"""Onglet Projet : dossier, source, URL série, profils, langues."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
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
        self._on_discover_episodes: Callable[[], None] | None = None
        self._on_fetch_all: Callable[[], None] | None = None

        main = QVBoxLayout(self)
        main.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)

        # —— 1. Projet (ouvrir / créer) ——
        group_projet = QGroupBox("Projet")
        group_projet.setToolTip("Choisir un dossier pour créer un nouveau projet ou ouvrir un projet existant.")
        form_projet = QFormLayout(group_projet)
        self.proj_root_edit = QLineEdit()
        self.proj_root_edit.setPlaceholderText("Chemin sélectionné apparaîtra ici...")
        self.proj_root_edit.setReadOnly(True)  # Lecture seule, rempli par le bouton
        form_projet.addRow("Dossier:", self.proj_root_edit)
        
        btn_row = QHBoxLayout()
        open_project_btn = QPushButton("📁 Ouvrir/Créer un projet...")
        open_project_btn.setToolTip(
            "Ouvre l'explorateur de fichiers pour sélectionner ou créer un dossier projet, "
            "puis valide automatiquement avec les paramètres ci-dessous."
        )
        open_project_btn.clicked.connect(self._browse_and_validate)
        open_project_btn.setDefault(True)
        save_config_btn = QPushButton("💾 Sauvegarder modifications")
        save_config_btn.setToolTip(
            "Sauvegarde les modifications (source, URL, profil) dans config.toml du projet déjà ouvert."
        )
        save_config_btn.clicked.connect(self._save_config)
        btn_row.addWidget(open_project_btn)
        btn_row.addWidget(save_config_btn)
        btn_row.addStretch()
        form_projet.addRow("", btn_row)
        layout.addWidget(group_projet)

        # —— 2. Source et série ——
        group_source = QGroupBox("Source et série")
        group_source.setToolTip("D’où viennent les épisodes et les transcripts (ignoré si projet SRT uniquement).")
        form_source = QFormLayout(group_source)
        self.source_id_combo = QComboBox()
        self.source_id_combo.addItems(AdapterRegistry.list_ids() or ["subslikescript"])
        self.source_id_combo.currentTextChanged.connect(self._on_source_changed)
        form_source.addRow("Source:", self.source_id_combo)
        
        # Label dynamique selon la source
        self.series_url_label = QLabel("URL série:")
        self.series_url_edit = QLineEdit()
        self.series_url_edit.setPlaceholderText("https://subslikescript.com/series/...")
        form_source.addRow(self.series_url_label, self.series_url_edit)
        self.srt_only_cb = QCheckBox("Projet SRT uniquement (sans transcriptions)")
        self.srt_only_cb.setToolTip(
            "Cochez si vous partez des SRT sans transcriptions. "
            "URL série vide = SRT only automatiquement."
        )
        form_source.addRow("", self.srt_only_cb)
        self.rate_limit_spin = QSpinBox()
        self.rate_limit_spin.setRange(1, 60)
        self.rate_limit_spin.setValue(2)
        self.rate_limit_spin.setSuffix(" s")
        self.rate_limit_spin.setToolTip("Délai minimal entre requêtes vers la source.")
        form_source.addRow("Rate limit:", self.rate_limit_spin)
        layout.addWidget(group_source)

        # —— 3. Acquisition (§15.3) ——
        group_acquisition = QGroupBox("Acquisition — Remplir le corpus")
        group_acquisition.setToolTip(
            "Découvrir les épisodes puis télécharger les transcripts. Le Corpus affiche la liste après téléchargement."
        )
        acq_row = QHBoxLayout(group_acquisition)
        self.discover_btn = QPushButton("Découvrir épisodes")
        self.discover_btn.setToolTip("Récupère la liste des épisodes depuis la source.")
        self.discover_btn.clicked.connect(self._on_discover_clicked)
        self.fetch_all_btn = QPushButton("Télécharger tout")
        self.fetch_all_btn.setToolTip("Télécharge tous les épisodes découverts. Rafraîchit le Corpus à la fin.")
        self.fetch_all_btn.clicked.connect(self._on_fetch_all_clicked)
        acq_row.addWidget(self.discover_btn)
        acq_row.addWidget(self.fetch_all_btn)
        acq_row.addStretch()
        layout.addWidget(group_acquisition)
        self.discover_btn.setEnabled(False)
        self.fetch_all_btn.setEnabled(False)

        # —— 4. Normalisation ——
        group_norm = QGroupBox("Normalisation")
        group_norm.setToolTip("Profil utilisé pour RAW → CLEAN (transcripts et sous-titres).")
        form_norm = QFormLayout(group_norm)
        self.normalize_profile_combo = QComboBox()
        self.normalize_profile_combo.addItems(list(PROFILES.keys()))
        form_norm.addRow("Profil:", self.normalize_profile_combo)
        profiles_btn = QPushButton("Gérer les profils…")
        profiles_btn.setToolTip("Créer, modifier ou supprimer les profils personnalisés (profiles.json).")
        profiles_btn.clicked.connect(self._emit_open_profiles)
        form_norm.addRow("", profiles_btn)
        layout.addWidget(group_norm)

        # —— 5. Langues ——
        group_lang = QGroupBox("Langues du projet")
        group_lang.setToolTip("Langues pour sous-titres, personnages et concordancier (ex. en, fr, it).")
        form_lang = QFormLayout(group_lang)
        self.languages_list = QListWidget()
        self.languages_list.setMaximumHeight(100)
        self.languages_list.currentRowChanged.connect(self._on_languages_selection_changed)
        form_lang.addRow("Codes langue:", self.languages_list)
        lang_btn_row = QHBoxLayout()
        self.add_lang_btn = QPushButton("Ajouter…")
        self.add_lang_btn.setToolTip("Ajouter un code langue (ex. de, es).")
        self.add_lang_btn.clicked.connect(self._add_language)
        self.remove_lang_btn = QPushButton("Supprimer")
        self.remove_lang_btn.setToolTip("Retirer la langue sélectionnée (n’affecte pas les fichiers déjà importés).")
        self.remove_lang_btn.clicked.connect(self._remove_language)
        lang_btn_row.addWidget(self.add_lang_btn)
        lang_btn_row.addWidget(self.remove_lang_btn)
        lang_btn_row.addStretch()
        form_lang.addRow("", lang_btn_row)
        layout.addWidget(group_lang)

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

    def set_acquisition_callbacks(
        self,
        on_discover_episodes: Callable[[], None] | None,
        on_fetch_all: Callable[[], None] | None,
    ) -> None:
        """§15.3 — Connecte Découvrir / Télécharger tout à la logique Corpus (appelé par MainWindow après création du Corpus)."""
        self._on_discover_episodes = on_discover_episodes
        self._on_fetch_all = on_fetch_all
    
    def _on_source_changed(self, source_id: str) -> None:
        """Adapte le label et placeholder selon la source sélectionnée."""
        if source_id == "tvmaze":
            self.series_url_label.setText("Nom de la série:")
            self.series_url_edit.setPlaceholderText("Breaking Bad, The Wire, Friends...")
            self.series_url_edit.setToolTip(
                "Nom de la série à rechercher sur TVMaze. "
                "TVMaze retournera la liste complète des épisodes, "
                "que vous pourrez ensuite remplir avec des transcripts ou des SRT."
            )
        else:  # subslikescript ou autre
            self.series_url_label.setText("URL série:")
            self.series_url_edit.setPlaceholderText("https://subslikescript.com/series/...")
            self.series_url_edit.setToolTip("URL de la page série sur le site source.")

    def _on_discover_clicked(self) -> None:
        if self._on_discover_episodes:
            self._on_discover_episodes()
        else:
            self._show_status("Ouvrez un projet puis utilisez l'onglet Corpus pour découvrir les épisodes.", 4000)

    def _on_fetch_all_clicked(self) -> None:
        if self._on_fetch_all:
            self._on_fetch_all()
        else:
            self._show_status("Ouvrez un projet puis utilisez l'onglet Corpus pour télécharger.", 4000)

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
        # Déclencher l'adaptation du label après changement de source
        self._on_source_changed(config.source_id)

    def refresh_languages_list(self) -> None:
        """Remplit la liste des langues depuis le store (appelé après ouverture projet)."""
        self.languages_list.clear()
        store = self._get_store()
        if store:
            for lang in store.load_project_languages():
                self.languages_list.addItem(lang)
        self.add_lang_btn.setEnabled(bool(store))
        # §15.3 — Découvrir / Télécharger tout actifs seulement si projet ouvert
        self.discover_btn.setEnabled(bool(store))
        self.fetch_all_btn.setEnabled(bool(store))
        self._on_languages_selection_changed()

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choisir le dossier projet")
        if d:
            self.proj_root_edit.setText(d)
    
    def _browse_and_validate(self) -> None:
        """Ouvre l'explorateur, sélectionne un dossier, puis valide automatiquement."""
        d = QFileDialog.getExistingDirectory(self, "Sélectionner ou créer un dossier projet")
        if d:
            self.proj_root_edit.setText(d)
            # Valider automatiquement après sélection
            self._emit_validate()

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
