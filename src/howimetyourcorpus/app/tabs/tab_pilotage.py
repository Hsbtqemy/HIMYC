"""Onglet Pilotage : fusion visuelle Projet + Corpus pour un workflow unique."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, Qt, QSettings
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_HELP_EXPANDED_KEY = "pilotage/helpExpanded"
_SPLITTER_KEY = "pilotage/splitter_hcols"
_PROJECT_PANEL_VISIBLE_KEY = "pilotage/projectPanelVisible"
_DEFAULT_SPLITTER_SIZES = [820, 560]
_RIGHT_PANEL_BOX_BASE_WIDTH = 440
_RIGHT_PANEL_BOX_EXPANDED_MAX_WIDTH = 860
_RIGHT_PANEL_BOX_SIDE_PADDING = 72


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
        self._right_column_boxes: list[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._header_widget = QWidget(self)
        self._header_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        header_layout = QVBoxLayout(self._header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._state_summary_label = QLabel("")
        self._state_summary_label.setStyleSheet("color: #505050; font-weight: 600;")
        self._state_summary_label.setWordWrap(True)
        self._state_summary_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        header_layout.addWidget(self._state_summary_label)

        self._project_panel_toggle_btn = QToolButton()
        self._project_panel_toggle_btn.setCheckable(True)
        self._project_panel_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._project_panel_toggle_btn.toggled.connect(self._set_project_panel_visible)

        self._help_toggle_btn = QToolButton()
        self._help_toggle_btn.setCheckable(True)
        self._help_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._help_toggle_btn.toggled.connect(self._set_help_expanded)

        top_actions_row = QHBoxLayout()
        top_actions_row.setContentsMargins(0, 0, 0, 0)
        top_actions_row.setSpacing(6)
        top_actions_row.addWidget(self._project_panel_toggle_btn)
        top_actions_row.addWidget(self._help_toggle_btn)
        top_actions_row.addSpacing(8)
        top_actions_row.addWidget(QLabel("Étapes suivantes:"))
        inspect_btn = QPushButton("Inspecteur (QA local)")
        inspect_btn.setToolTip("Comparer RAW/CLEAN, normaliser/segmenter un épisode, inspecter les pistes SRT.")
        inspect_btn.setMinimumHeight(28)
        inspect_btn.setEnabled(self._on_open_inspector is not None)
        inspect_btn.clicked.connect(self._open_inspector)
        top_actions_row.addWidget(inspect_btn)
        validation_btn = QPushButton("Validation & Annotation")
        validation_btn.setToolTip("Lancer/relire l'alignement et assigner/propager les personnages.")
        validation_btn.setMinimumHeight(28)
        validation_btn.setEnabled(self._on_open_validation is not None)
        validation_btn.clicked.connect(self._open_validation)
        top_actions_row.addWidget(validation_btn)
        concordance_btn = QPushButton("Concordance")
        concordance_btn.setToolTip("Explorer le corpus (KWIC) et exporter des résultats.")
        concordance_btn.setMinimumHeight(28)
        concordance_btn.setEnabled(self._on_open_concordance is not None)
        concordance_btn.clicked.connect(self._open_concordance)
        top_actions_row.addWidget(concordance_btn)
        top_actions_row.addStretch()
        header_layout.addLayout(top_actions_row)

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
        header_layout.addWidget(self._help_panel)
        layout.addWidget(self._header_widget, 0)

        self._right_column_content = QWidget(self)
        right_layout = QVBoxLayout(self._right_column_content)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        self._right_column_boxes.append(self._project_widget)
        project_row = QHBoxLayout()
        project_row.setContentsMargins(0, 0, 0, 0)
        project_row.setSpacing(0)
        project_row.addStretch()
        project_row.addWidget(self._project_widget)
        project_row.addStretch()
        right_layout.addLayout(project_row)
        take_sidebar_sections = getattr(self._corpus_widget, "take_right_column_sections", None)
        if callable(take_sidebar_sections):
            for section in take_sidebar_sections():
                self._right_column_boxes.append(section)
                section_row = QHBoxLayout()
                section_row.setContentsMargins(0, 0, 0, 0)
                section_row.setSpacing(0)
                section_row.addStretch()
                section_row.addWidget(section)
                section_row.addStretch()
                right_layout.addLayout(section_row)
        right_layout.addStretch()
        self._right_column_scroll = QScrollArea(self)
        self._right_column_scroll.setWidgetResizable(True)
        self._right_column_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._right_column_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._right_column_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._right_column_scroll.setWidget(self._right_column_content)
        self._right_column_scroll.viewport().installEventFilter(self)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._corpus_widget)
        self._splitter.addWidget(self._right_column_scroll)
        self._splitter.setChildrenCollapsible(False)
        self._right_column_scroll.setMinimumWidth(500)
        self._corpus_widget.setMinimumWidth(640)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes(list(_DEFAULT_SPLITTER_SIZES))
        self._splitter.splitterMoved.connect(self._on_splitter_moved)
        layout.addWidget(self._splitter, 1)
        self._restore_help_expanded()
        self._restore_splitter_sizes()
        self._restore_project_panel_visibility()
        self._update_right_panel_box_widths()
        self.refresh_state_banner()

    def eventFilter(self, obj, event):  # type: ignore[override]
        viewport = self._right_column_scroll.viewport() if hasattr(self, "_right_column_scroll") else None
        if obj is viewport and event.type() == QEvent.Type.Resize:
            self._update_right_panel_box_widths()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._update_right_panel_box_widths()

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
            if not self._right_column_scroll.isVisible():
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
        self._update_right_panel_box_widths()
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
        if len(sizes) >= 2 and sizes[1] > 0:
            self._project_panel_sizes = [int(sizes[0]), int(sizes[1])]
        self._right_column_scroll.setVisible(panel_visible)
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
            self._splitter.setSizes([total, 0])
        self._update_right_panel_box_widths()
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
                self._update_right_panel_box_widths()

    def save_state(self) -> None:
        settings = QSettings()
        settings.setValue(_SPLITTER_KEY, self._splitter.sizes())

    def _on_splitter_moved(self, *_args) -> None:
        self._update_right_panel_box_widths()

    def _update_right_panel_box_widths(self) -> None:
        if not self._right_column_boxes or not self._right_column_scroll.isVisible():
            return
        viewport = self._right_column_scroll.viewport()
        available = viewport.width() if viewport is not None else 0
        if available <= 0:
            available = self._right_column_scroll.width()
        if available <= 0:
            return
        target = max(
            _RIGHT_PANEL_BOX_BASE_WIDTH,
            min(
                _RIGHT_PANEL_BOX_EXPANDED_MAX_WIDTH,
                available - _RIGHT_PANEL_BOX_SIDE_PADDING,
            ),
        )
        for box in self._right_column_boxes:
            box.setMinimumWidth(target)
            box.setMaximumWidth(target)
