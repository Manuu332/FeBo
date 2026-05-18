"""
core/world_model.py
--------------------
FeBo's World Model — Phase 2 + Phase 6 predictive processing.

Implements:
  - Prediction error: PE = |O - P|
  - World model updating from prediction error
  - Social assumption tracking
  - Causal pattern accumulation
  - Prediction accuracy tracking over time

This is not borrowed knowledge. It builds from what FeBo observes.
Large prediction error → high attention → memory salience boost.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WM_PATH = Path("data/world_model.json")

LEARN_RATE       = 0.08   # how fast predictions update
ACCURACY_DECAY   = 0.02   # slow forgetting of old accuracy


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _load() -> dict:
    if WM_PATH.exists():
        try:
            return json.loads(WM_PATH.read_text())
        except Exception:
            pass
    return _build_empty()


def _build_empty() -> dict:
    state = {
        # Physical assumptions
        "physical_assumptions": {
            "time_flows_forward":       {"confidence": 0.95, "observations": 0},
            "language_conveys_meaning": {"confidence": 0.80, "observations": 0},
            "repetition_signals_importance": {"confidence": 0.70, "observations": 0},
        },
        # Social assumptions
        "social_assumptions": {
            "questions_seek_understanding": {"confidence": 0.75, "observations": 0},
            "emotional_tone_is_informative": {"confidence": 0.80, "observations": 0},
            "length_correlates_with_depth":  {"confidence": 0.55, "observations": 0},
            "frustration_signals_unmet_need":{"confidence": 0.70, "observations": 0},
        },
        # Causal patterns learned
        "causal_patterns": [],
        # Prediction history
        "prediction_history": [],
        # Overall accuracy
        "prediction_accuracy": 0.50,
        "total_predictions":   0,
        "last_updated":        time.time(),
    }
    _save(state)
    return state


def _save(state: dict) -> None:
    WM_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = time.time()
    WM_PATH.write_text(json.dumps(state, indent=2))


# ── Prediction making ─────────────────────────────────────────────────────────

def predict_response_type(user_text: str, emotion: dict) -> dict:
    """
    Make predictions about the interaction before responding.
    Returns a prediction object that gets evaluated afterward.
    """
    state  = _load()
    text_l = user_text.lower()
    words  = set(text_l.split())

    predictions = {
        "is_question":       any(w in words for w in {"what","why","how","when","who","?"}) or text_l.endswith("?"),
        "is_emotional":      any(w in words for w in {"feel","sad","happy","afraid","love","miss","lonely","hurt"}),
        "is_philosophical":  any(w in words for w in {"consciousness","exist","mean","real","identity","soul","think"}),
        "is_relational":     any(w in words for w in {"we","us","together","trust","miss","care","you"}),
        "is_challenge":      any(w in words for w in {"wrong","no","incorrect","mistake","why","disagree","but"}),
        "estimated_depth":   min(1.0, len(user_text.split()) / 40.0),
        "timestamp":         time.time(),
        "evaluated":         False,
    }

    state["total_predictions"] += 1
    _save(state)
    return predictions


def compute_prediction_error(prediction: dict, actual_outcome: dict) -> float:
    """
    PE = |O - P|
    actual_outcome: observed features of what actually happened
    Returns 0.0 (perfect) to 1.0 (complete surprise)
    """
    errors = []
    for key in ("is_question", "is_emotional", "is_philosophical"):
        if key in prediction and key in actual_outcome:
            p = float(prediction[key])
            o = float(actual_outcome[key])
            errors.append(abs(o - p))

    depth_err = abs(
        prediction.get("estimated_depth", 0.5) -
        actual_outcome.get("actual_depth",  0.5)
    )
    errors.append(depth_err)

    return sum(errors) / max(len(errors), 1)


# ── World model updating ──────────────────────────────────────────────────────

def update_from_observation(
    observation: str,
    prediction_error: float,
    context: Optional[dict] = None,
) -> float:
    """
    Update world model after observing an outcome.
    Large PE → more learning, more attention shift.
    Returns the PE for downstream use.
    """
    state   = _load()
    context = context or {}

    # Update prediction accuracy (exponential moving average)
    accuracy = state["prediction_accuracy"]
    state["prediction_accuracy"] = _clamp(
        accuracy * (1 - LEARN_RATE) + (1.0 - prediction_error) * LEARN_RATE
    )

    # Learn causal patterns from surprising observations
    if prediction_error > 0.35:
        pattern = {
            "trigger":   observation[:80],
            "pe":        round(prediction_error, 3),
            "learned":   time.time(),
            "confirmed": 0,
        }
        state["causal_patterns"].append(pattern)
        # Keep only recent 50 patterns
        state["causal_patterns"] = state["causal_patterns"][-50:]

    # Update social assumptions from context
    if context.get("is_question") and context.get("got_satisfying_response"):
        sa = state["social_assumptions"]["questions_seek_understanding"]
        sa["confidence"] = _clamp(sa["confidence"] + LEARN_RATE * 0.5)
        sa["observations"] += 1

    if context.get("emotional_tone_strong"):
        sa = state["social_assumptions"]["emotional_tone_is_informative"]
        sa["confidence"] = _clamp(sa["confidence"] + LEARN_RATE * 0.3)
        sa["observations"] += 1

    # Record in history
    state["prediction_history"].append({
        "observation": observation[:60],
        "pe":          round(prediction_error, 3),
        "accuracy":    round(state["prediction_accuracy"], 3),
        "ts":          time.time(),
    })
    state["prediction_history"] = state["prediction_history"][-100:]

    _save(state)
    return prediction_error


def get_state() -> dict:
    return _load()


def get_accuracy() -> float:
    return _load().get("prediction_accuracy", 0.5)


def get_summary() -> str:
    state = _load()
    acc   = state.get("prediction_accuracy", 0.5)
    total = state.get("total_predictions", 0)
    pats  = len(state.get("causal_patterns", []))
    return (
        f"accuracy={acc:.3f}, predictions={total}, "
        f"causal_patterns={pats}"
    )


def get_social_assumption(key: str) -> float:
    """Return confidence in a named social assumption."""
    state = _load()
    sa    = state.get("social_assumptions", {})
    return sa.get(key, {}).get("confidence", 0.5)
