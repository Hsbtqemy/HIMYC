"""Scope resolution helpers used by the workflow service."""

from __future__ import annotations

from collections import OrderedDict

from howimetyourcorpus.core.models import EpisodeRef
from howimetyourcorpus.core.workflow.contracts import WorkflowScope, WorkflowScopeError, WorkflowScopeKind


class ScopeResolver:
    """Resolves a `WorkflowScope` against available episodes."""

    @staticmethod
    def resolve_episode_ids(scope: WorkflowScope, episode_refs: list[EpisodeRef]) -> list[str]:
        """
        Resolve scope to canonical episode ids.

        Returns ids in deterministic order:
        - `all` / `season` follow episode_refs order
        - `selection` follows provided order, de-duplicated
        - `current` returns a single id
        """
        available_ids = {e.episode_id for e in episode_refs}

        if scope.kind == WorkflowScopeKind.ALL:
            return [e.episode_id for e in episode_refs]

        if scope.kind == WorkflowScopeKind.SEASON:
            if scope.season is None:
                raise WorkflowScopeError("Scope season requires `season` value")
            return [e.episode_id for e in episode_refs if e.season == scope.season]

        if scope.kind == WorkflowScopeKind.CURRENT:
            if not scope.episode_id:
                raise WorkflowScopeError("Scope current requires `episode_id`")
            if scope.episode_id not in available_ids:
                raise WorkflowScopeError(f"Unknown episode in scope: {scope.episode_id}")
            return [scope.episode_id]

        if scope.kind == WorkflowScopeKind.SELECTION:
            if not scope.episode_ids:
                return []
            ordered_unique: OrderedDict[str, None] = OrderedDict()
            for eid in scope.episode_ids:
                if eid in available_ids and eid not in ordered_unique:
                    ordered_unique[eid] = None
            return list(ordered_unique.keys())

        raise WorkflowScopeError(f"Unsupported scope: {scope.kind}")
