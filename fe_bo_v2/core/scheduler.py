"""
core/scheduler.py
──────────────────
Single heartbeat scheduler for ALL of FeBo's background tasks.

Replaces the fragmented thread-per-subsystem approach that causes:
  - race conditions
  - deadlocks
  - inconsistent state
  - scheduler chaos

Architecture: ONE thread, ONE tick loop, registered callbacks.

Every background task registers with the scheduler:
    scheduler.register("dreams", interval=300, callback=dream_system.tick)
    scheduler.register("defender", interval=30, callback=defender.check)
    scheduler.register("drives_decay", interval=60, callback=drives.tick)

The scheduler calls each callback at its interval.
Callbacks MUST NOT block for more than 10 seconds.
Callbacks MUST handle their own exceptions.
"""

from __future__ import annotations
import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger("core.scheduler")

TICK_INTERVAL = 1.0   # seconds — the heartbeat (fast enough for short-interval tasks)


@dataclass
class ScheduledTask:
    name:          str
    interval_s:    float
    callback:      Callable[[], None]
    last_run:      float  = 0.0
    run_count:     int    = 0
    error_count:   int    = 0
    enabled:       bool   = True
    max_duration_s: float = 10.0

    def is_due(self) -> bool:
        return self.enabled and (time.time() - self.last_run) >= self.interval_s


class FeBo_Scheduler:
    """Single heartbeat scheduler. ONE instance manages ALL background work."""

    _instance: Optional["FeBo_Scheduler"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "FeBo_Scheduler":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._tasks:    dict[str, ScheduledTask] = {}
        self._rw_lock   = threading.RLock()
        self._thread:   Optional[threading.Thread] = None
        self._stop_evt  = threading.Event()
        self._running   = False

    # ── Registration ─────────────────────────────────────────────
    def register(
        self,
        name:       str,
        interval_s: float,
        callback:   Callable[[], None],
        enabled:    bool  = True,
        max_duration_s: float = 10.0,
    ) -> None:
        with self._rw_lock:
            self._tasks[name] = ScheduledTask(
                name=name,
                interval_s=interval_s,
                callback=callback,
                enabled=enabled,
                max_duration_s=max_duration_s,
            )
        logger.debug(f"[scheduler] registered '{name}' every {interval_s:.0f}s")

    def unregister(self, name: str):
        with self._rw_lock:
            self._tasks.pop(name, None)

    def enable(self, name: str, enabled: bool = True):
        with self._rw_lock:
            if name in self._tasks:
                self._tasks[name].enabled = enabled

    # ── Lifecycle ────────────────────────────────────────────────
    def start(self):
        if self._running:
            return
        self._stop_evt.clear()
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, name="FeBo-Scheduler", daemon=True
        )
        self._thread.start()
        logger.info("[scheduler] heartbeat started")

    def stop(self, timeout: float = 5.0):
        self._running = False
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("[scheduler] stopped")

    # ── Main loop ────────────────────────────────────────────────
    def _loop(self):
        while not self._stop_evt.is_set():
            self._stop_evt.wait(TICK_INTERVAL)
            if self._stop_evt.is_set():
                break

            with self._rw_lock:
                tasks_due = [t for t in self._tasks.values() if t.is_due()]

            for task in tasks_due:
                self._run_task(task)

    def _run_task(self, task: ScheduledTask):
        t0 = time.time()
        try:
            task.callback()
            task.run_count += 1
            elapsed = time.time() - t0
            if elapsed > task.max_duration_s:
                logger.warning(
                    f"[scheduler] '{task.name}' ran for {elapsed:.1f}s "
                    f"(limit {task.max_duration_s}s)"
                )
        except Exception as e:
            task.error_count += 1
            logger.error(f"[scheduler] '{task.name}' error: {e}")
        finally:
            task.last_run = time.time()

    # ── Status ───────────────────────────────────────────────────
    def status(self) -> list[dict]:
        with self._rw_lock:
            return [
                {
                    "name":       t.name,
                    "interval_s": t.interval_s,
                    "enabled":    t.enabled,
                    "run_count":  t.run_count,
                    "error_count": t.error_count,
                    "last_run_ago": round(time.time() - t.last_run, 1) if t.last_run else None,
                }
                for t in self._tasks.values()
            ]

    def __repr__(self) -> str:
        n = len(self._tasks)
        active = sum(1 for t in self._tasks.values() if t.enabled)
        return f"<FeBo_Scheduler tasks={n} active={active} running={self._running}>"


# Singleton
scheduler = FeBo_Scheduler()
