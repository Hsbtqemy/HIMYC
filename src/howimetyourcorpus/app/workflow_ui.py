"""Helpers UI pour la construction des plans workflow."""

from __future__ import annotations

from typing import Any, Callable

from howimetyourcorpus.core.models import EpisodeRef
from howimetyourcorpus.core.workflow import (
    WorkflowActionError,
    WorkflowActionId,
    WorkflowOptionError,
    WorkflowScope,
    WorkflowScopeError,
    WorkflowService,
)


def build_workflow_steps_or_warn(
    *,
    workflow_service: WorkflowService,
    action_id: WorkflowActionId,
    context: dict[str, Any],
    scope: WorkflowScope,
    episode_refs: list[EpisodeRef],
    options: dict[str, Any] | None = None,
    warn_precondition_message: Callable[[str], None],
) -> list[Any] | None:
    """Construit les steps d'un plan workflow, ou avertit l'utilisateur sur erreur."""
    try:
        plan = workflow_service.build_plan(
            action_id=action_id,
            context=context,
            scope=scope,
            episode_refs=episode_refs,
            options=options,
        )
    except (WorkflowActionError, WorkflowScopeError, WorkflowOptionError) as exc:
        warn_precondition_message(str(exc))
        return None
    return list(plan.steps)
