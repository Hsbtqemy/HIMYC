"""Contrôleur léger pour l'exécution des actions workflow du Corpus."""

from __future__ import annotations

from typing import Any, Callable

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
