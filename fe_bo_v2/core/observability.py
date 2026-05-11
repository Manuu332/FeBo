"""
core/observability.py
──────────────────────
Observability layer for FeBo.

Without this, you can never know:
  "Is FeBo evolving, or merely looping?"

Provides:
  - EmotionDriftTracker   : logs emotion vector every N turns for graphing
  - ReflectionTracer      : structured log of every reflection event
  - InteractionLedger     : compact record of every turn (reward, mood, vocab)
  - HealthMonitor         : detects stagnation, recursion, memory issues
  - snapshot()            : single-call diagnostic dump

All writers are non-blocking. If a write fails, it is silently skipped.
All files are JSONL (one JSON object per line) for easy grep/tail/parse.
"""

from __future__ import annotations
import time
import json
import threading
from pathlib import Path
from typing import Optional

from core.logging_config import get_logger

logger = get_logger("core.observability")

# ── Output paths ──────────────────────────────────────────────────
LOGS_DIR              = Path("logs")
EMOTION_DRIFT_LOG     = LOGS_DIR / "emotion_drift.jsonl"
REFLECTION_TRACE_LOG  = LOGS_DIR / "reflection_trace.jsonl"
INTERACTION_LOG       = LOGS_DIR / "interactions.jsonl"
HEALTH_LOG            = LOGS_DIR / "health.jsonl"

LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _append(path: Path, record: dict):
    """Non-blocking JSONL append. Never raises."""
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


# ── Emotion Drift Tracker ─────────────────────────────────────────
class EmotionDriftTracker:
    """
    Records the emotion vector at regular intervals.
    Lets you graph emotional trajectory over time —
    the primary signal for whether FeBo is 'evolving or looping'.
    """

    def __init__(self, sample_every_n_turns: int = 10):
        self._n        = sample_every_n_turns
        self._turn     = 0
        self._baseline: Optional[dict] = None

    def record(self, emotion_state: dict, turn: int, reward: float = 0.0):
        self._turn = turn
        if turn % self._n != 0:
            return
        record = {
            "ts":      time.time(),
            "turn":    turn,
            "reward":  round(reward, 3),
            "v":   round(emotion_state.get("valence",    0.5), 3),
            "a":   round(emotion_state.get("arousal",    0.5), 3),
            "c":   round(emotion_state.get("curiosity",  0.8), 3),
            "t":   round(emotion_state.get("tension",    0.0), 3),
            "w":   round(emotion_state.get("warmth",     0.5), 3),
            "cf":  round(emotion_state.get("confidence", 0.5), 3),
            "b":   round(emotion_state.get("boredom",    0.0), 3),
            "mood": emotion_state.get("dominant_mood", "?"),
        }
        if self._baseline is None:
            self._baseline = record
        _append(EMOTION_DRIFT_LOG, record)

    def compute_drift(self) -> Optional[float]:
        """Euclidean drift from baseline emotion. None if no baseline yet."""
        if self._baseline is None:
            return None
        from brain.emotion import load_state
        current = load_state()
        dims = ["valence", "arousal", "curiosity", "tension", "warmth", "confidence", "boredom"]
        diff_sq = sum(
            (current.get(d, 0.5) - self._baseline.get(d[0] if len(d) == 1 else d[:2], 0.5)) ** 2
            for d in dims
        )
        return round(diff_sq ** 0.5, 4)


# ── Reflection Tracer ────────────────────────────────────────────
class ReflectionTracer:
    """
    Logs every reflection/dream event with structured metadata.
    Lets you inspect whether FeBo's reflections are:
      - diverse  (new topics each time)
      - coherent (building on prior reflections)
      - productive (linked to emotion/drive shifts)
    """

    def record(
        self,
        event_type:  str,   # "dream" | "oracle_query" | "self_reflection"
        topic:       str,
        content:     str,
        emotion_before: dict,
        emotion_after:  dict,
        source:      str = "unknown",
    ):
        record = {
            "ts":           time.time(),
            "type":         event_type,
            "topic":        topic[:80],
            "content":      content[:300],
            "source":       source,
            "mood_before":  emotion_before.get("dominant_mood", "?"),
            "mood_after":   emotion_after.get("dominant_mood",  "?"),
            "valence_delta": round(
                emotion_after.get("valence", 0.5) - emotion_before.get("valence", 0.5), 3
            ),
        }
        _append(REFLECTION_TRACE_LOG, record)
        logger.debug(f"[reflect] {event_type}:{topic[:40]}")


# ── Interaction Ledger ───────────────────────────────────────────
class InteractionLedger:
    """
    Compact record of every interaction turn.
    Primary tool for detecting:
      - Response quality trends
      - Vocabulary stagnation
      - Reward pattern drift
    """

    def record(
        self,
        turn:      int,
        user_len:  int,
        resp_len:  int,
        mood:      str,
        desire:    str,
        reward:    float,
        vocab_sz:  int,
    ):
        _append(INTERACTION_LOG, {
            "ts":       time.time(),
            "turn":     turn,
            "ulen":     user_len,
            "rlen":     resp_len,
            "mood":     mood,
            "desire":   desire,
            "reward":   round(reward, 3),
            "vocab":    vocab_sz,
        })


# ── Health Monitor ───────────────────────────────────────────────
class HealthMonitor:
    """
    Detects signs of system stagnation or instability:
      - Vocabulary not growing after many turns
      - Same mood for 50+ consecutive turns
      - Reward never changing (stuck policy)
      - Emotion state not drifting (frozen)
    """

    def __init__(self):
        self._mood_streak:   int   = 0
        self._last_mood:     str   = ""
        self._last_vocab:    int   = 0
        self._stable_vocab_turns: int = 0
        self._reward_history: list = []

    def check(self, turn: int, mood: str, vocab_sz: int, reward: float) -> list[str]:
        """Run health checks. Returns list of warning strings (empty if healthy)."""
        warnings = []

        # Mood monotony
        if mood == self._last_mood:
            self._mood_streak += 1
        else:
            self._mood_streak  = 0
            self._last_mood    = mood
        if self._mood_streak > 50:
            warnings.append(f"MOOD_STAGNATION: '{mood}' for {self._mood_streak} turns")

        # Vocabulary stagnation
        if vocab_sz <= self._last_vocab:
            self._stable_vocab_turns += 1
        else:
            self._stable_vocab_turns = 0
            self._last_vocab = vocab_sz
        if self._stable_vocab_turns > 30 and turn > 50:
            warnings.append(f"VOCAB_STAGNATION: no growth for {self._stable_vocab_turns} turns (size={vocab_sz})")

        # Reward monotony
        self._reward_history.append(reward)
        if len(self._reward_history) > 20:
            self._reward_history.pop(0)
        if len(self._reward_history) >= 20:
            rng = max(self._reward_history) - min(self._reward_history)
            if rng < 0.01:
                warnings.append(f"REWARD_MONOTONY: range={rng:.4f} over 20 turns")

        if warnings:
            for w in warnings:
                logger.warning(f"[health] {w}")
                _append(HEALTH_LOG, {"ts": time.time(), "turn": turn, "warning": w})

        return warnings


# ── Diagnostic snapshot ──────────────────────────────────────────
def snapshot() -> str:
    """
    Print a full observability snapshot to the console.
    Shows emotion drift, recent interactions, health, scheduler.
    """
    lines = ["─── FeBo Observability Snapshot ───"]

    # Emotion drift
    try:
        recent = []
        if EMOTION_DRIFT_LOG.exists():
            with open(EMOTION_DRIFT_LOG) as f:
                for line in f:
                    try:
                        recent.append(json.loads(line))
                    except Exception:
                        pass
        if recent:
            first = recent[0]
            last  = recent[-1]
            lines.append(f"  Emotion drift: {len(recent)} samples")
            lines.append(f"    First: mood={first.get('mood')} val={first.get('v')} cur={first.get('c')}")
            lines.append(f"    Last:  mood={last.get('mood')}  val={last.get('v')} cur={last.get('c')}")
        else:
            lines.append("  Emotion drift: no data yet")
    except Exception:
        pass

    # Recent interactions
    try:
        if INTERACTION_LOG.exists():
            with open(INTERACTION_LOG) as f:
                entries = [json.loads(l) for l in f if l.strip()]
            if entries:
                last5 = entries[-5:]
                lines.append(f"  Last {len(last5)} interactions:")
                for e in last5:
                    lines.append(
                        f"    turn={e.get('turn')} mood={e.get('mood')} "
                        f"reward={e.get('reward')} vocab={e.get('vocab')}"
                    )
    except Exception:
        pass

    # Scheduler
    try:
        from core.scheduler import scheduler
        lines.append("  Scheduler tasks:")
        for t in scheduler.status():
            lines.append(
                f"    {t['name']:<25} runs={t['run_count']:>4} "
                f"errors={t['error_count']:>2} "
                f"last={t['last_run_ago']}s ago"
            )
    except Exception:
        pass

    # Runtime state
    try:
        from core.runtime_state import runtime
        snap = runtime.snapshot()
        lines.append(f"  Runtime: {snap}")
    except Exception:
        pass

    return "\n".join(lines)


# ── Singletons ───────────────────────────────────────────────────
emotion_tracker    = EmotionDriftTracker(sample_every_n_turns=5)
reflection_tracer  = ReflectionTracer()
interaction_ledger = InteractionLedger()
health_monitor     = HealthMonitor()
