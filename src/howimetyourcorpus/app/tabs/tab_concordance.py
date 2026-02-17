"""Onglet Concordance : recherche KWIC (épisodes, segments, cues) et export + Pack Rapide (C2, C9, C15, C4) + Pack Analyse (C1, C5, C8, C11)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QModelIndex, QSettings, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.export_utils import (
    export_kwic_csv,
    export_kwic_json,
    export_kwic_jsonl,
    export_kwic_tsv,
    export_kwic_docx,
)
from howimetyourcorpus.app.models_qt import KwicTableModel

logger = logging.getLogger(__name__)


class ConcordanceTabWidget(QWidget):
    """Widget de l'onglet Concordance : recherche KWIC, filtres, table, export, ouvrir dans Inspecteur."""

    def __init__(
        self,
        get_db: Callable[[], object],
        on_open_inspector: Callable[[str], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_db = get_db
        self._on_open_inspector = on_open_inspector
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Recherche:"))
        
        # Pack Rapide C4: ComboBox éditable avec historique au lieu de QLineEdit
        self.kwic_search_edit = QComboBox()
        self.kwic_search_edit.setEditable(True)
        self.kwic_search_edit.setPlaceholderText("Terme...")
        self.kwic_search_edit.setToolTip("Recherche KWIC (Entrée pour lancer, historique disponible)")
        self.kwic_search_edit.lineEdit().setPlaceholderText("Terme...")
        self.kwic_search_edit.lineEdit().returnPressed.connect(self._run_kwic)
        self._load_search_history()  # Pack Rapide C4
        row.addWidget(self.kwic_search_edit)
        
        self.kwic_go_btn = QPushButton("Rechercher")
        self.kwic_go_btn.clicked.connect(self._run_kwic)
        row.addWidget(self.kwic_go_btn)
        self.export_kwic_btn = QPushButton("Exporter résultats")
        self.export_kwic_btn.clicked.connect(self._export_kwic)
        row.addWidget(self.export_kwic_btn)
        row.addWidget(QLabel("Scope:"))
        self.kwic_scope_combo = QComboBox()
        self.kwic_scope_combo.addItem("Épisodes (texte)", "episodes")
        self.kwic_scope_combo.addItem("Segments", "segments")
        self.kwic_scope_combo.addItem("Cues (sous-titres)", "cues")
        row.addWidget(self.kwic_scope_combo)
        row.addWidget(QLabel("Kind:"))
        self.kwic_kind_combo = QComboBox()
        self.kwic_kind_combo.addItem("—", "")
        self.kwic_kind_combo.addItem("Phrases", "sentence")
        self.kwic_kind_combo.addItem("Tours", "utterance")
        row.addWidget(self.kwic_kind_combo)
        row.addWidget(QLabel("Langue:"))
        self.kwic_lang_combo = QComboBox()
        self.kwic_lang_combo.addItem("—", "")
        for lang in ["en", "fr", "it"]:
            self.kwic_lang_combo.addItem(lang, lang)
        row.addWidget(self.kwic_lang_combo)
        row.addWidget(QLabel("Saison:"))
        self.kwic_season_spin = QSpinBox()
        self.kwic_season_spin.setMinimum(0)
        self.kwic_season_spin.setMaximum(99)
        self.kwic_season_spin.setSpecialValueText("—")
        row.addWidget(self.kwic_season_spin)
        row.addWidget(QLabel("Épisode:"))
        self.kwic_episode_spin = QSpinBox()
        self.kwic_episode_spin.setMinimum(0)
        self.kwic_episode_spin.setMaximum(999)
        self.kwic_episode_spin.setSpecialValueText("—")
        row.addWidget(self.kwic_episode_spin)
        row.addWidget(QLabel("Page:"))
        self.kwic_page_spin = QSpinBox()
        self.kwic_page_spin.setMinimum(1)
        self.kwic_page_spin.setMaximum(1)
        self.kwic_page_spin.setSpecialValueText("1")
        self.kwic_page_spin.setToolTip("Navigation pagination (200 résultats par page)")
        self.kwic_page_spin.valueChanged.connect(self._on_page_changed)
        row.addWidget(self.kwic_page_spin)
        self.kwic_page_label = QLabel("/ 1")
        row.addWidget(self.kwic_page_label)
        layout.addLayout(row)
        
        # Pack Rapide : Row 2 avec options avancées (C2: Case-sensitive, C4: Historique à venir)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Options:"))
        self.case_sensitive_cb = QCheckBox("Respecter la casse")
        self.case_sensitive_cb.setToolTip("Recherche sensible à la casse (A ≠ a)")
        row2.addWidget(self.case_sensitive_cb)
        row2.addStretch()
        layout.addLayout(row2)
        
        self.kwic_table = QTableView()
        self.kwic_model = KwicTableModel()
        self.kwic_table.setModel(self.kwic_model)
        self.kwic_table.doubleClicked.connect(self._on_double_click)
        self.kwic_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.kwic_table.setSortingEnabled(True)  # Activer le tri par colonne
        layout.addWidget(self.kwic_table)
        
        # Pack Rapide C15: Copier presse-papier avec Ctrl+C
        self.kwic_table.keyPressEvent = self._handle_table_key_press
        
        self._all_hits: list = []  # Stocker tous les résultats pour pagination
        self._page_size = 200
        self._max_history = 20  # Pack Rapide C4: Nombre max d'entrées historique

    def set_languages(self, langs: list[str]) -> None:
        """Met à jour la liste des langues (projet). Appelé par la fenêtre principale."""
        self.kwic_lang_combo.clear()
        self.kwic_lang_combo.addItem("—", "")
        for lang in langs:
            self.kwic_lang_combo.addItem(lang, lang)
    
    def _load_search_history(self) -> None:
        """Pack Rapide C4: Charge l'historique depuis QSettings."""
        settings = QSettings()
        history = settings.value("concordance/search_history", [])
        if isinstance(history, list):
            self.kwic_search_edit.clear()
            for term in history[-self._max_history:]:  # Limiter à N dernières
                if term and isinstance(term, str):
                    self.kwic_search_edit.addItem(term)
    
    def _save_search_to_history(self, term: str) -> None:
        """Pack Rapide C4: Ajoute le terme à l'historique (sans doublons)."""
        if not term or not term.strip():
            return
        
        term = term.strip()
        settings = QSettings()
        history = settings.value("concordance/search_history", [])
        if not isinstance(history, list):
            history = []
        
        # Retirer terme s'il existe déjà (on le remettra en dernier)
        history = [h for h in history if h != term]
        history.append(term)
        
        # Limiter à N dernières recherches
        history = history[-self._max_history:]
        
        settings.setValue("concordance/search_history", history)
        
        # Mettre à jour le combo
        self._load_search_history()
        self.kwic_search_edit.setCurrentText(term)

    def _run_kwic(self) -> None:
        term = self.kwic_search_edit.currentText().strip()  # Pack Rapide C4: currentText() au lieu de text()
        db = self._get_db()
        if not term or not db:
            return
        
        # Pack Rapide C4: Sauvegarder dans l'historique
        self._save_search_to_history(term)
        
        season = self.kwic_season_spin.value() if self.kwic_season_spin.value() > 0 else None
        episode = self.kwic_episode_spin.value() if self.kwic_episode_spin.value() > 0 else None
        scope = self.kwic_scope_combo.currentData() or "episodes"
        # Récupérer TOUS les résultats (sans limite) pour pagination
        if scope == "segments":
            kind = self.kwic_kind_combo.currentData() or None
            hits = db.query_kwic_segments(term, kind=kind, season=season, episode=episode, window=45, limit=10000)
        elif scope == "cues":
            lang = self.kwic_lang_combo.currentData() or None
            hits = db.query_kwic_cues(term, lang=lang, season=season, episode=episode, window=45, limit=10000)
        else:
            hits = db.query_kwic(term, season=season, episode=episode, window=45, limit=10000)
        self._all_hits = hits
        # Calculer nb pages
        total_pages = max(1, (len(hits) + self._page_size - 1) // self._page_size)
        self.kwic_page_spin.setMaximum(total_pages)
        self.kwic_page_spin.setValue(1)
        self.kwic_page_label.setText(f"/ {total_pages}  ({len(hits)} résultat(s))")
        # Afficher page 1
        self._display_page(1)

    def _on_page_changed(self) -> None:
        """Affiche la page sélectionnée."""
        self._display_page(self.kwic_page_spin.value())

    def _display_page(self, page: int) -> None:
        """Affiche les résultats de la page donnée."""
        start = (page - 1) * self._page_size
        end = start + self._page_size
        page_hits = self._all_hits[start:end]
        # Pack Rapide C9: Passer le terme de recherche pour highlight
        search_term = self.kwic_search_edit.currentText().strip()  # Pack Rapide C4: currentText()
        self.kwic_model.set_hits(page_hits, search_term=search_term)

    def _export_kwic(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        # Exporter TOUS les résultats, pas seulement la page affichée
        hits = self._all_hits if self._all_hits else self.kwic_model.get_all_hits()
        if not hits:
            QMessageBox.warning(self, "Concordance", "Effectuez d'abord une recherche ou aucun résultat à exporter.")
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter les résultats KWIC",
            "",
            "CSV (*.csv);;TSV (*.tsv);;JSON (*.json);;JSONL (*.jsonl);;Word (*.docx)",
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != ".docx" and "Word" in (selected_filter or ""):
            path = path.with_suffix(".docx")
        try:
            if path.suffix.lower() == ".csv" or "CSV" in (selected_filter or ""):
                export_kwic_csv(hits, path)
            elif path.suffix.lower() == ".tsv" or "TSV" in (selected_filter or ""):
                export_kwic_tsv(hits, path)
            elif path.suffix.lower() == ".json" or "JSON" in (selected_filter or ""):
                export_kwic_json(hits, path)
            elif path.suffix.lower() == ".jsonl" or "JSONL" in (selected_filter or ""):
                export_kwic_jsonl(hits, path)
            elif path.suffix.lower() == ".docx" or "Word" in (selected_filter or ""):
                export_kwic_docx(hits, path)
            else:
                QMessageBox.warning(self, "Export", "Format non reconnu. Utilisez .csv, .tsv, .json, .jsonl ou .docx")
                return
            QMessageBox.information(self, "Export", f"Résultats exportés : {len(hits)} occurrence(s).")
        except Exception as e:
            logger.exception("Export KWIC")
            QMessageBox.critical(self, "Erreur", str(e))

    def _on_double_click(self, index: QModelIndex) -> None:
        hit = self.kwic_model.get_hit_at(index.row())
        if not hit:
            return
        self._on_open_inspector(hit.episode_id)
    
    def _handle_table_key_press(self, event: QKeyEvent) -> None:
        """Pack Rapide C15: Gérer Ctrl+C pour copier vers presse-papier."""
        if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._copy_selection_to_clipboard()
            event.accept()
        else:
            # Appeler la méthode originale pour autres touches
            QTableView.keyPressEvent(self.kwic_table, event)
    
    def _copy_selection_to_clipboard(self) -> None:
        """Pack Rapide C15: Copie la sélection au format TSV vers le presse-papier."""
        from PySide6.QtWidgets import QApplication
        
        selection = self.kwic_table.selectionModel()
        if not selection or not selection.hasSelection():
            return
        
        indexes = sorted(selection.selectedIndexes(), key=lambda idx: (idx.row(), idx.column()))
        if not indexes:
            return
        
        # Construire TSV (lignes séparées par \n, colonnes par \t)
        rows = {}
        for idx in indexes:
            row_num = idx.row()
            col_num = idx.column()
            value = self.kwic_model.data(idx, Qt.ItemDataRole.DisplayRole) or ""
            if row_num not in rows:
                rows[row_num] = {}
            rows[row_num][col_num] = str(value)
        
        tsv_lines = []
        for row_num in sorted(rows.keys()):
            cols = rows[row_num]
            # Construire ligne avec toutes les colonnes (remplir vides si manquantes)
            max_col = max(cols.keys()) if cols else 0
            line_parts = [cols.get(c, "") for c in range(max_col + 1)]
            tsv_lines.append("\t".join(line_parts))
        
        tsv = "\n".join(tsv_lines)
        clipboard = QApplication.clipboard()
        clipboard.setText(tsv)

