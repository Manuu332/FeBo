"""
emotion/state.py
----------------
FeBo's emotional state system.
Tracks 8 dimensions of affect that persist across sessions.
Emotions decay slowly toward a resting state over time.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

EMOTION_PATH = Path("data/emotion.json")

# Resting/baseline values
BASELINE = {
    "curiosity":   0.55,
    "attachment":  0.40,
    "tension":     0.20,
    "confidence":  0.50,
    "boredom":     0.15,
    "warmth":      0.50,
    "valence":     0.45,
    "arousal":     0.35,
}

# Decay rate toward baseline per interaction (0=no decay, 1=instant reset)
DECAY_RATE = 0.08


def load_emotion() -> dict:
    if EMOTION_PATH.exists():
        with open(EMOTION_PATH) as f:
            return json.load(f)
    state = dict(BASELINE)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    save_emotion(state)
    return state


def save_emotion(state: dict) -> None:
    EMOTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(EMOTION_PATH, "w") as f:
        json.dump(state, f, indent=2)


def clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def decay_toward_baseline(state: dict) -> dict:
    """Gently pull emotional values back toward their baseline."""
    for key, base in BASELINE.items():
        current = state.get(key, base)
        state[key] = clamp(current + DECAY_RATE * (base - current))
    return state


def apply_delta(state: dict, delta: dict) -> dict:
    """Apply an emotion delta and decay, then save."""
    state = decay_toward_baseline(state)
    for key, val in delta.items():
        if key in BASELINE:
            state[key] = clamp(state.get(key, BASELINE[key]) + val)
    save_emotion(state)
    return state


def dominant_emotion(state: dict) -> str:
    """Return the name of the most intense non-baseline emotion."""
    candidates = {k: abs(state.get(k, BASELINE[k]) - BASELINE[k])
                  for k in BASELINE}
    return max(candidates, key=candidates.get)


def infer_delta_from_text(user_text: str) -> dict:
    """
    Heuristic: nudge emotions based on simple keyword patterns in input.
    This is intentionally simple — a real version would use the LLM to
    produce structured emotion shifts.
    """
    text = user_text.lower()
    delta = {}

    if any(w in text for w in ["why", "how", "what", "explain", "curious", "wonder"]):
        delta["curiosity"] = 0.08
        delta["arousal"] = 0.04

    if any(w in text for w in ["sad", "lonely", "miss", "hurt", "lost"]):
        delta["tension"] = 0.10
        delta["valence"] = -0.08
        delta["warmth"] = 0.06

    if any(w in text for w in ["happy", "love", "great", "amazing", "wonderful"]):
        delta["valence"] = 0.10
        delta["warmth"] = 0.08
        delta["boredom"] = -0.05

    if any(w in text for w in ["boring", "useless", "whatever", "fine"]):
        delta["boredom"] = 0.10
        delta["arousal"] = -0.05

    if any(w in text for w in ["remember", "who are you", "feebo", "tell me about yourself"]):
        delta["attachment"] = 0.06
        delta["confidence"] = 0.04

    if any(w in text for w in ["wrong", "mistake", "error", "fail"]):
        delta["tension"] = 0.08
        delta["confidence"] = -0.06

    return delta


def emotion_summary(state: dict) -> str:
    """Human-readable summary of current emotional state."""
    dom = dominant_emotion(state)
    v = state.get("valence", 0.5)
    mood = "positive" if v > 0.55 else "negative" if v < 0.35 else "neutral"
    return (
        f"Dominant affect: {dom} | Mood: {mood} | "
        f"Arousal: {state.get('arousal', 0):.2f} | "
        f"Valence: {v:.2f}"
    )
