"""Contrôleur léger pour l'exécution des actions workflow du Corpus."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable, Mapping

from howimetyourcorpus.app.corpus_scope import (
    build_episode_url_by_id,
    build_profile_by_episode,
    filter_ids_with_clean,
    filter_ids_with_raw,
    filter_ids_with_source_url,
    filter_runnable_ids_for_full_workflow,
    normalize_scope_mode,
)
from howimetyourcorpus.app.export_dialog import normalize_export_path, resolve_export_key
from howimetyourcorpus.app.workflow_advice import build_workflow_advice
from howimetyourcorpus.app.workflow_status import load_episode_status_map
from howimetyourcorpus.app.workflow_status import compute_workflow_status
from howimetyourcorpus.app.workflow_ui import build_workflow_steps_or_warn
from howimetyourcorpus.core.export_utils import (
    export_corpus_csv,
    export_corpus_docx,
    export_corpus_json,
    export_corpus_phrases_csv,
    export_corpus_phrases_jsonl,
    export_corpus_txt,
    export_corpus_utterances_csv,
    export_corpus_utterances_jsonl,
)
from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus, SeriesIndex
from howimetyourcorpus.core.pipeline.tasks import FetchAndMergeSeriesIndexStep, FetchSeriesIndexStep
from howimetyourcorpus.core.workflow import WorkflowActionId, WorkflowScope, WorkflowService


class CorpusWorkflowController:
    """Orchestre la construction de steps workflow et leur exécution côté UI Corpus."""

    def __init__(
        self,
        *,
        workflow_service: WorkflowService,
        run_steps: Callable[[list[Any]], None],
        warn_user: Callable[[str, str | None], None],
        step_builder: Callable[..., list[Any] | None] = build_workflow_steps_or_warn,
    ) -> None:
        self._workflow_service = workflow_service
        self._run_steps = run_steps
        self._warn_user = warn_user
        self._step_builder = step_builder

    def build_action_steps_or_warn(
        self,
        *,
        action_id: WorkflowActionId,
        context: dict[str, Any],
        scope: WorkflowScope,
        episode_refs: list[EpisodeRef],
        options: dict[str, Any] | None = None,
    ) -> list[Any] | None:
        return self._step_builder(
            workflow_service=self._workflow_service,
            action_id=action_id,
            context=context,
            scope=scope,
            episode_refs=episode_refs,
            options=options,
            warn_precondition_message=lambda message: self._warn_user(message, None),
        )

    def run_action_for_scope(
        self,
        *,
        action_id: WorkflowActionId,
        context: dict[str, Any],
        scope: WorkflowScope,
        episode_refs: list[EpisodeRef],
        options: dict[str, Any] | None,
        empty_message: str,
        empty_next_step: str | None = None,
    ) -> bool:
        steps = self.build_action_steps_or_warn(
            action_id=action_id,
            context=context,
            scope=scope,
            episode_refs=episode_refs,
            options=options,
        )
        if steps is None:
            return False
        if not steps:
            self._warn_user(empty_message, empty_next_step)
            return False
        self._run_steps(steps)
        return True

    def run_action_for_episode_ids_or_warn(
        self,
        *,
        action_id: WorkflowActionId,
        context: dict[str, Any],
        episode_ids: list[str],
        episode_refs: list[EpisodeRef],
        options: dict[str, Any] | None,
        empty_message: str,
        empty_next_step: str | None = None,
    ) -> bool:
        """Version pratique de `run_action_for_scope` pour un scope `selection(ids)`."""
        return self.run_action_for_scope(
            action_id=action_id,
            context=context,
            scope=WorkflowScope.selection(episode_ids),
            episode_refs=episode_refs,
            options=options,
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )

    def run_composed_steps_or_warn(
        self,
        *,
        steps: list[Any] | None,
        empty_message: str,
        empty_next_step: str | None = None,
    ) -> bool:
        """Exécute des steps déjà composés (ou avertit si la composition est vide)."""
        if steps is None:
            return False
        if not steps:
            self._warn_user(empty_message, empty_next_step)
            return False
        self._run_steps(steps)
        return True

    @staticmethod
    def build_skipped_scope_status_message(
        *,
        prefix: str,
        skipped: int,
        reason: str,
    ) -> str | None:
        if skipped <= 0:
            return None
        return f"{prefix}: {skipped} épisode(s) ignoré(s) ({reason})."

    @staticmethod
    def resolve_scope_action_availability(
        *,
        ids: list[str],
        capabilities: dict[str, tuple[bool, bool, bool, bool]],
    ) -> tuple[dict[str, bool], dict[str, str | None]]:
        """Calcule l'activation des actions de scope et leurs raisons de désactivation."""
        fetchable_ids = [eid for eid in ids if capabilities.get(eid, (False, False, False, False))[0]]
        ids_with_raw = [eid for eid in ids if capabilities.get(eid, (False, False, False, False))[1]]
        ids_with_clean = [eid for eid in ids if capabilities.get(eid, (False, False, False, False))[2]]
        runnable_ids = [eid for eid in ids if capabilities.get(eid, (False, False, False, False))[3]]
        enabled = {
            "fetch": bool(fetchable_ids),
            "normalize": bool(ids_with_raw),
            "segment": bool(ids_with_clean),
            "run_all": bool(runnable_ids),
            "index": bool(ids_with_clean),
        }
        reasons = {
            "fetch": None if enabled["fetch"] else "Action indisponible: aucune URL source disponible dans le scope.",
            "normalize": None if enabled["normalize"] else "Action indisponible: aucun transcript RAW dans le scope.",
            "segment": None if enabled["segment"] else "Action indisponible: aucun fichier CLEAN dans le scope.",
            "run_all": (
                None
                if enabled["run_all"]
                else "Action indisponible: aucun épisode exécutable (URL source, RAW ou CLEAN) dans le scope."
            ),
            "index": None if enabled["index"] else "Action indisponible: aucun fichier CLEAN dans le scope.",
        }
        return enabled, reasons

    @staticmethod
    def resolve_scope_action_ui_state(
        *,
        has_index: bool,
        has_store: bool,
        ids: list[str],
        capabilities: dict[str, tuple[bool, bool, bool, bool]],
    ) -> tuple[dict[str, bool], dict[str, str | None], str | None]:
        """
        Résout l'état UI des actions de scope.

        Retourne `(enabled, reasons, unavailable_reason)` où `unavailable_reason` est
        renseigné quand toutes les actions doivent être désactivées pour précondition globale.
        """
        if not has_index:
            disabled = {
                "fetch": False,
                "normalize": False,
                "segment": False,
                "run_all": False,
                "index": False,
            }
            return disabled, {}, "Action indisponible: aucun épisode dans le corpus."
        if not has_store:
            disabled = {
                "fetch": False,
                "normalize": False,
                "segment": False,
                "run_all": False,
                "index": False,
            }
            return disabled, {}, "Action indisponible: ouvrez un projet d'abord."
        if not ids:
            disabled = {
                "fetch": False,
                "normalize": False,
                "segment": False,
                "run_all": False,
                "index": False,
            }
            return disabled, {}, "Action indisponible: aucun épisode dans le scope courant."
        enabled, reasons = CorpusWorkflowController.resolve_scope_action_availability(
            ids=ids,
            capabilities=capabilities,
        )
        return enabled, reasons, None

    def resolve_project_context_or_warn(
        self,
        *,
        store: Any,
        db: Any,
        context: dict[str, Any],
        require_db: bool = False,
    ) -> tuple[Any, Any, dict[str, Any]] | None:
        """Valide le contexte projet requis pour lancer des actions Corpus."""
        if not context.get("config") or not store or (require_db and not db):
            self._warn_user(
                "Ouvrez un projet d'abord.",
                "Pilotage > Projet: ouvrez ou initialisez un projet.",
            )
            return None
        return store, db, context

    def resolve_index_or_warn(self, *, index: SeriesIndex | None) -> SeriesIndex | None:
        """Valide que l'index série est présent et non vide."""
        if not index or not index.episodes:
            self._warn_user(
                "Découvrez d'abord les épisodes.",
                "Pilotage > Corpus: cliquez sur « Découvrir épisodes ».",
            )
            return None
        return index

    def resolve_project_with_index_or_warn(
        self,
        *,
        store: Any,
        db: Any,
        context: dict[str, Any],
        require_db: bool = False,
    ) -> tuple[Any, Any, dict[str, Any], SeriesIndex] | None:
        """Valide le contexte projet puis charge/valide l'index série."""
        resolved_project = self.resolve_project_context_or_warn(
            store=store,
            db=db,
            context=context,
            require_db=require_db,
        )
        if resolved_project is None:
            return None
        store_ok, db_ok, context_ok = resolved_project
        index_ok = self.resolve_index_or_warn(index=store_ok.load_series_index())
        if index_ok is None:
            return None
        return store_ok, db_ok, context_ok, index_ok

    @staticmethod
    def build_discover_series_steps(*, context: dict[str, Any]) -> list[Any]:
        """Construit le step de découverte d'index principal."""
        config = context["config"]
        return [FetchSeriesIndexStep(config.series_url, config.user_agent)]

    def build_discover_merge_steps_or_warn(
        self,
        *,
        context: dict[str, Any],
        series_url: str | None,
        source_id: str | None,
    ) -> list[Any] | None:
        """Construit le step de découverte/fusion depuis une autre source."""
        url = (series_url or "").strip()
        if not url:
            self._warn_user(
                "Indiquez l'URL de la série.",
                "Renseignez une URL source puis relancez « Découvrir (fusionner) ».",
            )
            return None
        source = (source_id or "").strip() or "subslikescript"
        config = context["config"]
        return [FetchAndMergeSeriesIndexStep(url, source, config.user_agent)]

    def resolve_manual_episode_refs_or_warn(
        self,
        *,
        raw_text: str | None,
    ) -> tuple[list[EpisodeRef], int] | None:
        """Parse les episode_id saisis manuellement (format S01E01)."""
        lines = [
            ln.strip().upper()
            for ln in str(raw_text or "").strip().splitlines()
            if ln and ln.strip()
        ]
        if not lines:
            self._warn_user(
                "Aucun episode_id saisi.",
                "Saisissez un identifiant par ligne, ex. S01E01.",
            )
            return None
        new_refs_by_id: dict[str, EpisodeRef] = {}
        invalid_count = 0
        for ln in lines:
            mm = re.fullmatch(r"S(\d+)E(\d+)", ln, re.IGNORECASE)
            if not mm:
                invalid_count += 1
                continue
            ep_id = f"S{int(mm.group(1)):02d}E{int(mm.group(2)):02d}"
            if ep_id in new_refs_by_id:
                continue
            new_refs_by_id[ep_id] = EpisodeRef(
                episode_id=ep_id,
                season=int(mm.group(1)),
                episode=int(mm.group(2)),
                title="",
                url="",
            )
        if not new_refs_by_id:
            self._warn_user(
                "Aucun episode_id valide (format S01E01).",
                "Saisissez un identifiant par ligne, ex. S01E01.",
            )
            return None
        return list(new_refs_by_id.values()), invalid_count

    def merge_manual_episode_refs_or_warn(
        self,
        *,
        index: SeriesIndex | None,
        new_refs: list[EpisodeRef],
    ) -> tuple[SeriesIndex, int, int] | None:
        """Fusionne les épisodes saisis à la main dans l'index existant."""
        existing_ids = {e.episode_id for e in (index.episodes or [])} if index else set()
        episodes = list(index.episodes or []) if index else []
        added_count = 0
        skipped_existing = 0
        for ref in new_refs:
            if ref.episode_id not in existing_ids:
                episodes.append(ref)
                existing_ids.add(ref.episode_id)
                added_count += 1
            else:
                skipped_existing += 1
        if added_count <= 0:
            self._warn_user(
                "Tous les épisodes saisis existent déjà.",
                "Saisissez de nouveaux IDs (format S01E01).",
            )
            return None
        return (
            SeriesIndex(
                series_title=index.series_title if index else "",
                series_url=index.series_url if index else "",
                episodes=episodes,
            ),
            added_count,
            skipped_existing,
        )

    @staticmethod
    def build_manual_add_status_message(
        *,
        added_count: int,
        skipped_existing: int,
        invalid_count: int,
    ) -> str:
        parts = [f"{added_count} épisode(s) ajouté(s)"]
        if skipped_existing > 0:
            parts.append(f"{skipped_existing} déjà présent(s)")
        if invalid_count > 0:
            parts.append(f"{invalid_count} ignoré(s) (format invalide)")
        return "Ajout manuel: " + ", ".join(parts) + "."

    def resolve_clean_episodes_for_export_or_warn(
        self,
        *,
        store: Any,
        index: SeriesIndex | None = None,
    ) -> list[tuple[EpisodeRef, str]] | None:
        """Résout les épisodes CLEAN exportables avec préconditions utilisateur homogènes."""
        if not store:
            self._warn_user(
                "Ouvrez un projet d'abord.",
                "Pilotage > Projet: ouvrez ou initialisez un projet.",
            )
            return None
        index_ok = self.resolve_index_or_warn(index=index or store.load_series_index())
        if index_ok is None:
            return None
        episodes_data: list[tuple[EpisodeRef, str]] = []
        for ref in index_ok.episodes:
            if store.has_episode_clean(ref.episode_id):
                text = store.load_episode_text(ref.episode_id, kind="clean")
                episodes_data.append((ref, text))
        if not episodes_data:
            self._warn_user(
                "Aucun épisode normalisé (CLEAN) à exporter.",
                "Lancez « Normaliser » puis réessayez l'export.",
            )
            return None
        return episodes_data

    def export_episodes_data_or_warn(
        self,
        *,
        episodes_data: list[tuple[EpisodeRef, str]],
        path: Path,
        selected_filter: str | None,
        export_writers: Mapping[str, Callable[[list[tuple[EpisodeRef, str]], Path], None]] | None = None,
    ) -> Path | None:
        """Exporte les épisodes selon le format résolu (suffixe/filtre) et retourne le chemin final."""
        if not episodes_data:
            self._warn_user(
                "Aucun épisode normalisé (CLEAN) à exporter.",
                "Lancez « Normaliser » puis réessayez l'export.",
            )
            return None
        output_path = normalize_export_path(
            path,
            selected_filter,
            allowed_suffixes=(".txt", ".csv", ".json", ".jsonl", ".docx"),
            default_suffix=".txt",
            filter_to_suffix={
                "TXT": ".txt",
                "CSV": ".csv",
                "JSON": ".json",
                "JSONL": ".jsonl",
                "WORD": ".docx",
            },
        )
        selected_upper = (selected_filter or "").upper()
        if "JSONL - UTTERANCES" in selected_upper:
            export_key = "utterances_jsonl"
        elif "JSONL - PHRASES" in selected_upper:
            export_key = "phrases_jsonl"
        elif "CSV - UTTERANCES" in selected_upper:
            export_key = "utterances_csv"
        elif "CSV - PHRASES" in selected_upper:
            export_key = "phrases_csv"
        else:
            base_key = resolve_export_key(
                output_path,
                selected_filter,
                suffix_to_key={
                    ".txt": "txt",
                    ".csv": "csv",
                    ".json": "json",
                    ".jsonl": "jsonl",
                    ".docx": "docx",
                },
                default_key="txt",
            )
            export_key = "utterances_jsonl" if base_key == "jsonl" else base_key
        if export_writers is None:
            writers: Mapping[str, Callable[[list[tuple[EpisodeRef, str]], Path], None]] = {
                "txt": export_corpus_txt,
                "csv": export_corpus_csv,
                "json": export_corpus_json,
                "docx": export_corpus_docx,
                "utterances_jsonl": export_corpus_utterances_jsonl,
                "phrases_jsonl": export_corpus_phrases_jsonl,
                "utterances_csv": export_corpus_utterances_csv,
                "phrases_csv": export_corpus_phrases_csv,
            }
        else:
            writers = export_writers
        writer = writers.get(str(export_key))
        if writer is None:
            self._warn_user(
                "Format non reconnu. Utilisez .txt, .csv, .json, .jsonl ou .docx.",
                None,
            )
            return None
        writer(episodes_data, output_path)
        return output_path

    def resolve_scope_and_ids_or_warn(
        self,
        *,
        scope_mode: str | None,
        all_episode_ids: list[str],
        current_episode_id: str | None,
        selected_episode_ids: list[str],
        season: int | None,
        get_episode_ids_for_season: Callable[[int], list[str]],
    ) -> tuple[WorkflowScope, list[str]] | None:
        """Résout le scope workflow avec messages d'erreur utilisateur cohérents."""
        mode = normalize_scope_mode(scope_mode)
        if mode == "current":
            if not current_episode_id:
                self._warn_user(
                    "Scope « Épisode courant »: sélectionnez une ligne (ou cochez un épisode).",
                    "Sélectionnez un épisode dans la liste ou cochez sa case.",
                )
                return None
            return WorkflowScope.current(current_episode_id), [current_episode_id]
        if mode == "selection":
            ids = list(selected_episode_ids)
            if not ids:
                self._warn_user(
                    "Scope « Sélection »: cochez au moins un épisode ou sélectionnez des lignes.",
                    "Utilisez « Tout cocher » ou choisissez des épisodes manuellement.",
                )
                return None
            return WorkflowScope.selection(ids), ids
        if mode == "season":
            if season is None:
                self._warn_user(
                    "Scope « Saison filtrée »: choisissez d'abord une saison (pas « Toutes les saisons »).",
                    "Choisissez une saison dans le filtre « Saison ».",
                )
                return None
            ids = list(get_episode_ids_for_season(int(season)))
            if not ids:
                self._warn_user(
                    f"Aucun épisode trouvé pour la saison {season}.",
                    "Ajustez le filtre « Saison » ou lancez « Découvrir épisodes » pour recharger l'index.",
                )
                return None
            return WorkflowScope.season_scope(int(season)), ids
        if mode == "all":
            return WorkflowScope.all(), list(all_episode_ids)
        self._warn_user(
            f"Scope inconnu: {mode}",
            "Utilisez un périmètre valide: Épisode courant, Sélection, Saison filtrée ou Tout le corpus.",
        )
        return None

    def resolve_scope_context_or_warn(
        self,
        *,
        store: Any,
        db: Any,
        context: dict[str, Any],
        index: SeriesIndex | None,
        require_db: bool,
        scope_mode: str | None,
        all_episode_ids: list[str],
        current_episode_id: str | None,
        selected_episode_ids: list[str],
        season: int | None,
        get_episode_ids_for_season: Callable[[int], list[str]],
    ) -> tuple[Any, Any, dict[str, Any], SeriesIndex, WorkflowScope, list[str]] | None:
        """Résout tout le contexte nécessaire à une action workflow Corpus."""
        resolved_project = self.resolve_project_context_or_warn(
            store=store,
            db=db,
            context=context,
            require_db=require_db,
        )
        if resolved_project is None:
            return None
        store_ok, db_ok, context_ok = resolved_project
        index_ok = self.resolve_index_or_warn(index=index)
        if index_ok is None:
            return None
        resolved_scope = self.resolve_scope_and_ids_or_warn(
            scope_mode=scope_mode,
            all_episode_ids=all_episode_ids,
            current_episode_id=current_episode_id,
            selected_episode_ids=selected_episode_ids,
            season=season,
            get_episode_ids_for_season=get_episode_ids_for_season,
        )
        if resolved_scope is None:
            return None
        scope, ids = resolved_scope
        return store_ok, db_ok, context_ok, index_ok, scope, ids

    def resolve_ids_with_source_url_or_warn(
        self,
        *,
        ids: list[str],
        episode_url_by_id: dict[str, str],
    ) -> list[str] | None:
        filtered = filter_ids_with_source_url(ids=ids, episode_url_by_id=episode_url_by_id)
        if not filtered:
            self._warn_user(
                "Aucun épisode du scope choisi n'a d'URL source.",
                "Lancez « Découvrir épisodes » ou ajoutez des épisodes avec URL valide.",
            )
            return None
        return filtered

    def prepare_fetch_scope_plan_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
    ) -> tuple[list[str], dict[str, str], int] | None:
        """
        Prépare le scope de téléchargement:
        - construit la map d'URL par épisode,
        - filtre les épisodes ayant une URL source,
        - retourne le nombre d'épisodes ignorés.
        """
        episode_url_by_id = build_episode_url_by_id(index)
        ids_with_url = self.resolve_ids_with_source_url_or_warn(
            ids=ids,
            episode_url_by_id=episode_url_by_id,
        )
        if ids_with_url is None:
            return None
        skipped = len(ids) - len(ids_with_url)
        return ids_with_url, episode_url_by_id, skipped

    def run_fetch_scope_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        context: dict[str, Any],
        empty_message: str,
        empty_next_step: str | None = None,
        skipped_prefix: str = "Téléchargement",
        skipped_reason: str = "URL source absente",
    ) -> str | None:
        """
        Prépare puis exécute l'action de téléchargement pour un scope.

        Retourne le message de statut "épisodes ignorés" (ou `None` si aucun).
        """
        prepared = self.prepare_fetch_scope_plan_or_warn(ids=ids, index=index)
        if prepared is None:
            return None
        ids_with_url, episode_url_by_id, skipped = prepared
        ok = self.run_action_for_episode_ids_or_warn(
            action_id=WorkflowActionId.FETCH_EPISODES,
            context=context,
            episode_ids=ids_with_url,
            episode_refs=index.episodes,
            options={"episode_url_by_id": episode_url_by_id},
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )
        if not ok:
            return None
        return self.build_skipped_scope_status_message(
            prefix=skipped_prefix,
            skipped=skipped,
            reason=skipped_reason,
        )

    def resolve_ids_with_raw_or_warn(
        self,
        *,
        ids: list[str],
        has_episode_raw: Callable[[str], bool],
    ) -> list[str] | None:
        filtered = filter_ids_with_raw(ids=ids, has_episode_raw=has_episode_raw)
        if not filtered:
            self._warn_user(
                "Aucun épisode du scope choisi n'a de transcript RAW. Téléchargez d'abord ce scope.",
                "Pilotage > Corpus: lancez « Télécharger » sur ce scope.",
            )
            return None
        return filtered

    def resolve_ids_with_clean_or_warn(
        self,
        *,
        ids: list[str],
        has_episode_clean: Callable[[str], bool],
        empty_message: str,
        empty_next_step: str,
    ) -> list[str] | None:
        filtered = filter_ids_with_clean(ids=ids, has_episode_clean=has_episode_clean)
        if not filtered:
            self._warn_user(empty_message, empty_next_step)
            return None
        return filtered

    def prepare_normalize_scope_plan_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        batch_profile: str,
    ) -> tuple[list[str], dict[str, str], int] | None:
        """
        Prépare le scope de normalisation:
        - filtre les épisodes avec RAW,
        - construit les profils par épisode,
        - retourne le nombre d'épisodes ignorés.
        """
        ids_with_raw = self.resolve_ids_with_raw_or_warn(
            ids=ids,
            has_episode_raw=store.has_episode_raw,
        )
        if ids_with_raw is None:
            return None
        profile_by_episode = build_profile_by_episode(
            episode_refs=index.episodes,
            episode_ids=ids_with_raw,
            batch_profile=batch_profile,
            episode_preferred_profiles=store.load_episode_preferred_profiles(),
            source_profile_defaults=store.load_source_profile_defaults(),
        )
        skipped = len(ids) - len(ids_with_raw)
        return ids_with_raw, profile_by_episode, skipped

    def run_normalize_scope_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        context: dict[str, Any],
        batch_profile: str,
        empty_message: str,
        empty_next_step: str | None = None,
        skipped_prefix: str = "Normalisation",
        skipped_reason: str = "sans RAW dans le scope",
    ) -> str | None:
        """
        Prépare puis exécute l'action de normalisation pour un scope.

        Retourne le message de statut "épisodes ignorés" (ou `None` si aucun).
        """
        prepared = self.prepare_normalize_scope_plan_or_warn(
            ids=ids,
            index=index,
            store=store,
            batch_profile=batch_profile,
        )
        if prepared is None:
            return None
        ids_with_raw, profile_by_episode, skipped = prepared
        ok = self.run_action_for_episode_ids_or_warn(
            action_id=WorkflowActionId.NORMALIZE_EPISODES,
            context=context,
            episode_ids=ids_with_raw,
            episode_refs=index.episodes,
            options={
                "default_profile_id": batch_profile,
                "profile_by_episode": profile_by_episode,
            },
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )
        if not ok:
            return None
        return self.build_skipped_scope_status_message(
            prefix=skipped_prefix,
            skipped=skipped,
            reason=skipped_reason,
        )

    def prepare_clean_scope_ids_or_warn(
        self,
        *,
        ids: list[str],
        has_episode_clean: Callable[[str], bool],
        empty_message: str,
        empty_next_step: str,
    ) -> tuple[list[str], int] | None:
        """
        Prépare un scope basé sur les épisodes disposant d'un CLEAN.

        Retourne `(ids_with_clean, skipped)`.
        """
        ids_with_clean = self.resolve_ids_with_clean_or_warn(
            ids=ids,
            has_episode_clean=has_episode_clean,
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )
        if ids_with_clean is None:
            return None
        skipped = len(ids) - len(ids_with_clean)
        return ids_with_clean, skipped

    def run_segment_scope_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        context: dict[str, Any],
        lang_hint: str,
        clean_empty_message: str,
        clean_empty_next_step: str,
        empty_message: str,
        empty_next_step: str | None = None,
        skipped_prefix: str = "Segmentation",
        skipped_reason: str = "sans CLEAN dans le scope",
    ) -> str | None:
        """
        Prépare puis exécute l'action de segmentation pour un scope CLEAN.

        Retourne le message de statut "épisodes ignorés" (ou `None` si aucun).
        """
        prepared = self.prepare_clean_scope_ids_or_warn(
            ids=ids,
            has_episode_clean=store.has_episode_clean,
            empty_message=clean_empty_message,
            empty_next_step=clean_empty_next_step,
        )
        if prepared is None:
            return None
        ids_with_clean, skipped = prepared
        ok = self.run_action_for_episode_ids_or_warn(
            action_id=WorkflowActionId.SEGMENT_EPISODES,
            context=context,
            episode_ids=ids_with_clean,
            episode_refs=index.episodes,
            options={"lang_hint": lang_hint},
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )
        if not ok:
            return None
        return self.build_skipped_scope_status_message(
            prefix=skipped_prefix,
            skipped=skipped,
            reason=skipped_reason,
        )

    def run_index_scope_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        context: dict[str, Any],
        clean_empty_message: str,
        clean_empty_next_step: str,
        empty_message: str,
        empty_next_step: str | None = None,
        skipped_prefix: str = "Indexation",
        skipped_reason: str = "sans CLEAN dans le scope",
    ) -> str | None:
        """
        Prépare puis exécute l'action d'indexation DB pour un scope CLEAN.

        Retourne le message de statut "épisodes ignorés" (ou `None` si aucun).
        """
        prepared = self.prepare_clean_scope_ids_or_warn(
            ids=ids,
            has_episode_clean=store.has_episode_clean,
            empty_message=clean_empty_message,
            empty_next_step=clean_empty_next_step,
        )
        if prepared is None:
            return None
        ids_with_clean, skipped = prepared
        ok = self.run_action_for_episode_ids_or_warn(
            action_id=WorkflowActionId.BUILD_DB_INDEX,
            context=context,
            episode_ids=ids_with_clean,
            episode_refs=index.episodes,
            options=None,
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )
        if not ok:
            return None
        return self.build_skipped_scope_status_message(
            prefix=skipped_prefix,
            skipped=skipped,
            reason=skipped_reason,
        )

    def resolve_runnable_ids_for_full_workflow_or_warn(
        self,
        *,
        ids: list[str],
        episode_url_by_id: dict[str, str],
        has_episode_raw: Callable[[str], bool],
        has_episode_clean: Callable[[str], bool],
    ) -> list[str] | None:
        if not ids:
            self._warn_user(
                "Aucun épisode résolu pour le scope choisi.",
                "Ajustez le scope ou sélectionnez/cochez au moins un épisode.",
            )
            return None
        runnable_ids = filter_runnable_ids_for_full_workflow(
            ids=ids,
            episode_url_by_id=episode_url_by_id,
            has_episode_raw=has_episode_raw,
            has_episode_clean=has_episode_clean,
        )
        if not runnable_ids:
            self._warn_user(
                "Aucun épisode exécutable dans le scope choisi (URL source, RAW ou CLEAN manquant).",
                "Ajoutez des URL source valides ou préparez des fichiers RAW/CLEAN puis relancez.",
            )
            return None
        return runnable_ids

    def prepare_full_workflow_scope_plan_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        context: dict[str, Any],
        batch_profile: str,
        lang_hint: str,
    ) -> tuple[list[Any], int] | None:
        """
        Prepare le plan "Tout faire" pour un scope:
        - filtre les episodes executables,
        - construit la map de profils par episode,
        - compose les steps fetch -> normalize -> segment -> index.

        Retourne `(steps, skipped)` avec `skipped` = episodes hors preconditions executables.
        """
        episode_url_by_id = build_episode_url_by_id(index)
        runnable_ids = self.resolve_runnable_ids_for_full_workflow_or_warn(
            ids=ids,
            episode_url_by_id=episode_url_by_id,
            has_episode_raw=store.has_episode_raw,
            has_episode_clean=store.has_episode_clean,
        )
        if runnable_ids is None:
            return None
        skipped = len(ids) - len(runnable_ids)
        profile_by_episode = build_profile_by_episode(
            episode_refs=index.episodes,
            episode_ids=runnable_ids,
            batch_profile=batch_profile,
            episode_preferred_profiles=store.load_episode_preferred_profiles(),
            source_profile_defaults=store.load_source_profile_defaults(),
        )
        steps = self.build_full_workflow_steps(
            context=context,
            episode_refs=index.episodes,
            all_scope_ids=ids,
            runnable_ids=runnable_ids,
            episode_url_by_id=episode_url_by_id,
            batch_profile=batch_profile,
            profile_by_episode=profile_by_episode,
            lang_hint=lang_hint,
        )
        if steps is None:
            return None
        return list(steps), skipped

    def prepare_segment_and_index_scope_plan_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        context: dict[str, Any],
        lang_hint: str,
        clean_empty_message: str,
        clean_empty_next_step: str,
    ) -> tuple[list[Any], int] | None:
        """
        Prépare le plan "Segmenter+Indexer" pour un scope CLEAN:
        - filtre les épisodes ayant CLEAN,
        - compose les steps segment -> index,
        - retourne `(steps, skipped)`.
        """
        prepared_clean = self.prepare_clean_scope_ids_or_warn(
            ids=ids,
            has_episode_clean=store.has_episode_clean,
            empty_message=clean_empty_message,
            empty_next_step=clean_empty_next_step,
        )
        if prepared_clean is None:
            return None
        ids_with_clean, skipped = prepared_clean
        steps = self.build_segment_and_index_steps(
            context=context,
            episode_refs=index.episodes,
            ids_with_clean=ids_with_clean,
            lang_hint=lang_hint,
        )
        if steps is None:
            return None
        return list(steps), skipped

    def run_full_workflow_scope_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        context: dict[str, Any],
        batch_profile: str,
        lang_hint: str,
        empty_message: str,
        empty_next_step: str | None = None,
        skipped_prefix: str = "Tout faire",
        skipped_reason: str = "sans URL source, RAW ni CLEAN",
    ) -> str | None:
        """
        Prépare puis exécute le plan "Tout faire" pour un scope.

        Retourne le message de statut "épisodes ignorés" (ou `None` si aucun).
        """
        prepared = self.prepare_full_workflow_scope_plan_or_warn(
            ids=ids,
            index=index,
            store=store,
            context=context,
            batch_profile=batch_profile,
            lang_hint=lang_hint,
        )
        if prepared is None:
            return None
        steps, skipped = prepared
        ok = self.run_composed_steps_or_warn(
            steps=steps,
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )
        if not ok:
            return None
        return self.build_skipped_scope_status_message(
            prefix=skipped_prefix,
            skipped=skipped,
            reason=skipped_reason,
        )

    def run_segment_and_index_scope_or_warn(
        self,
        *,
        ids: list[str],
        index: SeriesIndex,
        store: Any,
        context: dict[str, Any],
        lang_hint: str,
        clean_empty_message: str,
        clean_empty_next_step: str,
        empty_message: str,
        empty_next_step: str | None = None,
        skipped_prefix: str = "Segmenter+Indexer",
        skipped_reason: str = "sans CLEAN dans le scope",
    ) -> str | None:
        """
        Prépare puis exécute le plan composé "Segmenter+Indexer" pour un scope CLEAN.

        Retourne le message de statut "épisodes ignorés" (ou `None` si aucun).
        """
        prepared = self.prepare_segment_and_index_scope_plan_or_warn(
            ids=ids,
            index=index,
            store=store,
            context=context,
            lang_hint=lang_hint,
            clean_empty_message=clean_empty_message,
            clean_empty_next_step=clean_empty_next_step,
        )
        if prepared is None:
            return None
        steps, skipped = prepared
        ok = self.run_composed_steps_or_warn(
            steps=steps,
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )
        if not ok:
            return None
        return self.build_skipped_scope_status_message(
            prefix=skipped_prefix,
            skipped=skipped,
            reason=skipped_reason,
        )

    @staticmethod
    def load_status_map_for_index(
        *,
        index: SeriesIndex | None,
        db: Any,
        status_map_loader: Callable[[Any, list[str]], dict[str, str]] = load_episode_status_map,
    ) -> dict[str, str]:
        """Charge la map de statuts pour les épisodes de l'index."""
        if not db or not index or not index.episodes:
            return {}
        episode_ids = [e.episode_id for e in index.episodes]
        return status_map_loader(db, episode_ids)

    def resolve_workflow_snapshot(
        self,
        *,
        index: SeriesIndex,
        store: Any,
        db: Any,
        status_map_loader: Callable[[Any, list[str]], dict[str, str]] = load_episode_status_map,
        compute_status_fn: Callable[..., tuple[Any, list[str]]] = compute_workflow_status,
        advice_builder: Callable[[Any], Any] = build_workflow_advice,
    ) -> tuple[Any, list[str], Any]:
        """Calcule le snapshot workflow (counts, erreurs, advice) pour l'UI Corpus."""
        status_map = self.load_status_map_for_index(
            index=index,
            db=db,
            status_map_loader=status_map_loader,
        )
        counts, error_ids = compute_status_fn(
            index=index,
            store=store,
            db=db,
            status_map=status_map,
        )
        advice = advice_builder(counts)
        return counts, error_ids, advice

    @staticmethod
    def build_workflow_status_line(counts: Any) -> str:
        """Construit la ligne de statut workflow affichée dans l'onglet Corpus."""
        return (
            "Workflow : "
            f"Découverts {counts.n_total} | Téléchargés {counts.n_fetched} | "
            f"Normalisés {counts.n_norm} | Segmentés {counts.n_segmented} | "
            f"Indexés {counts.n_indexed} | Erreurs {counts.n_error} | "
            f"SRT {counts.n_with_srt} | Alignés {counts.n_aligned}"
        )

    @staticmethod
    def resolve_default_scope_action_enabled_from_counts(counts: Any) -> dict[str, bool]:
        """Règle d'activation par défaut des actions selon les compteurs workflow globaux."""
        return {
            "fetch": bool(getattr(counts, "n_total", 0) > 0),
            "normalize": bool(getattr(counts, "n_fetched", 0) > 0),
            "segment": bool(getattr(counts, "n_norm", 0) > 0),
            "run_all": bool(getattr(counts, "n_total", 0) > 0),
            "index": bool(getattr(counts, "n_norm", 0) > 0),
        }

    @staticmethod
    def resolve_error_episode_ids(
        *,
        index: SeriesIndex,
        status_map: dict[str, str],
    ) -> list[str]:
        episode_ids = [e.episode_id for e in index.episodes]
        return [
            eid
            for eid in episode_ids
            if (status_map.get(eid) or "").lower() == EpisodeStatus.ERROR.value
        ]

    def resolve_error_episode_ids_from_index(
        self,
        *,
        index: SeriesIndex | None,
        db: Any,
        status_map_loader: Callable[[Any, list[str]], dict[str, str]] = load_episode_status_map,
    ) -> list[str]:
        """Résout les épisodes en erreur à partir de l'index et de la DB de statut."""
        if not index or not index.episodes:
            return []
        status_map = self.load_status_map_for_index(
            index=index,
            db=db,
            status_map_loader=status_map_loader,
        )
        return self.resolve_error_episode_ids(index=index, status_map=status_map)

    def resolve_selected_retry_ids_or_warn(
        self,
        *,
        selected_episode_id: str | None,
        index: SeriesIndex,
    ) -> list[str] | None:
        """Valide l'épisode sélectionné pour une relance ciblée."""
        eid = self.resolve_selected_error_episode_id_or_warn(
            selected_episode_id=selected_episode_id,
            empty_message="Sélectionnez un épisode en erreur à relancer.",
            empty_next_step="Choisissez une ligne dans la liste « Reprise — Erreurs ».",
        )
        if eid is None:
            return None
        known_ids = {e.episode_id for e in index.episodes}
        if eid not in known_ids:
            self._warn_user(
                f"Épisode introuvable dans l'index: {eid}",
                "Rafraîchissez la liste des erreurs puis réessayez.",
            )
            return None
        return [eid]

    def resolve_all_error_retry_ids_or_warn(
        self,
        *,
        index: SeriesIndex,
        status_map: dict[str, str],
    ) -> list[str] | None:
        """Résout les épisodes en erreur à relancer (mode bulk)."""
        error_ids = self.resolve_error_episode_ids(index=index, status_map=status_map)
        if not error_ids:
            self._warn_user(
                "Aucun épisode en erreur à relancer.",
                "Consultez le panneau erreurs après un job en échec, puis utilisez « Reprendre erreurs ».",
            )
            return None
        return error_ids

    def resolve_all_error_retry_ids_from_index_db_or_warn(
        self,
        *,
        index: SeriesIndex,
        db: Any,
        status_map_loader: Callable[[Any, list[str]], dict[str, str]] = load_episode_status_map,
    ) -> list[str] | None:
        """Résout et valide les épisodes en erreur à relancer depuis la DB."""
        error_ids = self.resolve_error_episode_ids_from_index(
            index=index,
            db=db,
            status_map_loader=status_map_loader,
        )
        if not error_ids:
            self._warn_user(
                "Aucun épisode en erreur à relancer.",
                "Consultez le panneau erreurs après un job en échec, puis utilisez « Reprendre erreurs ».",
            )
            return None
        return error_ids

    def resolve_selected_error_episode_id_or_warn(
        self,
        *,
        selected_episode_id: str | None,
        empty_message: str,
        empty_next_step: str | None = None,
    ) -> str | None:
        """Valide qu'un épisode est sélectionné dans la liste d'erreurs."""
        eid = (selected_episode_id or "").strip()
        if not eid:
            self._warn_user(empty_message, empty_next_step)
            return None
        return eid

    def run_selected_error_callback_or_warn(
        self,
        *,
        selected_episode_id: str | None,
        callback: Callable[[str], None],
        empty_message: str,
        empty_next_step: str | None = None,
    ) -> bool:
        """
        Résout l'épisode d'erreur sélectionné puis exécute un callback (Inspecteur/Logs...).

        Retourne `True` si le callback a été exécuté.
        """
        eid = self.resolve_selected_error_episode_id_or_warn(
            selected_episode_id=selected_episode_id,
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )
        if eid is None:
            return False
        callback(eid)
        return True

    def run_retry_selected_error_or_warn(
        self,
        *,
        store: Any,
        db: Any,
        context: dict[str, Any],
        selected_episode_id: str | None,
        batch_profile: str,
        lang_hint: str,
        empty_message: str = "Aucune opération à exécuter.",
        empty_next_step: str | None = "Ajustez le scope ou préparez des épisodes (URL/RAW/CLEAN) avant relance.",
    ) -> str | None:
        """Relance un épisode en erreur sélectionné avec le workflow complet."""
        resolved = self.resolve_project_with_index_or_warn(
            store=store,
            db=db,
            context=context,
            require_db=True,
        )
        if resolved is None:
            return None
        store_ok, _db_ok, context_ok, index_ok = resolved
        retry_ids = self.resolve_selected_retry_ids_or_warn(
            selected_episode_id=selected_episode_id,
            index=index_ok,
        )
        if retry_ids is None:
            return None
        return self.run_full_workflow_scope_or_warn(
            ids=retry_ids,
            index=index_ok,
            store=store_ok,
            context=context_ok,
            batch_profile=batch_profile,
            lang_hint=lang_hint,
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )

    def run_retry_all_errors_or_warn(
        self,
        *,
        store: Any,
        db: Any,
        context: dict[str, Any],
        batch_profile: str,
        lang_hint: str,
        status_map_loader: Callable[[Any, list[str]], dict[str, str]] = load_episode_status_map,
        empty_message: str = "Aucune opération à exécuter.",
        empty_next_step: str | None = "Ajustez le scope ou préparez des épisodes (URL/RAW/CLEAN) avant relance.",
    ) -> str | None:
        """Relance tous les épisodes en erreur (depuis index+DB) avec le workflow complet."""
        resolved = self.resolve_project_with_index_or_warn(
            store=store,
            db=db,
            context=context,
            require_db=True,
        )
        if resolved is None:
            return None
        store_ok, db_ok, context_ok, index_ok = resolved
        retry_ids = self.resolve_all_error_retry_ids_from_index_db_or_warn(
            index=index_ok,
            db=db_ok,
            status_map_loader=status_map_loader,
        )
        if retry_ids is None:
            return None
        return self.run_full_workflow_scope_or_warn(
            ids=retry_ids,
            index=index_ok,
            store=store_ok,
            context=context_ok,
            batch_profile=batch_profile,
            lang_hint=lang_hint,
            empty_message=empty_message,
            empty_next_step=empty_next_step,
        )

    def build_full_workflow_steps(
        self,
        *,
        context: dict[str, Any],
        episode_refs: list[EpisodeRef],
        all_scope_ids: list[str],
        runnable_ids: list[str],
        episode_url_by_id: dict[str, str],
        batch_profile: str,
        profile_by_episode: dict[str, str],
        lang_hint: str,
    ) -> list[Any] | None:
        """Construit le plan composé fetch -> normalize -> segment -> index pour un scope."""
        fetch_scope = WorkflowScope.selection(all_scope_ids)
        fetch_steps = self.build_action_steps_or_warn(
            action_id=WorkflowActionId.FETCH_EPISODES,
            context=context,
            scope=fetch_scope,
            episode_refs=episode_refs,
            options={"episode_url_by_id": episode_url_by_id},
        )
        if fetch_steps is None:
            return None
        if not runnable_ids:
            return list(fetch_steps)
        runnable_scope = WorkflowScope.selection(runnable_ids)
        normalize_steps = self.build_action_steps_or_warn(
            action_id=WorkflowActionId.NORMALIZE_EPISODES,
            context=context,
            scope=runnable_scope,
            episode_refs=episode_refs,
            options={
                "default_profile_id": batch_profile,
                "profile_by_episode": profile_by_episode,
            },
        )
        if normalize_steps is None:
            return None
        segment_steps = self.build_action_steps_or_warn(
            action_id=WorkflowActionId.SEGMENT_EPISODES,
            context=context,
            scope=runnable_scope,
            episode_refs=episode_refs,
            options={"lang_hint": lang_hint},
        )
        if segment_steps is None:
            return None
        index_steps = self.build_action_steps_or_warn(
            action_id=WorkflowActionId.BUILD_DB_INDEX,
            context=context,
            scope=runnable_scope,
            episode_refs=episode_refs,
            options=None,
        )
        if index_steps is None:
            return None
        return list(fetch_steps) + list(normalize_steps) + list(segment_steps) + list(index_steps)

    def build_segment_and_index_steps(
        self,
        *,
        context: dict[str, Any],
        episode_refs: list[EpisodeRef],
        ids_with_clean: list[str],
        lang_hint: str,
    ) -> list[Any] | None:
        """Construit le plan composé segment -> index sur un scope CLEAN."""
        scope = WorkflowScope.selection(ids_with_clean)
        segment_steps = self.build_action_steps_or_warn(
            action_id=WorkflowActionId.SEGMENT_EPISODES,
            context=context,
            scope=scope,
            episode_refs=episode_refs,
            options={"lang_hint": lang_hint},
        )
        if segment_steps is None:
            return None
        index_steps = self.build_action_steps_or_warn(
            action_id=WorkflowActionId.BUILD_DB_INDEX,
            context=context,
            scope=scope,
            episode_refs=episode_refs,
            options=None,
        )
        if index_steps is None:
            return None
        return list(segment_steps) + list(index_steps)
