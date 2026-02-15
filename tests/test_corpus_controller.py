"""Tests du contrôleur workflow Corpus."""

from __future__ import annotations

from howimetyourcorpus.app.corpus_controller import CorpusWorkflowController
from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex
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


def test_resolve_scope_and_ids_or_warn_selection_and_all() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    resolved_selection = controller.resolve_scope_and_ids_or_warn(
        scope_mode="selection",
        all_episode_ids=["S01E01", "S01E02"],
        current_episode_id=None,
        selected_episode_ids=["S01E02"],
        season=None,
        get_episode_ids_for_season=lambda _season: [],
    )
    resolved_all = controller.resolve_scope_and_ids_or_warn(
        scope_mode="all",
        all_episode_ids=["S01E01", "S01E02"],
        current_episode_id=None,
        selected_episode_ids=[],
        season=None,
        get_episode_ids_for_season=lambda _season: [],
    )
    assert resolved_selection == (WorkflowScope.selection(["S01E02"]), ["S01E02"])
    assert resolved_all == (WorkflowScope.all(), ["S01E01", "S01E02"])
    assert warned == []


def test_resolve_scope_and_ids_or_warn_reports_missing_current() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    resolved = controller.resolve_scope_and_ids_or_warn(
        scope_mode="current",
        all_episode_ids=["S01E01", "S01E02"],
        current_episode_id=None,
        selected_episode_ids=["S01E02"],
        season=None,
        get_episode_ids_for_season=lambda _season: [],
    )
    assert resolved is None
    assert warned == [
        (
            "Scope « Épisode courant »: sélectionnez une ligne (ou cochez un épisode).",
            "Sélectionnez un épisode dans la liste ou cochez sa case.",
        )
    ]


def test_resolve_project_context_or_warn_requires_config_and_store() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    resolved = controller.resolve_project_context_or_warn(
        store=None,
        db=object(),
        context={},
        require_db=False,
    )
    assert resolved is None
    assert warned == [
        (
            "Ouvrez un projet d'abord.",
            "Pilotage > Projet: ouvrez ou initialisez un projet.",
        )
    ]


def test_resolve_project_context_or_warn_allows_without_db_when_not_required() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    store = object()
    context = {"config": object()}
    resolved = controller.resolve_project_context_or_warn(
        store=store,
        db=None,
        context=context,
        require_db=False,
    )
    assert resolved == (store, None, context)
    assert warned == []


def test_resolve_index_or_warn_requires_non_empty_index() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    resolved = controller.resolve_index_or_warn(index=None)
    assert resolved is None
    assert warned == [
        (
            "Découvrez d'abord les épisodes.",
            "Pilotage > Corpus: cliquez sur « Découvrir épisodes ».",
        )
    ]


def test_resolve_ids_with_source_url_or_warn() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    ok = controller.resolve_ids_with_source_url_or_warn(
        ids=["S01E01", "S01E02"],
        episode_url_by_id={"S01E01": "https://src/1", "S01E02": ""},
    )
    assert ok == ["S01E01"]
    ko = controller.resolve_ids_with_source_url_or_warn(
        ids=["S01E02"],
        episode_url_by_id={"S01E02": ""},
    )
    assert ko is None
    assert warned[-1] == (
        "Aucun épisode du scope choisi n'a d'URL source.",
        "Lancez « Découvrir épisodes » ou ajoutez des épisodes avec URL valide.",
    )


def test_resolve_ids_with_raw_and_clean_or_warn() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    assert controller.resolve_ids_with_raw_or_warn(
        ids=["S01E01", "S01E02"],
        has_episode_raw=lambda eid: eid == "S01E02",
    ) == ["S01E02"]
    assert controller.resolve_ids_with_clean_or_warn(
        ids=["S01E01", "S01E02"],
        has_episode_clean=lambda eid: eid == "S01E01",
        empty_message="no clean",
        empty_next_step="normalize first",
    ) == ["S01E01"]
    no_raw = controller.resolve_ids_with_raw_or_warn(
        ids=["S01E03"],
        has_episode_raw=lambda _eid: False,
    )
    no_clean = controller.resolve_ids_with_clean_or_warn(
        ids=["S01E03"],
        has_episode_clean=lambda _eid: False,
        empty_message="no clean",
        empty_next_step="normalize first",
    )
    assert no_raw is None
    assert no_clean is None
    assert warned[-2] == (
        "Aucun épisode du scope choisi n'a de transcript RAW. Téléchargez d'abord ce scope.",
        "Pilotage > Corpus: lancez « Télécharger » sur ce scope.",
    )
    assert warned[-1] == ("no clean", "normalize first")


def test_resolve_runnable_ids_for_full_workflow_or_warn() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    assert controller.resolve_runnable_ids_for_full_workflow_or_warn(
        ids=["S01E01", "S01E02"],
        episode_url_by_id={"S01E01": "", "S01E02": "https://src/2"},
        has_episode_raw=lambda _eid: False,
        has_episode_clean=lambda _eid: False,
    ) == ["S01E02"]
    no_ids = controller.resolve_runnable_ids_for_full_workflow_or_warn(
        ids=[],
        episode_url_by_id={},
        has_episode_raw=lambda _eid: False,
        has_episode_clean=lambda _eid: False,
    )
    none_runnable = controller.resolve_runnable_ids_for_full_workflow_or_warn(
        ids=["S01E03"],
        episode_url_by_id={"S01E03": ""},
        has_episode_raw=lambda _eid: False,
        has_episode_clean=lambda _eid: False,
    )
    assert no_ids is None
    assert none_runnable is None


def test_resolve_scope_context_or_warn_success() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    store = object()
    db = object()
    context = {"config": object()}
    index = SeriesIndex("s", "u", episodes=_sample_episode_refs())
    resolved = controller.resolve_scope_context_or_warn(
        store=store,
        db=db,
        context=context,
        index=index,
        require_db=True,
        scope_mode="all",
        all_episode_ids=["S01E01"],
        current_episode_id=None,
        selected_episode_ids=[],
        season=None,
        get_episode_ids_for_season=lambda _season: [],
    )
    assert resolved is not None
    assert resolved[0] is store
    assert resolved[1] is db
    assert resolved[2] is context
    assert resolved[3] is index
    assert resolved[4] == WorkflowScope.all()
    assert resolved[5] == ["S01E01"]
    assert warned == []


def test_resolve_scope_context_or_warn_fails_on_empty_index() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    resolved = controller.resolve_scope_context_or_warn(
        store=object(),
        db=object(),
        context={"config": object()},
        index=SeriesIndex("s", "u", episodes=[]),
        require_db=False,
        scope_mode="all",
        all_episode_ids=[],
        current_episode_id=None,
        selected_episode_ids=[],
        season=None,
        get_episode_ids_for_season=lambda _season: [],
    )
    assert resolved is None
    assert warned == [
        (
            "Découvrez d'abord les épisodes.",
            "Pilotage > Corpus: cliquez sur « Découvrir épisodes ».",
        )
    ]


def test_resolve_error_episode_ids_filters_only_error_status() -> None:
    index = SeriesIndex(
        "s",
        "u",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "Pilot", "u"),
            EpisodeRef("S01E02", 1, 2, "Purple", "u"),
            EpisodeRef("S01E03", 1, 3, "Liberty", "u"),
        ],
    )
    status_map = {
        "S01E01": "indexed",
        "S01E02": "ERROR",
        "S01E03": "error",
    }
    error_ids = CorpusWorkflowController.resolve_error_episode_ids(
        index=index,
        status_map=status_map,
    )
    assert error_ids == ["S01E02", "S01E03"]
