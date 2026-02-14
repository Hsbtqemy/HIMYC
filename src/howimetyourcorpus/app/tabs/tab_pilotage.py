"""Onglet Pilotage : fusion visuelle Projet + Corpus pour un workflow unique."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSplitter, QToolButton, QVBoxLayout, QWidget

_HELP_EXPANDED_KEY = "pilotage/helpExpanded"
_SPLITTER_KEY = "pilotage/splitter"
_PROJECT_PANEL_VISIBLE_KEY = "pilotage/projectPanelVisible"
_DEFAULT_SPLITTER_SIZES = [320, 760]


class PilotageTabWidget(QWidget):
    """Conteneur de pilotage qui assemble la configuration projet et le workflow corpus."""

    def __init__(
        self,
        *,
        project_widget: QWidget,
        corpus_widget: QWidget,
        on_open_inspector: Callable[[], None] | None = None,
        on_open_validation: Callable[[], None] | None = None,
        on_open_concordance: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_widget = project_widget
        self._corpus_widget = corpus_widget
        self._on_open_inspector = on_open_inspector
        self._on_open_validation = on_open_validation
        self._on_open_concordance = on_open_concordance
        self._project_panel_sizes = list(_DEFAULT_SPLITTER_SIZES)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self._state_summary_label = QLabel("")
        self._state_summary_label.setStyleSheet("color: #505050; font-weight: 600;")
        self._state_summary_label.setWordWrap(True)
        layout.addWidget(self._state_summary_label)

        self._project_panel_toggle_btn = QToolButton()
        self._project_panel_toggle_btn.setCheckable(True)
        self._project_panel_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._project_panel_toggle_btn.toggled.connect(self._set_project_panel_visible)
        layout.addWidget(self._project_panel_toggle_btn)

        self._help_toggle_btn = QToolButton()
        self._help_toggle_btn.setCheckable(True)
        self._help_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._help_toggle_btn.toggled.connect(self._set_help_expanded)
        layout.addWidget(self._help_toggle_btn)

        self._help_panel = QWidget(self)
        help_layout = QVBoxLayout(self._help_panel)
        help_layout.setContentsMargins(0, 0, 0, 0)
        help_layout.setSpacing(4)
        helper = QLabel(
            "Pilotage unifié : 1) configurer/ouvrir le projet, 2) exécuter le workflow corpus "
            "(import, normalisation, segmentation, indexation) puis passer à l'alignement."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #555;")
        help_layout.addWidget(helper)
        policy = QLabel(
            "Politique profils: Acquisition = source + rate limit (web/API). "
            "Normalisation = transcript RAW→CLEAN + pistes sous-titres "
            "(profil épisode > défaut source > profil batch). "
            "Export = format de sortie uniquement (pas de normalisation implicite)."
        )
        policy.setWordWrap(True)
        policy.setStyleSheet("color: #666;")
        help_layout.addWidget(policy)
        layout.addWidget(self._help_panel)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(6)
        nav_row.addWidget(QLabel("Étapes suivantes:"))
        inspect_btn = QPushButton("Inspecteur (QA local)")
        inspect_btn.setToolTip("Comparer RAW/CLEAN, normaliser/segmenter un épisode, inspecter les pistes SRT.")
        inspect_btn.setMinimumHeight(28)
        inspect_btn.setEnabled(self._on_open_inspector is not None)
        inspect_btn.clicked.connect(self._open_inspector)
        nav_row.addWidget(inspect_btn)
        validation_btn = QPushButton("Validation & Annotation")
        validation_btn.setToolTip("Lancer/relire l'alignement et assigner/propager les personnages.")
        validation_btn.setMinimumHeight(28)
        validation_btn.setEnabled(self._on_open_validation is not None)
        validation_btn.clicked.connect(self._open_validation)
        nav_row.addWidget(validation_btn)
        concordance_btn = QPushButton("Concordance")
        concordance_btn.setToolTip("Explorer le corpus (KWIC) et exporter des résultats.")
        concordance_btn.setMinimumHeight(28)
        concordance_btn.setEnabled(self._on_open_concordance is not None)
        concordance_btn.clicked.connect(self._open_concordance)
        nav_row.addWidget(concordance_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._project_widget)
        self._splitter.addWidget(self._corpus_widget)
        self._splitter.setChildrenCollapsible(False)
        self._project_widget.setMinimumHeight(180)
        self._corpus_widget.setMinimumHeight(360)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes(list(_DEFAULT_SPLITTER_SIZES))
        layout.addWidget(self._splitter)
        self._restore_help_expanded()
        self._restore_splitter_sizes()
        self._restore_project_panel_visibility()
        self.refresh_state_banner()

    def focus_corpus(self) -> None:
        """Met l'accent sur la zone Corpus quand l'utilisateur vient de la section Projet."""
        self._set_project_panel_visible(False)
        self.refresh_state_banner()
        # Optionnel : donner le focus à la vue corpus si disponible.
        episodes_tree = getattr(self._corpus_widget, "episodes_tree", None)
        if episodes_tree is not None:
            episodes_tree.setFocus()

    def refresh_state_banner(self) -> None:
        """Affiche un résumé d'état compact pour réduire la charge visuelle de l'entête."""
        project_store_getter = getattr(self._project_widget, "_get_store", None)
        project_open = bool(callable(project_store_getter) and project_store_getter())
        index = getattr(self._corpus_widget, "_cached_index", None)
        n_episodes = len(index.episodes) if index and getattr(index, "episodes", None) else 0

        if not project_open:
            if not self._project_widget.isVisible():
                self._set_project_panel_visible(True, persist=False)
            self._state_summary_label.setText(
                "État rapide: projet non ouvert. Commencez par « Ouvrir / créer le projet »."
            )
            return
        if n_episodes <= 0:
            self._state_summary_label.setText(
                "État rapide: projet ouvert, 0 épisode. Prochaine action: « Découvrir épisodes »."
            )
            return
        self._state_summary_label.setText(
            f"État rapide: projet ouvert, {n_episodes} épisode(s) dans le corpus."
        )

    def reset_layout(self) -> None:
        """Réinitialise la répartition Projet/Corpus à la configuration par défaut."""
        self._project_panel_sizes = list(_DEFAULT_SPLITTER_SIZES)
        self._set_project_panel_visible(True)
        self._splitter.setSizes(list(_DEFAULT_SPLITTER_SIZES))
        self.save_state()

    def _open_inspector(self) -> None:
        if self._on_open_inspector:
            self._on_open_inspector()

    def _open_validation(self) -> None:
        if self._on_open_validation:
            self._on_open_validation()

    def _open_concordance(self) -> None:
        if self._on_open_concordance:
            self._on_open_concordance()

    def _set_help_expanded(self, expanded: bool, *, persist: bool = True) -> None:
        self._help_panel.setVisible(bool(expanded))
        self._help_toggle_btn.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._help_toggle_btn.setText(
            "Aide workflow (masquer)" if expanded else "Aide workflow (afficher)"
        )
        if persist:
            settings = QSettings()
            settings.setValue(_HELP_EXPANDED_KEY, bool(expanded))

    def _restore_help_expanded(self) -> None:
        settings = QSettings()
        expanded = bool(settings.value(_HELP_EXPANDED_KEY, False))
        self._help_toggle_btn.blockSignals(True)
        self._help_toggle_btn.setChecked(expanded)
        self._help_toggle_btn.blockSignals(False)
        self._set_help_expanded(expanded, persist=False)

    def _set_project_panel_visible(self, visible: bool, *, persist: bool = True) -> None:
        panel_visible = bool(visible)
        sizes = self._splitter.sizes()
        if len(sizes) >= 2 and sizes[0] > 0:
            self._project_panel_sizes = [int(sizes[0]), int(sizes[1])]
        self._project_widget.setVisible(panel_visible)
        self._project_panel_toggle_btn.blockSignals(True)
        self._project_panel_toggle_btn.setChecked(panel_visible)
        self._project_panel_toggle_btn.blockSignals(False)
        self._project_panel_toggle_btn.setArrowType(
            Qt.ArrowType.DownArrow if panel_visible else Qt.ArrowType.RightArrow
        )
        self._project_panel_toggle_btn.setText(
            "Configuration projet (masquer)" if panel_visible else "Configuration projet (afficher)"
        )
        if panel_visible:
            self._splitter.setSizes(list(self._project_panel_sizes))
        else:
            total = max(1, sum(self._splitter.sizes()))
            self._splitter.setSizes([0, total])
        if persist:
            settings = QSettings()
            settings.setValue(_PROJECT_PANEL_VISIBLE_KEY, panel_visible)

    def _restore_project_panel_visibility(self) -> None:
        settings = QSettings()
        raw = settings.value(_PROJECT_PANEL_VISIBLE_KEY, True)
        if isinstance(raw, str):
            visible = raw.strip().lower() in {"1", "true", "yes", "on"}
        else:
            visible = bool(raw)
        self._set_project_panel_visible(visible, persist=False)

    def _restore_splitter_sizes(self) -> None:
        settings = QSettings()
        raw = settings.value(_SPLITTER_KEY)
        if isinstance(raw, (list, tuple)):
            try:
                sizes = [int(x) for x in raw]
            except (TypeError, ValueError):
                return
            if len(sizes) >= 2:
                self._splitter.setSizes(sizes)

    def save_state(self) -> None:
        settings = QSettings()
        settings.setValue(_SPLITTER_KEY, self._splitter.sizes())
