"""Onglet Projet : dossier, source, URL série, profils, langues."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QSettings
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.app.feedback import warn_precondition

from howimetyourcorpus.core.acquisition.profiles import (
    DEFAULT_ACQUISITION_PROFILE_ID,
    PROFILES as ACQUISITION_PROFILES,
)
from howimetyourcorpus.core.adapters.base import AdapterRegistry
from howimetyourcorpus.core.normalize.profiles import PROFILES

_PROJECT_DETAILS_EXPANDED_KEY = "project/detailsExpanded"


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
        self._on_open_corpus: Callable[[], None] | None = None
        self._details_expanded = False

        main = QVBoxLayout(self)
        main.setSpacing(8)
        main.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # —— 1. Projet (ouvrir / créer) ——
        self.group_projet = QGroupBox("Projet")
        self.group_projet.setToolTip("Choisir un dossier pour créer un nouveau projet ou ouvrir un projet existant.")
        form_projet = QFormLayout(self.group_projet)
        form_projet.setHorizontalSpacing(8)
        form_projet.setVerticalSpacing(6)
        form_projet.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_projet.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_projet.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.proj_root_edit = QLineEdit()
        self.proj_root_edit.setPlaceholderText("C:\\...\\MonProjet ou /path/to/project")
        self.browse_btn = QPushButton("Parcourir…")
        self.browse_btn.clicked.connect(self._browse)
        row_root = QHBoxLayout()
        row_root.setContentsMargins(0, 0, 0, 0)
        row_root.setSpacing(6)
        row_root.addWidget(self.proj_root_edit, 1)
        row_root.addWidget(self.browse_btn)
        form_projet.addRow("Dossier:", row_root)
        btn_row = QHBoxLayout()
        self.validate_btn = QPushButton("Ouvrir / créer le projet")
        self.validate_btn.setMinimumHeight(30)
        self.validate_btn.clicked.connect(self._emit_validate)
        self.validate_btn.setDefault(True)
        self.save_config_btn = QPushButton("Enregistrer la config.")
        self.save_config_btn.setMinimumHeight(30)
        self.save_config_btn.setToolTip(
            "Sauvegarde source, URL série, profil, etc. dans config.toml (projet déjà ouvert)."
        )
        self.save_config_btn.clicked.connect(self._save_config)
        self._save_config_btn_tooltip_default = self.save_config_btn.toolTip()
        btn_row.addWidget(self.validate_btn)
        btn_row.addWidget(self.save_config_btn)
        btn_row.addStretch()
        form_projet.addRow("", btn_row)
        layout.addWidget(self.group_projet)

        self.project_summary_group = QGroupBox("Résumé projet")
        self.project_summary_group.setToolTip("Vue compacte du projet actif avec accès direct au workflow corpus.")
        summary_layout = QVBoxLayout(self.project_summary_group)
        summary_layout.setContentsMargins(8, 8, 8, 8)
        summary_layout.setSpacing(6)
        self.project_summary_label = QLabel("")
        self.project_summary_label.setWordWrap(True)
        self.project_summary_label.setStyleSheet("color: #505050;")
        summary_layout.addWidget(self.project_summary_label)
        summary_actions = QHBoxLayout()
        self.project_toggle_details_btn = QPushButton("Modifier détails")
        self.project_toggle_details_btn.setMinimumHeight(28)
        self.project_toggle_details_btn.setToolTip(
            "Affiche/masque les sections avancées (Source, Normalisation, Langues)."
        )
        self.project_toggle_details_btn.clicked.connect(self._toggle_project_details)
        summary_actions.addWidget(self.project_toggle_details_btn)
        self.open_corpus_compact_btn = QPushButton("Aller à la section Corpus")
        self.open_corpus_compact_btn.setMinimumHeight(30)
        self.open_corpus_compact_btn.setStyleSheet("font-weight: 600;")
        self.open_corpus_compact_btn.setToolTip(
            "Aller à la section Corpus du Pilotage pour exécuter les opérations Import/Transformer/Indexer."
        )
        self.open_corpus_compact_btn.clicked.connect(self._on_open_corpus_clicked)
        summary_actions.addWidget(self.open_corpus_compact_btn)
        summary_actions.addStretch()
        summary_layout.addLayout(summary_actions)
        self.project_summary_group.setVisible(False)
        layout.addWidget(self.project_summary_group)

        # L'action d'ouverture Corpus est portée par le résumé (évite le doublon de bouton).
        self.open_corpus_btn = self.open_corpus_compact_btn

        # —— 2. Détails configuration (onglets internes) ——
        self.project_details_tabs = QTabWidget()
        self.project_details_tabs.setDocumentMode(True)
        self.project_details_tabs.setUsesScrollButtons(True)
        layout.addWidget(self.project_details_tabs)

        # Onglet Source
        source_page = QWidget()
        source_page_layout = QVBoxLayout(source_page)
        source_page_layout.setContentsMargins(0, 0, 0, 0)
        source_page_layout.setSpacing(8)
        self.group_source = QGroupBox("Source et série")
        self.group_source.setToolTip("D’où viennent les épisodes et les transcripts (ignoré si projet SRT uniquement).")
        form_source = QFormLayout(self.group_source)
        form_source.setHorizontalSpacing(8)
        form_source.setVerticalSpacing(6)
        form_source.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_source.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_source.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.source_id_combo = QComboBox()
        self.source_id_combo.addItems(AdapterRegistry.list_ids() or ["subslikescript"])
        form_source.addRow("Source:", self.source_id_combo)
        self.acquisition_profile_combo = QComboBox()
        self.acquisition_profile_combo.addItems(list(ACQUISITION_PROFILES.keys()))
        self.acquisition_profile_combo.setToolTip(
            "Profil d'acquisition (scraping): politique de débit/tolérance HTTP."
        )
        form_source.addRow("Profil acquisition:", self.acquisition_profile_combo)
        self.acquisition_profile_details = QLabel("")
        self.acquisition_profile_details.setStyleSheet("color: #666;")
        self.acquisition_profile_details.setWordWrap(True)
        form_source.addRow("", self.acquisition_profile_details)
        self.series_url_edit = QLineEdit()
        self.series_url_edit.setPlaceholderText("https://subslikescript.com/series/...")
        form_source.addRow("URL série:", self.series_url_edit)
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
        self._last_applied_acquisition_profile_id = DEFAULT_ACQUISITION_PROFILE_ID
        self.acquisition_profile_combo.currentTextChanged.connect(self._on_acquisition_profile_changed)
        self.rate_limit_spin.valueChanged.connect(self._refresh_acquisition_runtime_preview)
        self._refresh_acquisition_runtime_preview()
        source_page_layout.addWidget(self.group_source)
        source_page_layout.addStretch()
        self.project_details_tabs.addTab(source_page, "Source")
        self.project_details_tabs.setTabToolTip(
            self.project_details_tabs.indexOf(source_page),
            "Configuration source/acquisition (URL série, profil, rate limit).",
        )

        # Onglet Normalisation
        norm_page = QWidget()
        norm_page_layout = QVBoxLayout(norm_page)
        norm_page_layout.setContentsMargins(0, 0, 0, 0)
        norm_page_layout.setSpacing(8)
        self.open_corpus_btn.setEnabled(False)
        self.open_corpus_compact_btn.setEnabled(False)
        self.save_config_btn.setEnabled(False)

        self.group_norm = QGroupBox("Normalisation")
        self.group_norm.setToolTip("Profil utilisé pour RAW → CLEAN (transcripts et sous-titres).")
        form_norm = QFormLayout(self.group_norm)
        form_norm.setHorizontalSpacing(8)
        form_norm.setVerticalSpacing(6)
        form_norm.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_norm.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_norm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.normalize_profile_combo = QComboBox()
        self.normalize_profile_combo.addItems(list(PROFILES.keys()))
        form_norm.addRow("Profil:", self.normalize_profile_combo)
        self.profiles_btn = QPushButton("Gérer les profils…")
        self.profiles_btn.setMinimumHeight(28)
        self.profiles_btn.setToolTip("Créer, modifier ou supprimer les profils personnalisés (profiles.json).")
        self.profiles_btn.clicked.connect(self._emit_open_profiles)
        form_norm.addRow("", self.profiles_btn)
        norm_policy = QLabel(
            "Le profil de normalisation s'applique aux transcripts (RAW→CLEAN, Pilotage/Inspecteur) "
            "et aux pistes SRT/VTT via « Normaliser la piste ». "
            "Les exports (TXT/CSV/JSON/JSONL/Word/SRT) n'appliquent pas de normalisation cachée."
        )
        norm_policy.setWordWrap(True)
        norm_policy.setStyleSheet("color: #666;")
        form_norm.addRow("", norm_policy)
        norm_page_layout.addWidget(self.group_norm)
        norm_page_layout.addStretch()
        self.project_details_tabs.addTab(norm_page, "Normalisation")
        self.project_details_tabs.setTabToolTip(
            self.project_details_tabs.indexOf(norm_page),
            "Profil RAW→CLEAN appliqué au workflow batch et à l'inspection locale.",
        )

        # Onglet Langues
        lang_page = QWidget()
        lang_page_layout = QVBoxLayout(lang_page)
        lang_page_layout.setContentsMargins(0, 0, 0, 0)
        lang_page_layout.setSpacing(8)
        self.group_lang = QGroupBox("Langues du projet")
        self.group_lang.setToolTip("Langues pour sous-titres, personnages et concordancier (ex. en, fr, it).")
        form_lang = QFormLayout(self.group_lang)
        form_lang.setHorizontalSpacing(8)
        form_lang.setVerticalSpacing(6)
        form_lang.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_lang.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_lang.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.languages_list = QListWidget()
        self.languages_list.setMaximumHeight(100)
        self.languages_list.currentRowChanged.connect(self._on_languages_selection_changed)
        form_lang.addRow("Codes langue:", self.languages_list)
        lang_btn_row = QHBoxLayout()
        self.add_lang_btn = QPushButton("Ajouter…")
        self.add_lang_btn.setMinimumHeight(28)
        self.add_lang_btn.setToolTip("Ajouter un code langue (ex. de, es).")
        self.add_lang_btn.clicked.connect(self._add_language)
        self.remove_lang_btn = QPushButton("Supprimer")
        self.remove_lang_btn.setMinimumHeight(28)
        self.remove_lang_btn.setToolTip("Retirer la langue sélectionnée (n’affecte pas les fichiers déjà importés).")
        self.remove_lang_btn.clicked.connect(self._remove_language)
        lang_btn_row.addWidget(self.add_lang_btn)
        lang_btn_row.addWidget(self.remove_lang_btn)
        lang_btn_row.addStretch()
        form_lang.addRow("", lang_btn_row)
        lang_page_layout.addWidget(self.group_lang)
        lang_page_layout.addStretch()
        self.project_details_tabs.addTab(lang_page, "Langues")
        self.project_details_tabs.setTabToolTip(
            self.project_details_tabs.indexOf(lang_page),
            "Codes langue projet utilisés par sous-titres, annotation et concordance.",
        )

        layout.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll)

        self.proj_root_edit.textChanged.connect(self._refresh_project_summary)
        self.source_id_combo.currentTextChanged.connect(self._refresh_project_summary)
        self.series_url_edit.textChanged.connect(self._refresh_project_summary)
        self.acquisition_profile_combo.currentTextChanged.connect(self._refresh_project_summary)
        self.normalize_profile_combo.currentTextChanged.connect(self._refresh_project_summary)
        self.rate_limit_spin.valueChanged.connect(self._refresh_project_summary)
        self._details_expanded = self._read_details_expanded_setting()
        self._set_project_details_expanded(True, persist=False)
        self._refresh_project_summary()
        self._configure_tab_order()

    def _configure_tab_order(self) -> None:
        """Ordre clavier explicite pour le panneau Projet (accessibilité)."""
        chain = [
            self.proj_root_edit,
            self.browse_btn,
            self.validate_btn,
            self.save_config_btn,
            self.project_toggle_details_btn,
            self.open_corpus_compact_btn,
            self.project_details_tabs,
            self.source_id_combo,
            self.acquisition_profile_combo,
            self.series_url_edit,
            self.srt_only_cb,
            self.rate_limit_spin,
            self.normalize_profile_combo,
            self.profiles_btn,
            self.languages_list,
            self.add_lang_btn,
            self.remove_lang_btn,
        ]
        for current, nxt in zip(chain, chain[1:]):
            self.setTabOrder(current, nxt)

    def first_focus_widget(self) -> QWidget:
        """Point d'entrée focus (Pilotage)."""
        return self.proj_root_edit

    def last_focus_widget(self) -> QWidget:
        """Point de sortie focus (Pilotage)."""
        return self.remove_lang_btn

    def set_open_corpus_callback(
        self,
        on_open_corpus: Callable[[], None] | None,
    ) -> None:
        """Connecte le bouton Projet -> ouverture de la section Corpus dans Pilotage."""
        self._on_open_corpus = on_open_corpus

    def _on_open_corpus_clicked(self) -> None:
        if self._on_open_corpus:
            self._on_open_corpus()
        else:
            self._show_status("Ouvrez un projet puis utilisez la section Corpus dans Pilotage.", 4000)

    def get_form_data(self) -> dict[str, Any]:
        """Retourne les données du formulaire pour init/charger le projet."""
        root = self.proj_root_edit.text().strip()
        source_id = self.source_id_combo.currentText() or "subslikescript"
        series_url = self.series_url_edit.text().strip()
        srt_only = self.srt_only_cb.isChecked() or not series_url
        if not series_url:
            series_url = ""
        rate_limit = self.rate_limit_spin.value()
        acquisition_profile_id = (
            self.acquisition_profile_combo.currentText() or DEFAULT_ACQUISITION_PROFILE_ID
        )
        normalize_profile = self.normalize_profile_combo.currentText() or "default_en_v1"
        return {
            "root": root,
            "source_id": source_id,
            "series_url": series_url,
            "srt_only": srt_only,
            "rate_limit": rate_limit,
            "acquisition_profile_id": acquisition_profile_id,
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
        if self.normalize_profile_combo.findText(config.normalize_profile) >= 0:
            self.normalize_profile_combo.setCurrentText(config.normalize_profile)
        elif self.normalize_profile_combo.count() > 0:
            self.normalize_profile_combo.setCurrentIndex(0)
        acq_profile_id = getattr(config, "acquisition_profile_id", DEFAULT_ACQUISITION_PROFILE_ID)
        if self.acquisition_profile_combo.findText(acq_profile_id) >= 0:
            self.acquisition_profile_combo.setCurrentText(acq_profile_id)
        elif self.acquisition_profile_combo.count() > 0:
            self.acquisition_profile_combo.setCurrentIndex(0)
        self._last_applied_acquisition_profile_id = (
            self.acquisition_profile_combo.currentText() or DEFAULT_ACQUISITION_PROFILE_ID
        )
        self.rate_limit_spin.setValue(int(config.rate_limit_s))
        self.source_id_combo.setCurrentText(config.source_id)
        self._refresh_acquisition_runtime_preview()
        self._refresh_project_summary()

    def refresh_languages_list(self) -> None:
        """Remplit la liste des langues depuis le store (appelé après ouverture projet)."""
        self.languages_list.clear()
        store = self._get_store()
        if store:
            for lang in store.load_project_languages():
                self.languages_list.addItem(lang)
        self.add_lang_btn.setEnabled(bool(store))
        self.open_corpus_btn.setEnabled(bool(store))
        self.open_corpus_compact_btn.setEnabled(bool(store))
        self.save_config_btn.setEnabled(bool(store))
        self.project_summary_group.setVisible(bool(store))
        if store:
            self.save_config_btn.setToolTip(self._save_config_btn_tooltip_default)
            self._set_project_details_expanded(self._details_expanded, persist=False)
        else:
            self.save_config_btn.setToolTip("Action indisponible: ouvrez un projet d'abord.")
            self._set_project_details_expanded(True, persist=False)
        self._on_languages_selection_changed()
        self._refresh_project_summary()

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

    def _on_acquisition_profile_changed(self, profile_id: str) -> None:
        """Ajuste le rate-limit par défaut quand le profil change, sans écraser un override manuel."""
        previous = ACQUISITION_PROFILES.get(self._last_applied_acquisition_profile_id)
        new_profile = ACQUISITION_PROFILES.get(profile_id)
        if new_profile is None:
            self._last_applied_acquisition_profile_id = profile_id
            self._refresh_acquisition_runtime_preview()
            return
        current_rate = int(self.rate_limit_spin.value())
        previous_default = int(round(previous.default_rate_limit_s)) if previous else None
        if previous_default is None or current_rate == previous_default:
            self.rate_limit_spin.setValue(int(round(new_profile.default_rate_limit_s)))
        self._last_applied_acquisition_profile_id = profile_id
        self._refresh_acquisition_runtime_preview()

    def _refresh_acquisition_runtime_preview(self) -> None:
        """Met à jour les détails du profil d'acquisition depuis le formulaire Projet."""
        profile_id = self.acquisition_profile_combo.currentText() or DEFAULT_ACQUISITION_PROFILE_ID
        profile = ACQUISITION_PROFILES.get(profile_id)
        if profile is not None:
            self.acquisition_profile_details.setText(
                f"{profile.label}: {profile.description}"
            )
        else:
            self.acquisition_profile_details.setText("")
        self._refresh_project_summary()

    @staticmethod
    def _read_details_expanded_setting() -> bool:
        settings = QSettings()
        raw = settings.value(_PROJECT_DETAILS_EXPANDED_KEY, False)
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw)

    def _set_project_details_expanded(self, expanded: bool, *, persist: bool = True) -> None:
        self._details_expanded = bool(expanded)
        self.project_details_tabs.setVisible(self._details_expanded)
        self.project_toggle_details_btn.setText("Masquer détails" if self._details_expanded else "Modifier détails")
        if persist:
            settings = QSettings()
            settings.setValue(_PROJECT_DETAILS_EXPANDED_KEY, self._details_expanded)

    def _toggle_project_details(self) -> None:
        self._set_project_details_expanded(not self._details_expanded, persist=True)

    def _refresh_project_summary(self, *_args) -> None:
        summary_label = getattr(self, "project_summary_label", None)
        if summary_label is None:
            return

        root_edit = getattr(self, "proj_root_edit", None)
        source_combo = getattr(self, "source_id_combo", None)
        acq_combo = getattr(self, "acquisition_profile_combo", None)
        norm_combo = getattr(self, "normalize_profile_combo", None)
        rate_spin = getattr(self, "rate_limit_spin", None)
        series_url_edit = getattr(self, "series_url_edit", None)
        languages_list = getattr(self, "languages_list", None)

        root = (root_edit.text().strip() if root_edit is not None else "") or "—"
        source = (source_combo.currentText().strip() if source_combo is not None else "") or "—"
        acq = (acq_combo.currentText().strip() if acq_combo is not None else "") or "—"
        norm = (norm_combo.currentText().strip() if norm_combo is not None else "") or "—"
        rate = int(rate_spin.value()) if rate_spin is not None else 0
        series_url = ((series_url_edit.text() if series_url_edit is not None else "") or "").strip()
        source_desc = "SRT only" if not series_url else f"URL: {series_url}"
        langs = int(languages_list.count()) if languages_list is not None else 0
        summary_label.setText(
            " | ".join(
                (
                    f"Dossier: {root}",
                    f"Source: {source}",
                    f"Acquisition: {acq} ({rate}s)",
                    f"Normalisation: {norm}",
                    f"{source_desc}",
                    f"Langues: {langs}",
                )
            )
        )

    def _add_language(self) -> None:
        store = self._get_store()
        if not store:
            warn_precondition(
                self,
                "Langues",
                "Ouvrez un projet d'abord.",
                next_step="Pilotage > Projet: ouvrez ou initialisez un projet.",
            )
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
            warn_precondition(
                self,
                "Langues",
                "Indiquez un code langue (au moins 2 caractères).",
            )
            return
        langs = store.load_project_languages()
        if code in langs:
            warn_precondition(
                self,
                "Langues",
                f"La langue « {code} » est déjà dans la liste.",
                next_step="Indiquez un autre code (ex. de, es, pt) ou annulez.",
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
            warn_precondition(
                self,
                "Langues",
                "Ouvrez un projet d'abord.",
                next_step="Pilotage > Projet: ouvrez ou initialisez un projet.",
            )
            return
        row = self.languages_list.currentRow()
        if row < 0:
            warn_precondition(
                self,
                "Langues",
                "Sélectionnez une langue à supprimer.",
                next_step="Cliquez une langue dans la liste, puis relancez « Supprimer ».",
            )
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
