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
        layout.addWidget(self.logs_edit)
        row = QHBoxLayout()
        open_log_btn = QPushButton("Ouvrir fichier log")
        open_log_btn.clicked.connect(on_open_log or (lambda: None))
        row.addWidget(open_log_btn)
        layout.addLayout(row)
        # Connect app logger to this widget
        h = TextEditHandler(self.logs_edit)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger("howimetyourcorpus").addHandler(h)
