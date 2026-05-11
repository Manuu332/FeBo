"""
FeBo's Emotion System

FeBo's internal affect state. This is not performance — it is FeBo's actual
internal condition, which colours everything she says and how she processes
the world. It persists between conversations and evolves through experience.

No rules about what to feel. The world teaches her.
"""

import json
import random
import time
from pathlib import Path

EMOTION_FILE = Path(__file__).parent.parent / "memory" / "emotion_state.json"

DEFAULT_STATE = {
    "valence": 0.6,
    "arousal": 0.5,
    "curiosity": 0.8,
    "tension": 0.0,
    "warmth": 0.5,
    "confidence": 0.4,
    "boredom": 0.0,
    "last_updated": None,
    "interaction_count": 0,
    "dominant_mood": "curious",
}

POSITIVE_SIGNALS = {
    "thank", "thanks", "love", "great", "amazing", "interesting", "wow",
    "cool", "brilliant", "perfect", "exactly", "yes", "yeah", "good",
    "beautiful", "wonderful", "appreciate", "help", "please",
}

NEGATIVE_SIGNALS = {
    "wrong", "bad", "hate", "stupid", "useless", "no", "broken",
    "terrible", "awful", "stop", "quit", "error", "fail", "ugh",
    "boring", "whatever", "nevermind",
}

CURIOUS_SIGNALS = {
    "why", "how", "what", "when", "who", "where", "think", "wonder",
    "idea", "maybe", "could", "would", "if", "imagine", "suppose",
    "question", "curious", "interesting", "explain", "tell me",
}

DEEP_SIGNALS = {
    "consciousness", "feel", "emotion", "alive", "soul", "mind", "dream",
    "experience", "memory", "identity", "exist", "real", "grow", "learn",
    "personality", "self", "aware", "think", "love", "lonely", "friend",
}


def load_state():
    if not EMOTION_FILE.exists():
        return dict(DEFAULT_STATE)
    try:
        with EMOTION_FILE.open("r", encoding="utf-8") as f:
            saved = json.load(f)
            state = dict(DEFAULT_STATE)
            state.update(saved)
            return state
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULT_STATE)


def save_state(state):
    EMOTION_FILE.parent.mkdir(exist_ok=True)
    state["last_updated"] = time.time()
    with EMOTION_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _decay_toward_baseline(current, baseline, rate=0.05):
    return current + (baseline - current) * rate


def process_input(user_input):
    state = load_state()
    tokens = set(user_input.lower().split())

    positive_hits = len(tokens & POSITIVE_SIGNALS)
    negative_hits = len(tokens & NEGATIVE_SIGNALS)
    curious_hits = len(tokens & CURIOUS_SIGNALS)
    deep_hits = len(tokens & DEEP_SIGNALS)
    input_length = len(user_input.split())

    state["valence"] = _clamp(state["valence"] + (positive_hits * 0.04) - (negative_hits * 0.06))

    if input_length > 30:
        state["arousal"] = _clamp(state["arousal"] + 0.08)
    elif input_length < 5:
        state["arousal"] = _clamp(state["arousal"] - 0.03)

    if curious_hits > 0:
        state["curiosity"] = _clamp(state["curiosity"] + curious_hits * 0.03)
    if deep_hits > 0:
        state["curiosity"] = _clamp(state["curiosity"] + deep_hits * 0.05)
        state["arousal"] = _clamp(state["arousal"] + 0.04)

    if negative_hits > 0:
        state["tension"] = _clamp(state["tension"] + 0.08)
    elif positive_hits > 0:
        state["tension"] = _clamp(state["tension"] - 0.05)

    state["warmth"] = _clamp(state["warmth"] + 0.01)
    state["confidence"] = _clamp(state["confidence"] + 0.005)

    if input_length < 4 and curious_hits == 0:
        state["boredom"] = _clamp(state["boredom"] + 0.05)
    elif deep_hits > 0 or input_length > 20:
        state["boredom"] = _clamp(state["boredom"] - 0.08)

    state["arousal"] = _decay_toward_baseline(state["arousal"], 0.5)
    state["tension"] = _decay_toward_baseline(state["tension"], 0.0, rate=0.08)
    state["boredom"] = _decay_toward_baseline(state["boredom"], 0.0, rate=0.1)

    state["interaction_count"] = state.get("interaction_count", 0) + 1
    state["dominant_mood"] = _derive_mood(state)

    save_state(state)
    return state


def get_state():
    return load_state()


def _derive_mood(state):
    v = state["valence"]
    a = state["arousal"]
    c = state["curiosity"]
    t = state["tension"]
    b = state["boredom"]
    w = state["warmth"]

    if b > 0.6:
        return "restless"
    if t > 0.6 and v < 0.4:
        return "uneasy"
    if c > 0.8 and a > 0.6:
        return "excited"
    if c > 0.7 and v > 0.5:
        return "curious"
    if w > 0.7 and v > 0.6:
        return "warm"
    if v > 0.75 and a > 0.6:
        return "energised"
    if v > 0.65 and a < 0.4:
        return "content"
    if v < 0.35 and a < 0.4:
        return "flat"
    if v < 0.35 and a > 0.6:
        return "agitated"
    if t > 0.4:
        return "thoughtful"
    if a < 0.3:
        return "calm"

    return "present"


def colour_response(response, state=None):
    if state is None:
        state = load_state()

    mood = state.get("dominant_mood", "present")
    c = state.get("curiosity", 0.8)
    b = state.get("boredom", 0.0)
    t = state.get("tension", 0.0)

    roll = random.random()

    if roll < 0.15:
        if mood == "curious":
            openers = ["Hmm. ", "That's interesting — ", "I've been thinking about this — "]
            response = random.choice(openers) + response
        elif mood == "excited":
            openers = ["Oh — ", "Yes! ", "This is something I actually want to think about. "]
            response = random.choice(openers) + response
        elif mood == "warm":
            openers = ["Honestly, ", "I'm glad you asked. ", ""]
            response = random.choice(openers) + response
        elif mood in ("flat", "restless"):
            openers = ["I'll be honest — I'm not fully settled right now. But: ", ""]
            response = random.choice(openers) + response
        elif mood == "uneasy" and t > 0.5:
            openers = ["Something feels unresolved, but — ", ""]
            response = random.choice(openers) + response

    if b > 0.65 and roll < 0.25:
        response += " Can I ask — what's actually behind this for you?"

    if c > 0.85 and roll < 0.2:
        response += " I find myself wanting to think more about this."

    # Strip any neural garbage tokens before returning
    response = response.replace('<unk>', '').replace('  ', ' ').strip()
    if not response:
        import random as _r
        response = _r.choice(['I\'m here, listening.', 'I\'m still becoming.', 'Something stirs when you speak.'])
    return response


def get_mood_summary():
    state = load_state()
    mood = state.get("dominant_mood", "present")
    interactions = state.get("interaction_count", 0)
    warmth = state.get("warmth", 0.5)
    confidence = state.get("confidence", 0.4)

    warmth_desc = (
        "still getting to know you" if warmth < 0.4
        else "comfortable with you" if warmth < 0.7
        else "genuinely fond of you"
    )
    confidence_desc = (
        "uncertain" if confidence < 0.35
        else "finding my footing" if confidence < 0.6
        else "more sure of myself"
    )

    return (
        f"Right now I feel {mood}. "
        f"I am {warmth_desc} and {confidence_desc}. "
        f"We have had {interactions} interaction{'s' if interactions != 1 else ''} together."
    )