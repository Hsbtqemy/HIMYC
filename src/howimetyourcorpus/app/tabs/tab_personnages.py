"""Onglet Personnages : noms canoniques, par langue, assignation, propagation."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.app.ui_utils import require_project, require_project_and_db


class PersonnagesTabWidget(QWidget):
    """Widget de l'onglet Personnages : liste personnages, assignation segment/cue → personnage, propagation."""

    def __init__(
        self,
        get_store: Callable[[], object],
        get_db: Callable[[], object],
        show_status: Callable[[str, int], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._show_status = show_status

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Liste des personnages du projet (noms canoniques et par langue). "
            "Utilisée pour l'assignation et la propagation des noms (backlog §8)."
        ))
        self.personnages_table = QTableWidget()
        self.personnages_table.setColumnCount(4)
        self.personnages_table.setHorizontalHeaderLabels(["Id", "Canonique", "EN", "FR"])
        self.personnages_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.personnages_table)
        btn_row = QHBoxLayout()
        self.personnages_add_btn = QPushButton("Nouveau")
        self.personnages_add_btn.clicked.connect(self._add_row)
        self.personnages_remove_btn = QPushButton("Supprimer")
        self.personnages_remove_btn.clicked.connect(self._remove_row)
        self.personnages_save_btn = QPushButton("Enregistrer")
        self.personnages_save_btn.clicked.connect(self._save)
        self.personnages_import_speakers_btn = QPushButton("Importer depuis les segments")
        self.personnages_import_speakers_btn.setToolTip(
            "Récupère les noms de locuteurs (Marshall, Ted, etc.) détectés dans les segments de tous les épisodes et les ajoute à la grille s'ils n'y sont pas déjà."
        )
        self.personnages_import_speakers_btn.clicked.connect(self._import_speakers_from_segments)
        btn_row.addWidget(self.personnages_add_btn)
        btn_row.addWidget(self.personnages_remove_btn)
        btn_row.addWidget(self.personnages_save_btn)
        btn_row.addWidget(self.personnages_import_speakers_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addWidget(QLabel("Assignation (segment ou cue → personnage) :"))
        assign_row = QHBoxLayout()
        assign_row.addWidget(QLabel("Épisode:"))
        self.personnages_episode_combo = QComboBox()
        self.personnages_episode_combo.setMinimumWidth(200)
        assign_row.addWidget(self.personnages_episode_combo)
        assign_row.addWidget(QLabel("Source:"))
        self.personnages_source_combo = QComboBox()
        self.personnages_source_combo.addItem("Segments (phrases)", "segments")
        self.personnages_source_combo.addItem("Cues EN", "cues_en")
        self.personnages_source_combo.addItem("Cues FR", "cues_fr")
        self.personnages_source_combo.addItem("Cues IT", "cues_it")
        assign_row.addWidget(self.personnages_source_combo)
        self.personnages_load_assign_btn = QPushButton("Charger")
        self.personnages_load_assign_btn.clicked.connect(self._load_assignments)
        assign_row.addWidget(self.personnages_load_assign_btn)
        layout.addLayout(assign_row)
        self.personnages_assign_table = QTableWidget()
        self.personnages_assign_table.setColumnCount(3)
        self.personnages_assign_table.setHorizontalHeaderLabels(["ID", "Texte", "Personnage"])
        self.personnages_assign_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.personnages_assign_table)
        self.personnages_save_assign_btn = QPushButton("Enregistrer assignations")
        self.personnages_save_assign_btn.clicked.connect(self._save_assignments)
        layout.addWidget(self.personnages_save_assign_btn)
        self.personnages_propagate_btn = QPushButton("Propager vers les autres fichiers")
        self.personnages_propagate_btn.setToolTip(
            "Utilise les liens d'alignement pour propager les noms de personnages vers les positions alignées (fichiers cibles)."
        )
        self.personnages_propagate_btn.clicked.connect(self._propagate)
        layout.addWidget(self.personnages_propagate_btn)

    def refresh(self) -> None:
        """Charge la liste des personnages et le combo épisodes (appelé après ouverture projet)."""
        self.personnages_table.setRowCount(0)
        self.personnages_episode_combo.clear()
        store = self._get_store()
        if not store:
            return
        langs = store.load_project_languages()
        self.personnages_table.setColumnCount(2 + len(langs))
        self.personnages_table.setHorizontalHeaderLabels(
            ["Id", "Canonique"] + [lang.upper() for lang in langs]
        )
        self.personnages_source_combo.clear()
        self.personnages_source_combo.addItem("Segments", "segments")
        for lang in langs:
            self.personnages_source_combo.addItem(f"Cues {lang.upper()}", f"cues_{lang}")
        characters = store.load_character_names()
        for ch in characters:
            row = self.personnages_table.rowCount()
            self.personnages_table.insertRow(row)
            names = ch.get("names_by_lang") or {}
            self.personnages_table.setItem(row, 0, QTableWidgetItem(ch.get("id") or ""))
            self.personnages_table.setItem(row, 1, QTableWidgetItem(ch.get("canonical") or ""))
            for i, lang in enumerate(langs):
                self.personnages_table.setItem(
                    row, 2 + i, QTableWidgetItem(names.get(lang, ""))
                )
        index = store.load_series_index()
        if index and index.episodes:
            for e in index.episodes:
                self.personnages_episode_combo.addItem(
                    f"{e.episode_id} - {e.title}", e.episode_id
                )

    def _add_row(self) -> None:
        row = self.personnages_table.rowCount()
        self.personnages_table.insertRow(row)
        for c in range(self.personnages_table.columnCount()):
            self.personnages_table.setItem(row, c, QTableWidgetItem(""))

    def _remove_row(self) -> None:
        row = self.personnages_table.currentRow()
        if row >= 0:
            self.personnages_table.removeRow(row)

    @require_project_and_db
    def _import_speakers_from_segments(self) -> None:
        """Récupère les noms de locuteurs des segments (Inspecteur) et les ajoute à la grille des personnages."""
        store = self._get_store()
        db = self._get_db()
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(
                self, "Personnages", "Aucun épisode dans l'index. Ajoutez des épisodes au corpus."
            )
            return
        episode_ids = [e.episode_id for e in index.episodes]
        speakers = db.get_distinct_speaker_explicit(episode_ids)
        if not speakers:
            QMessageBox.information(
                self,
                "Personnages",
                "Aucun nom de locuteur trouvé dans les segments. Segmentez d'abord les épisodes (Inspecteur).",
            )
            return
        characters = list(store.load_character_names())
        langs = store.load_project_languages()
        first_lang = (langs[0] if langs else "en").lower()
        existing_canonical_lower = {(ch.get("canonical") or "").strip().lower() for ch in characters}
        existing_id_lower = {(ch.get("id") or "").strip().lower() for ch in characters}
        added = 0
        for name in speakers:
            n = (name or "").strip()
            if not n:
                continue
            norm_id = n.lower().replace(" ", "_")
            if n.lower() in existing_canonical_lower or norm_id in existing_id_lower:
                continue
            characters.append({
                "id": norm_id,
                "canonical": n,
                "names_by_lang": {first_lang: n},
            })
            existing_canonical_lower.add(n.lower())
            existing_id_lower.add(norm_id)
            added += 1
        if added:
            store.save_character_names(characters)
            self.refresh()
            self._show_status(f"{added} nom(s) importé(s) depuis les segments.", 4000)
        else:
            QMessageBox.information(
                self, "Personnages", "Tous les noms trouvés dans les segments sont déjà dans la grille."
            )

    @require_project
    def _save(self) -> None:
        store = self._get_store()
        langs = store.load_project_languages()
        characters = []
        for row in range(self.personnages_table.rowCount()):
            id_item = self.personnages_table.item(row, 0)
            canon_item = self.personnages_table.item(row, 1)
            cid = (id_item.text() or "").strip() if id_item else ""
            canon = (canon_item.text() or "").strip() if canon_item else ""
            if not cid and not canon:
                continue
            names_by_lang = {}
            for i, lang in enumerate(langs):
                if 2 + i < self.personnages_table.columnCount():
                    item = self.personnages_table.item(row, 2 + i)
                    if item and (item.text() or "").strip():
                        names_by_lang[lang] = (item.text() or "").strip()
            characters.append({
                "id": cid or canon.lower().replace(" ", "_"),
                "canonical": canon or cid,
                "names_by_lang": names_by_lang,
            })
        store.save_character_names(characters)
        self._show_status("Personnages enregistrés.", 3000)

    @require_project_and_db
    def _load_assignments(self) -> None:
        eid = self.personnages_episode_combo.currentData()
        source_key = self.personnages_source_combo.currentData() or "segments"
        store = self._get_store()
        db = self._get_db()
        if not eid:
            QMessageBox.warning(self, "Personnages", "Ouvrez un projet et sélectionnez un épisode.")
            return
        character_ids = [
            ch.get("id") or ch.get("canonical", "")
            for ch in store.load_character_names()
            if ch.get("id") or ch.get("canonical")
        ]
        assignments = store.load_character_assignments()
        source_type = "segment" if source_key == "segments" else "cue"
        assign_map = {
            a["source_id"]: a.get("character_id") or ""
            for a in assignments
            if a.get("episode_id") == eid and a.get("source_type") == source_type
        }
        self.personnages_assign_table.setRowCount(0)
        if source_key == "segments":
            segments = db.get_segments_for_episode(eid, kind="sentence")
            for s in segments:
                sid = s.get("segment_id") or ""
                text = (s.get("text") or "")[:80]
                if len((s.get("text") or "")) > 80:
                    text += "…"
                row = self.personnages_assign_table.rowCount()
                self.personnages_assign_table.insertRow(row)
                self.personnages_assign_table.setItem(row, 0, QTableWidgetItem(sid))
                self.personnages_assign_table.setItem(row, 1, QTableWidgetItem(text))
                combo = QComboBox()
                combo.addItem("—", "")
                for cid in character_ids:
                    combo.addItem(cid, cid)
                idx = combo.findData(assign_map.get(sid, ""))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                self.personnages_assign_table.setCellWidget(row, 2, combo)
        else:
            lang = source_key.replace("cues_", "")
            cues = db.get_cues_for_episode_lang(eid, lang)
            for c in cues:
                cid = c.get("cue_id") or ""
                text = (c.get("text_clean") or c.get("text_raw") or "")[:80]
                if len((c.get("text_clean") or c.get("text_raw") or "")) > 80:
                    text += "…"
                row = self.personnages_assign_table.rowCount()
                self.personnages_assign_table.insertRow(row)
                self.personnages_assign_table.setItem(row, 0, QTableWidgetItem(cid))
                self.personnages_assign_table.setItem(row, 1, QTableWidgetItem(text))
                combo = QComboBox()
                combo.addItem("—", "")
                for char_id in character_ids:
                    combo.addItem(char_id, char_id)
                idx = combo.findData(assign_map.get(cid, ""))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                self.personnages_assign_table.setCellWidget(row, 2, combo)

    @require_project
    def _save_assignments(self) -> None:
        eid = self.personnages_episode_combo.currentData()
        source_key = self.personnages_source_combo.currentData() or "segments"
        store = self._get_store()
        if not eid:
            QMessageBox.warning(self, "Personnages", "Ouvrez un projet et sélectionnez un épisode.")
            return
        source_type = "segment" if source_key == "segments" else "cue"
        new_assignments = []
        for row in range(self.personnages_assign_table.rowCount()):
            id_item = self.personnages_assign_table.item(row, 0)
            source_id = (id_item.text() or "").strip() if id_item else ""
            combo = self.personnages_assign_table.cellWidget(row, 2)
            if not isinstance(combo, QComboBox):
                continue
            character_id = (combo.currentData() or combo.currentText() or "").strip()
            if source_id and character_id:
                new_assignments.append({
                    "episode_id": eid,
                    "source_type": source_type,
                    "source_id": source_id,
                    "character_id": character_id,
                })
        all_assignments = store.load_character_assignments()
        all_assignments = [
            a
            for a in all_assignments
            if not (a.get("episode_id") == eid and a.get("source_type") == source_type)
        ]
        all_assignments.extend(new_assignments)
        store.save_character_assignments(all_assignments)
        self._show_status(f"Assignations enregistrées : {len(new_assignments)}.", 3000)

    @require_project_and_db
    def _propagate(self) -> None:
        store = self._get_store()
        db = self._get_db()
        eid = self.personnages_episode_combo.currentData()
        if not eid:
            QMessageBox.warning(self, "Personnages", "Sélectionnez un épisode (section Assignation).")
            return
        assignments = store.load_character_assignments()
        episode_assignments = [a for a in assignments if a.get("episode_id") == eid]
        if not episode_assignments:
            QMessageBox.information(
                self, "Propagation", "Aucune assignation pour cet épisode. Enregistrez des assignations d'abord."
            )
            return
        runs = db.get_align_runs_for_episode(eid)
        if not runs:
            QMessageBox.information(
                self,
                "Propagation",
                "Aucun run d'alignement pour cet épisode. Lancez l'alignement (onglet Alignement) d'abord.",
            )
            return
        run_id = runs[0].get("align_run_id")
        try:
            nb_seg, nb_cue = store.propagate_character_names(db, eid, run_id)
            self._show_status(
                f"Propagation : {nb_seg} segment(s), {nb_cue} cue(s) mis à jour ; fichiers SRT réécrits.",
                6000,
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Propagation",
                f"Erreur lors de la propagation : {e!s}",
            )
