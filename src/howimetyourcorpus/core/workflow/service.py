"""Workflow service: resolve scope, pick action and build runnable plan."""

from __future__ import annotations

from typing import Any, Mapping

from howimetyourcorpus.core.models import EpisodeRef
from howimetyourcorpus.core.pipeline.context import PipelineContext
from howimetyourcorpus.core.workflow.actions import ACTION_CATALOG, WorkflowActionSpec
from howimetyourcorpus.core.workflow.contracts import (
    WorkflowActionError,
    WorkflowActionId,
    WorkflowPlan,
    WorkflowScope,
    WorkflowScopeError,
    WorkflowScopeKind,
)
from howimetyourcorpus.core.workflow.scope import ScopeResolver


class WorkflowService:
    """Builds workflow plans from declarative actions and requested scope."""

    def __init__(self, catalog: Mapping[WorkflowActionId, WorkflowActionSpec] | None = None):
        self._catalog = dict(catalog or ACTION_CATALOG)

    def build_plan(
        self,
        action_id: WorkflowActionId | str,
        context: PipelineContext,
        scope: WorkflowScope,
        episode_refs: list[EpisodeRef],
        options: Mapping[str, Any] | None = None,
    ) -> WorkflowPlan:
        """Resolve and build a runnable plan for one action."""
        if "config" not in context or "store" not in context:
            raise WorkflowActionError("Pipeline context must contain `config` and `store`")

        action_enum = self._normalize_action_id(action_id)
        spec = self._catalog.get(action_enum)
        if spec is None:
            raise WorkflowActionError(f"Unknown workflow action: {action_enum}")

        resolved_ids = ScopeResolver.resolve_episode_ids(scope, episode_refs)
        if not resolved_ids and scope.kind != WorkflowScopeKind.ALL:
            raise WorkflowScopeError(f"No episode resolved for scope: {scope.kind.value}")

        safe_options: Mapping[str, Any] = options or {}
        steps = spec.build_steps(context, resolved_ids, safe_options)

        return WorkflowPlan(
            action_id=action_enum,
            scope=scope,
            episode_ids=tuple(resolved_ids),
            steps=tuple(steps),
            metadata={"action_label": spec.label},
        )

    @staticmethod
    def _normalize_action_id(action_id: WorkflowActionId | str) -> WorkflowActionId:
        if isinstance(action_id, WorkflowActionId):
            return action_id
        try:
            return WorkflowActionId(action_id)
        except ValueError as exc:
            raise WorkflowActionError(f"Unknown workflow action id: {action_id}") from exc
