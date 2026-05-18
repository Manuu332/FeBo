"""
core/runtime_state.py
----------------------
Thread-safe singleton owning all mutable runtime state.

Replaces module-level globals in app.py, pipeline.py, and elsewhere.
FastAPI is async and can create weird behavior with scattered globals —
all mutable state lives here, accessed through a single well-defined interface.

Owns:
  - Session metadata (id, number, start time)
  - Interaction counter (session-scoped, persisted separately from identity)
  - Last reflection timestamp
  - Last maintenance timestamp
  - Current cognitive phase (active, sleeping, dreaming)
  - Recent exchange buffer (last N user/feebo turns for context)
  - Pattern reinforcement queue (pending reinforcements)
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional


class RuntimeState:
    """
    Single source of truth for all mutable runtime state.
    Thread-safe via RLock. One instance per process.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Session
        self._session_started       = False
        self._session_number        = 0
        self._session_start_time    = 0.0

        # Interaction counting (session-scoped)
        self._session_interactions  = 0
        self._total_interactions_cache = 0  # mirrors identity DB, refreshed periodically

        # Scheduling
        self._last_reflection_ts    = 0.0
        self._last_maintenance_ts   = 0.0
        self._last_curiosity_age_ts = 0.0

        # Cognitive phase
        # "active" | "sleeping" | "dreaming"
        self._cognitive_phase       = "active"

        # Recent exchange ring buffer (last 12 turns for novelty scoring)
        self._exchange_buffer: List[Dict[str, Any]] = []
        self._exchange_buffer_max   = 12

        # Pending pattern reinforcement queue
        # Each entry: {"category": str, "phrase": str, "reward": float}
        self._reinforce_queue: List[Dict[str, Any]] = []

        # Last generated response metadata (for external reinforcement)
        self._last_response: Dict[str, Any] = {}

        # Startup flag
        self._initialized = False

    # ── Session ───────────────────────────────────────────────────────────────

    def begin_session(self, session_number: int) -> None:
        with self._lock:
            if self._session_started:
                return
            self._session_started    = True
            self._session_number     = session_number
            self._session_start_time = time.time()
            self._initialized        = True

    @property
    def session_started(self) -> bool:
        with self._lock:
            return self._session_started

    @property
    def session_number(self) -> int:
        with self._lock:
            return self._session_number

    @property
    def session_uptime(self) -> float:
        """Seconds since session began."""
        with self._lock:
            if not self._session_start_time:
                return 0.0
            return time.time() - self._session_start_time

    # ── Interaction counter ───────────────────────────────────────────────────

    def increment_session_interactions(self) -> int:
        with self._lock:
            self._session_interactions += 1
            return self._session_interactions

    @property
    def session_interactions(self) -> int:
        with self._lock:
            return self._session_interactions

    def sync_total_interactions(self, n: int) -> None:
        """Called after identity.increment_interactions() to keep cache fresh."""
        with self._lock:
            self._total_interactions_cache = n

    @property
    def total_interactions(self) -> int:
        with self._lock:
            return self._total_interactions_cache

    # ── Scheduling ────────────────────────────────────────────────────────────

    def should_reflect(self) -> bool:
        """True if enough interactions OR enough time have passed."""
        with self._lock:
            by_count = (self._session_interactions > 0 and
                        self._session_interactions % 5 == 0)
            by_time  = (time.time() - self._last_reflection_ts) > 900
            return by_count or by_time

    def mark_reflected(self) -> None:
        with self._lock:
            self._last_reflection_ts = time.time()

    def should_run_maintenance(self, interval_hours: float = 4.0) -> bool:
        with self._lock:
            return (time.time() - self._last_maintenance_ts) > interval_hours * 3600

    def mark_maintenance_done(self) -> None:
        with self._lock:
            self._last_maintenance_ts = time.time()

    def should_age_curiosity(self, interval_hours: float = 0.5) -> bool:
        with self._lock:
            return (time.time() - self._last_curiosity_age_ts) > interval_hours * 3600

    def mark_curiosity_aged(self) -> None:
        with self._lock:
            self._last_curiosity_age_ts = time.time()

    # ── Cognitive phase ───────────────────────────────────────────────────────

    @property
    def cognitive_phase(self) -> str:
        with self._lock:
            return self._cognitive_phase

    def set_phase(self, phase: str) -> None:
        """phase: 'active' | 'sleeping' | 'dreaming'"""
        with self._lock:
            assert phase in ("active", "sleeping", "dreaming")
            self._cognitive_phase = phase

    @property
    def is_sleeping(self) -> bool:
        with self._lock:
            return self._cognitive_phase in ("sleeping", "dreaming")

    # ── Exchange buffer ───────────────────────────────────────────────────────

    def add_exchange(self, role: str, text: str, concepts: List[str],
                     emotion_snapshot: Optional[Dict[str, float]] = None) -> None:
        """Add a turn to the recent exchange ring buffer."""
        with self._lock:
            self._exchange_buffer.append({
                "role":     role,
                "text":     text,
                "concepts": concepts,
                "emotion":  emotion_snapshot or {},
                "ts":       time.time(),
            })
            if len(self._exchange_buffer) > self._exchange_buffer_max:
                self._exchange_buffer.pop(0)

    def get_recent_exchanges(self, n: int = 8) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._exchange_buffer[-n:])

    def get_recent_concepts(self, n: int = 8) -> List[str]:
        """All concepts from last N exchanges, deduplicated, ordered by recency."""
        with self._lock:
            seen = set()
            result = []
            for ex in reversed(self._exchange_buffer[-n:]):
                for c in ex.get("concepts", []):
                    if c not in seen:
                        seen.add(c)
                        result.append(c)
            return result

    # ── Reinforcement queue ───────────────────────────────────────────────────

    def queue_reinforcement(self, category: str, phrase: str, reward: float) -> None:
        with self._lock:
            self._reinforce_queue.append({
                "category": category,
                "phrase":   phrase,
                "reward":   reward,
                "ts":       time.time(),
            })

    def flush_reinforcement_queue(self) -> List[Dict[str, Any]]:
        """Return and clear the reinforcement queue."""
        with self._lock:
            q = list(self._reinforce_queue)
            self._reinforce_queue.clear()
            return q

    # ── Last response ─────────────────────────────────────────────────────────

    def set_last_response(self, metadata: Dict[str, Any]) -> None:
        with self._lock:
            self._last_response = dict(metadata)

    def get_last_response(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._last_response)

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_started":      self._session_started,
                "session_number":       self._session_number,
                "session_uptime_s":     round(time.time() - self._session_start_time, 1)
                                        if self._session_start_time else 0.0,
                "session_interactions": self._session_interactions,
                "total_interactions":   self._total_interactions_cache,
                "cognitive_phase":      self._cognitive_phase,
                "exchange_buffer_size": len(self._exchange_buffer),
                "reinforce_queue_size": len(self._reinforce_queue),
            }


# ── Singleton ──────────────────────────────────────────────────────────────────

_runtime: Optional[RuntimeState] = None
_init_lock = threading.Lock()


def get_runtime() -> RuntimeState:
    """Return the process-wide RuntimeState singleton."""
    global _runtime
    if _runtime is None:
        with _init_lock:
            if _runtime is None:
                _runtime = RuntimeState()
    return _runtime
