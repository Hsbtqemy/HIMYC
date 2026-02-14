"""Onglet Inspecteur : RAW/CLEAN, segments, normalisation, export segments, notes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from howimetyourcorpus.core.normalize.profiles import (
    PROFILES,
    get_all_profile_ids,
    resolve_lang_hint_from_profile_id,
)
from howimetyourcorpus.core.export_utils import (
    export_segments_txt,
    export_segments_csv,
    export_segments_tsv,
    export_segments_docx,
)
from howimetyourcorpus.app.feedback import show_error, show_info, warn_precondition
from howimetyourcorpus.app.export_dialog import (
    build_export_success_message,
    normalize_export_path,
    resolve_export_key,
)
from howimetyourcorpus.app.qt_helpers import refill_combo_preserve_selection
from howimetyourcorpus.core.workflow import (
    WorkflowActionId,
    WorkflowScope,
    WorkflowService,
)
from howimetyourcorpus.app.workflow_ui import build_workflow_steps_or_warn

logger = logging.getLogger(__name__)

_INSPECTOR_FORCE_REPROCESS_KEY = "inspecteur/forceReprocess"


class InspectorTabWidget(QWidget):
    """Widget de l'onglet Inspecteur : épisode, RAW/CLEAN, segments, normaliser, segmenter, export, notes."""

    def __init__(
        self,
        get_store: Callable[[], object],
        get_db: Callable[[], object],
        get_config: Callable[[], object],
        run_job: Callable[..., None],
        show_status: Callable[[str, int], None],
        on_open_pilotage: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_store = get_store
        self._get_db = get_db
        self._get_config = get_config
        self._run_job = run_job
        self._show_status = show_status
        self._on_open_pilotage = on_open_pilotage
        self._current_episode_id: str | None = None
        self._workflow_service = WorkflowService()
        self._job_busy = False

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self._inspect_episode_label = QLabel("Épisode:")
        row.addWidget(self._inspect_episode_label)
        self.inspect_episode_combo = QComboBox()
        self.inspect_episode_combo.currentIndexChanged.connect(self._load_episode)
        row.addWidget(self.inspect_episode_combo)
        row.addWidget(QLabel("Vue:"))
        self.inspect_view_combo = QComboBox()
        self.inspect_view_combo.addItem("Épisode", "episode")
        self.inspect_view_combo.addItem("Segments", "segments")
        self.inspect_view_combo.currentIndexChanged.connect(self._switch_view)
        row.addWidget(self.inspect_view_combo)
        row.addWidget(QLabel("Profil:"))
        self.inspect_profile_combo = QComboBox()
        self.inspect_profile_combo.addItems(list(PROFILES.keys()))
        self.inspect_profile_combo.setToolTip(
            "Profil pour « Normaliser cet épisode ». Priorité : préféré épisode > défaut source (Profils) > config projet."
        )
        row.addWidget(self.inspect_profile_combo)
        self.inspect_norm_btn = QPushButton("Normaliser cet épisode")
        self.inspect_norm_btn.setToolTip(
            "Applique la normalisation (RAW → CLEAN) à l'épisode affiché, avec le profil choisi."
        )
        self.inspect_norm_btn.clicked.connect(self._run_normalize)
        row.addWidget(self.inspect_norm_btn)
        self.inspect_set_preferred_profile_btn = QPushButton("Définir comme préféré pour cet épisode")
        self.inspect_set_preferred_profile_btn.setToolTip(
            "Mémorise ce profil pour cet épisode. Utilisé en priorité lors du batch (Corpus) et ici."
        )
        self.inspect_set_preferred_profile_btn.clicked.connect(self._set_episode_preferred_profile)
        row.addWidget(self.inspect_set_preferred_profile_btn)
        self.inspect_segment_btn = QPushButton("Segmente l'épisode")
        self.inspect_segment_btn.setToolTip(
            "Découpe le fichier CLEAN de l'épisode en segments (phrases/tours) pour QA et alignement."
        )
        self.inspect_segment_btn.clicked.connect(self._run_segment)
        row.addWidget(self.inspect_segment_btn)
        self.inspect_export_segments_btn = QPushButton("Exporter les segments")
        self.inspect_export_segments_btn.setToolTip(
            "Exporte les segments de l'épisode courant (TXT/CSV/TSV/Word)."
        )
        self.inspect_export_segments_btn.clicked.connect(self._export_segments)
        row.addWidget(self.inspect_export_segments_btn)
        self.inspect_force_reprocess_check = QCheckBox("Forcer re-traitement")
        self.inspect_force_reprocess_check.setToolTip(
            "Ignore les skips idempotents pour cet épisode (normalisation/segmentation) même si les artefacts existent."
        )
        self.inspect_force_reprocess_check.toggled.connect(self._save_force_reprocess_state)
        row.addWidget(self.inspect_force_reprocess_check)
        self._inspect_norm_tooltip_default = self.inspect_norm_btn.toolTip()
        self._inspect_segment_tooltip_default = self.inspect_segment_btn.toolTip()
        self._inspect_export_segments_tooltip_default = self.inspect_export_segments_btn.toolTip()
        layout.addLayout(row)
        workflow_hint_row = QHBoxLayout()
        inspect_scope_hint = QLabel("Mode Inspecteur: actions locales sur l'épisode courant.")
        inspect_scope_hint.setStyleSheet("color: #505050;")
        workflow_hint_row.addWidget(inspect_scope_hint)
        self.inspect_open_pilotage_btn = QPushButton("Aller au Pilotage (batch)")
        self.inspect_open_pilotage_btn.setToolTip(
            "Ouvre l'onglet Pilotage pour les opérations en lot (sélection, saison, tout le corpus)."
        )
        self.inspect_open_pilotage_btn.setEnabled(self._on_open_pilotage is not None)
        self.inspect_open_pilotage_btn.clicked.connect(self._open_pilotage_batch)
        workflow_hint_row.addWidget(self.inspect_open_pilotage_btn)
        workflow_hint_row.addStretch()
        layout.addLayout(workflow_hint_row)

        self.inspect_main_split = QSplitter(Qt.Orientation.Horizontal)
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setPlaceholderText("RAW")
        self.clean_edit = QPlainTextEdit()
        self.clean_edit.setPlaceholderText("CLEAN")
        self.inspect_segments_list = QListWidget()
        self.inspect_segments_list.setMinimumWidth(80)
        self.inspect_segments_list.currentItemChanged.connect(self._on_segment_selected)
        self.inspect_main_split.addWidget(self.inspect_segments_list)
        self.inspect_right_split = QSplitter(Qt.Orientation.Vertical)
        self.inspect_right_split.addWidget(self.raw_edit)
        self.inspect_right_split.addWidget(self.clean_edit)
        self.inspect_main_split.addWidget(self.inspect_right_split)
        layout.addWidget(self.inspect_main_split)
        self._restore_splitter_sizes()

        self.inspect_stats_label = QLabel("Stats: —")
        layout.addWidget(self.inspect_stats_label)
        self.merge_examples_edit = QPlainTextEdit()
        self.merge_examples_edit.setReadOnly(True)
        self.merge_examples_edit.setMaximumHeight(120)
        layout.addWidget(QLabel("Exemples de fusions:"))
        layout.addWidget(self.merge_examples_edit)
        layout.addWidget(QLabel("Notes — à vérifier / à affiner (sauvegardé par épisode) :"))
        self.inspect_notes_edit = QPlainTextEdit()
        self.inspect_notes_edit.setPlaceholderText(
            "Points à vérifier, à changer, à affiner pour cet épisode…"
        )
        self.inspect_notes_edit.setMaximumHeight(100)
        layout.addWidget(self.inspect_notes_edit)
        self.inspect_segments_list.setVisible(False)
        self._restore_force_reprocess_state()
        self._refresh_action_buttons(episode_id=None, store=None)

    def _restore_splitter_sizes(self) -> None:
        def to_sizes(val) -> list[int] | None:
            if val is None:
                return None
            if isinstance(val, (list, tuple)):
                try:
                    return [int(x) for x in val][:10]
                except (TypeError, ValueError):
                    return None
            if isinstance(val, str):
                try:
                    return [int(x) for x in val.split(",") if x.strip()][:10]
                except ValueError:
                    return None
            return None

        settings = QSettings()
        main = to_sizes(settings.value("inspecteur/mainSplitter"))
        right = to_sizes(settings.value("inspecteur/rightSplitter"))
        if main is not None and len(main) >= 2:
            self.inspect_main_split.setSizes(main)
        if right is not None and len(right) >= 2:
            self.inspect_right_split.setSizes(right)

    def save_state(self) -> None:
        """Sauvegarde les proportions des splitters et les notes de l'épisode courant (appelé à la fermeture)."""
        settings = QSettings()
        settings.setValue("inspecteur/mainSplitter", self.inspect_main_split.sizes())
        settings.setValue("inspecteur/rightSplitter", self.inspect_right_split.sizes())
        settings.setValue(_INSPECTOR_FORCE_REPROCESS_KEY, self.inspect_force_reprocess_check.isChecked())
        store = self._get_store()
        if self._current_episode_id and store:
            store.save_episode_notes(
                self._current_episode_id,
                self.inspect_notes_edit.toPlainText(),
            )

    def _save_force_reprocess_state(self, checked: bool) -> None:
        settings = QSettings()
        settings.setValue(_INSPECTOR_FORCE_REPROCESS_KEY, bool(checked))

    def _restore_force_reprocess_state(self) -> None:
        settings = QSettings()
        checked = bool(settings.value(_INSPECTOR_FORCE_REPROCESS_KEY, False))
        self.inspect_force_reprocess_check.setChecked(checked)

    def refresh(self) -> None:
        """Recharge la liste des épisodes et l'épisode courant."""
        store = self._get_store()
        if not store:
            refill_combo_preserve_selection(
                self.inspect_episode_combo,
                items=[],
                current_data=None,
            )
            self._refresh_action_buttons(episode_id=None, store=None)
            return
        index = store.load_series_index()
        current_episode = self.inspect_episode_combo.currentData()
        items: list[tuple[str, str]] = []
        if index and index.episodes:
            items = [(f"{e.episode_id} - {e.title}", e.episode_id) for e in index.episodes]
        refill_combo_preserve_selection(
            self.inspect_episode_combo,
            items=items,
            current_data=current_episode,
        )
        self._load_episode()

    def refresh_profile_combo(self, profile_ids: list[str], current: str | None) -> None:
        """Met à jour la liste des profils (après ouverture projet ou dialogue profils)."""
        current_inspect = self.inspect_profile_combo.currentText()
        self.inspect_profile_combo.clear()
        self.inspect_profile_combo.addItems(profile_ids)
        if current_inspect and current_inspect in profile_ids:
            self.inspect_profile_combo.setCurrentText(current_inspect)
        elif current and current in profile_ids:
            self.inspect_profile_combo.setCurrentText(current)

    def set_episode_selector_visible(self, visible: bool) -> None:
        """§15.4 — Masque ou affiche le sélecteur d'épisode (quand intégré dans l'onglet fusionné)."""
        self._inspect_episode_label.setVisible(visible)
        self.inspect_episode_combo.setVisible(visible)

    def set_episode_and_load(self, episode_id: str) -> None:
        """Sélectionne l'épisode donné et charge son contenu (ex. depuis Concordance « Ouvrir dans Inspecteur »)."""
        for i in range(self.inspect_episode_combo.count()):
            if self.inspect_episode_combo.itemData(i) == episode_id:
                if self.inspect_episode_combo.currentIndex() != i:
                    # Le signal currentIndexChanged déclenche déjà _load_episode.
                    self.inspect_episode_combo.setCurrentIndex(i)
                else:
                    self._load_episode()
                return
        self._load_episode()

    def _load_episode(self) -> None:
        eid = self.inspect_episode_combo.currentData()
        store = self._get_store()
        if not eid or not store:
            self._current_episode_id = None
            self.raw_edit.clear()
            self.clean_edit.clear()
            self.inspect_stats_label.setText("Stats: —")
            self.merge_examples_edit.clear()
            self.inspect_notes_edit.clear()
            self.inspect_segments_list.clear()
            self._refresh_action_buttons(episode_id=None, store=store)
            return
        if self._current_episode_id and self._current_episode_id != eid:
            store.save_episode_notes(
                self._current_episode_id,
                self.inspect_notes_edit.toPlainText(),
            )
        self._current_episode_id = eid
        self.inspect_notes_edit.setPlainText(store.load_episode_notes(eid))
        raw = store.load_episode_text(eid, kind="raw")
        clean = store.load_episode_text(eid, kind="clean")
        self.raw_edit.setPlainText(raw)
        self.clean_edit.setPlainText(clean)
        meta = store.load_episode_transform_meta(eid)
        if meta is not None:
            stats = meta.get("raw_lines", 0), meta.get("clean_lines", 0), meta.get("merges", 0)
            profile = str(meta.get("profile_id") or "").strip()
            profile_info = f", profil={profile}" if profile else ""
            self.inspect_stats_label.setText(
                f"Stats: raw_lines={stats[0]}, clean_lines={stats[1]}, merges={stats[2]}{profile_info}"
            )
            examples = meta.get("debug", {}).get("merge_examples", [])
            self.merge_examples_edit.setPlainText(
                "\n".join(
                    f"{x.get('before', '')} | {x.get('after', '')}" for x in examples[:15]
                )
            )
        else:
            self.inspect_stats_label.setText("Stats: —")
            self.merge_examples_edit.clear()
        config = self._get_config()
        episode_preferred = store.load_episode_preferred_profiles()
        source_defaults = store.load_source_profile_defaults()
        index = store.load_series_index()
        ref = (
            next((e for e in (index.episodes or []) if e.episode_id == eid), None)
            if index
            else None
        )
        profile = (
            episode_preferred.get(eid)
            or (source_defaults.get(ref.source_id or "") if ref else None)
            or (config.normalize_profile if config else "default_en_v1")
        )
        if profile and profile in get_all_profile_ids():
            self.inspect_profile_combo.setCurrentText(profile)
        self._fill_segments(eid)
        self._refresh_action_buttons(episode_id=str(eid), store=store)

    def _refresh_action_buttons(self, *, episode_id: str | None, store: Any | None) -> None:
        has_episode = bool(episode_id and store)
        has_raw = bool(has_episode and store and store.has_episode_raw(str(episode_id)))
        has_clean = bool(has_episode and store and store.has_episode_clean(str(episode_id)))
        db = self._get_db()
        has_segments = False
        if has_episode and db:
            try:
                has_segments = bool(db.get_segments_for_episode(str(episode_id)))
            except Exception:
                logger.exception("Failed to load segments for button state")
                has_segments = False
        controls_enabled = not self._job_busy
        self.inspect_set_preferred_profile_btn.setEnabled(has_episode and controls_enabled)
        self.inspect_norm_btn.setEnabled(has_raw and controls_enabled)
        self.inspect_segment_btn.setEnabled(has_clean and controls_enabled)
        self.inspect_export_segments_btn.setEnabled(has_segments and bool(db) and controls_enabled)
        self.inspect_profile_combo.setEnabled(has_episode and controls_enabled)
        self.inspect_view_combo.setEnabled(has_episode and controls_enabled)
        self.inspect_force_reprocess_check.setEnabled(has_episode and controls_enabled)
        if not controls_enabled:
            self.inspect_norm_btn.setToolTip("Action indisponible pendant un job.")
            self.inspect_segment_btn.setToolTip("Action indisponible pendant un job.")
            self.inspect_export_segments_btn.setToolTip("Action indisponible pendant un job.")
            return
        if not has_episode:
            self.inspect_norm_btn.setToolTip("Sélectionnez un épisode.")
            self.inspect_segment_btn.setToolTip("Sélectionnez un épisode.")
            self.inspect_export_segments_btn.setToolTip("Sélectionnez un épisode.")
            return
        if has_raw:
            self.inspect_norm_btn.setToolTip(self._inspect_norm_tooltip_default)
        else:
            self.inspect_norm_btn.setToolTip("Normalisation indisponible: transcript RAW manquant.")
        if has_clean:
            self.inspect_segment_btn.setToolTip(self._inspect_segment_tooltip_default)
        else:
            self.inspect_segment_btn.setToolTip("Segmentation indisponible: fichier CLEAN manquant.")
        if has_segments:
            self.inspect_export_segments_btn.setToolTip(self._inspect_export_segments_tooltip_default)
        else:
            self.inspect_export_segments_btn.setToolTip("Export indisponible: aucun segment pour cet épisode.")

    def set_job_busy(self, busy: bool) -> None:
        """Désactive les actions de mutation pendant un job de fond."""
        self._job_busy = busy
        self.inspect_episode_combo.setEnabled(not busy)
        store = self._get_store()
        self._refresh_action_buttons(episode_id=self._current_episode_id, store=store)

    def _switch_view(self) -> None:
        is_segments = self.inspect_view_combo.currentData() == "segments"
        self.inspect_segments_list.setVisible(is_segments)
        eid = self.inspect_episode_combo.currentData()
        if eid:
            self._fill_segments(eid)

    def _fill_segments(self, episode_id: str) -> None:
        self.inspect_segments_list.clear()
        if self.inspect_view_combo.currentData() != "segments":
            return
        db = self._get_db()
        if not db:
            return
        try:
            segments = db.get_segments_for_episode(episode_id)
        except Exception:
            logger.exception("Failed to load segments in inspector view")
            return
        for s in segments:
            kind = s.get("kind", "")
            n = s.get("n", 0)
            speaker = s.get("speaker_explicit") or ""
            text = (s.get("text") or "")[:60]
            if len((s.get("text") or "")) > 60:
                text += "…"
            if speaker:
                label = f"[{kind}] {n} {speaker}: {text}"
            else:
                label = f"[{kind}] {n}: {text}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.inspect_segments_list.addItem(item)

    def _on_segment_selected(self, current: QListWidgetItem | None) -> None:
        if not current:
            return
        seg = current.data(Qt.ItemDataRole.UserRole)
        if not seg:
            return
        start_char = seg.get("start_char", 0)
        end_char = seg.get("end_char", 0)
        text = self.clean_edit.toPlainText()
        cursor = self.clean_edit.textCursor()
        cursor.setPosition(min(start_char, len(text)))
        cursor.setPosition(min(end_char, len(text)), QTextCursor.MoveMode.KeepAnchor)
        self.clean_edit.setTextCursor(cursor)
        self.clean_edit.ensureCursorVisible()

    def _resolve_episode_store_or_warn(self, *, title: str) -> tuple[str, object] | None:
        eid = self.inspect_episode_combo.currentData()
        store = self._get_store()
        if not eid or not store:
            warn_precondition(
                self,
                title,
                "Sélectionnez un épisode et ouvrez un projet.",
                next_step="Pilotage: ouvrez/créez un projet puis choisissez un épisode dans l'Inspecteur.",
            )
            return None
        return str(eid), store

    def _open_pilotage_batch(self) -> None:
        if self._on_open_pilotage is None:
            warn_precondition(
                self,
                "Inspecteur",
                "Navigation vers Pilotage indisponible.",
                next_step="Ouvrez l'onglet Pilotage manuellement pour lancer un traitement batch.",
            )
            return
        self._on_open_pilotage()

    def _run_job_with_force(self, steps: list[Any], *, force: bool | None = None) -> None:
        force_flag = self.inspect_force_reprocess_check.isChecked() if force is None else bool(force)
        try:
            self._run_job(steps, force=force_flag)
        except TypeError:
            self._run_job(steps)

    def _resolve_episode_store_db_or_warn(self, *, title: str) -> tuple[str, object, object] | None:
        resolved = self._resolve_episode_store_or_warn(title=title)
        if resolved is None:
            return None
        eid, store = resolved
        db = self._get_db()
        if not db:
            warn_precondition(
                self,
                title,
                "Base de données indisponible.",
                next_step="Pilotage: rouvrez le projet pour réinitialiser la base.",
            )
            return None
        return eid, store, db

    def _run_normalize(self) -> None:
        resolved = self._resolve_episode_store_or_warn(title="Normalisation")
        if resolved is None:
            return
        eid, store = resolved
        if not store.has_episode_raw(eid):
            warn_precondition(
                self,
                "Normalisation",
                "L'épisode doit d'abord être téléchargé (RAW).",
                next_step="Pilotage > Corpus: lancez « Télécharger » sur cet épisode.",
            )
            return
        profile = self.inspect_profile_combo.currentText() or "default_en_v1"
        steps = self._build_single_episode_steps(
            WorkflowActionId.NORMALIZE_EPISODES,
            str(eid),
            options={
                "default_profile_id": profile,
                "profile_by_episode": {str(eid): profile},
            },
            title="Normalisation",
        )
        if steps is None:
            return
        self._run_job_with_force(steps)

    def _set_episode_preferred_profile(self) -> None:
        resolved = self._resolve_episode_store_or_warn(title="Profil préféré")
        if resolved is None:
            return
        eid, store = resolved
        profile = self.inspect_profile_combo.currentText() or "default_en_v1"
        preferred = store.load_episode_preferred_profiles()
        preferred[eid] = profile
        store.save_episode_preferred_profiles(preferred)
        self._show_status(f"Profil « {profile} » défini comme préféré pour {eid}.", 3000)

    def _run_segment(self) -> None:
        resolved = self._resolve_episode_store_db_or_warn(title="Segmentation")
        if resolved is None:
            return
        eid, store, _db = resolved
        if not store.has_episode_clean(eid):
            warn_precondition(
                self,
                "Segmentation",
                "L'épisode doit d'abord être normalisé (clean.txt).",
                next_step="Inspecteur: cliquez sur « Normaliser cet épisode ».",
            )
            return
        config = self._get_config()
        lang_hint = resolve_lang_hint_from_profile_id(
            getattr(config, "normalize_profile", None),
            fallback="en",
        )
        steps = self._build_single_episode_steps(
            WorkflowActionId.SEGMENT_EPISODES,
            str(eid),
            options={"lang_hint": lang_hint},
            title="Segmentation",
        )
        if steps is None:
            return
        self._run_job_with_force(steps)

    def _export_segments(self) -> None:
        resolved = self._resolve_episode_store_db_or_warn(title="Export segments")
        if resolved is None:
            return
        eid, _store, db = resolved
        segments = db.get_segments_for_episode(eid)
        if not segments:
            warn_precondition(
                self,
                "Export segments",
                "Aucun segment pour cet épisode. Lancez d'abord « Segmente l'épisode ».",
                next_step="Inspecteur: cliquez sur « Segmente l'épisode ».",
            )
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter les segments",
            "",
            "TXT — un segment par ligne (*.txt);;CSV (*.csv);;TSV (*.tsv);;Word (*.docx)",
        )
        if not path:
            return
        path = Path(path)
        path = normalize_export_path(
            path,
            selected_filter,
            allowed_suffixes=(".txt", ".csv", ".tsv", ".docx"),
            default_suffix=".txt",
            filter_to_suffix={
                "TXT": ".txt",
                "CSV": ".csv",
                "TSV": ".tsv",
                "WORD": ".docx",
            },
        )
        export_key = resolve_export_key(
            path,
            selected_filter,
            suffix_to_key={
                ".txt": "txt",
                ".csv": "csv",
                ".tsv": "tsv",
                ".docx": "docx",
            },
        )
        try:
            if export_key == "txt":
                export_segments_txt(segments, path)
            elif export_key == "tsv":
                export_segments_tsv(segments, path)
            elif export_key == "docx":
                export_segments_docx(segments, path)
            else:
                export_segments_csv(segments, path)
            show_info(
                self,
                "Export",
                build_export_success_message(
                    subject="Segments exportés",
                    count=len(segments),
                    count_label="segment(s)",
                    path=path,
                ),
                status_callback=self._show_status,
            )
        except Exception as e:
            logger.exception("Export segments Inspecteur")
            show_error(self, exc=e, context="Export segments")

    def _build_single_episode_steps(
        self,
        action_id: WorkflowActionId,
        episode_id: str,
        *,
        options: dict[str, Any] | None,
        title: str,
    ) -> list[Any] | None:
        store = self._get_store()
        if not store:
            warn_precondition(
                self,
                title,
                "Ouvrez un projet d'abord.",
                next_step="Pilotage: ouvrez un projet puis revenez dans l'Inspecteur.",
            )
            return None
        index = store.load_series_index()
        refs = index.episodes if index else []
        context = {
            "config": self._get_config(),
            "store": store,
            "db": self._get_db(),
        }
        return build_workflow_steps_or_warn(
            workflow_service=self._workflow_service,
            action_id=action_id,
            context=context,
            scope=WorkflowScope.current(episode_id),
            episode_refs=refs,
            options=options or {},
            warn_precondition_message=lambda message: warn_precondition(self, title, message),
        )
