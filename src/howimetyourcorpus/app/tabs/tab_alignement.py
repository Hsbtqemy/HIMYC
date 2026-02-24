"""Onglet Alignement : run par épisode, table des liens, accepter/rejeter, exports + Undo/Redo (Basse Priorité #3)."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, Qt, QSettings
from PySide6.QtGui import QUndoStack
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
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.align import (
    format_segment_kind_label,
    normalize_segment_kind,
    parse_run_segment_kind,
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
from howimetyourcorpus.app.models_qt import AlignLinksTableModel
from howimetyourcorpus.app.ui_utils import require_project_and_db, confirm_action
from howimetyourcorpus.app.widgets import AlignStatsWidget
from howimetyourcorpus.app.undo_commands import (
    BulkAcceptLinksCommand,
    BulkRejectLinksCommand,
    DeleteAlignRunCommand,
    EditAlignLinkCommand,
    SetAlignStatusCommand,
)

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
    """Widget de l'onglet Alignement : épisode, run, table liens, lancer alignement, exports + Undo/Redo (BP3)."""

    def __init__(
        self,
        get_store: Callable[[], object],
        get_db: Callable[[], object],
        run_job: Callable[[list], None],
        undo_stack: QUndoStack | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._run_job = run_job
        self.undo_stack = undo_stack  # Basse Priorité #3

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
        row.addWidget(QLabel("Segments:"))
        self.align_segment_kind_combo = QComboBox()
        self.align_segment_kind_combo.addItem("Phrases", "sentence")
        self.align_segment_kind_combo.addItem("Tours", "utterance")
        self.align_segment_kind_combo.setToolTip(
            "Type de segments transcript à aligner avec les cues (phrases ou tours)."
        )
        row.addWidget(self.align_segment_kind_combo)
        self.align_run_btn = QPushButton("Lancer alignement")
        self.align_run_btn.clicked.connect(self._run_align_episode)
        row.addWidget(self.align_run_btn)
        self.align_delete_run_btn = QPushButton("Supprimer ce run")
        self.align_delete_run_btn.setToolTip("Supprime le run sélectionné et tous ses liens. Annulable avec Ctrl+Z.")
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
        self.align_group_btn = QPushButton("Générer groupes")
        self.align_group_btn.setToolTip(
            "Construit des groupes multi-langues par personnage à partir du run (non destructif)."
        )
        self.align_group_btn.clicked.connect(self._generate_alignment_groups)
        row.addWidget(self.align_group_btn)
        self.export_grouped_btn = QPushButton("Exporter groupes alignés")
        self.export_grouped_btn.setToolTip(
            "Exporte le concordancier à partir des groupes multi-langues générés (ou les génère si absents)."
        )
        self.export_grouped_btn.clicked.connect(self._export_grouped_alignment)
        row.addWidget(self.export_grouped_btn)
        self.align_report_btn = QPushButton("Rapport HTML")
        self.align_report_btn.clicked.connect(self._export_align_report)
        row.addWidget(self.align_report_btn)
        # Phase 7 HP4 : Bouton "Stats" supprimé (remplacé par panneau permanent)
        self.align_accepted_only_cb = QCheckBox("Liens acceptés uniquement")
        self.align_accepted_only_cb.setToolTip(
            "Export concordancier et rapport HTML : ne considérer que les liens acceptés"
        )
        row.addWidget(self.align_accepted_only_cb)
        layout.addLayout(row)
        help_label = QLabel(
            "Flux : 1) Onglet Sous-titres : importer SRT EN (pivot) et FR (cible). "
            "2) Inspecteur : segmenter l'épisode (transcript → segments phrases et/ou tours). "
            "3) Ici : choisir Segment (Phrases ou Tours), puis « Lancer alignement » crée un run (segment↔cue pivot, puis cue pivot↔cue cible). "
            "Un run = un calcul d'alignement ; vous pouvez en relancer un autre ou supprimer un run. "
            "Clic droit sur une ligne : Accepter, Rejeter, Modifier la cible."
        )
        help_label.setStyleSheet("color: gray; font-size: 0.9em;")
        help_label.setWordWrap(True)
        help_label.setToolTip(
            "Segment = phrase du transcript (Phrases) ou tour de parole (Tours, une ligne par réplique). Cue pivot = réplique SRT. Cue cible = réplique SRT autre langue."
        )
        layout.addWidget(help_label)
        
        # Moyenne Priorité #4 : Actions bulk alignement
        bulk_row = QHBoxLayout()
        bulk_row.addWidget(QLabel("Actions bulk:"))
        self.bulk_accept_btn = QPushButton("Accepter tous > seuil")
        self.bulk_accept_btn.setToolTip("Accepte automatiquement tous les liens avec confidence > seuil")
        self.bulk_accept_btn.clicked.connect(self._bulk_accept)
        bulk_row.addWidget(self.bulk_accept_btn)
        
        self.bulk_reject_btn = QPushButton("Rejeter tous < seuil")
        self.bulk_reject_btn.setToolTip("Rejette automatiquement tous les liens avec confidence < seuil")
        self.bulk_reject_btn.clicked.connect(self._bulk_reject)
        bulk_row.addWidget(self.bulk_reject_btn)
        
        bulk_row.addWidget(QLabel("Seuil:"))
        self.bulk_threshold_spin = QSpinBox()
        self.bulk_threshold_spin.setRange(0, 100)
        self.bulk_threshold_spin.setValue(80)
        self.bulk_threshold_spin.setSuffix("%")
        self.bulk_threshold_spin.setToolTip("Seuil de confidence pour les actions bulk (0-100%)")
        bulk_row.addWidget(self.bulk_threshold_spin)
        bulk_row.addStretch()
        layout.addLayout(bulk_row)
        
        # Phase 7 HP4 : Splitter horizontal (table à gauche, stats à droite)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.align_table = QTableView()
        self.align_table.setToolTip("Clic droit : Accepter, Rejeter ou Modifier la cible (alignement manuel).")
        self.align_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.align_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.align_table.customContextMenuRequested.connect(self._table_context_menu)
        
        # Phase 7 HP4 : Widget stats permanent
        self.stats_widget = AlignStatsWidget()
        self.stats_widget.setMaximumWidth(250)
        
        self.main_splitter.addWidget(self.align_table)
        self.main_splitter.addWidget(self.stats_widget)
        self.main_splitter.setStretchFactor(0, 3)  # Table prend 75%
        self.main_splitter.setStretchFactor(1, 1)  # Stats prend 25%
        
        layout.addWidget(self.main_splitter)
        self._restore_align_splitter()

    def _restore_align_splitter(self) -> None:
        """Restaure les proportions du splitter table | stats depuis QSettings."""
        settings = QSettings("HIMYC", "AlignmentTab")
        val = settings.value("mainSplitter")
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            try:
                self.main_splitter.setSizes([int(x) for x in val[:2]])
            except (TypeError, ValueError) as exc:
                logger.debug("Invalid AlignmentTab splitter state %r: %s", val, exc)

    def save_state(self) -> None:
        """Sauvegarde les proportions du splitter (appelé à la fermeture de l'application)."""
        settings = QSettings("HIMYC", "AlignmentTab")
        settings.setValue("mainSplitter", self.main_splitter.sizes())

    def refresh(self) -> None:
        """Recharge la liste des épisodes et des runs (préserve la sélection d'épisode si possible)."""
        current_episode_id = self.align_episode_combo.currentData()
        self.align_episode_combo.clear()
        store = self._get_store()
        if not store:
            return
        index = store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.align_episode_combo.addItem(f"{e.episode_id} - {e.title}", e.episode_id)
            if current_episode_id:
                for i in range(self.align_episode_combo.count()):
                    if self.align_episode_combo.itemData(i) == current_episode_id:
                        self.align_episode_combo.setCurrentIndex(i)
                        break
        self._on_episode_changed()

    def set_episode_and_segment_kind(self, episode_id: str, segment_kind: str = "sentence") -> None:
        """Sélectionne épisode + kind (utilisé par le handoff depuis Préparer)."""
        sk = normalize_segment_kind(segment_kind)
        idx_sk = self.align_segment_kind_combo.findData(sk)
        if idx_sk >= 0:
            self.align_segment_kind_combo.setCurrentIndex(idx_sk)
        for i in range(self.align_episode_combo.count()):
            if self.align_episode_combo.itemData(i) == episode_id:
                self.align_episode_combo.setCurrentIndex(i)
                break
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
            params_json = r.get("params_json")
            segment_kind_label = ""
            if params_json:
                parsed_kind, is_valid_payload = parse_run_segment_kind(
                    params_json,
                    run_id=run_id,
                    logger_obj=logger,
                )
                if is_valid_payload:
                    segment_kind_label = format_segment_kind_label(parsed_kind)
            self.align_run_combo.addItem(f"{run_id}{segment_kind_label} ({created})", run_id)
        self._on_run_changed()

    def _on_run_changed(self) -> None:
        run_id = self.align_run_combo.currentData()
        self.align_delete_run_btn.setEnabled(bool(run_id))
        self._fill_links()
        self._update_stats()  # Phase 7 HP4 : Mettre à jour stats panneau
    
    def _update_stats(self) -> None:
        """Phase 7 HP4 : Met à jour le panneau stats permanent."""
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        
        if not eid or not run_id or not db:
            self.stats_widget.clear_stats()
            return
        
        try:
            status_filter = "accepted" if self.align_accepted_only_cb.isChecked() else None
            stats = db.get_align_stats_for_run(eid, run_id, status_filter=status_filter)
            self.stats_widget.update_stats(stats)
        except Exception:
            logger.exception("Update stats widget")
            self.stats_widget.clear_stats()

    def _delete_current_run(self) -> None:
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        eid = self.align_episode_combo.currentData()
        
        if not run_id or not db or not eid:
            if not run_id:
                QMessageBox.information(
                    self,
                    "Supprimer le run",
                    "Aucun run sélectionné. Choisissez un run dans la liste déroulante « Run ».",
                )
            return
        
        # Compter les liens avant suppression
        links = db.query_alignment_for_episode(eid, run_id=run_id)
        nb_links = len(links)
        
        if not confirm_action(
            self,
            "Supprimer le run",
            f"Supprimer le run « {run_id} » ?\n\n"
            f"• {nb_links} lien(s) d'alignement seront supprimés\n"
            f"• Les corrections manuelles seront perdues\n"
            f"• Vous devrez relancer l'alignement pour recréer les liens\n\n"
            f"Vous pourrez annuler cette suppression avec Ctrl+Z (Undo) après validation."
        ):
            return

        try:
            if self.undo_stack:
                cmd = DeleteAlignRunCommand(db, run_id, eid)
                self.undo_stack.push(cmd)
            else:
                db.delete_align_run(run_id)
        except Exception:
            logger.exception("Suppression run (Undo)")
            try:
                db.delete_align_run(run_id)
                QMessageBox.information(
                    self,
                    "Run supprimé",
                    "Le run a été supprimé (annulation Undo non disponible).",
                )
            except Exception as e2:
                logger.exception("Suppression run directe")
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible de supprimer le run : {e2}",
                )
                return

        self.refresh()
        self._fill_links()
    
    @require_project_and_db
    def _bulk_accept(self) -> None:
        """Moyenne Priorité #4 : Accepte tous les liens avec confidence > seuil + Undo/Redo (BP3)."""
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        
        if not eid or not run_id:
            QMessageBox.warning(self, "Actions bulk", "Sélectionnez un épisode et un run.")
            return
        
        threshold = self.bulk_threshold_spin.value() / 100.0  # 80% → 0.80
        links = db.query_alignment_for_episode(eid, run_id=run_id)
        
        # Filtrer liens auto avec confidence > seuil
        candidates = [
            link for link in links
            if link.get("status") == "auto" and (link.get("confidence") or 0) >= threshold
        ]
        
        if not candidates:
            QMessageBox.information(
                self,
                "Actions bulk",
                f"Aucun lien 'auto' avec confidence >= {threshold:.0%} à accepter."
            )
            return
        
        if not confirm_action(
            self,
            "Accepter en masse",
            f"Accepter {len(candidates)} lien(s) avec confidence >= {threshold:.0%} ?\n\n"
            f"Ces liens passeront du statut 'auto' à 'accepted'."
        ):
            return
        
        # Basse Priorité #3 : Utiliser commande Undo/Redo
        if self.undo_stack:
            link_ids = [link["link_id"] for link in candidates if link.get("link_id")]
            cmd = BulkAcceptLinksCommand(db, link_ids, len(link_ids))
            self.undo_stack.push(cmd)
        else:
            # Pas de undo_stack → ancienne méthode
            with db.connection() as conn:
                for link in candidates:
                    link_id = link.get("link_id")
                    if link_id:
                        conn.execute("UPDATE align_links SET status = 'accepted' WHERE link_id = ?", (link_id,))
                conn.commit()
        
        self._fill_links()
        self._update_stats()
        QMessageBox.information(self, "Actions bulk", f"{len(candidates)} lien(s) accepté(s).")
    
    @require_project_and_db
    def _bulk_reject(self) -> None:
        """Moyenne Priorité #4 : Rejette tous les liens avec confidence < seuil + Undo/Redo (BP3)."""
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        
        if not eid or not run_id:
            QMessageBox.warning(self, "Actions bulk", "Sélectionnez un épisode et un run.")
            return
        
        threshold = self.bulk_threshold_spin.value() / 100.0
        links = db.query_alignment_for_episode(eid, run_id=run_id)
        
        # Filtrer liens auto avec confidence < seuil
        candidates = [
            link for link in links
            if link.get("status") == "auto" and (link.get("confidence") or 0) < threshold
        ]
        
        if not candidates:
            QMessageBox.information(
                self,
                "Actions bulk",
                f"Aucun lien 'auto' avec confidence < {threshold:.0%} à rejeter."
            )
            return
        
        if not confirm_action(
            self,
            "Rejeter en masse",
            f"Rejeter {len(candidates)} lien(s) avec confidence < {threshold:.0%} ?\n\n"
            f"⚠️ Ces liens passeront du statut 'auto' à 'rejected'.\n"
            f"Vous pourrez les accepter individuellement plus tard si nécessaire."
        ):
            return
        
        # Basse Priorité #3 : Utiliser commande Undo/Redo
        if self.undo_stack:
            link_ids = [link["link_id"] for link in candidates if link.get("link_id")]
            cmd = BulkRejectLinksCommand(db, link_ids, len(link_ids))
            self.undo_stack.push(cmd)
        else:
            # Pas de undo_stack → ancienne méthode
            with db.connection() as conn:
                for link in candidates:
                    link_id = link.get("link_id")
                    if link_id:
                        conn.execute("UPDATE align_links SET status = 'rejected' WHERE link_id = ?", (link_id,))
                conn.commit()
        
        self._fill_links()
        self._update_stats()
        QMessageBox.information(self, "Actions bulk", f"{len(candidates)} lien(s) rejeté(s).")

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
            # Basse Priorité #3 : Utiliser commande Undo/Redo
            if self.undo_stack:
                cmd = SetAlignStatusCommand(
                    db,
                    link_id,
                    "accepted",
                    link.get("status", "auto"),
                    f"Accepter lien #{link_id[:8]}"
                )
                self.undo_stack.push(cmd)
            else:
                db.set_align_status(link_id, "accepted")
            self._fill_links()
            self._update_stats()
            
        elif action == reject_act:
            # Basse Priorité #3 : Utiliser commande Undo/Redo
            if self.undo_stack:
                cmd = SetAlignStatusCommand(
                    db,
                    link_id,
                    "rejected",
                    link.get("status", "auto"),
                    f"Rejeter lien #{link_id[:8]}"
                )
                self.undo_stack.push(cmd)
            else:
                db.set_align_status(link_id, "rejected")
            self._fill_links()
            self._update_stats()
            
        elif action == edit_act and eid:
            dlg = EditAlignLinkDialog(link, eid, db, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                # Basse Priorité #3 : Utiliser commande Undo/Redo
                old_target_id = link.get("cue_id_target")
                new_target_id = dlg.selected_cue_id_target()
                
                if self.undo_stack and old_target_id != new_target_id:
                    cmd = EditAlignLinkCommand(
                        db,
                        link_id,
                        new_target_id,
                        old_target_id,
                        "manual",
                        link.get("status", "auto")
                    )
                    self.undo_stack.push(cmd)
                else:
                    # Pas de undo_stack ou pas de changement → ancienne méthode
                    pass  # Le dialogue a déjà fait la mise à jour
                
                self._fill_links()
                self._update_stats()

    @require_project_and_db
    def _run_align_episode(self) -> None:
        eid = self.align_episode_combo.currentData()
        if not eid:
            QMessageBox.warning(self, "Alignement", "Sélectionnez un épisode.")
            return
        use_similarity = self.align_by_similarity_cb.isChecked()
        segment_kind = self.align_segment_kind_combo.currentData() or "sentence"
        self._run_job([
            AlignEpisodeStep(
                eid,
                pivot_lang="en",
                target_langs=["fr"],
                use_similarity_for_cues=use_similarity,
                segment_kind=segment_kind,
            )
        ])

    @require_project_and_db
    def _generate_alignment_groups(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        store = self._get_store()
        if not eid or not run_id:
            QMessageBox.warning(self, "Groupes alignés", "Sélectionnez un épisode et un run.")
            return
        if not db or not store:
            return
        try:
            grouping = store.generate_align_grouping(db, eid, run_id, tolerant=True)
            groups = grouping.get("groups") or []
            QMessageBox.information(
                self,
                "Groupes alignés",
                f"Groupes générés: {len(groups)} (run {run_id}).\n"
                "Aucune donnée source n'a été modifiée.",
            )
        except Exception as exc:
            logger.exception("Generate alignment groups")
            QMessageBox.critical(self, "Groupes alignés", f"Erreur génération groupes: {exc}")

    @require_project_and_db
    def _export_grouped_alignment(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        store = self._get_store()
        if not eid or not run_id:
            QMessageBox.warning(self, "Export groupes alignés", "Sélectionnez un épisode et un run.")
            return
        if not db or not store:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter groupes alignés",
            "",
            "CSV (*.csv);;TSV (*.tsv);;TXT (*.txt);;HTML (*.html);;JSONL (*.jsonl);;Word (*.docx)",
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != ".docx" and (selected_filter or "").strip().startswith("Word"):
            path = path.with_suffix(".docx")
        if path.suffix.lower() not in (".csv", ".tsv", ".txt", ".html", ".jsonl", ".docx"):
            path = path.with_suffix(".csv")
        try:
            grouping = store.load_align_grouping(eid, run_id)
            if not grouping:
                grouping = store.generate_align_grouping(db, eid, run_id, tolerant=True)
            rows = store.align_grouping_to_parallel_rows(grouping)
            if path.suffix.lower() == ".jsonl":
                export_parallel_concordance_jsonl(rows, path)
            elif path.suffix.lower() == ".tsv":
                export_parallel_concordance_tsv(rows, path)
            elif path.suffix.lower() == ".txt":
                export_parallel_concordance_txt(rows, path)
            elif path.suffix.lower() == ".html":
                export_parallel_concordance_html(rows, path, title=f"Groupes {eid} — {run_id}")
            elif path.suffix.lower() == ".docx":
                export_parallel_concordance_docx(rows, path)
            else:
                export_parallel_concordance_csv(rows, path)
            QMessageBox.information(self, "Export", f"Groupes alignés exportés : {len(rows)} groupe(s).")
        except Exception as exc:
            logger.exception("Export grouped alignment")
            QMessageBox.critical(self, "Export groupes alignés", f"Erreur export: {exc}")

    @require_project_and_db
    def _export_alignment(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not eid or not run_id:
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
            QMessageBox.critical(
                self,
                "Erreur export",
                f"Erreur lors de l'export : {e}\n\n"
                "Vérifiez les droits d'écriture, que le fichier n'est pas ouvert ailleurs et l'encodage (UTF-8)."
            )

    @require_project_and_db
    def _export_parallel_concordance(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not eid or not run_id:
            QMessageBox.warning(self, "Concordancier parallèle", "Sélectionnez un épisode et un run.")
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Exporter concordancier parallèle (comparaison de traductions)", "",
            "CSV (*.csv);;TSV (*.tsv);;TXT (*.txt);;HTML (*.html);;JSONL (*.jsonl);;Word (*.docx)"
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != ".docx" and (selected_filter or "").strip().startswith("Word"):
            path = path.with_suffix(".docx")
        if path.suffix.lower() not in (".csv", ".tsv", ".txt", ".html", ".jsonl", ".docx"):
            path = path.with_suffix(".csv")
        try:
            status_filter = "accepted" if self.align_accepted_only_cb.isChecked() else None
            rows = db.get_parallel_concordance(eid, run_id, status_filter=status_filter)
            if path.suffix.lower() == ".jsonl":
                export_parallel_concordance_jsonl(rows, path)
            elif path.suffix.lower() == ".tsv":
                export_parallel_concordance_tsv(rows, path)
            elif path.suffix.lower() == ".txt":
                export_parallel_concordance_txt(rows, path)
            elif path.suffix.lower() == ".html":
                export_parallel_concordance_html(rows, path, title=f"Comparaison {eid} — {run_id}")
            elif path.suffix.lower() == ".docx":
                export_parallel_concordance_docx(rows, path)
            else:
                export_parallel_concordance_csv(rows, path)
            QMessageBox.information(
                self, "Export", f"Concordancier parallèle exporté : {len(rows)} ligne(s)."
            )
        except Exception as e:
            logger.exception("Export concordancier parallèle")
            QMessageBox.critical(
                self,
                "Erreur export",
                f"Erreur lors de l'export : {e}\n\n"
                "Vérifiez les droits d'écriture et que le fichier n'est pas ouvert ailleurs."
            )

    @require_project_and_db
    def _export_align_report(self) -> None:
        eid = self.align_episode_combo.currentData()
        run_id = self.align_run_combo.currentData()
        db = self._get_db()
        if not eid or not run_id:
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
            QMessageBox.critical(
                self,
                "Erreur rapport",
                f"Erreur lors de la génération du rapport : {e}\n\n"
                "Vérifiez les droits d'écriture et que le fichier n'est pas ouvert ailleurs."
            )
