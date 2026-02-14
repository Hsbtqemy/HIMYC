"""Onglet Personnages : noms canoniques, par langue, assignation, propagation."""

from __future__ import annotations

import json
from typing import Callable

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.app.feedback import show_error, show_info, warn_precondition
from howimetyourcorpus.app.models_qt import CharacterNamesTableModel
from howimetyourcorpus.app.qt_helpers import refill_combo_preserve_selection

_RUN_SELECTIONS_BY_PROJECT_KEY = "personnages/runSelectionsByProject"


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
        self._selected_run_by_episode: dict[str, str] = {}
        self._current_project_key: str | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Liste des personnages du projet (noms canoniques et par langue). "
            "Utilisée pour l'assignation et la propagation des noms (backlog §8)."
        ))
        self.personnages_table = QTableView()
        self.personnages_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.personnages_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.personnages_table.setAlternatingRowColors(True)
        self._personnages_model = CharacterNamesTableModel(self.personnages_table)
        self.personnages_table.setModel(self._personnages_model)
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
        self.personnages_episode_combo.currentIndexChanged.connect(self._on_assignment_context_changed)
        assign_row.addWidget(self.personnages_episode_combo)
        assign_row.addWidget(QLabel("Source:"))
        self.personnages_source_combo = QComboBox()
        self.personnages_source_combo.addItem("Segments (phrases)", "segments")
        self.personnages_source_combo.addItem("Cues EN", "cues_en")
        self.personnages_source_combo.addItem("Cues FR", "cues_fr")
        self.personnages_source_combo.addItem("Cues IT", "cues_it")
        self.personnages_source_combo.currentIndexChanged.connect(self._on_assignment_context_changed)
        assign_row.addWidget(self.personnages_source_combo)
        self.personnages_load_assign_btn = QPushButton("Charger")
        self.personnages_load_assign_btn.setToolTip(
            "Charge les segments/cues de la source choisie pour l'épisode sélectionné."
        )
        self.personnages_load_assign_btn.clicked.connect(self._load_assignments)
        assign_row.addWidget(self.personnages_load_assign_btn)
        assign_row.addWidget(QLabel("Run alignement:"))
        self.personnages_run_combo = QComboBox()
        self.personnages_run_combo.setMinimumWidth(260)
        self.personnages_run_combo.setToolTip(
            "Run d'alignement utilisé pour la propagation des personnages (sélection explicite)."
        )
        self.personnages_run_combo.currentIndexChanged.connect(self._on_run_selection_changed)
        assign_row.addWidget(self.personnages_run_combo)
        self.personnages_refresh_runs_btn = QPushButton("Rafraîchir runs")
        self.personnages_refresh_runs_btn.setToolTip(
            "Recharge la liste des runs d'alignement pour l'épisode sélectionné."
        )
        self.personnages_refresh_runs_btn.clicked.connect(self._refresh_align_runs_for_current_episode)
        assign_row.addWidget(self.personnages_refresh_runs_btn)
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
        sel_model = self.personnages_table.selectionModel()
        if sel_model is not None:
            sel_model.selectionChanged.connect(self._apply_controls_enabled)
        self._apply_controls_enabled()

    def refresh(self) -> None:
        """Charge la liste des personnages et le combo épisodes (appelé après ouverture projet)."""
        current_episode = self.personnages_episode_combo.currentData()
        current_source = self.personnages_source_combo.currentData()
        self._personnages_model.set_characters([], [])
        self.personnages_assign_table.setRowCount(0)
        store = self._get_store()
        if not store:
            self._selected_run_by_episode.clear()
            self._current_project_key = None
            refill_combo_preserve_selection(
                self.personnages_episode_combo,
                items=[],
                current_data=None,
            )
            refill_combo_preserve_selection(
                self.personnages_source_combo,
                items=[],
                current_data=None,
            )
            refill_combo_preserve_selection(
                self.personnages_run_combo,
                items=[],
                current_data=None,
            )
            self._apply_controls_enabled()
            return
        self._load_run_selection_state_for_current_project()
        langs = store.load_project_languages()
        source_items = [("Segments", "segments")] + [
            (f"Cues {lang.upper()}", f"cues_{lang}") for lang in langs
        ]
        refill_combo_preserve_selection(
            self.personnages_source_combo,
            items=source_items,
            current_data=current_source,
        )
        characters = store.load_character_names()
        self._personnages_model.set_characters(characters, langs)
        index = store.load_series_index()
        episode_items: list[tuple[str, str]] = []
        if index and index.episodes:
            episode_items = [(f"{e.episode_id} - {e.title}", e.episode_id) for e in index.episodes]
        refill_combo_preserve_selection(
            self.personnages_episode_combo,
            items=episode_items,
            current_data=current_episode,
        )
        self._refresh_align_runs_for_current_episode()
        self._apply_controls_enabled()

    def _on_assignment_context_changed(self, *_args) -> None:
        """Changement d'épisode/source: invalide les lignes chargées pour éviter les sauvegardes hors contexte."""
        if self.personnages_assign_table.rowCount() > 0:
            self.personnages_assign_table.setRowCount(0)
        self._refresh_align_runs_for_current_episode()
        self._apply_controls_enabled()

    def _on_run_selection_changed(self, *_args) -> None:
        episode_id = self.personnages_episode_combo.currentData()
        run_id = self.personnages_run_combo.currentData()
        if episode_id and run_id:
            self._selected_run_by_episode[str(episode_id)] = str(run_id)
        elif episode_id:
            self._selected_run_by_episode.pop(str(episode_id), None)
        self._save_run_selection_state_for_current_project()
        self._apply_controls_enabled()

    def set_episode_and_run_context(self, episode_id: str | None, run_id: str | None) -> None:
        """Synchronise le contexte depuis Alignement (épisode + run actif)."""
        target_episode = str(episode_id or "").strip()
        target_run = str(run_id or "").strip()
        if not target_episode:
            return
        episode_index = self.personnages_episode_combo.findData(target_episode)
        if episode_index >= 0 and self.personnages_episode_combo.currentIndex() != episode_index:
            self.personnages_episode_combo.setCurrentIndex(episode_index)
        else:
            self._refresh_align_runs_for_current_episode()
        if not target_run:
            return
        run_index = self.personnages_run_combo.findData(target_run)
        if run_index >= 0 and self.personnages_run_combo.currentIndex() != run_index:
            self.personnages_run_combo.setCurrentIndex(run_index)

    @staticmethod
    def _format_run_label(run: dict) -> str:
        run_id = str(run.get("align_run_id") or "").strip()
        if not run_id:
            return ""
        created_at = str(run.get("created_at") or "").strip()
        created_label = created_at.replace("T", " ").replace("Z", " UTC") if created_at else ""
        langs_label = ""
        params_raw = run.get("params_json")
        if params_raw:
            try:
                params = json.loads(params_raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                params = {}
            target_langs = params.get("target_langs")
            if isinstance(target_langs, list):
                langs = sorted({str(lang).strip().lower() for lang in target_langs if str(lang).strip()})
                if langs:
                    langs_label = "/".join(lang.upper() for lang in langs)
        details: list[str] = []
        if created_label:
            details.append(created_label)
        if langs_label:
            details.append(f"Cible {langs_label}")
        if details:
            return f"{' | '.join(details)} | {run_id}"
        return run_id

    def _refresh_align_runs_for_current_episode(self) -> None:
        db = self._get_db()
        episode_id = self.personnages_episode_combo.currentData()
        if not db or not episode_id:
            refill_combo_preserve_selection(
                self.personnages_run_combo,
                items=[],
                current_data=None,
            )
            return
        episode_key = str(episode_id)
        current_run = self._selected_run_by_episode.get(episode_key) or self.personnages_run_combo.currentData()
        try:
            runs = db.get_align_runs_for_episode(episode_key)
        except Exception:
            runs = []
        items: list[tuple[str, str]] = []
        for run in runs:
            run_id = str(run.get("align_run_id") or "").strip()
            if not run_id:
                continue
            label = self._format_run_label(run)
            items.append((label, run_id))
        refill_combo_preserve_selection(
            self.personnages_run_combo,
            items=items,
            current_data=current_run,
        )

    @staticmethod
    def _decode_run_selections_payload(raw: object) -> dict[str, dict[str, str]]:
        """Decode QSettings -> mapping project_key -> {episode_id: run_id}."""
        payload = raw
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return {}
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return {}
        if not isinstance(payload, dict):
            return {}
        out: dict[str, dict[str, str]] = {}
        for project_key, episode_map in payload.items():
            pkey = str(project_key or "").strip()
            if not pkey or not isinstance(episode_map, dict):
                continue
            cleaned: dict[str, str] = {}
            for episode_id, run_id in episode_map.items():
                eid = str(episode_id or "").strip()
                rid = str(run_id or "").strip()
                if eid and rid:
                    cleaned[eid] = rid
            if cleaned:
                out[pkey] = cleaned
        return out

    @staticmethod
    def _encode_run_selections_payload(data: dict[str, dict[str, str]]) -> str:
        """Encode mapping project_key -> {episode_id: run_id} for QSettings."""
        payload: dict[str, dict[str, str]] = {}
        for project_key, episode_map in data.items():
            pkey = str(project_key or "").strip()
            if not pkey or not isinstance(episode_map, dict):
                continue
            cleaned: dict[str, str] = {}
            for episode_id, run_id in episode_map.items():
                eid = str(episode_id or "").strip()
                rid = str(run_id or "").strip()
                if eid and rid:
                    cleaned[eid] = rid
            if cleaned:
                payload[pkey] = cleaned
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _project_key_from_store(self) -> str | None:
        store = self._get_store()
        root_dir = getattr(store, "root_dir", None)
        if root_dir is None:
            return None
        try:
            return str(root_dir)
        except Exception:
            return None

    def _load_run_selection_state_for_current_project(self) -> None:
        project_key = self._project_key_from_store()
        self._current_project_key = project_key
        if not project_key:
            self._selected_run_by_episode = {}
            return
        settings = QSettings()
        raw = settings.value(_RUN_SELECTIONS_BY_PROJECT_KEY, "")
        all_projects = self._decode_run_selections_payload(raw)
        self._selected_run_by_episode = dict(all_projects.get(project_key, {}))

    def _save_run_selection_state_for_current_project(self) -> None:
        project_key = self._current_project_key or self._project_key_from_store()
        if not project_key:
            return
        settings = QSettings()
        raw = settings.value(_RUN_SELECTIONS_BY_PROJECT_KEY, "")
        all_projects = self._decode_run_selections_payload(raw)
        if self._selected_run_by_episode:
            all_projects[project_key] = dict(self._selected_run_by_episode)
        else:
            all_projects.pop(project_key, None)
        settings.setValue(
            _RUN_SELECTIONS_BY_PROJECT_KEY,
            self._encode_run_selections_payload(all_projects),
        )

    def _apply_controls_enabled(self, *_args) -> None:
        has_project = bool(self._get_store() and self._get_db())
        controls_enabled = has_project and not self._job_busy
        has_episode = bool(self.personnages_episode_combo.currentData())
        has_align_run = bool(self.personnages_run_combo.currentData())
        has_character_rows = self._personnages_model.rowCount() > 0
        has_character_selection = self._selected_character_row() >= 0
        has_assignment_rows = self.personnages_assign_table.rowCount() > 0
        self.personnages_table.setEnabled(controls_enabled)
        self.personnages_add_btn.setEnabled(controls_enabled)
        self.personnages_remove_btn.setEnabled(controls_enabled and has_character_selection)
        self.personnages_save_btn.setEnabled(controls_enabled and has_character_rows)
        self.personnages_import_speakers_btn.setEnabled(controls_enabled)
        self.personnages_episode_combo.setEnabled(controls_enabled)
        self.personnages_source_combo.setEnabled(controls_enabled and has_episode)
        self.personnages_load_assign_btn.setEnabled(controls_enabled and has_episode)
        self.personnages_run_combo.setEnabled(controls_enabled and has_episode)
        self.personnages_refresh_runs_btn.setEnabled(controls_enabled and has_episode)
        self.personnages_assign_table.setEnabled(controls_enabled and has_episode)
        self.personnages_save_assign_btn.setEnabled(controls_enabled and has_episode and has_assignment_rows)
        self.personnages_propagate_btn.setEnabled(controls_enabled and has_episode and has_align_run)
        if self._job_busy:
            hint = "Action indisponible pendant l'exécution d'un job."
            self.personnages_load_assign_btn.setToolTip(hint)
            self.personnages_save_assign_btn.setToolTip(hint)
            self.personnages_propagate_btn.setToolTip(hint)
            self.personnages_run_combo.setToolTip(hint)
            return
        if not has_project:
            hint = "Action indisponible: ouvrez un projet."
            self.personnages_load_assign_btn.setToolTip(hint)
            self.personnages_save_assign_btn.setToolTip(hint)
            self.personnages_propagate_btn.setToolTip(hint)
            self.personnages_run_combo.setToolTip(hint)
            return
        if not has_episode:
            hint = "Action indisponible: sélectionnez un épisode."
            self.personnages_load_assign_btn.setToolTip(hint)
            self.personnages_save_assign_btn.setToolTip(hint)
            self.personnages_propagate_btn.setToolTip(hint)
            self.personnages_run_combo.setToolTip(hint)
            return
        self.personnages_load_assign_btn.setToolTip(self._load_assign_tooltip_default)
        if has_align_run:
            self.personnages_run_combo.setToolTip(
                "Run d'alignement utilisé pour la propagation des personnages (sélection explicite)."
            )
        else:
            self.personnages_run_combo.setToolTip(
                "Aucun run d'alignement pour cet épisode. Lancez d'abord un alignement dans la partie supérieure."
            )
        if has_assignment_rows:
            self.personnages_save_assign_btn.setToolTip(self._save_assign_tooltip_default)
        else:
            self.personnages_save_assign_btn.setToolTip(
                "Action indisponible: chargez d'abord une source (segments/cues)."
            )
        if has_align_run:
            self.personnages_propagate_btn.setToolTip(self._propagate_tooltip_default)
        else:
            self.personnages_propagate_btn.setToolTip(
                "Action indisponible: aucun run d'alignement sélectionné pour cet épisode."
            )

    def set_job_busy(self, busy: bool) -> None:
        """Désactive les actions d'annotation pendant un job pipeline."""
        self._job_busy = busy
        self._apply_controls_enabled()

    def _add_row(self) -> None:
        row = self._personnages_model.add_empty_row()
        if row >= 0:
            self.personnages_table.selectRow(row)
            idx = self._personnages_model.index(row, 0)
            if idx.isValid():
                self.personnages_table.setCurrentIndex(idx)
        self._apply_controls_enabled()

    def _remove_row(self) -> None:
        row = self._selected_character_row()
        if row >= 0:
            self._personnages_model.remove_row(row)
        self._apply_controls_enabled()

    def _selected_character_row(self) -> int:
        sel_model = self.personnages_table.selectionModel()
        if sel_model is not None:
            selected_rows = sel_model.selectedRows()
            if selected_rows:
                return selected_rows[0].row()
        current = self.personnages_table.currentIndex()
        if current.isValid():
            return current.row()
        return -1

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
            warn_precondition(
                self,
                "Personnages",
                "Aucun nom de locuteur trouvé dans les segments. Segmentez d'abord les épisodes (Inspecteur).",
                next_step="Inspecteur: lancez « Segmente l'épisode » puis revenez importer les locuteurs.",
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
            show_info(
                self,
                "Personnages",
                "Tous les noms trouvés dans les segments sont déjà dans la grille.",
                status_callback=self._show_status,
            )

    def _save(self) -> None:
        resolved = self._resolve_store_db_or_warn()
        if resolved is None:
            return
        store, _db = resolved
        langs = self._personnages_model.get_languages()
        characters = []
        for row in self._personnages_model.get_rows_payload():
            cid = (row.get("id") or "").strip()
            canon = (row.get("canonical") or "").strip()
            if not cid and not canon:
                continue
            names_by_lang = {}
            row_names = row.get("names_by_lang") or {}
            for lang in langs:
                value = str(row_names.get(lang) or "").strip()
                if value:
                    names_by_lang[lang] = value
            characters.append({
                "id": cid or canon.lower().replace(" ", "_"),
                "canonical": canon or cid,
                "names_by_lang": names_by_lang,
            })
        try:
            store.save_character_names(characters)
        except Exception as e:
            show_error(self, title="Personnages", exc=e, context="Enregistrement personnages")
            return
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
        try:
            store.save_character_assignments(all_assignments)
        except Exception as e:
            show_error(self, title="Assignation", exc=e, context="Enregistrement assignations personnages")
            return
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
        run_id = self.personnages_run_combo.currentData()
        if not run_id:
            warn_precondition(
                self,
                "Propagation",
                "Sélectionnez explicitement un run d'alignement.",
                next_step="Choisissez un run dans le sélecteur « Run alignement ».",
            )
            return
        run_id = str(run_id)
        try:
            runs = db.get_align_runs_for_episode(eid)
        except Exception as e:
            show_error(self, title="Propagation", exc=e, context="Chargement runs d'alignement")
            return
        available_run_ids = {str(run.get("align_run_id") or "") for run in runs}
        if run_id not in available_run_ids:
            self._refresh_align_runs_for_current_episode()
            warn_precondition(
                self,
                "Propagation",
                "Le run sélectionné n'existe plus pour cet épisode.",
                next_step="Sélectionnez un run valide puis relancez la propagation.",
            )
            return
        try:
            nb_seg, nb_cue = store.propagate_character_names(db, eid, run_id)
            self._show_status(
                f"Propagation ({run_id}) : {nb_seg} segment(s), {nb_cue} cue(s) mis à jour ; fichiers SRT réécrits.",
                6000,
            )
        except Exception as e:
            show_error(self, title="Propagation", exc=e, context="Erreur lors de la propagation")
