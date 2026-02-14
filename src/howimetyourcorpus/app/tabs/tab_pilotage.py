"""Onglet Pilotage : fusion visuelle Projet + Corpus pour un workflow unique."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSplitter, QVBoxLayout, QWidget


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

        layout = QVBoxLayout(self)
        helper = QLabel(
            "Pilotage unifié : 1) configurer/ouvrir le projet, 2) exécuter le workflow corpus "
            "(import, normalisation, segmentation, indexation) puis passer à l'alignement."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #555;")
        layout.addWidget(helper)
        policy = QLabel(
            "Politique profils: Acquisition = source + rate limit (web/API). "
            "Normalisation = transcript RAW→CLEAN + pistes sous-titres "
            "(profil épisode > défaut source > profil batch). "
            "Export = format de sortie uniquement (pas de normalisation implicite)."
        )
        policy.setWordWrap(True)
        policy.setStyleSheet("color: #666;")
        layout.addWidget(policy)
        nav_row = QHBoxLayout()
        nav_row.addWidget(QLabel("Étapes suivantes:"))
        inspect_btn = QPushButton("Inspecteur (QA local)")
        inspect_btn.setToolTip("Comparer RAW/CLEAN, normaliser/segmenter un épisode, inspecter les pistes SRT.")
        inspect_btn.setEnabled(self._on_open_inspector is not None)
        inspect_btn.clicked.connect(self._open_inspector)
        nav_row.addWidget(inspect_btn)
        validation_btn = QPushButton("Validation & Annotation")
        validation_btn.setToolTip("Lancer/relire l'alignement et assigner/propager les personnages.")
        validation_btn.setEnabled(self._on_open_validation is not None)
        validation_btn.clicked.connect(self._open_validation)
        nav_row.addWidget(validation_btn)
        concordance_btn = QPushButton("Concordance")
        concordance_btn.setToolTip("Explorer le corpus (KWIC) et exporter des résultats.")
        concordance_btn.setEnabled(self._on_open_concordance is not None)
        concordance_btn.clicked.connect(self._open_concordance)
        nav_row.addWidget(concordance_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

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

    def _open_inspector(self) -> None:
        if self._on_open_inspector:
            self._on_open_inspector()

    def _open_validation(self) -> None:
        if self._on_open_validation:
            self._on_open_validation()

    def _open_concordance(self) -> None:
        if self._on_open_concordance:
            self._on_open_concordance()

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
