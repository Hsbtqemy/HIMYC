"""Onglet Concordance : recherche KWIC (épisodes, segments, cues) et export."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
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
from howimetyourcorpus.app.feedback import show_error, warn_precondition
from howimetyourcorpus.app.export_dialog import normalize_export_path, resolve_export_key
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
        self._job_busy = False
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Recherche:"))
        self.kwic_search_edit = QLineEdit()
        self.kwic_search_edit.setPlaceholderText("Terme...")
        row.addWidget(self.kwic_search_edit)
        self.kwic_go_btn = QPushButton("Rechercher")
        self.kwic_go_btn.clicked.connect(self._run_kwic)
        self.kwic_go_btn.setToolTip("Lance la recherche KWIC sur le scope sélectionné.")
        row.addWidget(self.kwic_go_btn)
        self.export_kwic_btn = QPushButton("Exporter résultats")
        self.export_kwic_btn.clicked.connect(self._export_kwic)
        self.export_kwic_btn.setToolTip("Exporte les résultats KWIC actuels.")
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
        layout.addLayout(row)
        self.kwic_table = QTableView()
        self.kwic_model = KwicTableModel()
        self.kwic_table.setModel(self.kwic_model)
        self.kwic_table.doubleClicked.connect(self._on_double_click)
        self.kwic_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.kwic_table)
        self.kwic_search_edit.returnPressed.connect(self._run_kwic)
        self.kwic_search_edit.textChanged.connect(lambda _text: self._apply_controls_enabled())
        self._kwic_go_tooltip_default = self.kwic_go_btn.toolTip()
        self._kwic_export_tooltip_default = self.export_kwic_btn.toolTip()
        self._apply_controls_enabled()

    def _apply_controls_enabled(self) -> None:
        enabled = not self._job_busy
        controls = (
            self.kwic_search_edit,
            self.kwic_scope_combo,
            self.kwic_kind_combo,
            self.kwic_lang_combo,
            self.kwic_season_spin,
            self.kwic_episode_spin,
        )
        for widget in controls:
            widget.setEnabled(enabled)
        has_db = self._get_db() is not None
        has_term = bool(self.kwic_search_edit.text().strip())
        has_hits = bool(self.kwic_model.get_all_hits())
        go_enabled = enabled and has_db and has_term
        export_enabled = enabled and has_hits
        self.kwic_go_btn.setEnabled(go_enabled)
        self.export_kwic_btn.setEnabled(export_enabled)
        if go_enabled:
            self.kwic_go_btn.setToolTip(self._kwic_go_tooltip_default)
        elif not enabled:
            self.kwic_go_btn.setToolTip("Recherche indisponible pendant un job.")
        elif not has_db:
            self.kwic_go_btn.setToolTip("Recherche indisponible: ouvrez un projet.")
        else:
            self.kwic_go_btn.setToolTip("Saisissez un terme pour lancer la recherche.")
        if export_enabled:
            self.export_kwic_btn.setToolTip(self._kwic_export_tooltip_default)
        elif not enabled:
            self.export_kwic_btn.setToolTip("Export indisponible pendant un job.")
        else:
            self.export_kwic_btn.setToolTip("Aucun résultat à exporter.")

    def set_job_busy(self, busy: bool) -> None:
        """Désactive les actions de recherche/export pendant un job pipeline."""
        self._job_busy = busy
        self._apply_controls_enabled()

    def set_languages(self, langs: list[str]) -> None:
        """Met à jour la liste des langues (projet). Appelé par la fenêtre principale."""
        self.kwic_lang_combo.clear()
        self.kwic_lang_combo.addItem("—", "")
        for lang in langs:
            self.kwic_lang_combo.addItem(lang, lang)

    def _run_kwic(self) -> None:
        if self._job_busy:
            return
        term = self.kwic_search_edit.text().strip()
        db = self._get_db()
        if not term:
            warn_precondition(
                self,
                "Concordance",
                "Saisissez un terme avant de lancer la recherche.",
            )
            self._apply_controls_enabled()
            return
        if not db:
            warn_precondition(
                self,
                "Concordance",
                "Base de données indisponible.",
                next_step="Ouvrez un projet puis indexez au moins un épisode.",
            )
            self._apply_controls_enabled()
            return
        season = self.kwic_season_spin.value() if self.kwic_season_spin.value() > 0 else None
        episode = self.kwic_episode_spin.value() if self.kwic_episode_spin.value() > 0 else None
        scope = self.kwic_scope_combo.currentData() or "episodes"
        if scope == "segments":
            kind = self.kwic_kind_combo.currentData() or None
            hits = db.query_kwic_segments(term, kind=kind, season=season, episode=episode, window=45, limit=200)
        elif scope == "cues":
            lang = self.kwic_lang_combo.currentData() or None
            hits = db.query_kwic_cues(term, lang=lang, season=season, episode=episode, window=45, limit=200)
        else:
            hits = db.query_kwic(term, season=season, episode=episode, window=45, limit=200)
        self.kwic_model.set_hits(hits)
        self._apply_controls_enabled()

    def _export_kwic(self) -> None:
        if self._job_busy:
            return
        from PySide6.QtWidgets import QFileDialog

        hits = self.kwic_model.get_all_hits()
        if not hits:
            warn_precondition(
                self,
                "Concordance",
                "Aucun résultat à exporter.",
                next_step="Lancez d'abord une recherche KWIC.",
            )
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
        path = normalize_export_path(
            path,
            selected_filter,
            allowed_suffixes=(".csv", ".tsv", ".json", ".jsonl", ".docx"),
            default_suffix=".csv",
            filter_to_suffix={
                "CSV": ".csv",
                "TSV": ".tsv",
                "JSONL": ".jsonl",
                "JSON": ".json",
                "WORD": ".docx",
            },
        )
        export_key = resolve_export_key(
            path,
            selected_filter,
            suffix_to_key={
                ".csv": "csv",
                ".tsv": "tsv",
                ".json": "json",
                ".jsonl": "jsonl",
                ".docx": "docx",
            },
        )
        try:
            if export_key == "csv":
                export_kwic_csv(hits, path)
            elif export_key == "tsv":
                export_kwic_tsv(hits, path)
            elif export_key == "jsonl":
                export_kwic_jsonl(hits, path)
            elif export_key == "json":
                export_kwic_json(hits, path)
            elif export_key == "docx":
                export_kwic_docx(hits, path)
            else:
                warn_precondition(
                    self,
                    "Export",
                    "Format non reconnu. Utilisez .csv, .tsv, .json, .jsonl ou .docx",
                )
                return
            QMessageBox.information(self, "Export", f"Résultats exportés : {len(hits)} occurrence(s).")
        except Exception as e:
            logger.exception("Export KWIC")
            show_error(self, exc=e, context="Export KWIC")

    def _on_double_click(self, index: QModelIndex) -> None:
        hit = self.kwic_model.get_hit_at(index.row())
        if not hit:
            return
        self._on_open_inspector(hit.episode_id)
