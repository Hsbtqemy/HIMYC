"""Point d'entrée de l'application desktop HowIMetYourCorpus."""

from __future__ import annotations

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from corpusstudio.core.utils.logging import setup_logging
from corpusstudio.app.ui_mainwindow import MainWindow


def main() -> int:
    setup_logging(level=logging.INFO)
    logging.getLogger("corpusstudio").info("Starting HowIMetYourCorpus")
    app = QApplication(sys.argv)
    app.setApplicationName("HowIMetYourCorpus")
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
