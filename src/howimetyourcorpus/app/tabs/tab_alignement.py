"""Onglet Alignement : run par épisode, table des liens, accepter/rejeter, exports."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QMenu,
    QComboBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.pipeline.tasks import AlignEpisodeStep
from howimetyourcorpus.core.export_utils import (
    export_parallel_concordance_csv,
    export_parallel_concordance_tsv,
    export_parallel_concordance_jsonl,
    export_parallel_concordance_docx,
    export_parallel_concordance_txt,
    export_parallel_concordance_html,
    export_align_report_html,
)
from howimetyourcorpus.app.feedback import show_error, warn_precondition
from howimetyourcorpus.app.export_dialog import normalize_export_path, resolve_export_key
from howimetyourcorpus.app.models_qt import AlignLinksTableModel

logger = logging.getLogger(__name__)


def _cue_display(c: dict, max_len: int = 60) -> str:
    """Texte affiché pour une cue dans les listes (n + extrait)."""
    n = c.get("n") or ""
    text = (c.get("text_clean") or c.get("text_raw") or "").replace("\n", " ").strip()
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return f"#{n}: {text}" if text else str(c.get("cue_id", ""))


class EditAlignLinkDialog(QDialog):
    """Dialogue pour modifier manuellement la réplique EN et/ou cible d'un lien d'alignement."""

    def __init__(
        self,
        link: dict,
        episode_id: str,
        db: object,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._link = link
        self._episode_id = episode_id
        self._db = db
        self.setWindowTitle("Modifier le lien d'alignement")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        role = (link.get("role") or "").lower()
        cues_en = db.get_cues_for_episode_lang(episode_id, "en")
        self._combo_en = QComboBox()
        for c in cues_en:
            self._combo_en.addItem(_cue_display(c), c["cue_id"])
        current_cue = link.get("cue_id")
        idx_en = next((i for i in range(self._combo_en.count()) if self._combo_en.itemData(i) == current_cue), 0)
        self._combo_en.setCurrentIndex(idx_en)
        form.addRow("Réplique EN (pivot):", self._combo_en)

        self._combo_target: QComboBox | None = None
        if role == "target":
            lang = (link.get("lang") or "fr").lower()
            cues_target = db.get_cues_for_episode_lang(episode_id, lang)
            self._combo_target = QComboBox()
            for c in cues_target:
                self._combo_target.addItem(_cue_display(c), c["cue_id"])
            current_target = link.get("cue_id_target")
            idx_t = next(
                (i for i in range(self._combo_target.count()) if self._combo_target.itemData(i) == current_target),
                0,
            )
            self._combo_target.setCurrentIndex(idx_t)
            form.addRow(f"Réplique cible ({lang}):", self._combo_target)
        layout.addLayout(form)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self._on_ok)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _on_ok(self) -> None:
        self.apply()
        self.accept()

    def selected_cue_id(self) -> str | None:
        return self._combo_en.itemData(self._combo_en.currentIndex())

    def selected_cue_id_target(self) -> str | None:
        if self._combo_target is not None:
            return self._combo_target.itemData(self._combo_target.currentIndex())
        return None

    def apply(self) -> None:
        """Appelle la DB et ferme. Appelé après accept()."""
        link_id = self._link.get("link_id")
        if not link_id or not self._db:
            return
        cue_id = self.selected_cue_id()
        cue_id_target = self.selected_cue_id_target()
        self._db.update_align_link_cues(link_id, cue_id=cue_id, cue_id_target=cue_id_target or None)


class AlignmentTabWidget(QWidget):
    """Widget de l'onglet Alignement : épisode, run, table liens, lancer alignement, exports."""

    def __init__(
        self,
        get_store: Callable[[], object],
        get_db: Callable[[], object],
        run_job: Callable[[list], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._run_job = run_job
        self._job_busy = False

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Épisode:"))
        self.align_episode_combo = QComboBox()
        self.align_episode_combo.currentIndexChanged.connect(self._on_episode_changed)
        row.addWidget(self.align_episode_combo)
        row.addWidget(QLabel("Run:"))
        self.align_run_combo = QComboBox()
        self.align_run_combo.currentIndexChanged.connect(self._on_run_changed)
        row.addWidget(self.align_run_combo)
        row.addWidget(QLabel("Langue cible:"))
        self.align_target_lang_combo = QComboBox()
        self.align_target_lang_combo.setToolTip(
            "Langue des sous-titres à aligner contre EN (pivot). "
            "Les valeurs sont déduites des langues projet et des pistes disponibles."
        )
        self.align_target_lang_combo.currentIndexChanged.connect(self._on_target_lang_changed)
        row.addWidget(self.align_target_lang_combo)
        self.align_run_btn = QPushButton("Lancer alignement")
        self.align_run_btn.clicked.connect(self._run_align_episode)
        row.addWidget(self.align_run_btn)
        self.align_delete_run_btn = QPushButton("Supprimer ce run")
        self.align_delete_run_btn.setToolTip("Supprime le run sélectionné et tous ses liens (irréversible).")
        self.align_delete_run_btn.clicked.connect(self._delete_current_run)
        self.align_delete_run_btn.setEnabled(False)
        row.addWidget(self.align_delete_run_btn)
        self.align_by_similarity_cb = QCheckBox("Forcer alignement par similarité")
        self.align_by_similarity_cb.setToolTip(
            "Ignorer les timecodes et apparier EN↔cible par similarité textuelle (utile si timecodes absents ou peu fiables)."
        )
        row.addWidget(self.align_by_similarity_cb)
        self.export_align_btn = QPushButton("Exporter aligné")
        self.export_align_btn.setToolTip("Exporte les liens du run sélectionné (CSV/JSONL).")
        self.export_align_btn.clicked.connect(self._export_alignment)
        self.export_align_btn.setEnabled(False)
        row.addWidget(self.export_align_btn)
        self.export_parallel_btn = QPushButton("Exporter concordancier parallèle")
        self.export_parallel_btn.setToolTip(
            "Exporte le concordancier parallèle EN↔cible du run sélectionné."
        )
        self.export_parallel_btn.clicked.connect(self._export_parallel_concordance)
        self.export_parallel_btn.setEnabled(False)
        row.addWidget(self.export_parallel_btn)
        self.align_report_btn = QPushButton("Rapport HTML")
        self.align_report_btn.setToolTip("Génère un rapport HTML synthétique pour le run sélectionné.")
        self.align_report_btn.clicked.connect(self._export_align_report)
        self.align_report_btn.setEnabled(False)
        row.addWidget(self.align_report_btn)
        self.align_stats_btn = QPushButton("Stats")
        self.align_stats_btn.setToolTip("Affiche les statistiques du run sélectionné.")
        self.align_stats_btn.clicked.connect(self._show_align_stats)
        self.align_stats_btn.setEnabled(False)
        row.addWidget(self.align_stats_btn)
        self.align_accepted_only_cb = QCheckBox("Liens acceptés uniquement")
        self.align_accepted_only_cb.setToolTip(
            "Export concordancier, rapport HTML et stats : ne considérer que les liens acceptés"
        )
        row.addWidget(self.align_accepted_only_cb)
        layout.addLayout(row)
        self._align_delete_run_tooltip_default = self.align_delete_run_btn.toolTip()
        self._export_align_tooltip_default = self.export_align_btn.toolTip()
        self._export_parallel_tooltip_default = self.export_parallel_btn.toolTip()
        self._align_report_tooltip_default = self.align_report_btn.toolTip()
        self._align_stats_tooltip_default = self.align_stats_btn.toolTip()
        help_label = QLabel(
            "Flux : 1) Onglet Sous-titres : importer SRT EN (pivot) et la langue cible (FR/IT/...). "
            "2) Inspecteur : segmenter l'épisode (transcript → segments). "
            "3) Ici : choisir la langue cible, puis « Lancer alignement » crée un run (segment↔cue EN, puis cue EN↔cue cible). "
            "Un run = un calcul d'alignement ; vous pouvez en relancer un autre ou supprimer un run. "
            "Clic droit sur une ligne : Accepter, Rejeter, Modifier la cible."
        )
        help_label.setStyleSheet("color: gray; font-size: 0.9em;")
        help_label.setWordWrap(True)
        help_label.setToolTip(
            "Segment = phrase du transcript (Inspecteur). Cue pivot = réplique SRT EN. Cue cible = réplique SRT FR/IT."
        )
        layout.addWidget(help_label)
        self.align_table = QTableView()
        self.align_table.setToolTip("Clic droit : Accepter, Rejeter ou Modifier la cible (alignement manuel).")
        self.align_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.align_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.align_table.customContextMenuRequested.connect(self._table_context_menu)
        layout.addWidget(self.align_table)

    def _current_episode_id(self) -> str | None:
        episode_id = self.align_episode_combo.currentData()
        return str(episode_id) if episode_id else None

    def _current_run_id(self) -> str | None:
        run_id = self.align_run_combo.currentData()
        return str(run_id) if run_id else None

    def _selected_status_filter(self) -> str | None:
        return "accepted" if self.align_accepted_only_cb.isChecked() else None

    def _resolve_episode_store_db_or_warn(
        self,
        *,
        title: str,
        next_step: str,
    ) -> tuple[str, object, object] | None:
        episode_id = self._current_episode_id()
        store = self._get_store()
        db = self._get_db()
        if not episode_id or not store or not db:
            warn_precondition(
                self,
                title,
                "Sélectionnez un épisode et ouvrez un projet.",
                next_step=next_step,
            )
            return None
        return episode_id, store, db

    def _resolve_target_lang_or_warn(self, *, title: str) -> str | None:
        if self.align_target_lang_combo.count() == 0:
            warn_precondition(
                self,
                title,
                "Aucune langue cible disponible pour cet épisode. Importez un SRT/VTT cible dans l'Inspecteur.",
                next_step="Inspecteur > Sous-titres: importez une piste non-EN pour cet épisode.",
            )
            return None
        target_lang = (self.align_target_lang_combo.currentData() or "fr").lower()
        if target_lang == "en":
            warn_precondition(
                self,
                title,
                "La langue cible doit être différente de EN (pivot).",
            )
            return None
        return target_lang

    def _require_episode_run_and_db(self, title: str, message: str) -> tuple[str, str, object] | None:
        episode_id = self._current_episode_id()
        run_id = self._current_run_id()
        db = self._get_db()
        if not episode_id or not run_id or not db:
            warn_precondition(
                self,
                title,
                message,
                next_step="Sélectionnez un épisode puis un run d'alignement.",
            )
            return None
        return episode_id, run_id, db

    def refresh(self) -> None:
        """Recharge la liste des épisodes et des runs (appelé après ouverture projet / alignement)."""
        self.align_episode_combo.clear()
        store = self._get_store()
        if not store:
            self._refresh_target_lang_combo(None)
            return
        index = store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.align_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
        self._on_episode_changed()

    def _resolve_target_langs(self, episode_id: str | None) -> list[str]:
        project_langs: list[str] = []
        store = self._get_store()
        if store:
            try:
                project_langs = [(lng or "").lower() for lng in store.load_project_languages()]
            except Exception:
                logger.exception("Failed to load project languages for alignment")
                project_langs = []
        track_langs: list[str] = []
        db = self._get_db()
        if db and episode_id:
            try:
                tracks = db.get_tracks_for_episode(episode_id)
                track_langs = [(t.get("lang") or "").lower() for t in tracks]
            except Exception:
                logger.exception("Failed to load subtitle tracks for alignment")
                track_langs = []
        # Priorité aux langues réellement disponibles pour l'épisode.
        langs = track_langs or project_langs
        dedup: list[str] = []
        seen: set[str] = set()
        for lng in langs:
            if not lng or lng == "en" or lng in seen:
                continue
            seen.add(lng)
            dedup.append(lng)
        return dedup

    def _refresh_target_lang_combo(self, episode_id: str | None) -> None:
        current = (self.align_target_lang_combo.currentData() or "").lower()
        langs = self._resolve_target_langs(episode_id)
        self.align_target_lang_combo.clear()
        for lng in langs:
            self.align_target_lang_combo.addItem(lng.upper(), lng)
        if current and current in langs:
            idx = langs.index(current)
            self.align_target_lang_combo.setCurrentIndex(idx)
        has_target = self.align_target_lang_combo.count() > 0
        controls_enabled = not self._job_busy
        self.align_target_lang_combo.setEnabled(has_target and controls_enabled)
        if not has_target:
            self.align_target_lang_combo.setToolTip(
                "Aucune piste cible disponible pour cet épisode. Importez d'abord un SRT/VTT non-EN."
            )
        else:
            self.align_target_lang_combo.setToolTip(
                "Langue des sous-titres à aligner contre EN (pivot). "
                "Les valeurs sont déduites des pistes disponibles."
            )
        self._refresh_run_button_state(episode_id)

    def _refresh_run_button_state(self, episode_id: str | None) -> None:
        controls_enabled = not self._job_busy
        if not controls_enabled:
            self.align_run_btn.setEnabled(False)
            self.align_run_btn.setToolTip("Alignement indisponible pendant l'exécution d'un job.")
            return
        if not episode_id:
            self.align_run_btn.setEnabled(False)
            self.align_run_btn.setToolTip("Sélectionnez un épisode.")
            return
        db = self._get_db()
        if not db:
            self.align_run_btn.setEnabled(False)
            self.align_run_btn.setToolTip("Base de données indisponible. Rouvrez le projet.")
            return
        prerequisites = self._resolve_run_prerequisites(episode_id, db)
        if prerequisites is None:
            self.align_run_btn.setEnabled(False)
            self.align_run_btn.setToolTip("Impossible de vérifier les prérequis d'alignement.")
            return
        can_run, missing = prerequisites
        self.align_run_btn.setEnabled(can_run)
        if can_run:
            self.align_run_btn.setToolTip("Lancer l'alignement de l'épisode sélectionné.")
            return
        self.align_run_btn.setToolTip(
            "Prérequis manquants: " + ", ".join(missing) + "."
        )

    def _resolve_run_prerequisites(self, episode_id: str, db: object) -> tuple[bool, list[str]] | None:
        has_target = self.align_target_lang_combo.count() > 0
        try:
            has_segments = bool(db.get_segments_for_episode(episode_id, kind="sentence"))
            has_cues_en = bool(db.get_cues_for_episode_lang(episode_id, "en"))
        except Exception:
            logger.exception("Failed to evaluate align prerequisites")
            return None
        missing: list[str] = []
        if not has_segments:
            missing.append("segments transcript")
        if not has_cues_en:
            missing.append("piste EN")
        if not has_target:
            missing.append("piste cible")
        return len(missing) == 0, missing

    def _on_episode_changed(self) -> None:
        self.align_run_combo.clear()
        self._set_run_actions_enabled(False, reason="Sélectionnez d'abord un run d'alignement.")
        eid = self._current_episode_id()
        db = self._get_db()
        self._refresh_target_lang_combo(eid if eid else None)
        if not eid or not db:
            self._fill_links()
            return
        try:
            runs = db.get_align_runs_for_episode(eid)
        except Exception:
            logger.exception("Failed to load alignment runs")
            runs = []
        for r in runs:
            run_id = r.get("align_run_id", "")
            created = r.get("created_at", "")[:19] if r.get("created_at") else ""
            self.align_run_combo.addItem(f"{run_id} ({created})", run_id)
        self._on_run_changed()

    def _on_run_changed(self) -> None:
        run_id = self._current_run_id()
        self._set_run_actions_enabled(
            bool(run_id),
            reason="Sélectionnez d'abord un run d'alignement.",
        )
        self._fill_links()

    def _on_target_lang_changed(self, *_args) -> None:
        self._refresh_run_button_state(self._current_episode_id())

    def _set_run_actions_enabled(self, enabled: bool, *, reason: str | None = None) -> None:
        controls_enabled = enabled and not self._job_busy
        self.align_delete_run_btn.setEnabled(controls_enabled)
        self.export_align_btn.setEnabled(controls_enabled)
        self.export_parallel_btn.setEnabled(controls_enabled)
        self.align_report_btn.setEnabled(controls_enabled)
        self.align_stats_btn.setEnabled(controls_enabled)
        if controls_enabled:
            self.align_delete_run_btn.setToolTip(self._align_delete_run_tooltip_default)
            self.export_align_btn.setToolTip(self._export_align_tooltip_default)
            self.export_parallel_btn.setToolTip(self._export_parallel_tooltip_default)
            self.align_report_btn.setToolTip(self._align_report_tooltip_default)
            self.align_stats_btn.setToolTip(self._align_stats_tooltip_default)
            return
        hint = (
            "Action indisponible pendant l'exécution d'un job."
            if self._job_busy
            else (reason or "Créez ou sélectionnez d'abord un run d'alignement.")
        )
        self.align_delete_run_btn.setToolTip(hint)
        self.export_align_btn.setToolTip(hint)
        self.export_parallel_btn.setToolTip(hint)
        self.align_report_btn.setToolTip(hint)
        self.align_stats_btn.setToolTip(hint)

    def set_job_busy(self, busy: bool) -> None:
        """Désactive les actions interactives pendant un job en cours."""
        self._job_busy = busy
        controls = (
            self.align_episode_combo,
            self.align_run_combo,
            self.align_target_lang_combo,
            self.align_run_btn,
            self.align_delete_run_btn,
            self.align_by_similarity_cb,
            self.export_align_btn,
            self.export_parallel_btn,
            self.align_report_btn,
            self.align_stats_btn,
            self.align_accepted_only_cb,
            self.align_table,
        )
        for widget in controls:
            widget.setEnabled(not busy)
        if busy:
            self._set_run_actions_enabled(False, reason="Action indisponible pendant l'exécution d'un job.")
            return
        # Restaurer l'état normal selon les données courantes.
        eid = self._current_episode_id()
        self._refresh_target_lang_combo(eid if eid else None)
        self._set_run_actions_enabled(
            bool(self._current_run_id()),
            reason="Sélectionnez d'abord un run d'alignement.",
        )
        self.align_episode_combo.setEnabled(True)
        self.align_run_combo.setEnabled(True)
        self.align_by_similarity_cb.setEnabled(True)
        self.align_accepted_only_cb.setEnabled(True)
        self.align_table.setEnabled(True)

    def _delete_current_run(self) -> None:
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not run_id or not db:
            warn_precondition(
                self,
                "Alignement",
                "Sélectionnez un run d'alignement.",
                next_step="Choisissez un épisode puis un run dans la liste.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Supprimer le run",
            f"Supprimer le run « {run_id} » et tous ses liens ? (irréversible)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        db.delete_align_run(run_id)
        self.refresh()
        self._fill_links()

    def _fill_links(self) -> None:
        eid = self._current_episode_id()
        run_id = self._current_run_id()
        model = AlignLinksTableModel()
        db = self._get_db()
        if not db or not eid:
            self.align_table.setModel(model)
            return
        try:
            links = db.query_alignment_for_episode(eid, run_id=run_id)
        except Exception as e:
            logger.exception("Failed to load alignment links")
            self.align_table.setModel(model)
            show_error(self, exc=e, context="Chargement alignement")
            return
        model.set_links(links, db, episode_id=eid)
        self.align_table.setModel(model)

    def _table_context_menu(self, pos: QPoint) -> None:
        idx = self.align_table.indexAt(pos)
        if not idx.isValid():
            return
        db = self._get_db()
        if not db:
            return
        model = self.align_table.model()
        if not isinstance(model, AlignLinksTableModel):
            return
        link = model.get_link_at(idx.row())
        if not link or not link.get("link_id"):
            return
        link_id = link["link_id"]
        eid = self._current_episode_id()
        menu = QMenu(self)
        accept_act = menu.addAction("Accepter")
        reject_act = menu.addAction("Rejeter")
        edit_act = menu.addAction("Modifier la cible…")
        action = menu.exec(self.align_table.viewport().mapToGlobal(pos))
        if action == accept_act:
            db.set_align_status(link_id, "accepted")
            self._fill_links()
        elif action == reject_act:
            db.set_align_status(link_id, "rejected")
            self._fill_links()
        elif action == edit_act and eid:
            dlg = EditAlignLinkDialog(link, eid, db, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._fill_links()

    def _run_align_episode(self) -> None:
        resolved = self._resolve_episode_store_db_or_warn(
            title="Alignement",
            next_step="Pilotage: ouvrez/créez un projet puis choisissez un épisode ici.",
        )
        if resolved is None:
            return
        eid, _store, db = resolved
        prerequisites = self._resolve_run_prerequisites(eid, db)
        if prerequisites is None:
            warn_precondition(
                self,
                "Alignement",
                "Impossible de vérifier les prérequis d'alignement.",
                next_step="Rafraîchissez l'onglet puis réessayez.",
            )
            return
        can_run, missing = prerequisites
        if not can_run:
            warn_precondition(
                self,
                "Alignement",
                "Prérequis manquants: " + ", ".join(missing) + ".",
                next_step="Inspecteur: importez EN + cible, puis segmentez l'épisode.",
            )
            return
        target_lang = self._resolve_target_lang_or_warn(title="Alignement")
        if target_lang is None:
            return
        use_similarity = self.align_by_similarity_cb.isChecked()
        self._run_job([
            AlignEpisodeStep(
                eid,
                pivot_lang="en",
                target_langs=[target_lang],
                use_similarity_for_cues=use_similarity,
            )
        ])

    def _export_alignment(self) -> None:
        state = self._require_episode_run_and_db(
            "Alignement",
            "Sélectionnez un épisode et un run.",
        )
        if not state:
            return
        eid, run_id, db = state
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Exporter alignement", "", "CSV (*.csv);;JSONL (*.jsonl)"
        )
        if not path:
            return
        path = Path(path)
        path = normalize_export_path(
            path,
            selected_filter,
            allowed_suffixes=(".csv", ".jsonl"),
            default_suffix=".csv",
            filter_to_suffix={
                "CSV": ".csv",
                "JSONL": ".jsonl",
            },
        )
        export_key = resolve_export_key(
            path,
            selected_filter,
            suffix_to_key={".csv": "csv", ".jsonl": "jsonl"},
        )
        links = db.query_alignment_for_episode(eid, run_id=run_id)
        try:
            if export_key == "jsonl":
                with path.open("w", encoding="utf-8") as f:
                    for row in links:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
            else:
                with path.open("w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f)
                    w.writerow([
                        "link_id", "segment_id", "cue_id", "cue_id_target", "lang", "role",
                        "confidence", "status", "meta",
                    ])
                    for row in links:
                        meta = row.get("meta")
                        meta_str = json.dumps(meta, ensure_ascii=False) if meta else ""
                        w.writerow([
                            row.get("link_id"), row.get("segment_id"), row.get("cue_id"),
                            row.get("cue_id_target"), row.get("lang"), row.get("role"),
                            row.get("confidence"), row.get("status"), meta_str,
                        ])
            QMessageBox.information(self, "Export", f"Alignement exporté : {len(links)} lien(s).")
        except Exception as e:
            logger.exception("Export alignement")
            show_error(self, exc=e, context="Export alignement")

    def _export_parallel_concordance(self) -> None:
        state = self._require_episode_run_and_db(
            "Concordancier parallèle",
            "Sélectionnez un épisode et un run.",
        )
        if not state:
            return
        eid, run_id, db = state
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Exporter concordancier parallèle (comparaison de traductions)", "",
            "CSV (*.csv);;TSV (*.tsv);;TXT (*.txt);;HTML (*.html);;JSONL (*.jsonl);;Word (*.docx)"
        )
        if not path:
            return
        path = Path(path)
        path = normalize_export_path(
            path,
            selected_filter,
            allowed_suffixes=(".csv", ".tsv", ".txt", ".html", ".jsonl", ".docx"),
            default_suffix=".csv",
            filter_to_suffix={
                "CSV": ".csv",
                "TSV": ".tsv",
                "TXT": ".txt",
                "HTML": ".html",
                "JSONL": ".jsonl",
                "WORD": ".docx",
            },
        )
        export_key = resolve_export_key(
            path,
            selected_filter,
            suffix_to_key={
                ".csv": "csv",
                ".tsv": "tsv",
                ".txt": "txt",
                ".html": "html",
                ".jsonl": "jsonl",
                ".docx": "docx",
            },
        )
        try:
            status_filter = self._selected_status_filter()
            rows = db.get_parallel_concordance(eid, run_id, status_filter=status_filter)
            if export_key == "jsonl":
                export_parallel_concordance_jsonl(rows, path)
            elif export_key == "tsv":
                export_parallel_concordance_tsv(rows, path)
            elif export_key == "txt":
                export_parallel_concordance_txt(rows, path)
            elif export_key == "html":
                export_parallel_concordance_html(rows, path, title=f"Comparaison {eid} — {run_id}")
            elif export_key == "docx":
                export_parallel_concordance_docx(rows, path)
            else:
                export_parallel_concordance_csv(rows, path)
            QMessageBox.information(
                self, "Export", f"Concordancier parallèle exporté : {len(rows)} ligne(s)."
            )
        except Exception as e:
            logger.exception("Export concordancier parallèle")
            show_error(self, exc=e, context="Export concordancier parallèle")

    def _export_align_report(self) -> None:
        state = self._require_episode_run_and_db(
            "Rapport",
            "Sélectionnez un épisode et un run.",
        )
        if not state:
            return
        eid, run_id, db = state
        path, _ = QFileDialog.getSaveFileName(
            self, "Rapport alignement", "", "HTML (*.html)"
        )
        if not path:
            return
        path = normalize_export_path(
            Path(path),
            None,
            allowed_suffixes=(".html",),
            default_suffix=".html",
        )
        try:
            status_filter = self._selected_status_filter()
            stats = db.get_align_stats_for_run(eid, run_id, status_filter=status_filter)
            sample = db.get_parallel_concordance(eid, run_id, status_filter=status_filter)
            export_align_report_html(stats, sample, eid, run_id, path)
            QMessageBox.information(self, "Rapport", f"Rapport enregistré : {path.name}")
        except Exception as e:
            logger.exception("Rapport alignement")
            show_error(self, exc=e, context="Rapport alignement")

    def _show_align_stats(self) -> None:
        state = self._require_episode_run_and_db(
            "Stats",
            "Sélectionnez un épisode et un run.",
        )
        if not state:
            return
        eid, run_id, db = state
        try:
            status_filter = self._selected_status_filter()
            stats = db.get_align_stats_for_run(eid, run_id, status_filter=status_filter)
            by_status = stats.get("by_status") or {}
            msg = (
                f"Épisode: {stats.get('episode_id', '')}\n"
                f"Run: {stats.get('run_id', '')}\n\n"
                f"Liens totaux: {stats.get('nb_links', 0)}\n"
                f"Liens pivot (segment↔EN): {stats.get('nb_pivot', 0)}\n"
                f"Liens target (EN↔cible): {stats.get('nb_target', 0)}\n"
                f"Confiance moyenne: {stats.get('avg_confidence', '—')}\n"
                f"Par statut: {', '.join(f'{k}={v}' for k, v in sorted(by_status.items()))}"
            )
            QMessageBox.information(self, "Statistiques alignement", msg)
        except Exception as e:
            logger.exception("Stats alignement")
            show_error(self, exc=e, context="Statistiques alignement")
