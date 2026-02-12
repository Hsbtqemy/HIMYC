"""Workers pour exécuter le pipeline en arrière-plan (QThread) sans bloquer l'UI."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal, QThread

from corpusstudio.core.pipeline.runner import PipelineRunner
from corpusstudio.core.pipeline.steps import Step

logger = logging.getLogger(__name__)


class JobRunner(QObject):
    """
    Exécute une liste d'étapes du pipeline dans un thread séparé.
    Émet progress, log, error, finished, cancelled.
    """

    progress = Signal(str, float, str)   # step_name, percent, message
    log = Signal(str, str)                 # level, message
    error = Signal(str, object)           # step_name, exception
    finished = Signal(list)               # results
    cancelled = Signal()

    def __init__(self, steps: list[Step], context: dict[str, Any], force: bool = False):
        super().__init__()
        self.steps = steps
        self.context = context
        self.force = force
        self._runner = PipelineRunner()
        self._thread: QThread | None = None
        self._worker_obj: QObject | None = None

    def run_async(self) -> None:
        """Lance l'exécution dans un thread dédié."""
        self._thread = QThread()
        self._worker_obj = _PipelineWorker(
            self._runner,
            self.steps,
            self.context,
            self.force,
        )
        self._worker_obj.moveToThread(self._thread)
        self._thread.started.connect(self._worker_obj.run)
        self._worker_obj.progress.connect(self.progress.emit)
        self._worker_obj.log.connect(self.log.emit)
        self._worker_obj.error.connect(self.error.emit)
        self._worker_obj.finished.connect(self._on_worker_finished)
        self._worker_obj.cancelled.connect(self.cancelled.emit)
        self._thread.start()

    def _on_worker_finished(self, results: list):
        self.finished.emit(results)
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(3000):
                logger.warning("Worker thread did not finish within 3s")

    def cancel(self) -> None:
        self._runner.cancel()


class _PipelineWorker(QObject):
    """Objet qui exécute le pipeline dans son thread (connecté via moveToThread)."""

    progress = Signal(str, float, str)
    log = Signal(str, str)
    error = Signal(str, object)
    finished = Signal(list)
    cancelled = Signal()

    def __init__(
        self,
        runner: PipelineRunner,
        steps: list[Step],
        context: dict[str, Any],
        force: bool,
    ):
        super().__init__()
        self.runner = runner
        self.steps = steps
        self.context = context
        self.force = force

    def run(self) -> None:
        results = self.runner.run(
            self.steps,
            self.context,
            force=self.force,
            on_progress=lambda s, p, m: self.progress.emit(s, p, m),
            on_log=lambda level, msg: self.log.emit(level, msg),
            on_error=lambda s, e: self.error.emit(s, e),
            on_cancelled=lambda: self.cancelled.emit(),
        )
        self.finished.emit(results)
