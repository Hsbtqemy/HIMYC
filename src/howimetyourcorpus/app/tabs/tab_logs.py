"""Onglet Logs : affichage des logs applicatifs + bouton ouvrir fichier log."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class TextEditHandler(logging.Handler):
    """Redirige les logs vers un QPlainTextEdit."""

    def __init__(self, widget: QPlainTextEdit):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        try:
            msg = self.format(record)
            self.widget.appendPlainText(msg)
        except Exception:
            logging.getLogger(__name__).exception("TextEditHandler.emit")


class LogsTabWidget(QWidget):
    """Widget de l'onglet Logs : zone lecture seule + bouton pour ouvrir le fichier log du projet."""

    def __init__(
        self,
        on_open_log: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.logs_edit = QPlainTextEdit()
        self.logs_edit.setReadOnly(True)
        # Empêche une croissance mémoire infinie pendant les longues sessions.
        self.logs_edit.document().setMaximumBlockCount(5000)
        layout.addWidget(self.logs_edit)
        row = QHBoxLayout()
        open_log_btn = QPushButton("Ouvrir fichier log")
        open_log_btn.clicked.connect(on_open_log or (lambda: None))
        row.addWidget(open_log_btn)
        layout.addLayout(row)
        # Connect app logger to this widget
        self._logger = logging.getLogger("howimetyourcorpus")
        self._handler: logging.Handler | None = TextEditHandler(self.logs_edit)
        self._handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self._logger.addHandler(self._handler)

    def closeEvent(self, event) -> None:
        if self._handler is not None:
            self._logger.removeHandler(self._handler)
            self._handler = None
        super().closeEvent(event)
