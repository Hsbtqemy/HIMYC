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

from howimetyourcorpus.app.feedback import show_error, warn_precondition


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
        self._job_busy = False

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
        self.personnages_episode_combo.currentIndexChanged.connect(self._apply_controls_enabled)
        assign_row.addWidget(self.personnages_episode_combo)
        assign_row.addWidget(QLabel("Source:"))
        self.personnages_source_combo = QComboBox()
        self.personnages_source_combo.addItem("Segments (phrases)", "segments")
        self.personnages_source_combo.addItem("Cues EN", "cues_en")
        self.personnages_source_combo.addItem("Cues FR", "cues_fr")
        self.personnages_source_combo.addItem("Cues IT", "cues_it")
        self.personnages_source_combo.currentIndexChanged.connect(self._apply_controls_enabled)
        assign_row.addWidget(self.personnages_source_combo)
        self.personnages_load_assign_btn = QPushButton("Charger")
        self.personnages_load_assign_btn.setToolTip(
            "Charge les segments/cues de la source choisie pour l'épisode sélectionné."
        )
        self.personnages_load_assign_btn.clicked.connect(self._load_assignments)
        assign_row.addWidget(self.personnages_load_assign_btn)
        layout.addLayout(assign_row)
        self.personnages_assign_table = QTableWidget()
        self.personnages_assign_table.setColumnCount(3)
        self.personnages_assign_table.setHorizontalHeaderLabels(["ID", "Texte", "Personnage"])
        self.personnages_assign_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.personnages_assign_table.itemSelectionChanged.connect(self._apply_controls_enabled)
        layout.addWidget(self.personnages_assign_table)
        self.personnages_save_assign_btn = QPushButton("Enregistrer assignations")
        self.personnages_save_assign_btn.setToolTip(
            "Enregistre les correspondances source -> personnage pour cet épisode."
        )
        self.personnages_save_assign_btn.clicked.connect(self._save_assignments)
        layout.addWidget(self.personnages_save_assign_btn)
        self.personnages_propagate_btn = QPushButton("Propager vers les autres fichiers")
        self.personnages_propagate_btn.setToolTip(
            "Utilise les liens d'alignement pour propager les noms de personnages vers les positions alignées (fichiers cibles)."
        )
        self.personnages_propagate_btn.clicked.connect(self._propagate)
        layout.addWidget(self.personnages_propagate_btn)
        self._load_assign_tooltip_default = self.personnages_load_assign_btn.toolTip()
        self._save_assign_tooltip_default = self.personnages_save_assign_btn.toolTip()
        self._propagate_tooltip_default = self.personnages_propagate_btn.toolTip()
        self.personnages_table.itemSelectionChanged.connect(self._apply_controls_enabled)
        self._apply_controls_enabled()

    def refresh(self) -> None:
        """Charge la liste des personnages et le combo épisodes (appelé après ouverture projet)."""
        self.personnages_table.setRowCount(0)
        self.personnages_episode_combo.clear()
        store = self._get_store()
        if not store:
            self._apply_controls_enabled()
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
        self._apply_controls_enabled()

    def _apply_controls_enabled(self, *_args) -> None:
        has_project = bool(self._get_store() and self._get_db())
        controls_enabled = has_project and not self._job_busy
        has_episode = bool(self.personnages_episode_combo.currentData())
        has_character_rows = self.personnages_table.rowCount() > 0
        has_character_selection = self.personnages_table.currentRow() >= 0
        has_assignment_rows = self.personnages_assign_table.rowCount() > 0
        self.personnages_table.setEnabled(controls_enabled)
        self.personnages_add_btn.setEnabled(controls_enabled)
        self.personnages_remove_btn.setEnabled(controls_enabled and has_character_selection)
        self.personnages_save_btn.setEnabled(controls_enabled and has_character_rows)
        self.personnages_import_speakers_btn.setEnabled(controls_enabled)
        self.personnages_episode_combo.setEnabled(controls_enabled)
        self.personnages_source_combo.setEnabled(controls_enabled and has_episode)
        self.personnages_load_assign_btn.setEnabled(controls_enabled and has_episode)
        self.personnages_assign_table.setEnabled(controls_enabled and has_episode)
        self.personnages_save_assign_btn.setEnabled(controls_enabled and has_episode and has_assignment_rows)
        self.personnages_propagate_btn.setEnabled(controls_enabled and has_episode)
        if self._job_busy:
            hint = "Action indisponible pendant l'exécution d'un job."
            self.personnages_load_assign_btn.setToolTip(hint)
            self.personnages_save_assign_btn.setToolTip(hint)
            self.personnages_propagate_btn.setToolTip(hint)
            return
        if not has_project:
            hint = "Action indisponible: ouvrez un projet."
            self.personnages_load_assign_btn.setToolTip(hint)
            self.personnages_save_assign_btn.setToolTip(hint)
            self.personnages_propagate_btn.setToolTip(hint)
            return
        if not has_episode:
            hint = "Action indisponible: sélectionnez un épisode."
            self.personnages_load_assign_btn.setToolTip(hint)
            self.personnages_save_assign_btn.setToolTip(hint)
            self.personnages_propagate_btn.setToolTip(hint)
            return
        self.personnages_load_assign_btn.setToolTip(self._load_assign_tooltip_default)
        if has_assignment_rows:
            self.personnages_save_assign_btn.setToolTip(self._save_assign_tooltip_default)
        else:
            self.personnages_save_assign_btn.setToolTip(
                "Action indisponible: chargez d'abord une source (segments/cues)."
            )
        self.personnages_propagate_btn.setToolTip(self._propagate_tooltip_default)

    def set_job_busy(self, busy: bool) -> None:
        """Désactive les actions d'annotation pendant un job pipeline."""
        self._job_busy = busy
        self._apply_controls_enabled()

    def _add_row(self) -> None:
        row = self.personnages_table.rowCount()
        self.personnages_table.insertRow(row)
        for c in range(self.personnages_table.columnCount()):
            self.personnages_table.setItem(row, c, QTableWidgetItem(""))
        self._apply_controls_enabled()

    def _remove_row(self) -> None:
        row = self.personnages_table.currentRow()
        if row >= 0:
            self.personnages_table.removeRow(row)
        self._apply_controls_enabled()

    def _resolve_store_db_or_warn(
        self,
        *,
        title: str = "Personnages",
        message: str = "Ouvrez un projet d'abord.",
        next_step: str = "Pilotage > Projet: ouvrez ou initialisez un projet.",
    ) -> tuple[object, object] | None:
        store = self._get_store()
        db = self._get_db()
        if not store or not db:
            warn_precondition(self, title, message, next_step=next_step)
            return None
        return store, db

    def _resolve_episode_store_db_or_warn(
        self,
        *,
        title: str = "Personnages",
        message: str = "Ouvrez un projet et sélectionnez un épisode.",
        next_step: str = "Choisissez un épisode dans la section Assignation.",
    ) -> tuple[str, object, object] | None:
        resolved = self._resolve_store_db_or_warn(title=title, message=message, next_step=next_step)
        if resolved is None:
            return None
        store, db = resolved
        eid = self.personnages_episode_combo.currentData()
        if not eid:
            warn_precondition(self, title, "Sélectionnez un épisode.", next_step=next_step)
            return None
        return str(eid), store, db

    def _import_speakers_from_segments(self) -> None:
        """Récupère les noms de locuteurs des segments (Inspecteur) et les ajoute à la grille des personnages."""
        resolved = self._resolve_store_db_or_warn()
        if resolved is None:
            return
        store, db = resolved
        index = store.load_series_index()
        if not index or not index.episodes:
            warn_precondition(
                self,
                "Personnages",
                "Aucun épisode dans l'index. Ajoutez des épisodes au corpus.",
                next_step="Pilotage > Corpus: cliquez sur « Découvrir épisodes ».",
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

    def _save(self) -> None:
        resolved = self._resolve_store_db_or_warn()
        if resolved is None:
            return
        store, _db = resolved
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
        self._apply_controls_enabled()

    def _load_assignments(self) -> None:
        resolved = self._resolve_episode_store_db_or_warn()
        if resolved is None:
            return
        eid, store, db = resolved
        source_key = self.personnages_source_combo.currentData() or "segments"
        character_ids = [
            ch.get("id") or ch.get("canonical", "")
            for ch in store.load_character_names()
            if ch.get("id") or ch.get("canonical")
        ]
        if not character_ids:
            warn_precondition(
                self,
                "Assignation",
                "Aucun personnage défini dans le projet.",
                next_step="Ajoutez des personnages dans la grille puis cliquez sur « Enregistrer ».",
            )
            return
        assignments = store.load_character_assignments()
        source_type = "segment" if source_key == "segments" else "cue"
        assign_map = {
            a["source_id"]: a.get("character_id") or ""
            for a in assignments
            if a.get("episode_id") == eid and a.get("source_type") == source_type
        }
        self.personnages_assign_table.setRowCount(0)
        try:
            if source_key == "segments":
                segments = db.get_segments_for_episode(eid, kind="sentence")
                for s in segments:
                    sid = s.get("segment_id") or ""
                    text = (s.get("text") or "")[:80]
                    if len((s.get("text") or "")) > 80:
                        text += "…"
                    self._insert_assignment_row(
                        source_id=sid,
                        text=text,
                        character_ids=character_ids,
                        assigned_character_id=assign_map.get(sid, ""),
                    )
            else:
                lang = source_key.replace("cues_", "")
                cues = db.get_cues_for_episode_lang(eid, lang)
                for c in cues:
                    cid = c.get("cue_id") or ""
                    text = (c.get("text_clean") or c.get("text_raw") or "")[:80]
                    if len((c.get("text_clean") or c.get("text_raw") or "")) > 80:
                        text += "…"
                    self._insert_assignment_row(
                        source_id=cid,
                        text=text,
                        character_ids=character_ids,
                        assigned_character_id=assign_map.get(cid, ""),
                    )
        except Exception as e:
            show_error(self, title="Assignation", exc=e, context="Chargement assignations personnages")
            return
        if self.personnages_assign_table.rowCount() == 0:
            if source_key == "segments":
                warn_precondition(
                    self,
                    "Assignation",
                    "Aucun segment disponible pour cet épisode.",
                    next_step="Inspecteur: segmentez l'épisode puis cliquez sur « Charger ».",
                )
            else:
                lang = source_key.replace("cues_", "").upper()
                warn_precondition(
                    self,
                    "Assignation",
                    f"Aucune cue {lang} disponible pour cet épisode.",
                    next_step=f"Inspecteur > Sous-titres: importez une piste {lang} puis cliquez sur « Charger ».",
                )
        self._apply_controls_enabled()

    def _save_assignments(self) -> None:
        resolved = self._resolve_episode_store_db_or_warn()
        if resolved is None:
            return
        eid, store, _db = resolved
        source_key = self.personnages_source_combo.currentData() or "segments"
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
            self._apply_controls_enabled()

    def _insert_assignment_row(
        self,
        *,
        source_id: str,
        text: str,
        character_ids: list[str],
        assigned_character_id: str,
    ) -> None:
        row = self.personnages_assign_table.rowCount()
        self.personnages_assign_table.insertRow(row)
        self.personnages_assign_table.setItem(row, 0, QTableWidgetItem(source_id))
        self.personnages_assign_table.setItem(row, 1, QTableWidgetItem(text))
        combo = QComboBox()
        combo.addItem("—", "")
        for char_id in character_ids:
            combo.addItem(char_id, char_id)
        idx = combo.findData(assigned_character_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self.personnages_assign_table.setCellWidget(row, 2, combo)

    def _propagate(self) -> None:
        resolved = self._resolve_episode_store_db_or_warn(
            message="Ouvrez un projet et sélectionnez un épisode (section Assignation).",
            next_step="Choisissez un épisode dans la section Assignation.",
        )
        if resolved is None:
            return
        eid, store, db = resolved
        assignments = store.load_character_assignments()
        episode_assignments = [a for a in assignments if a.get("episode_id") == eid]
        if not episode_assignments:
            warn_precondition(
                self,
                "Propagation",
                "Aucune assignation pour cet épisode.",
                next_step="Chargez une source, assignez des personnages puis cliquez sur « Enregistrer assignations ».",
            )
            return
        try:
            runs = db.get_align_runs_for_episode(eid)
        except Exception as e:
            show_error(self, title="Propagation", exc=e, context="Chargement runs d'alignement")
            return
        if not runs:
            warn_precondition(
                self,
                "Propagation",
                "Aucun run d'alignement pour cet épisode.",
                next_step="Validation & Annotation > Alignement: lancez un alignement pour cet épisode.",
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
            show_error(self, title="Propagation", exc=e, context="Erreur lors de la propagation")
