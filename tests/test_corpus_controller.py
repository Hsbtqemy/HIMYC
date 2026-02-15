"""Tests du contrôleur workflow Corpus."""

from __future__ import annotations

from pathlib import Path

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
