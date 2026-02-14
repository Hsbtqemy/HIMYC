"""Onglet Logs : affichage des logs applicatifs avec filtres et raccourcis diagnostic."""

from __future__ import annotations

from collections import deque
import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.app.feedback import show_info, warn_precondition
from howimetyourcorpus.app.logs_utils import (
    LogEntry,
    extract_episode_id,
    matches_log_filters,
    parse_formatted_log_line,
)


class _LogSignalBridge(QObject):
    log_emitted = Signal(str, str, str)  # level, message, formatted_line


class TextEditHandler(logging.Handler):
    """Redirige les logs vers le panneau via signal Qt (thread-safe)."""

    def __init__(self, emit_entry: Callable[[str, str, str], None]):
        super().__init__()
        self._emit_entry = emit_entry

    def emit(self, record):
        try:
            formatted_line = self.format(record)
            level = str(getattr(record, "levelname", "") or "").upper()
            message = record.getMessage()
            self._emit_entry(level, message, formatted_line)
        except Exception:
            # Les logs ne doivent jamais provoquer de récursion ou bloquer l'UI.
            return


class LogsTabWidget(QWidget):
    """Widget logs live avec filtres (niveau/texte) et raccourci vers l'Inspecteur."""

    def __init__(
        self,
        on_open_log: Callable[[], None] | None = None,
        on_open_inspector: Callable[[str], None] | None = None,
        get_log_path: Callable[[], Path | None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._on_open_inspector = on_open_inspector
        self._get_log_path = get_log_path
        self._entries: deque[LogEntry] = deque(maxlen=5000)
        self._applying_preset = False

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Tous", ("ALL", ""))
        self.preset_combo.addItem("Erreurs (ERROR+)", ("ERROR", ""))
        self.preset_combo.addItem("Pipeline", ("INFO", "step"))
        self.preset_combo.addItem("Fetch", ("ALL", "fetch"))
        self.preset_combo.addItem("Normalize", ("ALL", "normalize"))
        self.preset_combo.addItem("Segment", ("ALL", "segment"))
        self.preset_combo.addItem("Index", ("ALL", "index"))
        self.preset_combo.addItem("Alignement", ("ALL", "align"))
        self.preset_combo.addItem("Concordance", ("ALL", "kwic"))
        self.preset_combo.addItem("Personnalisé", ("CUSTOM", ""))
        self.preset_combo.currentIndexChanged.connect(self._apply_selected_preset)
        controls.addWidget(self.preset_combo)
        controls.addWidget(QLabel("Niveau:"))
        self.level_filter_combo = QComboBox()
        self.level_filter_combo.addItem("Tous", "ALL")
        self.level_filter_combo.addItem("INFO+", "INFO")
        self.level_filter_combo.addItem("WARNING+", "WARNING")
        self.level_filter_combo.addItem("ERROR+", "ERROR")
        self.level_filter_combo.currentIndexChanged.connect(self._on_filters_changed)
        controls.addWidget(self.level_filter_combo)
        controls.addWidget(QLabel("Recherche:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filtrer (texte, épisode, étape, erreur...)")
        self.search_edit.textChanged.connect(self._on_filters_changed)
        controls.addWidget(self.search_edit)
        self.clear_btn = QPushButton("Effacer tampon live")
        self.clear_btn.setToolTip("Vide le tampon des logs affichés dans cette session.")
        self.clear_btn.clicked.connect(self._clear_live_buffer)
        controls.addWidget(self.clear_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.logs_edit = QPlainTextEdit()
        self.logs_edit.setReadOnly(True)
        # Empêche une croissance mémoire infinie pendant les longues sessions.
        self.logs_edit.document().setMaximumBlockCount(5000)
        layout.addWidget(self.logs_edit)

        row = QHBoxLayout()
        open_episode_btn = QPushButton("Ouvrir épisode depuis la ligne")
        open_episode_btn.setToolTip(
            "Extrait SxxExx depuis la ligne sélectionnée et ouvre directement l'Inspecteur."
        )
        open_episode_btn.clicked.connect(self._open_episode_from_selected_log)
        row.addWidget(open_episode_btn)
        copy_line_btn = QPushButton("Copier ligne")
        copy_line_btn.setToolTip("Copie la ligne de log sélectionnée (ou la ligne courante).")
        copy_line_btn.clicked.connect(self._copy_selected_log_line)
        row.addWidget(copy_line_btn)
        copy_episode_btn = QPushButton("Copier épisode")
        copy_episode_btn.setToolTip("Copie l'episode_id SxxExx détecté dans la ligne sélectionnée.")
        copy_episode_btn.clicked.connect(self._copy_episode_id_from_selected_log)
        row.addWidget(copy_episode_btn)
        load_file_tail_btn = QPushButton("Charger extrait fichier")
        load_file_tail_btn.setToolTip("Charge les dernières lignes du fichier log projet (si disponible).")
        load_file_tail_btn.clicked.connect(self._load_file_tail_from_button)
        row.addWidget(load_file_tail_btn)
        open_log_btn = QPushButton("Ouvrir fichier log")
        open_log_btn.clicked.connect(on_open_log or (lambda: None))
        row.addWidget(open_log_btn)
        row.addStretch()
        layout.addLayout(row)

        # Connect app logger to this widget
        self._bridge = _LogSignalBridge(self)
        self._bridge.log_emitted.connect(self._on_log_emitted)
        self._logger = logging.getLogger("howimetyourcorpus")
        self._handler: logging.Handler | None = TextEditHandler(self._bridge.log_emitted.emit)
        self._handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self._logger.addHandler(self._handler)
        self._sync_preset_with_filters()

    def _current_level_filter(self) -> str:
        return str(self.level_filter_combo.currentData() or "ALL")

    def _current_query(self) -> str:
        return self.search_edit.text().strip()

    def _on_filters_changed(self, *_args) -> None:
        self._sync_preset_with_filters()
        self._refresh_view()

    def _apply_selected_preset(self, *_args) -> None:
        data = self.preset_combo.currentData()
        if not isinstance(data, tuple) or len(data) != 2:
            return
        level, query = str(data[0]), str(data[1])
        if level == "CUSTOM":
            return
        self._applying_preset = True
        try:
            idx = self.level_filter_combo.findData(level)
            if idx >= 0 and idx != self.level_filter_combo.currentIndex():
                self.level_filter_combo.setCurrentIndex(idx)
            if self.search_edit.text() != query:
                self.search_edit.setText(query)
        finally:
            self._applying_preset = False
        self._refresh_view()

    def _sync_preset_with_filters(self) -> None:
        if self._applying_preset:
            return
        current_level = self._current_level_filter()
        current_query = self._current_query()
        matching_idx = -1
        custom_idx = -1
        for i in range(self.preset_combo.count()):
            data = self.preset_combo.itemData(i)
            if not isinstance(data, tuple) or len(data) != 2:
                continue
            level, query = str(data[0]), str(data[1])
            if level == "CUSTOM":
                custom_idx = i
                continue
            if level == current_level and query == current_query:
                matching_idx = i
                break
        target_idx = matching_idx if matching_idx >= 0 else custom_idx
        if target_idx >= 0 and self.preset_combo.currentIndex() != target_idx:
            self._applying_preset = True
            try:
                self.preset_combo.setCurrentIndex(target_idx)
            finally:
                self._applying_preset = False

    def _entry_matches_current_filters(self, entry: LogEntry) -> bool:
        return matches_log_filters(
            entry,
            level_min=self._current_level_filter(),
            query=self._current_query(),
        )

    def _on_log_emitted(self, level: str, message: str, formatted_line: str) -> None:
        entry = LogEntry(level=level, message=message, formatted_line=formatted_line)
        self._entries.append(entry)
        if self._entry_matches_current_filters(entry):
            self.logs_edit.appendPlainText(formatted_line)

    def _refresh_view(self, *_args) -> None:
        self.logs_edit.clear()
        for entry in self._entries:
            if self._entry_matches_current_filters(entry):
                self.logs_edit.appendPlainText(entry.formatted_line)

    def _clear_live_buffer(self) -> None:
        self._entries.clear()
        self.logs_edit.clear()

    def load_file_tail(self, *, max_lines: int = 400, clear_existing: bool = False) -> int:
        """Charge les dernières lignes du fichier log projet dans le tampon visible."""
        if max_lines <= 0:
            return 0
        if self._get_log_path is None:
            return 0
        path = self._get_log_path()
        if not path or not path.exists():
            return 0
        tail: deque[str] = deque(maxlen=max_lines)
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    tail.append(line.rstrip("\n"))
        except OSError:
            return 0
        if clear_existing:
            self._entries.clear()
        added = 0
        for line in tail:
            if not line.strip():
                continue
            self._entries.append(parse_formatted_log_line(line))
            added += 1
        self._refresh_view()
        return added

    def _load_file_tail_from_button(self) -> None:
        added = self.load_file_tail(max_lines=500, clear_existing=False)
        if added > 0:
            return
        warn_precondition(
            self,
            "Logs",
            "Aucune ligne chargée depuis le fichier log.",
            next_step="Ouvrez un projet puis exécutez au moins une action pour générer des logs.",
        )

    def _selected_log_text(self) -> str:
        cursor = self.logs_edit.textCursor()
        selected = (cursor.selectedText() or "").strip().replace("\u2029", "\n")
        if selected:
            return selected
        line = (cursor.block().text() or "").strip()
        if line:
            return line
        all_text = (self.logs_edit.toPlainText() or "").strip()
        if not all_text:
            return ""
        return all_text.splitlines()[-1].strip()

    def _open_episode_from_selected_log(self) -> None:
        if not self._on_open_inspector:
            warn_precondition(
                self,
                "Logs",
                "Navigation Inspecteur indisponible.",
                next_step="Utilisez l'onglet Inspecteur manuellement.",
            )
            return
        text = self._selected_log_text()
        if not text:
            warn_precondition(
                self,
                "Logs",
                "Aucune ligne de log disponible.",
                next_step="Lancez une action workflow puis réessayez.",
            )
            return
        episode_id = extract_episode_id(text)
        if not episode_id:
            warn_precondition(
                self,
                "Logs",
                "Aucun episode_id trouvé dans la ligne sélectionnée.",
                next_step="Sélectionnez une ligne contenant un identifiant du type S01E01.",
            )
            return
        self._on_open_inspector(episode_id)

    @staticmethod
    def _copy_to_clipboard(text: str) -> bool:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(text)
        return True

    def _copy_selected_log_line(self) -> None:
        text = self._selected_log_text()
        if not text:
            warn_precondition(
                self,
                "Logs",
                "Aucune ligne de log disponible à copier.",
                next_step="Sélectionnez une ligne de log puis réessayez.",
            )
            return
        if not self._copy_to_clipboard(text):
            warn_precondition(
                self,
                "Logs",
                "Impossible d'accéder au presse-papiers.",
                next_step="Réessayez après avoir activé le focus de l'application.",
            )
            return
        show_info(self, "Logs", "Ligne copiée dans le presse-papiers.")

    def _copy_episode_id_from_selected_log(self) -> None:
        text = self._selected_log_text()
        if not text:
            warn_precondition(
                self,
                "Logs",
                "Aucune ligne de log disponible.",
                next_step="Sélectionnez une ligne contenant un identifiant épisode.",
            )
            return
        episode_id = extract_episode_id(text)
        if not episode_id:
            warn_precondition(
                self,
                "Logs",
                "Aucun episode_id trouvé dans la ligne sélectionnée.",
                next_step="Sélectionnez une ligne contenant un identifiant du type S01E01.",
            )
            return
        if not self._copy_to_clipboard(episode_id):
            warn_precondition(
                self,
                "Logs",
                "Impossible d'accéder au presse-papiers.",
                next_step="Réessayez après avoir activé le focus de l'application.",
            )
            return
        show_info(self, "Logs", f"Épisode copié: {episode_id}")

    def closeEvent(self, event) -> None:
        if self._handler is not None:
            self._logger.removeHandler(self._handler)
            self._handler = None
        super().closeEvent(event)
