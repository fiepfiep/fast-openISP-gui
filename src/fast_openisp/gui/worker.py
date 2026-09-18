"""Background pipeline execution on Qt thread pools."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from fast_openisp.config import IspConfig
from fast_openisp.pipeline import Pipeline, PipelineCancelled, PipelineResult


@dataclass(frozen=True)
class RunOutcome:
    generation: int
    result: PipelineResult
    wall_time: float
    preview_factor: int


class _JobSignals(QObject):
    progress = Signal(int, str, int, int)  # generation, module, index, total
    finished = Signal(object)  # RunOutcome
    failed = Signal(int, str)
    cancelled = Signal(int)


class _PipelineTask(QRunnable):
    def __init__(
        self,
        generation: int,
        config: IspConfig,
        bayer: np.ndarray,
        preview_factor: int,
        signals: _JobSignals,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self.generation = generation
        self.config = config
        self.bayer = bayer
        self.preview_factor = preview_factor
        self.signals = signals
        self.cancel_event = cancel_event

    def run(self) -> None:
        gen = self.generation
        if self.cancel_event.is_set():
            self.signals.cancelled.emit(gen)
            return
        start = time.perf_counter()
        try:
            pipeline = Pipeline(self.config, preview_factor=self.preview_factor)
            result = pipeline.execute(
                self.bayer,
                progress=lambda name, i, n: self.signals.progress.emit(gen, name, i, n),
                cancel=self.cancel_event.is_set,
            )
        except PipelineCancelled:
            self.signals.cancelled.emit(gen)
        except Exception as error:  # reported to the UI, never raised in the worker thread
            self.signals.failed.emit(gen, str(error))
        else:
            outcome = RunOutcome(gen, result, time.perf_counter() - start, self.preview_factor)
            self.signals.finished.emit(outcome)


class PipelineRunner(QObject):
    """Runs previews (latest request wins) and exports (cancellable) in the background."""

    preview_ready = Signal(object)  # RunOutcome
    preview_failed = Signal(str)
    progress = Signal(str, int, int)
    busy_changed = Signal(bool)

    export_ready = Signal(object)  # RunOutcome
    export_failed = Signal(str)
    export_cancelled = Signal()
    export_progress = Signal(str, int, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._preview_pool = QThreadPool(self)
        self._preview_pool.setMaxThreadCount(1)
        self._export_pool = QThreadPool(self)
        self._export_pool.setMaxThreadCount(1)

        self._generation = 0
        self._preview_cancel = threading.Event()
        self._busy = False
        self._preview_signals = _JobSignals(self)
        self._preview_signals.progress.connect(self._on_preview_progress)
        self._preview_signals.finished.connect(self._on_preview_finished)
        self._preview_signals.failed.connect(self._on_preview_failed)
        self._preview_signals.cancelled.connect(self._on_preview_cancelled)

        self._export_generation = 0
        self._export_cancel = threading.Event()
        self._export_signals = _JobSignals(self)
        self._export_signals.progress.connect(
            lambda _gen, name, i, n: self.export_progress.emit(name, i, n)
        )
        self._export_signals.finished.connect(self.export_ready)
        self._export_signals.failed.connect(lambda _gen, message: self.export_failed.emit(message))
        self._export_signals.cancelled.connect(lambda _gen: self.export_cancelled.emit())

    @property
    def busy(self) -> bool:
        return self._busy

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busy_changed.emit(busy)

    def request_preview(self, config: IspConfig, bayer: np.ndarray, preview_factor: int) -> int:
        """Start a preview run, cancelling any preview still in progress."""
        self._preview_cancel.set()
        self._preview_cancel = threading.Event()
        self._generation += 1
        self._set_busy(True)
        task = _PipelineTask(
            self._generation,
            config,
            bayer,
            preview_factor,
            self._preview_signals,
            self._preview_cancel,
        )
        self._preview_pool.start(task)
        return self._generation

    def cancel_preview(self) -> None:
        self._preview_cancel.set()
        self._generation += 1
        self._set_busy(False)

    def _is_current(self, generation: int) -> bool:
        return generation == self._generation

    def _on_preview_progress(self, generation: int, name: str, index: int, total: int) -> None:
        if self._is_current(generation):
            self.progress.emit(name, index, total)

    def _on_preview_finished(self, outcome: RunOutcome) -> None:
        if self._is_current(outcome.generation):
            self._set_busy(False)
            self.preview_ready.emit(outcome)

    def _on_preview_failed(self, generation: int, message: str) -> None:
        if self._is_current(generation):
            self._set_busy(False)
            self.preview_failed.emit(message)

    def _on_preview_cancelled(self, generation: int) -> None:
        if self._is_current(generation):
            self._set_busy(False)

    def start_export(self, config: IspConfig, bayer: np.ndarray) -> None:
        """Run the pipeline at full resolution."""
        self._export_cancel = threading.Event()
        self._export_generation += 1
        task = _PipelineTask(
            self._export_generation, config, bayer, 1, self._export_signals, self._export_cancel
        )
        self._export_pool.start(task)

    def cancel_export(self) -> None:
        self._export_cancel.set()

    def wait(self, msecs: int = 30000) -> bool:
        """Block until all background work is done (used on shutdown and in tests)."""
        return self._preview_pool.waitForDone(msecs) and self._export_pool.waitForDone(msecs)

    def shutdown(self) -> None:
        self._preview_cancel.set()
        self._export_cancel.set()
        self.wait()
