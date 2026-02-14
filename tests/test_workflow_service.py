"""Tests for workflow service plan building."""

from __future__ import annotations

import pytest

from howimetyourcorpus.core.models import EpisodeRef, ProjectConfig
from howimetyourcorpus.core.pipeline.tasks import BuildDbIndexStep, NormalizeEpisodeStep
from howimetyourcorpus.core.storage.project_store import ProjectStore
from howimetyourcorpus.core.workflow import (
    WorkflowActionId,
    WorkflowOptionError,
    WorkflowScope,
    WorkflowService,
)


def _context(tmp_path):
    config = ProjectConfig(
        project_name="wf",
        root_dir=tmp_path,
        source_id="subslikescript",
        series_url="",
    )
    ProjectStore.init_project(config)
    store = ProjectStore(tmp_path)
    return {"config": config, "store": store}


def _refs() -> list[EpisodeRef]:
    return [
        EpisodeRef("S01E01", season=1, episode=1, title="Pilot", url="u1"),
        EpisodeRef("S01E02", season=1, episode=2, title="Purple", url="u2"),
    ]


def test_workflow_service_builds_normalize_plan_with_profile_overrides(tmp_path) -> None:
    context = _context(tmp_path)
    service = WorkflowService()

    plan = service.build_plan(
        action_id=WorkflowActionId.NORMALIZE_EPISODES,
        context=context,
        scope=WorkflowScope.selection(["S01E02", "S01E01"]),
        episode_refs=_refs(),
        options={
            "default_profile_id": "default_en_v1",
            "profile_by_episode": {
                "S01E02": "aggressive_v1",
            },
        },
    )

    assert plan.action_id == WorkflowActionId.NORMALIZE_EPISODES
    assert list(plan.episode_ids) == ["S01E02", "S01E01"]
    assert len(plan.steps) == 2
    assert all(isinstance(step, NormalizeEpisodeStep) for step in plan.steps)
    assert plan.steps[0].profile_id == "aggressive_v1"
    assert plan.steps[1].profile_id == "default_en_v1"


def test_workflow_service_fetch_requires_episode_url_mapping(tmp_path) -> None:
    context = _context(tmp_path)
    service = WorkflowService()

    with pytest.raises(WorkflowOptionError):
        service.build_plan(
            action_id=WorkflowActionId.FETCH_EPISODES,
            context=context,
            scope=WorkflowScope.selection(["S01E01"]),
            episode_refs=_refs(),
            options={},
        )


def test_workflow_service_build_db_index_uses_episode_scope(tmp_path) -> None:
    context = _context(tmp_path)
    service = WorkflowService()

    plan = service.build_plan(
        action_id=WorkflowActionId.BUILD_DB_INDEX,
        context=context,
        scope=WorkflowScope.selection(["S01E02", "S01E01"]),
        episode_refs=_refs(),
    )

    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert isinstance(step, BuildDbIndexStep)
    assert step.episode_ids == ["S01E02", "S01E01"]


def test_workflow_service_build_db_index_can_fallback_to_all_clean_files(tmp_path) -> None:
    context = _context(tmp_path)
    service = WorkflowService()

    plan = service.build_plan(
        action_id=WorkflowActionId.BUILD_DB_INDEX,
        context=context,
        scope=WorkflowScope.all(),
        episode_refs=[],
        options={"allow_all_with_clean": True},
    )

    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert isinstance(step, BuildDbIndexStep)
    assert step.episode_ids is None
