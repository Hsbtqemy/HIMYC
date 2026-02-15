"""Contrôleur léger pour l'exécution des actions workflow du Corpus."""

from __future__ import annotations

from typing import Any, Callable

from howimetyourcorpus.app.corpus_scope import (
    filter_ids_with_clean,
    filter_ids_with_raw,
    filter_ids_with_source_url,
    filter_runnable_ids_for_full_workflow,
    normalize_scope_mode,
)
from howimetyourcorpus.app.workflow_ui import build_workflow_steps_or_warn
from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus, SeriesIndex
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
