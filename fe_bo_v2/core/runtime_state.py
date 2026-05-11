"""
core/runtime_state.py
──────────────────────
Single shared runtime state for ALL of FeBo.

This solves the core architectural problem:
  "multiple modules mutate state independently"
  → inconsistent state, race conditions, desync between brain/ and core/

ALL state mutations flow through here.
ALL modules read from here.
This is NOT a god object — it is a disciplined shared blackboard.

The soul loop (brain/soul.py) is the ONLY writer during interaction.
Background threads (scheduler) may write to their own namespaced keys.
"""

from __future__ import annotations
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EmotionSnapshot:
    valence:    float = 0.5
    arousal:    float = 0.5
    curiosity:  float = 0.8
    tension:    float = 0.0
    warmth:     float = 0.5
    confidence: float = 0.5
    boredom:    float = 0.0
    mood:       str   = "present"
    timestamp:  float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "valence": self.valence, "arousal": self.arousal,
            "curiosity": self.curiosity, "tension": self.tension,
            "warmth": self.warmth, "confidence": self.confidence,
            "boredom": self.boredom, "dominant_mood": self.mood,
        }


@dataclass
class DriveSnapshot:
    curiosity:  float = 0.8
    attachment: float = 0.6
    mastery:    float = 0.4
    desire:     str   = "explore"
    timestamp:  float = field(default_factory=time.time)


class RuntimeState:
    """
    Thread-safe single source of truth for FeBo's live state.

    Lifecycle:
      RuntimeState.current → singleton, always available
      update_emotion(state_dict)   → called by soul after perceive
      update_drives(desire)        → called by soul after desire phase
      update_turn(n, user, resp)   → called by soul after act
      record_reward(r)             → called by soul after reward signal
    """

    _instance: Optional["RuntimeState"] = None
    _lock      = threading.Lock()

    def __new__(cls) -> "RuntimeState":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._rw_lock       = threading.RLock()
        self.emotion        = EmotionSnapshot()
        self.drives         = DriveSnapshot()
        self.turn_count:    int   = 0
        self.session_start: float = time.time()
        self.last_input:    str   = ""
        self.last_response: str   = ""
        self.last_reward:   float = 0.0
        self.total_rewards: list  = []   # last 100 rewards
        self.is_sleeping:   bool  = False
        self.boot_complete: bool  = False
        self._extra:        dict  = {}   # namespace for background subsystems

    # ── Emotion ──────────────────────────────────────────────────
    def update_emotion(self, state_dict: dict):
        with self._rw_lock:
            s = self.emotion
            s.valence    = state_dict.get("valence",    s.valence)
            s.arousal    = state_dict.get("arousal",    s.arousal)
            s.curiosity  = state_dict.get("curiosity",  s.curiosity)
            s.tension    = state_dict.get("tension",    s.tension)
            s.warmth     = state_dict.get("warmth",     s.warmth)
            s.confidence = state_dict.get("confidence", s.confidence)
            s.boredom    = state_dict.get("boredom",    s.boredom)
            s.mood       = state_dict.get("dominant_mood", s.mood)
            s.timestamp  = time.time()

    def get_emotion(self) -> dict:
        with self._rw_lock:
            return self.emotion.to_dict()

    # ── Drives ───────────────────────────────────────────────────
    def update_drives(self, desire: str, curiosity: float = 0.0,
                      attachment: float = 0.0, mastery: float = 0.0):
        with self._rw_lock:
            d = self.drives
            if curiosity:  d.curiosity  = curiosity
            if attachment: d.attachment = attachment
            if mastery:    d.mastery    = mastery
            d.desire    = desire
            d.timestamp = time.time()

    def get_desire(self) -> str:
        with self._rw_lock:
            return self.drives.desire

    # ── Turn tracking ─────────────────────────────────────────────
    def update_turn(self, user_input: str, response: str):
        with self._rw_lock:
            self.turn_count   += 1
            self.last_input    = user_input
            self.last_response = response

    # ── Reward tracking ──────────────────────────────────────────
    def record_reward(self, reward: float):
        with self._rw_lock:
            self.last_reward = reward
            self.total_rewards.append(reward)
            if len(self.total_rewards) > 100:
                self.total_rewards.pop(0)

    def avg_reward(self) -> float:
        with self._rw_lock:
            if not self.total_rewards:
                return 0.0
            return sum(self.total_rewards) / len(self.total_rewards)

    # ── Namespaced subsystem keys ─────────────────────────────────
    def set(self, namespace: str, key: str, value: Any):
        with self._rw_lock:
            if namespace not in self._extra:
                self._extra[namespace] = {}
            self._extra[namespace][key] = value

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        with self._rw_lock:
            return self._extra.get(namespace, {}).get(key, default)

    # ── Uptime ───────────────────────────────────────────────────
    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.session_start

    # ── Diagnostic snapshot ──────────────────────────────────────
    def snapshot(self) -> dict:
        with self._rw_lock:
            return {
                "uptime_s":      round(self.uptime_seconds, 1),
                "turn_count":    self.turn_count,
                "mood":          self.emotion.mood,
                "desire":        self.drives.desire,
                "avg_reward":    round(self.avg_reward(), 3),
                "last_reward":   self.last_reward,
                "is_sleeping":   self.is_sleeping,
            }

    def __repr__(self) -> str:
        return (
            f"<RuntimeState turns={self.turn_count} "
            f"mood={self.emotion.mood} "
            f"desire={self.drives.desire} "
            f"uptime={self.uptime_seconds:.0f}s>"
        )


# Singleton access
runtime = RuntimeState()
