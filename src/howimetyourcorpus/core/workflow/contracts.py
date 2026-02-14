"""Core contracts for workflow actions, scopes and execution plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from howimetyourcorpus.core.pipeline.steps import Step


class WorkflowScopeKind(str, Enum):
    """Supported scope modes for workflow actions."""

    CURRENT = "current"
    SELECTION = "selection"
    SEASON = "season"
    ALL = "all"


@dataclass(frozen=True)
class WorkflowScope:
    """Scope requested by the UI/user for a workflow action."""

    kind: WorkflowScopeKind
    episode_id: str | None = None
    episode_ids: tuple[str, ...] = field(default_factory=tuple)
    season: int | None = None

    @classmethod
    def current(cls, episode_id: str) -> "WorkflowScope":
        return cls(kind=WorkflowScopeKind.CURRENT, episode_id=episode_id)

    @classmethod
    def selection(cls, episode_ids: list[str]) -> "WorkflowScope":
        return cls(kind=WorkflowScopeKind.SELECTION, episode_ids=tuple(episode_ids))

    @classmethod
    def season_scope(cls, season: int) -> "WorkflowScope":
        return cls(kind=WorkflowScopeKind.SEASON, season=season)

    @classmethod
    def all(cls) -> "WorkflowScope":
        return cls(kind=WorkflowScopeKind.ALL)


class WorkflowActionId(str, Enum):
    """Action identifiers exposed by the workflow service."""

    FETCH_EPISODES = "fetch_episodes"
    NORMALIZE_EPISODES = "normalize_episodes"
    SEGMENT_EPISODES = "segment_episodes"
    BUILD_DB_INDEX = "build_db_index"


@dataclass(frozen=True)
class WorkflowPlan:
    """Concrete, resolved workflow plan ready to run."""

    action_id: WorkflowActionId
    scope: WorkflowScope
    episode_ids: tuple[str, ...]
    steps: tuple[Step, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


class WorkflowActionError(ValueError):
    """Raised when an unknown action is requested."""


class WorkflowScopeError(ValueError):
    """Raised when a scope cannot be resolved."""


class WorkflowOptionError(ValueError):
    """Raised when action options are missing/invalid."""
