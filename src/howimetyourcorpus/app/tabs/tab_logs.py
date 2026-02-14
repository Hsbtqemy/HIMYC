"""Onglet Logs : affichage des logs applicatifs avec filtres et raccourcis diagnostic."""

from __future__ import annotations

from collections import deque
import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QSettings, Signal, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.app.feedback import show_info, warn_precondition
from howimetyourcorpus.app.logs_utils import (
    build_logs_diagnostic_report,
    decode_custom_logs_presets,
    encode_custom_logs_presets,
    LogEntry,
    LOGS_BUILTIN_PRESETS,
    LOGS_CUSTOM_PRESET_LABEL,
    extract_episode_id,
    matches_log_filters,
    parse_formatted_log_line,
)


_LOGS_LEVEL_FILTER_KEY = "logs/levelFilter"
_LOGS_QUERY_TEXT_KEY = "logs/queryText"
_LOGS_CUSTOM_PRESETS_KEY = "logs/customPresets"


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
        self._visible_count = 0
        self._applying_preset = False
        self._custom_presets: list[tuple[str, str, str]] = []
        self._builtin_preset_labels = {label.casefold() for label, _level, _query in LOGS_BUILTIN_PRESETS}
        self._refresh_debounce = QTimer(self)
        self._refresh_debounce.setSingleShot(True)
        self._refresh_debounce.setInterval(200)
        self._refresh_debounce.timeout.connect(self._refresh_view)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self._restore_custom_presets_state()
        self._rebuild_preset_combo()
        self.preset_combo.currentIndexChanged.connect(self._apply_selected_preset)
        controls.addWidget(self.preset_combo)
        save_preset_btn = QPushButton("Sauver preset")
        save_preset_btn.setToolTip("Enregistre les filtres actuels (niveau + recherche) sous un nom.")
        save_preset_btn.clicked.connect(self._save_current_as_custom_preset)
        controls.addWidget(save_preset_btn)
        delete_preset_btn = QPushButton("Supprimer preset")
        delete_preset_btn.setToolTip("Supprime le preset personnalisé sélectionné.")
        delete_preset_btn.clicked.connect(self._delete_selected_custom_preset)
        controls.addWidget(delete_preset_btn)
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
        self.search_edit.setPlaceholderText('Ex: fetch S01E01 -debug align|kwic "run failed"')
        self.search_edit.textChanged.connect(self._on_filters_changed)
        controls.addWidget(self.search_edit)
        self.count_label = QLabel("0 / 0")
        self.count_label.setToolTip("Nombre de lignes visibles / nombre total en tampon live.")
        controls.addWidget(self.count_label)
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
        copy_diagnostic_btn = QPushButton("Copier diagnostic")
        copy_diagnostic_btn.setToolTip(
            "Copie un diagnostic complet (ligne, épisode, filtres, extraits récents) pour QA."
        )
        copy_diagnostic_btn.clicked.connect(self._copy_logs_diagnostic)
        row.addWidget(copy_diagnostic_btn)
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
        self._restore_filters_state()
        self._sync_preset_with_filters()

    def _current_level_filter(self) -> str:
        return str(self.level_filter_combo.currentData() or "ALL")

    def _current_query(self) -> str:
        return self.search_edit.text().strip()

    def _rebuild_preset_combo(self, *, selected_label: str | None = None) -> None:
        if selected_label is None:
            selected_label = (self.preset_combo.currentText() or "").strip()
        self._applying_preset = True
        try:
            self.preset_combo.clear()
            for label, level, query in LOGS_BUILTIN_PRESETS:
                self.preset_combo.addItem(label, (level, query))
            for label, level, query in self._custom_presets:
                self.preset_combo.addItem(label, (level, query))
            self.preset_combo.addItem(LOGS_CUSTOM_PRESET_LABEL, ("CUSTOM", ""))
            if selected_label:
                idx = self.preset_combo.findText(selected_label)
                if idx >= 0:
                    self.preset_combo.setCurrentIndex(idx)
        finally:
            self._applying_preset = False

    def _find_custom_preset_index(self, label: str) -> int:
        needle = label.strip().casefold()
        if not needle:
            return -1
        for i, (current_label, _level, _query) in enumerate(self._custom_presets):
            if current_label.casefold() == needle:
                return i
        return -1

    def _restore_custom_presets_state(self) -> None:
        settings = QSettings()
        reserved = [label for label, _level, _query in LOGS_BUILTIN_PRESETS]
        reserved.append(LOGS_CUSTOM_PRESET_LABEL)
        self._custom_presets = decode_custom_logs_presets(
            settings.value(_LOGS_CUSTOM_PRESETS_KEY, ""),
            reserved_labels=reserved,
        )

    def _save_custom_presets_state(self) -> None:
        settings = QSettings()
        settings.setValue(_LOGS_CUSTOM_PRESETS_KEY, encode_custom_logs_presets(self._custom_presets))

    def _save_current_as_custom_preset(self) -> None:
        default_label = ""
        current_label = (self.preset_combo.currentText() or "").strip()
        if self._find_custom_preset_index(current_label) >= 0:
            default_label = current_label
        label, ok = QInputDialog.getText(self, "Logs", "Nom du preset:", text=default_label)
        if not ok:
            return
        clean_label = label.strip()
        if not clean_label:
            warn_precondition(
                self,
                "Logs",
                "Nom de preset vide.",
                next_step="Entrez un nom explicite (ex: QA Alignement, Erreurs corpus).",
            )
            return
        key = clean_label.casefold()
        if key in self._builtin_preset_labels or key == LOGS_CUSTOM_PRESET_LABEL.casefold():
            warn_precondition(
                self,
                "Logs",
                f"'{clean_label}' est réservé pour un preset système.",
                next_step="Choisissez un autre nom pour votre preset personnalisé.",
            )
            return
        level = self._current_level_filter()
        query = self._current_query()
        existing_idx = self._find_custom_preset_index(clean_label)
        if existing_idx >= 0:
            answer = QMessageBox.question(
                self,
                "Logs",
                f"Le preset '{clean_label}' existe déjà. Voulez-vous l'écraser ?",
            )
            if answer != QMessageBox.Yes:
                return
            self._custom_presets[existing_idx] = (clean_label, level, query)
        else:
            self._custom_presets.append((clean_label, level, query))
        self._save_custom_presets_state()
        self._rebuild_preset_combo(selected_label=clean_label)
        self._sync_preset_with_filters()
        self._save_filters_state()
        self._refresh_view()
        show_info(self, "Logs", f"Preset personnalisé enregistré: {clean_label}")

    def _delete_selected_custom_preset(self) -> None:
        label = (self.preset_combo.currentText() or "").strip()
        idx = self._find_custom_preset_index(label)
        if idx < 0:
            warn_precondition(
                self,
                "Logs",
                "Sélectionnez un preset personnalisé à supprimer.",
                next_step="Choisissez un preset utilisateur dans la liste puis réessayez.",
            )
            return
        answer = QMessageBox.question(self, "Logs", f"Supprimer le preset '{label}' ?")
        if answer != QMessageBox.Yes:
            return
        del self._custom_presets[idx]
        self._save_custom_presets_state()
        self._rebuild_preset_combo(selected_label=LOGS_CUSTOM_PRESET_LABEL)
        self._sync_preset_with_filters()
        self._save_filters_state()
        self._refresh_view()
        show_info(self, "Logs", f"Preset supprimé: {label}")

    def _on_filters_changed(self, *_args) -> None:
        if self._applying_preset:
            return
        self._sync_preset_with_filters()
        self._save_filters_state()
        self._schedule_refresh_view()

    def _schedule_refresh_view(self) -> None:
        self._refresh_debounce.start()

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
        self._sync_preset_with_filters()
        self._save_filters_state()
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
        dropped_entry: LogEntry | None = None
        if self._entries.maxlen and len(self._entries) >= self._entries.maxlen:
            dropped_entry = self._entries[0]
        entry = LogEntry(level=level, message=message, formatted_line=formatted_line)
        self._entries.append(entry)
        if dropped_entry and self._entry_matches_current_filters(dropped_entry):
            self._visible_count = max(0, self._visible_count - 1)
        if self._entry_matches_current_filters(entry):
            self.logs_edit.appendPlainText(formatted_line)
            self._visible_count += 1
        self.count_label.setText(f"{self._visible_count} / {len(self._entries)}")

    def _refresh_view(self, *_args) -> None:
        self.logs_edit.clear()
        visible_count = 0
        for entry in self._entries:
            if self._entry_matches_current_filters(entry):
                self.logs_edit.appendPlainText(entry.formatted_line)
                visible_count += 1
        self._visible_count = visible_count
        self.count_label.setText(f"{self._visible_count} / {len(self._entries)}")

    def _save_filters_state(self) -> None:
        settings = QSettings()
        settings.setValue(_LOGS_LEVEL_FILTER_KEY, self._current_level_filter())
        settings.setValue(_LOGS_QUERY_TEXT_KEY, self._current_query())

    def _restore_filters_state(self) -> None:
        settings = QSettings()
        level = str(settings.value(_LOGS_LEVEL_FILTER_KEY, "ALL") or "ALL")
        query = str(settings.value(_LOGS_QUERY_TEXT_KEY, "") or "")
        self._applying_preset = True
        try:
            idx = self.level_filter_combo.findData(level)
            self.level_filter_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.search_edit.setText(query)
        finally:
            self._applying_preset = False

    def save_state(self) -> None:
        """Sauvegarde l'état des filtres Logs (appelé à la fermeture globale)."""
        self._save_filters_state()
        self._save_custom_presets_state()

    def _clear_live_buffer(self) -> None:
        self._entries.clear()
        self.logs_edit.clear()
        self._visible_count = 0
        self.count_label.setText("0 / 0")

    def load_file_tail(self, *, max_lines: int = 400, clear_existing: bool = False) -> int:
        """Charge les dernières lignes du fichier log projet dans le tampon visible."""
        if max_lines <= 0:
            return 0
        if self._get_log_path is None:
            return 0
        path = self._get_log_path()
        if not path or not path.exists():
            return 0
        tail = self._read_tail_lines(path, max_lines)
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

    @staticmethod
    def _read_tail_lines(path: Path, max_lines: int) -> list[str]:
        """Lit au plus `max_lines` lignes depuis la fin du fichier sans parcours linéaire complet."""
        if max_lines <= 0:
            return []
        chunk_size = 8192
        chunks: list[bytes] = []
        newline_count = 0
        try:
            with path.open("rb") as handle:
                handle.seek(0, 2)
                position = handle.tell()
                while position > 0 and newline_count <= max_lines:
                    read_size = min(chunk_size, position)
                    position -= read_size
                    handle.seek(position)
                    chunk = handle.read(read_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    newline_count += chunk.count(b"\n")
        except OSError:
            return []
        if not chunks:
            return []
        data = b"".join(reversed(chunks))
        lines = data.splitlines()
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        return [line.decode("utf-8", errors="replace") for line in lines]

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

    def _selected_preset_label(self) -> str:
        label = (self.preset_combo.currentText() or "").strip()
        return label or "Personnalisé"

    def _collect_recent_matching_lines(self, *, max_lines: int = 25) -> list[str]:
        if max_lines <= 0:
            return []
        selected: list[str] = []
        for entry in reversed(self._entries):
            if not self._entry_matches_current_filters(entry):
                continue
            selected.append(entry.formatted_line)
            if len(selected) >= max_lines:
                break
        selected.reverse()
        return selected

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

    def _copy_logs_diagnostic(self) -> None:
        selected_line = self._selected_log_text()
        if not selected_line:
            warn_precondition(
                self,
                "Logs",
                "Aucune ligne de log disponible pour le diagnostic.",
                next_step="Sélectionnez une ligne de log puis réessayez.",
            )
            return
        episode_id = extract_episode_id(selected_line)
        report = build_logs_diagnostic_report(
            selected_line=selected_line,
            episode_id=episode_id,
            preset_label=self._selected_preset_label(),
            level_filter=self._current_level_filter(),
            query=self._current_query(),
            recent_lines=self._collect_recent_matching_lines(max_lines=25),
        )
        if not self._copy_to_clipboard(report):
            warn_precondition(
                self,
                "Logs",
                "Impossible d'accéder au presse-papiers.",
                next_step="Réessayez après avoir activé le focus de l'application.",
            )
            return
        show_info(self, "Logs", "Diagnostic complet copié dans le presse-papiers.")

    def closeEvent(self, event) -> None:
        self.save_state()
        self._refresh_debounce.stop()
        if self._handler is not None:
            self._logger.removeHandler(self._handler)
            self._handler = None
        super().closeEvent(event)
