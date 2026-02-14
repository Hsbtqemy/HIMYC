"""Onglet Concordance : recherche KWIC (épisodes, segments, cues) et export."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QModelIndex, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.export_utils import (
    export_kwic_csv,
    export_kwic_docx,
    export_kwic_json,
    export_kwic_jsonl,
    export_kwic_tsv,
)
from howimetyourcorpus.app.feedback import show_error, show_info, warn_precondition
from howimetyourcorpus.app.export_dialog import (
    build_export_success_message,
    normalize_export_path,
    resolve_export_key,
)
from howimetyourcorpus.app.models_qt import KwicTableModel

logger = logging.getLogger(__name__)


class _KwicQueryWorker(QObject):
    """Worker asynchrone pour exécuter une requête KWIC hors thread UI."""

    finished = Signal(list, bool)  # hits, has_more
    failed = Signal(object)
    cancelled = Signal()

    def __init__(
        self,
        *,
        db: object,
        term: str,
        scope: str,
        kind: str | None,
        lang: str | None,
        season: int | None,
        episode: int | None,
        window: int,
        page_size: int,
        offset: int,
    ) -> None:
        super().__init__()
        self._db = db
        self._term = term
        self._scope = scope
        self._kind = kind
        self._lang = lang
        self._season = season
        self._episode = episode
        self._window = window
        self._page_size = page_size
        self._offset = max(0, int(offset))
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        if self._cancel_requested:
            self.cancelled.emit()
            return
        limit = self._page_size + 1  # +1 pour détecter s'il reste des résultats.
        try:
            if self._scope == "segments":
                hits = self._db.query_kwic_segments(
                    self._term,
                    kind=self._kind,
                    season=self._season,
                    episode=self._episode,
                    window=self._window,
                    limit=limit,
                    offset=self._offset,
                )
            elif self._scope == "cues":
                hits = self._db.query_kwic_cues(
                    self._term,
                    lang=self._lang,
                    season=self._season,
                    episode=self._episode,
                    window=self._window,
                    limit=limit,
                    offset=self._offset,
                )
            else:
                hits = self._db.query_kwic(
                    self._term,
                    season=self._season,
                    episode=self._episode,
                    window=self._window,
                    limit=limit,
                    offset=self._offset,
                )
        except Exception as exc:
            self.failed.emit(exc)
            return
        if self._cancel_requested:
            self.cancelled.emit()
            return
        has_more = len(hits) > self._page_size
        self.finished.emit(hits[: self._page_size], has_more)


class ConcordanceTabWidget(QWidget):
    """Widget de l'onglet Concordance : recherche KWIC, filtres, table, export, ouvrir dans Inspecteur."""

    def __init__(
        self,
        get_db: Callable[[], object],
        on_open_inspector: Callable[..., None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_db = get_db
        self._on_open_inspector = on_open_inspector
        self._job_busy = False
        self._kwic_busy = False
        self._kwic_has_more = False
        self._kwic_page_size = 200
        self._kwic_query_signature: tuple[str, str, str, str, int, int] | None = None
        self._kwic_append_mode = False
        self._kwic_thread: QThread | None = None
        self._kwic_worker: _KwicQueryWorker | None = None

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
        self.kwic_more_btn = QPushButton("Charger plus")
        self.kwic_more_btn.clicked.connect(self._load_more_kwic)
        self.kwic_more_btn.setToolTip("Charge la page suivante des résultats de la requête courante.")
        row.addWidget(self.kwic_more_btn)
        self.kwic_cancel_btn = QPushButton("Annuler recherche")
        self.kwic_cancel_btn.clicked.connect(self._cancel_kwic_query)
        self.kwic_cancel_btn.setToolTip("Annule la recherche KWIC en cours.")
        row.addWidget(self.kwic_cancel_btn)
        self.export_kwic_btn = QPushButton("Exporter résultats")
        self.export_kwic_btn.clicked.connect(self._export_kwic)
        self.export_kwic_btn.setToolTip("Exporte les résultats KWIC actuels.")
        row.addWidget(self.export_kwic_btn)
        row.addWidget(QLabel("Scope:"))
        self.kwic_scope_combo = QComboBox()
        self.kwic_scope_combo.addItem("Épisodes (texte)", "episodes")
        self.kwic_scope_combo.addItem("Segments", "segments")
        self.kwic_scope_combo.addItem("Cues (sous-titres)", "cues")
        self.kwic_scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        row.addWidget(self.kwic_scope_combo)
        row.addWidget(QLabel("Kind:"))
        self.kwic_kind_combo = QComboBox()
        self.kwic_kind_combo.addItem("—", "")
        self.kwic_kind_combo.addItem("Phrases", "sentence")
        self.kwic_kind_combo.addItem("Tours", "utterance")
        self.kwic_kind_combo.setToolTip("Filtre applicable uniquement au scope « Segments ».")
        self.kwic_kind_combo.currentIndexChanged.connect(self._on_query_inputs_changed)
        row.addWidget(self.kwic_kind_combo)
        row.addWidget(QLabel("Langue:"))
        self.kwic_lang_combo = QComboBox()
        self.kwic_lang_combo.addItem("—", "")
        for lang in ["en", "fr", "it"]:
            self.kwic_lang_combo.addItem(lang, lang)
        self.kwic_lang_combo.setToolTip("Filtre applicable uniquement au scope « Cues ».")
        self.kwic_lang_combo.currentIndexChanged.connect(self._on_query_inputs_changed)
        row.addWidget(self.kwic_lang_combo)
        row.addWidget(QLabel("Saison:"))
        self.kwic_season_spin = QSpinBox()
        self.kwic_season_spin.setMinimum(0)
        self.kwic_season_spin.setMaximum(99)
        self.kwic_season_spin.setSpecialValueText("—")
        self.kwic_season_spin.valueChanged.connect(self._on_query_inputs_changed)
        row.addWidget(self.kwic_season_spin)
        row.addWidget(QLabel("Épisode:"))
        self.kwic_episode_spin = QSpinBox()
        self.kwic_episode_spin.setMinimum(0)
        self.kwic_episode_spin.setMaximum(999)
        self.kwic_episode_spin.setSpecialValueText("—")
        self.kwic_episode_spin.valueChanged.connect(self._on_query_inputs_changed)
        row.addWidget(self.kwic_episode_spin)
        layout.addLayout(row)

        self.kwic_table = QTableView()
        self.kwic_model = KwicTableModel()
        self.kwic_table.setModel(self.kwic_model)
        self.kwic_table.doubleClicked.connect(self._on_double_click)
        self.kwic_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.kwic_table)

        self.kwic_feedback_label = QLabel("")
        self.kwic_feedback_label.setStyleSheet("color: #666;")
        self.kwic_feedback_label.setWordWrap(True)
        layout.addWidget(self.kwic_feedback_label)

        self.kwic_search_edit.returnPressed.connect(self._run_kwic)
        self.kwic_search_edit.textChanged.connect(self._on_query_inputs_changed)
        self._kwic_go_tooltip_default = self.kwic_go_btn.toolTip()
        self._kwic_export_tooltip_default = self.export_kwic_btn.toolTip()
        self._kwic_more_tooltip_default = self.kwic_more_btn.toolTip()
        self._kwic_cancel_tooltip_default = self.kwic_cancel_btn.toolTip()
        self._kwic_kind_tooltip_default = self.kwic_kind_combo.toolTip()
        self._kwic_lang_tooltip_default = self.kwic_lang_combo.toolTip()
        self._apply_controls_enabled()

    def _on_scope_changed(self, *_args) -> None:
        self._invalidate_hits()
        self._apply_controls_enabled()

    def _on_query_inputs_changed(self, *_args) -> None:
        self._invalidate_hits()
        self._apply_controls_enabled()

    def _invalidate_hits(self) -> None:
        self._kwic_has_more = False
        self._kwic_query_signature = None
        if self.kwic_model.get_all_hits():
            self.kwic_model.set_hits([])
        if not self._kwic_busy:
            self.kwic_feedback_label.setText("")

    def _current_query_signature(self) -> tuple[str, str, str, str, int, int]:
        term = self.kwic_search_edit.text().strip()
        scope = str(self.kwic_scope_combo.currentData() or "episodes")
        kind = str(self.kwic_kind_combo.currentData() or "")
        lang = str(self.kwic_lang_combo.currentData() or "")
        season = self.kwic_season_spin.value() if self.kwic_season_spin.value() > 0 else 0
        episode = self.kwic_episode_spin.value() if self.kwic_episode_spin.value() > 0 else 0
        return term, scope, kind, lang, season, episode

    def _apply_scope_filter_states(self, *, controls_enabled: bool) -> None:
        scope = self.kwic_scope_combo.currentData() or "episodes"
        kind_enabled = controls_enabled and scope == "segments"
        lang_enabled = controls_enabled and scope == "cues"
        self.kwic_kind_combo.setEnabled(kind_enabled)
        self.kwic_lang_combo.setEnabled(lang_enabled)
        if not controls_enabled:
            hint = "Filtre indisponible pendant un job."
            self.kwic_kind_combo.setToolTip(hint)
            self.kwic_lang_combo.setToolTip(hint)
            return
        self.kwic_kind_combo.setToolTip(
            self._kwic_kind_tooltip_default if kind_enabled else "Filtre disponible uniquement pour le scope « Segments »."
        )
        self.kwic_lang_combo.setToolTip(
            self._kwic_lang_tooltip_default if lang_enabled else "Filtre disponible uniquement pour le scope « Cues »."
        )

    def _apply_controls_enabled(self) -> None:
        controls_enabled = not self._job_busy and not self._kwic_busy
        db = self._get_db()
        controls = (
            self.kwic_search_edit,
            self.kwic_scope_combo,
            self.kwic_season_spin,
            self.kwic_episode_spin,
        )
        for widget in controls:
            widget.setEnabled(controls_enabled)
        self._apply_scope_filter_states(controls_enabled=controls_enabled)
        has_db = db is not None
        if not has_db:
            self._invalidate_hits()
        has_term = bool(self.kwic_search_edit.text().strip())
        has_hits = bool(self.kwic_model.get_all_hits())
        signature_matches = self._kwic_query_signature == self._current_query_signature()
        go_enabled = controls_enabled and has_db and has_term
        export_enabled = controls_enabled and has_hits
        load_more_enabled = controls_enabled and has_hits and has_db and self._kwic_has_more and signature_matches
        cancel_enabled = self._kwic_busy
        self.kwic_go_btn.setEnabled(go_enabled)
        self.kwic_more_btn.setEnabled(load_more_enabled)
        self.kwic_cancel_btn.setEnabled(cancel_enabled)
        self.export_kwic_btn.setEnabled(export_enabled)
        if go_enabled:
            self.kwic_go_btn.setToolTip(self._kwic_go_tooltip_default)
        elif self._kwic_busy:
            self.kwic_go_btn.setToolTip("Recherche en cours…")
        elif self._job_busy:
            self.kwic_go_btn.setToolTip("Recherche indisponible pendant un job pipeline.")
        elif not has_db:
            self.kwic_go_btn.setToolTip("Recherche indisponible: ouvrez un projet.")
        else:
            self.kwic_go_btn.setToolTip("Saisissez un terme pour lancer la recherche.")
        if load_more_enabled:
            self.kwic_more_btn.setToolTip(self._kwic_more_tooltip_default)
        elif self._kwic_busy:
            self.kwic_more_btn.setToolTip("Chargement en cours…")
        elif not has_hits:
            self.kwic_more_btn.setToolTip("Aucun résultat courant.")
        elif not self._kwic_has_more:
            self.kwic_more_btn.setToolTip("Tous les résultats disponibles sont déjà affichés.")
        elif not signature_matches:
            self.kwic_more_btn.setToolTip("Les filtres ont changé: relancez une recherche complète.")
        else:
            self.kwic_more_btn.setToolTip(self._kwic_more_tooltip_default)
        if cancel_enabled:
            self.kwic_cancel_btn.setToolTip(self._kwic_cancel_tooltip_default)
        else:
            self.kwic_cancel_btn.setToolTip("Aucune recherche en cours.")
        if export_enabled:
            self.export_kwic_btn.setToolTip(self._kwic_export_tooltip_default)
        elif self._kwic_busy:
            self.export_kwic_btn.setToolTip("Export indisponible pendant une recherche KWIC.")
        elif self._job_busy:
            self.export_kwic_btn.setToolTip("Export indisponible pendant un job pipeline.")
        else:
            self.export_kwic_btn.setToolTip("Aucun résultat à exporter.")

    def set_job_busy(self, busy: bool) -> None:
        """Désactive les actions de recherche/export pendant un job pipeline."""
        self._job_busy = busy
        if busy and self._kwic_busy:
            self._cancel_kwic_query()
        self._apply_controls_enabled()

    def set_languages(self, langs: list[str]) -> None:
        """Met à jour la liste des langues (projet). Appelé par la fenêtre principale."""
        self.kwic_lang_combo.clear()
        self.kwic_lang_combo.addItem("—", "")
        for lang in langs:
            self.kwic_lang_combo.addItem(lang, lang)

    def _run_kwic(self) -> None:
        self._start_kwic_query(append=False)

    def _load_more_kwic(self) -> None:
        self._start_kwic_query(append=True)

    def _start_kwic_query(self, *, append: bool) -> None:
        if self._job_busy or self._kwic_busy:
            return
        term = self.kwic_search_edit.text().strip()
        db = self._get_db()
        if not term:
            warn_precondition(
                self,
                "Concordance",
                "Saisissez un terme avant de lancer la recherche.",
                next_step="Entrez un mot ou une expression, puis cliquez sur « Rechercher ».",
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
        signature = self._current_query_signature()
        if append:
            if not self._kwic_has_more:
                return
            if signature != self._kwic_query_signature:
                warn_precondition(
                    self,
                    "Concordance",
                    "Les filtres ont changé depuis la dernière recherche.",
                    next_step="Relancez « Rechercher » pour repartir d'une base cohérente.",
                )
                return
        scope = signature[1]
        kind = signature[2] or None
        lang = signature[3] or None
        season = signature[4] or None
        episode = signature[5] or None
        offset = len(self.kwic_model.get_all_hits()) if append else 0
        if not append:
            self.kwic_model.set_hits([])
            self._kwic_has_more = False
        self._kwic_append_mode = append
        self._kwic_busy = True
        self.kwic_feedback_label.setText("Recherche KWIC en cours…")
        self._apply_controls_enabled()
        worker = _KwicQueryWorker(
            db=db,
            term=term,
            scope=scope,
            kind=kind,
            lang=lang,
            season=season,
            episode=episode,
            window=45,
            page_size=self._kwic_page_size,
            offset=offset,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_kwic_finished)
        worker.failed.connect(self._on_kwic_failed)
        worker.cancelled.connect(self._on_kwic_cancelled)
        self._kwic_worker = worker
        self._kwic_thread = thread
        self._kwic_query_signature = signature
        thread.start()

    def _cancel_kwic_query(self) -> None:
        if not self._kwic_busy:
            return
        if self._kwic_worker is not None:
            self._kwic_worker.cancel()
        self.kwic_feedback_label.setText("Annulation de la recherche en cours…")

    def _cleanup_kwic_worker(self) -> None:
        worker = self._kwic_worker
        thread = self._kwic_thread
        self._kwic_worker = None
        self._kwic_thread = None
        if thread is not None:
            thread.quit()
            thread.wait(1500)
            thread.deleteLater()
        if worker is not None:
            worker.deleteLater()

    def _on_kwic_finished(self, hits: list, has_more: bool) -> None:
        try:
            existing = self.kwic_model.get_all_hits() if self._kwic_append_mode else []
            merged = existing + list(hits)
            self.kwic_model.set_hits(merged)
            self._kwic_has_more = bool(has_more)
            count = len(merged)
            if self._kwic_has_more:
                self.kwic_feedback_label.setText(
                    f"{count} résultat(s) affiché(s). D'autres résultats sont disponibles."
                )
            else:
                self.kwic_feedback_label.setText(f"{count} résultat(s) affiché(s).")
        finally:
            self._kwic_busy = False
            self._kwic_append_mode = False
            self._cleanup_kwic_worker()
            self._apply_controls_enabled()

    def _on_kwic_failed(self, exc: object) -> None:
        try:
            logger.error("KWIC query failed: %s", exc)
            self.kwic_feedback_label.setText("Erreur pendant la recherche KWIC.")
            show_error(self, exc=exc, context="Recherche KWIC")
        finally:
            self._kwic_busy = False
            self._kwic_append_mode = False
            self._cleanup_kwic_worker()
            self._apply_controls_enabled()

    def _on_kwic_cancelled(self) -> None:
        self._kwic_busy = False
        self._kwic_append_mode = False
        self.kwic_feedback_label.setText("Recherche KWIC annulée.")
        self._cleanup_kwic_worker()
        self._apply_controls_enabled()

    def _export_kwic(self) -> None:
        if self._job_busy or self._kwic_busy:
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
                    next_step="Choisissez un format supporté dans la boîte d'export.",
                )
                return
            show_info(
                self,
                "Export",
                build_export_success_message(
                    subject="Résultats exportés",
                    count=len(hits),
                    count_label="occurrence(s)",
                    path=path,
                ),
            )
        except Exception as e:
            logger.exception("Export KWIC")
            show_error(self, exc=e, context="Export KWIC")

    def _on_double_click(self, index: QModelIndex) -> None:
        hit = self.kwic_model.get_hit_at(index.row())
        if not hit:
            return
        try:
            self._on_open_inspector(
                hit.episode_id,
                segment_id=hit.segment_id,
                cue_id=hit.cue_id,
                cue_lang=hit.lang,
            )
        except TypeError:
            # Compatibilité: callback historique ne prend que l'episode_id.
            self._on_open_inspector(hit.episode_id)

    def closeEvent(self, event) -> None:
        if self._kwic_busy:
            self._cancel_kwic_query()
        self._cleanup_kwic_worker()
        super().closeEvent(event)
