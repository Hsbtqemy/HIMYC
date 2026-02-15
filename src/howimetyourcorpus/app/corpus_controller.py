"""Contrôleur léger pour l'exécution des actions workflow du Corpus."""

from __future__ import annotations

from typing import Any, Callable

from howimetyourcorpus.app.corpus_scope import normalize_scope_mode
from howimetyourcorpus.app.workflow_ui import build_workflow_steps_or_warn
from howimetyourcorpus.core.models import EpisodeRef
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
