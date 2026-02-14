"""Onglet Pilotage : fusion visuelle Projet + Corpus pour un workflow unique."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget


class PilotageTabWidget(QWidget):
    """Conteneur de pilotage qui assemble la configuration projet et le workflow corpus."""

    def __init__(
        self,
        *,
        project_widget: QWidget,
        corpus_widget: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_widget = project_widget
        self._corpus_widget = corpus_widget

        layout = QVBoxLayout(self)
        helper = QLabel(
            "Pilotage unifié : 1) configurer/ouvrir le projet, 2) exécuter le workflow corpus "
            "(import, normalisation, segmentation, indexation) puis passer à l'alignement."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #555;")
        layout.addWidget(helper)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._project_widget)
        self._splitter.addWidget(self._corpus_widget)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([320, 760])
        layout.addWidget(self._splitter)
        self._restore_splitter_sizes()

    def focus_corpus(self) -> None:
        """Met l'accent sur la zone Corpus quand l'utilisateur vient de la section Projet."""
        self._splitter.setSizes([220, 860])
        # Optionnel : donner le focus à la vue corpus si disponible.
        episodes_tree = getattr(self._corpus_widget, "episodes_tree", None)
        if episodes_tree is not None:
            episodes_tree.setFocus()

    def _restore_splitter_sizes(self) -> None:
        settings = QSettings()
        raw = settings.value("pilotage/splitter")
        if isinstance(raw, (list, tuple)):
            try:
                sizes = [int(x) for x in raw]
            except (TypeError, ValueError):
                return
            if len(sizes) >= 2:
                self._splitter.setSizes(sizes)

    def save_state(self) -> None:
        settings = QSettings()
        settings.setValue("pilotage/splitter", self._splitter.sizes())
