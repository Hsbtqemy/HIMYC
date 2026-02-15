"""Tests du contrôleur workflow Corpus."""

from __future__ import annotations

from pathlib import Path

from howimetyourcorpus.app.corpus_controller import CorpusWorkflowController
from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex
from howimetyourcorpus.core.pipeline.tasks import FetchAndMergeSeriesIndexStep, FetchSeriesIndexStep
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


def test_run_composed_steps_or_warn_executes_when_non_empty() -> None:
    warned: list[tuple[str, str | None]] = []
    ran: list[list[object]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda steps: ran.append(list(steps)),
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    ok = controller.run_composed_steps_or_warn(
        steps=["s1", "s2"],
        empty_message="unused",
    )
    assert ok is True
    assert ran == [["s1", "s2"]]
    assert warned == []


def test_run_composed_steps_or_warn_warns_when_empty() -> None:
    warned: list[tuple[str, str | None]] = []
    ran: list[list[object]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda steps: ran.append(list(steps)),
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    ok = controller.run_composed_steps_or_warn(
        steps=[],
        empty_message="Aucune opération à exécuter.",
        empty_next_step="Préparez des épisodes.",
    )
    assert ok is False
    assert ran == []
    assert warned == [("Aucune opération à exécuter.", "Préparez des épisodes.")]


def test_build_skipped_scope_status_message() -> None:
    assert (
        CorpusWorkflowController.build_skipped_scope_status_message(
            prefix="Téléchargement",
            skipped=2,
            reason="URL source absente",
        )
        == "Téléchargement: 2 épisode(s) ignoré(s) (URL source absente)."
    )
    assert (
        CorpusWorkflowController.build_skipped_scope_status_message(
            prefix="Téléchargement",
            skipped=0,
            reason="URL source absente",
        )
        is None
    )


def test_resolve_scope_action_availability_returns_enabled_and_reasons() -> None:
    enabled, reasons = CorpusWorkflowController.resolve_scope_action_availability(
        ids=["S01E01", "S01E02"],
        capabilities={
            "S01E01": (True, False, False, True),
            "S01E02": (False, True, True, True),
        },
    )
    assert enabled == {
        "fetch": True,
        "normalize": True,
        "segment": True,
        "run_all": True,
        "index": True,
    }
    assert reasons == {
        "fetch": None,
        "normalize": None,
        "segment": None,
        "run_all": None,
        "index": None,
    }


def test_resolve_scope_action_availability_sets_unavailable_reasons() -> None:
    enabled, reasons = CorpusWorkflowController.resolve_scope_action_availability(
        ids=["S01E03"],
        capabilities={"S01E03": (False, False, False, False)},
    )
    assert enabled == {
        "fetch": False,
        "normalize": False,
        "segment": False,
        "run_all": False,
        "index": False,
    }
    assert reasons == {
        "fetch": "Action indisponible: aucune URL source disponible dans le scope.",
        "normalize": "Action indisponible: aucun transcript RAW dans le scope.",
        "segment": "Action indisponible: aucun fichier CLEAN dans le scope.",
        "run_all": "Action indisponible: aucun épisode exécutable (URL source, RAW ou CLEAN) dans le scope.",
        "index": "Action indisponible: aucun fichier CLEAN dans le scope.",
    }


def test_resolve_scope_action_ui_state_handles_global_unavailable_cases() -> None:
    enabled, reasons, unavailable = CorpusWorkflowController.resolve_scope_action_ui_state(
        has_index=False,
        has_store=True,
        ids=[],
        capabilities={},
    )
    assert enabled == {
        "fetch": False,
        "normalize": False,
        "segment": False,
        "run_all": False,
        "index": False,
    }
    assert reasons == {}
    assert unavailable == "Action indisponible: aucun épisode dans le corpus."

    enabled, reasons, unavailable = CorpusWorkflowController.resolve_scope_action_ui_state(
        has_index=True,
        has_store=False,
        ids=["S01E01"],
        capabilities={},
    )
    assert enabled == {
        "fetch": False,
        "normalize": False,
        "segment": False,
        "run_all": False,
        "index": False,
    }
    assert reasons == {}
    assert unavailable == "Action indisponible: ouvrez un projet d'abord."

    enabled, reasons, unavailable = CorpusWorkflowController.resolve_scope_action_ui_state(
        has_index=True,
        has_store=True,
        ids=[],
        capabilities={},
    )
    assert enabled == {
        "fetch": False,
        "normalize": False,
        "segment": False,
        "run_all": False,
        "index": False,
    }
    assert reasons == {}
    assert unavailable == "Action indisponible: aucun épisode dans le scope courant."


def test_resolve_scope_action_ui_state_delegates_to_availability_when_ready() -> None:
    enabled, reasons, unavailable = CorpusWorkflowController.resolve_scope_action_ui_state(
        has_index=True,
        has_store=True,
        ids=["S01E01"],
        capabilities={"S01E01": (True, False, False, True)},
    )
    assert enabled == {
        "fetch": True,
        "normalize": False,
        "segment": False,
        "run_all": True,
        "index": False,
    }
    assert reasons["fetch"] is None
    assert reasons["run_all"] is None
    assert reasons["normalize"] == "Action indisponible: aucun transcript RAW dans le scope."
    assert reasons["segment"] == "Action indisponible: aucun fichier CLEAN dans le scope."
    assert reasons["index"] == "Action indisponible: aucun fichier CLEAN dans le scope."
    assert unavailable is None


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


def test_resolve_project_with_index_or_warn_success() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex("s", "u", episodes=[EpisodeRef("S01E01", 1, 1, "Pilot", "u")])

    class _Store:
        def load_series_index(self):
            return index

    store = _Store()
    db = object()
    context = {"config": object()}
    resolved = controller.resolve_project_with_index_or_warn(
        store=store,
        db=db,
        context=context,
        require_db=True,
    )
    assert resolved is not None
    assert resolved[0] is store
    assert resolved[1] is db
    assert resolved[2] is context
    assert resolved[3] is index
    assert warned == []


def test_resolve_project_with_index_or_warn_reports_missing_project() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    resolved = controller.resolve_project_with_index_or_warn(
        store=None,
        db=object(),
        context={},
        require_db=True,
    )
    assert resolved is None
    assert warned == [
        (
            "Ouvrez un projet d'abord.",
            "Pilotage > Projet: ouvrez ou initialisez un projet.",
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


def test_load_status_map_for_index_returns_empty_without_db_or_index() -> None:
    assert CorpusWorkflowController.load_status_map_for_index(index=None, db=object()) == {}
    assert (
        CorpusWorkflowController.load_status_map_for_index(
            index=SeriesIndex("s", "u", episodes=[]),
            db=object(),
        )
        == {}
    )
    assert (
        CorpusWorkflowController.load_status_map_for_index(
            index=SeriesIndex("s", "u", episodes=[EpisodeRef("S01E01", 1, 1, "Pilot", "u")]),
            db=None,
        )
        == {}
    )


def test_load_status_map_for_index_uses_loader() -> None:
    index = SeriesIndex(
        "s",
        "u",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "Pilot", "u"),
            EpisodeRef("S01E02", 1, 2, "Purple", "u"),
        ],
    )
    calls: list[tuple[object, list[str]]] = []

    def _loader(db: object, ids: list[str]) -> dict[str, str]:
        calls.append((db, list(ids)))
        return {"S01E01": "indexed", "S01E02": "error"}

    db = object()
    status_map = CorpusWorkflowController.load_status_map_for_index(
        index=index,
        db=db,
        status_map_loader=_loader,
    )
    assert status_map == {"S01E01": "indexed", "S01E02": "error"}
    assert calls == [(db, ["S01E01", "S01E02"])]


def test_resolve_workflow_snapshot_delegates_loader_compute_and_advice() -> None:
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda _msg, _next_step=None: None,
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex(
        "s",
        "u",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "Pilot", "u"),
            EpisodeRef("S01E02", 1, 2, "Purple", "u"),
        ],
    )
    store = object()
    db = object()
    calls: dict[str, object] = {}

    def _loader(db_arg: object, ids: list[str]) -> dict[str, str]:
        calls["loader"] = (db_arg, list(ids))
        return {"S01E01": "indexed", "S01E02": "error"}

    def _compute_status_fn(**kwargs):
        calls["compute"] = kwargs
        return ("counts-object", ["S01E02"])

    def _advice_builder(counts: object):
        calls["advice"] = counts
        return {"action_id": "retry_errors"}

    counts, error_ids, advice = controller.resolve_workflow_snapshot(
        index=index,
        store=store,
        db=db,
        status_map_loader=_loader,
        compute_status_fn=_compute_status_fn,
        advice_builder=_advice_builder,
    )
    assert counts == "counts-object"
    assert error_ids == ["S01E02"]
    assert advice == {"action_id": "retry_errors"}
    assert calls["loader"] == (db, ["S01E01", "S01E02"])
    assert calls["advice"] == "counts-object"
    compute_args = calls["compute"]
    assert isinstance(compute_args, dict)
    assert compute_args["index"] is index
    assert compute_args["store"] is store
    assert compute_args["db"] is db
    assert compute_args["status_map"] == {"S01E01": "indexed", "S01E02": "error"}


def test_build_workflow_status_line_formats_all_counters() -> None:
    class _Counts:
        n_total = 12
        n_fetched = 10
        n_norm = 8
        n_segmented = 7
        n_indexed = 6
        n_error = 1
        n_with_srt = 9
        n_aligned = 5

    line = CorpusWorkflowController.build_workflow_status_line(_Counts())
    assert line == (
        "Workflow : "
        "Découverts 12 | Téléchargés 10 | "
        "Normalisés 8 | Segmentés 7 | "
        "Indexés 6 | Erreurs 1 | "
        "SRT 9 | Alignés 5"
    )


def test_resolve_default_scope_action_enabled_from_counts() -> None:
    class _Counts:
        n_total = 3
        n_fetched = 2
        n_norm = 1

    enabled = CorpusWorkflowController.resolve_default_scope_action_enabled_from_counts(_Counts())
    assert enabled == {
        "fetch": True,
        "normalize": True,
        "segment": True,
        "run_all": True,
        "index": True,
    }

    class _EmptyCounts:
        n_total = 0
        n_fetched = 0
        n_norm = 0

    empty_enabled = CorpusWorkflowController.resolve_default_scope_action_enabled_from_counts(_EmptyCounts())
    assert empty_enabled == {
        "fetch": False,
        "normalize": False,
        "segment": False,
        "run_all": False,
        "index": False,
    }


def test_resolve_error_episode_ids_from_index_uses_loader() -> None:
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda _msg, _next_step=None: None,
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex(
        "s",
        "u",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "Pilot", "u"),
            EpisodeRef("S01E02", 1, 2, "Purple", "u"),
        ],
    )
    calls: list[tuple[object, list[str]]] = []

    def _loader(db: object, ids: list[str]) -> dict[str, str]:
        calls.append((db, list(ids)))
        return {"S01E01": "indexed", "S01E02": "error"}

    db = object()
    error_ids = controller.resolve_error_episode_ids_from_index(
        index=index,
        db=db,
        status_map_loader=_loader,
    )
    assert error_ids == ["S01E02"]
    assert calls == [(db, ["S01E01", "S01E02"])]


def test_resolve_all_error_retry_ids_from_index_db_or_warn() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex(
        "s",
        "u",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "Pilot", "u"),
            EpisodeRef("S01E02", 1, 2, "Purple", "u"),
        ],
    )
    ids = controller.resolve_all_error_retry_ids_from_index_db_or_warn(
        index=index,
        db=object(),
        status_map_loader=lambda _db, _ids: {"S01E01": "indexed", "S01E02": "error"},
    )
    assert ids == ["S01E02"]
    none_ids = controller.resolve_all_error_retry_ids_from_index_db_or_warn(
        index=index,
        db=object(),
        status_map_loader=lambda _db, _ids: {"S01E01": "indexed", "S01E02": "normalized"},
    )
    assert none_ids is None
    assert warned[-1] == (
        "Aucun épisode en erreur à relancer.",
        "Consultez le panneau erreurs après un job en échec, puis utilisez « Reprendre erreurs ».",
    )


def test_resolve_selected_retry_ids_or_warn() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex("s", "u", episodes=[EpisodeRef("S01E01", 1, 1, "Pilot", "u")])
    assert controller.resolve_selected_retry_ids_or_warn(
        selected_episode_id="S01E01",
        index=index,
    ) == ["S01E01"]
    assert controller.resolve_selected_retry_ids_or_warn(
        selected_episode_id=None,
        index=index,
    ) is None
    assert controller.resolve_selected_retry_ids_or_warn(
        selected_episode_id="S99E99",
        index=index,
    ) is None
    assert warned[-2] == (
        "Sélectionnez un épisode en erreur à relancer.",
        "Choisissez une ligne dans la liste « Reprise — Erreurs ».",
    )
    assert warned[-1] == (
        "Épisode introuvable dans l'index: S99E99",
        "Rafraîchissez la liste des erreurs puis réessayez.",
    )


def test_resolve_all_error_retry_ids_or_warn() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex(
        "s",
        "u",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "Pilot", "u"),
            EpisodeRef("S01E02", 1, 2, "Purple", "u"),
        ],
    )
    ids = controller.resolve_all_error_retry_ids_or_warn(
        index=index,
        status_map={"S01E01": "indexed", "S01E02": "error"},
    )
    assert ids == ["S01E02"]
    none_ids = controller.resolve_all_error_retry_ids_or_warn(
        index=index,
        status_map={"S01E01": "indexed", "S01E02": "normalized"},
    )
    assert none_ids is None
    assert warned[-1] == (
        "Aucun épisode en erreur à relancer.",
        "Consultez le panneau erreurs après un job en échec, puis utilisez « Reprendre erreurs ».",
    )


def test_resolve_selected_error_episode_id_or_warn() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    assert controller.resolve_selected_error_episode_id_or_warn(
        selected_episode_id=" S01E02 ",
        empty_message="missing",
        empty_next_step="pick one",
    ) == "S01E02"
    assert controller.resolve_selected_error_episode_id_or_warn(
        selected_episode_id=None,
        empty_message="missing",
        empty_next_step="pick one",
    ) is None
    assert warned[-1] == ("missing", "pick one")


def test_resolve_clean_episodes_for_export_or_warn_filters_clean_only() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex(
        "s",
        "u",
        episodes=[
            EpisodeRef("S01E01", 1, 1, "Pilot", "u1"),
            EpisodeRef("S01E02", 1, 2, "Purple", "u2"),
        ],
    )

    class _Store:
        def load_series_index(self):
            return index

        def has_episode_clean(self, episode_id: str) -> bool:
            return episode_id == "S01E02"

        def load_episode_text(self, episode_id: str, *, kind: str) -> str:
            assert kind == "clean"
            return f"clean::{episode_id}"

    episodes_data = controller.resolve_clean_episodes_for_export_or_warn(store=_Store())
    assert episodes_data is not None
    assert [(ref.episode_id, text) for ref, text in episodes_data] == [("S01E02", "clean::S01E02")]
    assert warned == []


def test_resolve_clean_episodes_for_export_or_warn_warns_when_no_clean() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex("s", "u", episodes=[EpisodeRef("S01E01", 1, 1, "Pilot", "u1")])

    class _Store:
        def load_series_index(self):
            return index

        def has_episode_clean(self, _episode_id: str) -> bool:
            return False

        def load_episode_text(self, episode_id: str, *, kind: str) -> str:
            assert kind == "clean"
            return f"clean::{episode_id}"

    episodes_data = controller.resolve_clean_episodes_for_export_or_warn(store=_Store())
    assert episodes_data is None
    assert warned[-1] == (
        "Aucun épisode normalisé (CLEAN) à exporter.",
        "Lancez « Normaliser » puis réessayez l'export.",
    )


def test_export_episodes_data_or_warn_uses_selected_variant_writer(tmp_path: Path) -> None:
    warned: list[tuple[str, str | None]] = []
    calls: list[tuple[str, Path, int]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    episodes_data = [(EpisodeRef("S01E01", 1, 1, "Pilot", "u"), "clean text")]

    def _writer(name: str):
        def _fn(data: list[tuple[EpisodeRef, str]], path: Path) -> None:
            calls.append((name, path, len(data)))

        return _fn

    output = controller.export_episodes_data_or_warn(
        episodes_data=episodes_data,
        path=tmp_path / "corpus_export",
        selected_filter="CSV - Phrases (*.csv)",
        export_writers={"phrases_csv": _writer("phrases_csv")},
    )
    assert output == tmp_path / "corpus_export.csv"
    assert calls == [("phrases_csv", tmp_path / "corpus_export.csv", 1)]
    assert warned == []


def test_export_episodes_data_or_warn_defaults_jsonl_to_utterances(tmp_path: Path) -> None:
    warned: list[tuple[str, str | None]] = []
    calls: list[tuple[Path, int]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    episodes_data = [(EpisodeRef("S01E01", 1, 1, "Pilot", "u"), "clean text")]

    def _utterances_writer(data: list[tuple[EpisodeRef, str]], path: Path) -> None:
        calls.append((path, len(data)))

    output = controller.export_episodes_data_or_warn(
        episodes_data=episodes_data,
        path=tmp_path / "corpus_export.jsonl",
        selected_filter="",
        export_writers={"utterances_jsonl": _utterances_writer},
    )
    assert output == tmp_path / "corpus_export.jsonl"
    assert calls == [(tmp_path / "corpus_export.jsonl", 1)]
    assert warned == []


def test_export_episodes_data_or_warn_warns_when_writer_missing(tmp_path: Path) -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    episodes_data = [(EpisodeRef("S01E01", 1, 1, "Pilot", "u"), "clean text")]

    output = controller.export_episodes_data_or_warn(
        episodes_data=episodes_data,
        path=tmp_path / "corpus_export",
        selected_filter="CSV - Phrases (*.csv)",
        export_writers={},
    )
    assert output is None
    assert warned[-1] == (
        "Format non reconnu. Utilisez .txt, .csv, .json, .jsonl ou .docx.",
        None,
    )


def test_build_discover_series_steps_returns_fetch_index_step() -> None:
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda _msg, _next_step=None: None,
        step_builder=lambda **_kwargs: [],
    )

    class _Config:
        series_url = "https://src/series"
        user_agent = "ua-test"

    steps = controller.build_discover_series_steps(context={"config": _Config()})
    assert len(steps) == 1
    assert isinstance(steps[0], FetchSeriesIndexStep)
    assert steps[0].series_url == "https://src/series"
    assert steps[0].user_agent == "ua-test"


def test_build_discover_merge_steps_or_warn_validates_url() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )

    class _Config:
        user_agent = "ua-test"

    steps = controller.build_discover_merge_steps_or_warn(
        context={"config": _Config()},
        series_url="",
        source_id="subslikescript",
    )
    assert steps is None
    assert warned[-1] == (
        "Indiquez l'URL de la série.",
        "Renseignez une URL source puis relancez « Découvrir (fusionner) ».",
    )

    valid_steps = controller.build_discover_merge_steps_or_warn(
        context={"config": _Config()},
        series_url=" https://src/other ",
        source_id="",
    )
    assert valid_steps is not None
    assert len(valid_steps) == 1
    assert isinstance(valid_steps[0], FetchAndMergeSeriesIndexStep)
    assert valid_steps[0].series_url == "https://src/other"
    assert valid_steps[0].source_id == "subslikescript"
    assert valid_steps[0].user_agent == "ua-test"


def test_resolve_manual_episode_refs_or_warn_parses_and_deduplicates() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    resolved = controller.resolve_manual_episode_refs_or_warn(
        raw_text="S01E01\ns1e1\nbad\nS02E03\n",
    )
    assert resolved is not None
    refs, invalid_count = resolved
    assert [r.episode_id for r in refs] == ["S01E01", "S02E03"]
    assert invalid_count == 1
    assert warned == []


def test_merge_manual_episode_refs_or_warn_builds_new_index() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex(
        "title",
        "url",
        episodes=[EpisodeRef("S01E01", 1, 1, "Pilot", "u")],
    )
    merged = controller.merge_manual_episode_refs_or_warn(
        index=index,
        new_refs=[
            EpisodeRef("S01E01", 1, 1, "", ""),
            EpisodeRef("S01E02", 1, 2, "", ""),
        ],
    )
    assert merged is not None
    merged_index, added_count, skipped_existing = merged
    assert [e.episode_id for e in merged_index.episodes] == ["S01E01", "S01E02"]
    assert added_count == 1
    assert skipped_existing == 1
    assert warned == []


def test_merge_manual_episode_refs_or_warn_warns_when_nothing_added() -> None:
    warned: list[tuple[str, str | None]] = []
    controller = CorpusWorkflowController(
        workflow_service=object(),  # type: ignore[arg-type]
        run_steps=lambda _steps: None,
        warn_user=lambda msg, next_step=None: warned.append((msg, next_step)),
        step_builder=lambda **_kwargs: [],
    )
    index = SeriesIndex(
        "title",
        "url",
        episodes=[EpisodeRef("S01E01", 1, 1, "Pilot", "u")],
    )
    merged = controller.merge_manual_episode_refs_or_warn(
        index=index,
        new_refs=[EpisodeRef("S01E01", 1, 1, "", "")],
    )
    assert merged is None
    assert warned[-1] == (
        "Tous les épisodes saisis existent déjà.",
        "Saisissez de nouveaux IDs (format S01E01).",
    )


def test_build_manual_add_status_message_includes_all_counts() -> None:
    msg = CorpusWorkflowController.build_manual_add_status_message(
        added_count=2,
        skipped_existing=1,
        invalid_count=3,
    )
    assert msg == "Ajout manuel: 2 épisode(s) ajouté(s), 1 déjà présent(s), 3 ignoré(s) (format invalide)."
