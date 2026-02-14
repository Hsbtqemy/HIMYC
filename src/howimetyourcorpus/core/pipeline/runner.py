"""Orchestration du pipeline : run(steps, callbacks), annulation, progression."""

from __future__ import annotations

import logging
from typing import Callable

from howimetyourcorpus.core.pipeline.context import PipelineContext
from howimetyourcorpus.core.pipeline.steps import (
    ErrorCallback,
    LogCallback,
    ProgressCallback,
    Step,
    StepResult,
)

logger = logging.getLogger(__name__)


class PipelineRunner:
    """
    Exécute une liste d'étapes avec callbacks (progress, log, error).
    Supporte l'annulation via _cancelled.
    """

    def __init__(self):
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(
        self,
        steps: list[Step],
        context: PipelineContext,
        *,
        force: bool = False,
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
        on_error: ErrorCallback | None = None,
        on_cancelled: Callable[[], None] | None = None,
    ) -> list[StepResult]:
        """
        Exécute les étapes dans l'ordre.
        En cas d'annulation ou d'erreur, arrête et appelle les callbacks appropriés.
        """
        self._cancelled = False
        results: list[StepResult] = []
        total_steps = len(steps)

        def log(level: str, msg: str):
            if on_log:
                on_log(level, msg)
                return
            getattr(logger, level.lower(), logger.info)(msg)

        for i, step in enumerate(steps):
            if self._cancelled:
                if on_cancelled:
                    on_cancelled()
                log("warning", "Pipeline cancelled")
                break
            log("info", f"Running step: {step.name}")
            ctx = dict(context)
            ctx["is_cancelled"] = lambda: self._cancelled

            def emit_progress(step_name: str, percent: float, message: str) -> None:
                if not on_progress:
                    return
                local = float(percent) if percent is not None else 0.0
                local = max(0.0, min(1.0, local))
                if total_steps <= 0:
                    global_percent = local
                else:
                    global_percent = (i + local) / total_steps
                on_progress(step_name, global_percent, message)

            emit_progress(step.name, 0.0, f"Starting: {step.name}")
            try:
                result = step.run(
                    ctx,
                    force=force,
                    on_progress=emit_progress,
                    on_log=on_log,
                )
                result.data = dict(result.data or {})
                result.data.setdefault("step_name", step.name)
                results.append(result)
                if not result.success:
                    if result.message == "Cancelled":
                        if on_cancelled:
                            on_cancelled()
                        log("warning", "Pipeline cancelled")
                    else:
                        if on_error:
                            on_error(step.name, RuntimeError(result.message))
                        log("error", result.message)
                    break
                emit_progress(step.name, 1.0, result.message or f"Done: {step.name}")
            except Exception as e:
                logger.exception("Step %s failed", step.name)
                if on_error:
                    on_error(step.name, e)
                results.append(StepResult(False, str(e), {"step_name": step.name}))
                break
        return results
