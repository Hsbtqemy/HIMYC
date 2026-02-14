"""Tests des helpers UI de planification workflow."""

from __future__ import annotations

from types import SimpleNamespace

from howimetyourcorpus.app.workflow_ui import build_workflow_steps_or_warn
from howimetyourcorpus.core.models import EpisodeRef
from howimetyourcorpus.core.workflow import WorkflowActionId, WorkflowScope, WorkflowScopeError


def _refs() -> list[EpisodeRef]:
    return [EpisodeRef("S01E01", season=1, episode=1, title="Pilot", url="u1")]


class _ServiceOk:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def build_plan(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(steps=("a", "b"))


class _ServiceFail:
    def build_plan(self, **kwargs):
        raise WorkflowScopeError("No episode resolved for scope: current")


def test_build_workflow_steps_or_warn_returns_steps_and_forwards_params() -> None:
    service = _ServiceOk()
    warnings: list[str] = []
    options = {"lang_hint": "en"}
    result = build_workflow_steps_or_warn(
        workflow_service=service,  # type: ignore[arg-type]
        action_id=WorkflowActionId.SEGMENT_EPISODES,
        context={"config": object(), "store": object()},
        scope=WorkflowScope.current("S01E01"),
        episode_refs=_refs(),
        options=options,
        warn_precondition_message=warnings.append,
    )

    assert result == ["a", "b"]
    assert warnings == []
    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["action_id"] == WorkflowActionId.SEGMENT_EPISODES
    assert call["scope"] == WorkflowScope.current("S01E01")
    assert call["options"] == options


def test_build_workflow_steps_or_warn_warns_and_returns_none_on_error() -> None:
    warnings: list[str] = []
    result = build_workflow_steps_or_warn(
        workflow_service=_ServiceFail(),  # type: ignore[arg-type]
        action_id=WorkflowActionId.BUILD_DB_INDEX,
        context={"config": object(), "store": object()},
        scope=WorkflowScope.current("S99E99"),
        episode_refs=_refs(),
        options=None,
        warn_precondition_message=warnings.append,
    )

    assert result is None
    assert warnings == ["No episode resolved for scope: current"]
