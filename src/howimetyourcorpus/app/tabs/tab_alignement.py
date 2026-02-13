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
    export_align_report_html,
)
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
        self.align_run_btn = QPushButton("Lancer alignement")
        self.align_run_btn.clicked.connect(self._run_align_episode)
        row.addWidget(self.align_run_btn)
        self.align_delete_run_btn = QPushButton("Supprimer ce run")
        self.align_delete_run_btn.setToolTip("Supprime le run sélectionné et tous ses liens (irréversible).")
        self.align_delete_run_btn.clicked.connect(self._delete_current_run)
        row.addWidget(self.align_delete_run_btn)
        self.align_by_similarity_cb = QCheckBox("Forcer alignement par similarité")
        self.align_by_similarity_cb.setToolTip(
            "Ignorer les timecodes et apparier EN↔cible par similarité textuelle (utile si timecodes absents ou peu fiables)."
        )
        row.addWidget(self.align_by_similarity_cb)
        self.export_align_btn = QPushButton("Exporter aligné")
        self.export_align_btn.clicked.connect(self._export_alignment)
        row.addWidget(self.export_align_btn)
        self.export_parallel_btn = QPushButton("Exporter concordancier parallèle")
        self.export_parallel_btn.clicked.connect(self._export_parallel_concordance)
        row.addWidget(self.export_parallel_btn)
        self.align_report_btn = QPushButton("Rapport HTML")
        self.align_report_btn.clicked.connect(self._export_align_report)
        row.addWidget(self.align_report_btn)
        self.align_stats_btn = QPushButton("Stats")
        self.align_stats_btn.clicked.connect(self._show_align_stats)
        row.addWidget(self.align_stats_btn)
        self.align_accepted_only_cb = QCheckBox("Liens acceptés uniquement")
        self.align_accepted_only_cb.setToolTip(
            "Export concordancier, rapport HTML et stats : ne considérer que les liens acceptés"
        )
        row.addWidget(self.align_accepted_only_cb)
        layout.addLayout(row)
        help_label = QLabel(
            "Flux : 1) Onglet Sous-titres : importer SRT EN (pivot) et FR (cible). "
            "2) Inspecteur : segmenter l'épisode (transcript → segments). "
            "3) Ici : « Lancer alignement » crée un run (segment↔cue EN, puis cue EN↔cue FR). "
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

    def refresh(self) -> None:
        """Recharge la liste des épisodes et des runs (appelé après ouverture projet / alignement)."""
        self.align_episode_combo.clear()
        store = self._get_store()
        if not store:
            return
        index = store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.align_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
        self._on_episode_changed()

    def _on_episode_changed(self) -> None:
        self.align_run_combo.clear()
        eid = self.align_episode_combo.currentData()
        db = self._get_db()
        if not eid or not db:
            self._fill_links()
            return
        runs = db.get_align_runs_for_episode(eid)
        for r in runs:
            run_id = r.get("align_run_id", "")
            created = r.get("created_at", "")[:19] if r.get("created_at") else ""
            self.align_run_combo.addItem(f"{run_id} ({created})", run_id)
        self._on_run_changed()

    def _on_run_changed(self) -> None:
        run_id = self.align_run_combo.currentData()
        self.align_delete_run_btn.setEnabled(bool(run_id))
        self._fill_links()

    def _delete_current_run(self) -> None:
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not run_id or not db:
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
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        model = AlignLinksTableModel()
        db = self._get_db()
        if not db or not eid:
            self.align_table.setModel(model)
            return
        links = db.query_alignment_for_episode(eid, run_id=run_id)
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
        eid = self.align_episode_combo.currentData()
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
        eid = self.align_episode_combo.currentData()
        store = self._get_store()
        db = self._get_db()
        if not eid or not store or not db:
            QMessageBox.warning(self, "Alignement", "Sélectionnez un épisode et ouvrez un projet.")
            return
        use_similarity = self.align_by_similarity_cb.isChecked()
        self._run_job([
            AlignEpisodeStep(
                eid,
                pivot_lang="en",
                target_langs=["fr"],
                use_similarity_for_cues=use_similarity,
            )
        ])

    def _export_alignment(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not eid or not run_id or not db:
            QMessageBox.warning(self, "Alignement", "Sélectionnez un épisode et un run.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter alignement", "", "CSV (*.csv);;JSONL (*.jsonl)"
        )
        if not path:
            return
        path = Path(path)
        links = db.query_alignment_for_episode(eid, run_id=run_id)
        try:
            if path.suffix.lower() == ".jsonl":
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
            QMessageBox.critical(self, "Erreur", str(e))

    def _export_parallel_concordance(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not eid or not run_id or not db:
            QMessageBox.warning(self, "Concordancier parallèle", "Sélectionnez un épisode et un run.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter concordancier parallèle", "",
            "CSV (*.csv);;TSV (*.tsv);;JSONL (*.jsonl)"
        )
        if not path:
            return
        path = Path(path)
        try:
            status_filter = "accepted" if self.align_accepted_only_cb.isChecked() else None
            rows = db.get_parallel_concordance(eid, run_id, status_filter=status_filter)
            if path.suffix.lower() == ".jsonl":
                export_parallel_concordance_jsonl(rows, path)
            elif path.suffix.lower() == ".tsv":
                export_parallel_concordance_tsv(rows, path)
            else:
                export_parallel_concordance_csv(rows, path)
            QMessageBox.information(
                self, "Export", f"Concordancier parallèle exporté : {len(rows)} ligne(s)."
            )
        except Exception as e:
            logger.exception("Export concordancier parallèle")
            QMessageBox.critical(self, "Erreur", str(e))

    def _export_align_report(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not eid or not run_id or not db:
            QMessageBox.warning(self, "Rapport", "Sélectionnez un épisode et un run.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Rapport alignement", "", "HTML (*.html)"
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != ".html":
            path = path.with_suffix(".html")
        try:
            status_filter = "accepted" if self.align_accepted_only_cb.isChecked() else None
            stats = db.get_align_stats_for_run(eid, run_id, status_filter=status_filter)
            sample = db.get_parallel_concordance(eid, run_id, status_filter=status_filter)
            export_align_report_html(stats, sample, eid, run_id, path)
            QMessageBox.information(self, "Rapport", f"Rapport enregistré : {path.name}")
        except Exception as e:
            logger.exception("Rapport alignement")
            QMessageBox.critical(self, "Erreur", str(e))

    def _show_align_stats(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not eid or not run_id or not db:
            QMessageBox.warning(self, "Stats", "Sélectionnez un épisode et un run.")
            return
        try:
            status_filter = "accepted" if self.align_accepted_only_cb.isChecked() else None
            stats = db.get_align_stats_for_run(eid, run_id, status_filter=status_filter)
            by_status = stats.get("by_status") or {}
            msg = (
                f"Épisode: {stats.get('episode_id', '')}\n"
                f"Run: {stats.get('run_id', '')}\n\n"
                f"Liens totaux: {stats.get('nb_links', 0)}\n"
                f"Liens pivot (segment↔EN): {stats.get('nb_pivot', 0)}\n"
                f"Liens target (EN↔FR): {stats.get('nb_target', 0)}\n"
                f"Confiance moyenne: {stats.get('avg_confidence', '—')}\n"
                f"Par statut: {', '.join(f'{k}={v}' for k, v in sorted(by_status.items()))}"
            )
            QMessageBox.information(self, "Statistiques alignement", msg)
        except Exception as e:
            logger.exception("Stats alignement")
            QMessageBox.critical(self, "Erreur", str(e))
