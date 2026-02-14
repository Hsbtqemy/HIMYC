"""Tests PipelineRunner: progression globale et bornage du pourcentage."""

from __future__ import annotations

from howimetyourcorpus.core.pipeline.runner import PipelineRunner
from howimetyourcorpus.core.pipeline.steps import Step, StepResult


class _ProgressStep(Step):
    name = "progress_step"

    def __init__(self, marks: list[float]):
        self._marks = marks

    def run(self, context, *, force=False, on_progress=None, on_log=None) -> StepResult:
        if on_progress:
            for p in self._marks:
                on_progress(self.name, p, f"p={p}")
        return StepResult(True, "ok")


def test_pipeline_runner_reports_global_monotonic_progress() -> None:
    runner = PipelineRunner()
    emitted: list[float] = []
    results = runner.run(
        [_ProgressStep([0.0, 0.5, 1.0]), _ProgressStep([0.0, 0.5, 1.0])],
        context={},
        on_progress=lambda _s, p, _m: emitted.append(p),
    )
    assert len(results) == 2
    assert emitted
    assert emitted[0] == 0.0
    assert emitted[-1] == 1.0
    assert all(emitted[i] <= emitted[i + 1] for i in range(len(emitted) - 1))


def test_pipeline_runner_clamps_out_of_range_progress() -> None:
    runner = PipelineRunner()
    emitted: list[float] = []
    runner.run(
        [_ProgressStep([-2.0, 2.0])],
        context={},
        on_progress=lambda _s, p, _m: emitted.append(p),
    )
    assert emitted
    assert min(emitted) >= 0.0
    assert max(emitted) <= 1.0
    assert emitted[-1] == 1.0


class _DataStep(Step):
    name = "data_step"

    def __init__(self, data=None):
        self._data = data

    def run(self, context, *, force=False, on_progress=None, on_log=None) -> StepResult:
        return StepResult(True, "ok", self._data)


def test_pipeline_runner_adds_step_name_to_result_data() -> None:
    runner = PipelineRunner()
    results = runner.run([_DataStep({"meta": 1})], context={})

    assert len(results) == 1
    data = results[0].data or {}
    assert data["meta"] == 1
    assert data["step_name"] == "data_step"


def test_pipeline_runner_preserves_existing_step_name_data() -> None:
    runner = PipelineRunner()
    results = runner.run([_DataStep({"step_name": "custom_step"})], context={})

    assert len(results) == 1
    data = results[0].data or {}
    assert data["step_name"] == "custom_step"


class _FailingStep(Step):
    name = "failing_step"

    def run(self, context, *, force=False, on_progress=None, on_log=None) -> StepResult:
        raise RuntimeError("boom")


def test_pipeline_runner_keeps_step_name_when_step_raises_exception() -> None:
    runner = PipelineRunner()
    results = runner.run([_FailingStep()], context={})

    assert len(results) == 1
    assert not results[0].success
    data = results[0].data or {}
    assert data["step_name"] == "failing_step"
