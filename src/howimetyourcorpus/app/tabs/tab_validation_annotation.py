"""Onglet Validation & Annotation : regroupe Alignement et Personnages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget


class ValidationAnnotationTabWidget(QWidget):
    """Conteneur UI pour validation des liens et annotation des personnages."""

    def __init__(
        self,
        *,
        alignment_widget: QWidget,
        characters_widget: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._alignment_widget = alignment_widget
        self._characters_widget = characters_widget

        layout = QVBoxLayout(self)
        helper = QLabel(
            "Validation & Annotation : valider/corriger les liens d'alignement puis assigner/propager "
            "les personnages sur segments et sous-titres."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #555;")
        layout.addWidget(helper)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._alignment_widget)
        self._splitter.addWidget(self._characters_widget)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([560, 480])
        layout.addWidget(self._splitter)

    def focus_alignment(self) -> None:
        """Met l'accent sur la partie Alignement."""
        self._splitter.setSizes([700, 340])
        align_table = getattr(self._alignment_widget, "align_table", None)
        if align_table is not None:
            align_table.setFocus()
