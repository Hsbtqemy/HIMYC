"""Tests du contrôleur workflow Corpus."""

from __future__ import annotations

from howimetyourcorpus.app.corpus_controller import CorpusWorkflowController
from howimetyourcorpus.core.models import EpisodeRef
from howimetyourcorpus.core.workflow import WorkflowActionId, WorkflowScope


def _sample_episode_refs() -> list[EpisodeRef]:
    return [EpisodeRef("S01E01", 1, 1, "Pilot", "https://src/1")]


def test_build_action_steps_or_warn_delegates_to_step_builder() -> None:
    calls: dict[str, object] = {}

    def _step_builder(**kwargs):
        calls.update(kwargs)
        return ["step-1", "step-2"]

    ran: list[list[object]] = []
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda steps: ran.append(list(steps)),
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=_step_builder,
    )

    steps = controller.build_action_steps_or_warn(
        action_id=WorkflowActionId.FETCH_EPISODES,
        context={"config": object()},
        scope=WorkflowScope.selection(["S01E01"]),
        episode_refs=_sample_episode_refs(),
        options={"x": 1},
    )

    assert steps == ["step-1", "step-2"]
    assert calls["action_id"] == WorkflowActionId.FETCH_EPISODES
    assert calls["scope"] == WorkflowScope.selection(["S01E01"])
    assert calls["episode_refs"] == _sample_episode_refs()
    assert calls["options"] == {"x": 1}
    assert callable(calls["warn_precondition_message"])
    assert ran == []
    assert warned == []


def test_run_action_for_scope_warns_when_no_steps() -> None:
    warned: list[tuple[str, str | None]] = []
    ran: list[list[object]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda steps: ran.append(list(steps)),
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )

    ok = controller.run_action_for_scope(
        action_id=WorkflowActionId.BUILD_DB_INDEX,
        context={"config": object()},
        scope=WorkflowScope.selection(["S01E01"]),
        episode_refs=_sample_episode_refs(),
        options=None,
        empty_message="Aucun step",
        empty_next_step="Lancer normalisation",
    )

    assert ok is False
    assert warned == [("Aucun step", "Lancer normalisation")]
    assert ran == []


def test_run_action_for_scope_runs_steps_on_success() -> None:
    warned: list[tuple[str, str | None]] = []
    ran: list[list[object]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda steps: ran.append(list(steps)),
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: ["s1"],
    )

    ok = controller.run_action_for_scope(
        action_id=WorkflowActionId.SEGMENT_EPISODES,
        context={"config": object()},
        scope=WorkflowScope.selection(["S01E01"]),
        episode_refs=_sample_episode_refs(),
        options={"lang_hint": "en"},
        empty_message="unused",
    )

    assert ok is True
    assert ran == [["s1"]]
    assert warned == []


def test_run_action_for_scope_stops_when_step_builder_returns_none() -> None:
    warned: list[tuple[str, str | None]] = []
    ran: list[list[object]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda steps: ran.append(list(steps)),
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: None,
    )

    ok = controller.run_action_for_scope(
        action_id=WorkflowActionId.NORMALIZE_EPISODES,
        context={"config": object()},
        scope=WorkflowScope.selection(["S01E01"]),
        episode_refs=_sample_episode_refs(),
        options=None,
        empty_message="unused",
    )

    assert ok is False
    assert ran == []
    assert warned == []


def test_build_full_workflow_steps_composes_expected_order() -> None:
    calls: list[WorkflowActionId] = []

    def _step_builder(**kwargs):
        action_id = kwargs["action_id"]
        calls.append(action_id)
        return [f"step:{action_id.value}"]

    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda _msg, _next_step=None: None,
        step_builder=_step_builder,
    )

    steps = controller.build_full_workflow_steps(
        context={"config": object()},
        episode_refs=_sample_episode_refs(),
        all_scope_ids=["S01E01"],
        runnable_ids=["S01E01"],
        episode_url_by_id={"S01E01": "https://src/1"},
        batch_profile="default_en_v1",
        profile_by_episode={"S01E01": "default_en_v1"},
        lang_hint="en",
    )

    assert steps == [
        "step:fetch_episodes",
        "step:normalize_episodes",
        "step:segment_episodes",
        "step:build_db_index",
    ]
    assert calls == [
        WorkflowActionId.FETCH_EPISODES,
        WorkflowActionId.NORMALIZE_EPISODES,
        WorkflowActionId.SEGMENT_EPISODES,
        WorkflowActionId.BUILD_DB_INDEX,
    ]


def test_build_segment_and_index_steps_returns_none_on_builder_failure() -> None:
    def _step_builder(**kwargs):
        action_id = kwargs["action_id"]
        if action_id == WorkflowActionId.BUILD_DB_INDEX:
            return None
        return ["segment-step"]

    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda _msg, _next_step=None: None,
        step_builder=_step_builder,
    )

    steps = controller.build_segment_and_index_steps(
        context={"config": object()},
        episode_refs=_sample_episode_refs(),
        ids_with_clean=["S01E01"],
        lang_hint="en",
    )

    assert steps is None
