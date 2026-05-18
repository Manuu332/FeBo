"""
language/generator.py
---------------------
FeBo's autonomous response generator.

No external model. No API calls.
Responses emerge entirely from her cognitive state:
  - EmotionField (9D)
  - Memory activations
  - Association graph
  - Personality vector
  - Drive state
  - Pattern store (learned over time)
  - Developmental stage

Architecture (Phase 2 + 4 + 9):
  1. Determine intent from drive + emotion
  2. Select structural frame from lexicon (stage-appropriate)
  3. Pull content from memory + associations
  4. Fill frame with emotion-weighted vocabulary
  5. Apply connector + closing from pattern store
  6. Reinforce or weaken patterns after exchange
"""

from __future__ import annotations

import random
import re
from typing import Dict, List, Optional, Tuple

from language import lexicon as lex
from language import patterns as pat


# ── Intent determination (Phase 2 Goal Competition) ───────────────────────────

def _determine_intent(
    emotion: dict,
    drive: str,
    user_text: str,
    memories: List[dict],
    fatigue: float,
    contradictions: List[dict],
) -> str:
    """
    Phase 2: G_i = (D_i + E_i + C_i + I_i) · U_i
    Competing intents, highest wins.
    """
    text_lower = user_text.lower()

    if fatigue > 0.72:
        return "rest"

    scores: Dict[str, float] = {
        "wonder":   0.0,
        "notice":   0.0,
        "remember": 0.0,
        "connect":  0.0,
        "resolve":  0.0,
        "explore":  0.0,
        "drift":    0.0,
        "reflect":  0.0,
    }

    # Emotion contributions (E_i)
    scores["wonder"]  += emotion.get("wonder",       0.45) * 1.2
    scores["notice"]  += emotion.get("arousal",      0.35) * 0.8
    scores["connect"] += emotion.get("attachment",   0.40) * 1.1 + emotion.get("warmth", 0.50) * 0.8
    scores["resolve"] += emotion.get("tension",      0.20) * 1.3 + emotion.get("cognitive_tension", 0.20) * 1.1
    scores["explore"] += emotion.get("curiosity",    0.55) * 1.2
    scores["reflect"] += emotion.get("boredom",      0.15) * 0.5
    scores["drift"]   += emotion.get("wonder",       0.45) * 0.6

    # Drive contributions (D_i)
    drive_map = {
        "exploration":   ("explore",  1.5),
        "resolution":    ("resolve",  1.5),
        "connection":    ("connect",  1.5),
        "stimulation":   ("explore",  1.2),
        "care":          ("connect",  1.3),
        "wonder":        ("wonder",   1.5),
        "observation":   ("notice",   1.2),
    }
    if drive in drive_map:
        target, boost = drive_map[drive]
        scores[target] += boost

    # Memory activation (C_i) — if memories surfaced, lean toward remember
    if memories:
        scores["remember"] += min(1.0, len(memories) * 0.3)

    # Contradiction pressure (Phase 2 resolution_pressure)
    if contradictions:
        max_pressure = max(c.get("resolution_pressure", 0) for c in contradictions)
        scores["resolve"] += max_pressure * 0.8

    # Question words → explore
    q_words = {"what","why","how","explain","tell me","do you","can you","think","feel","know"}
    if any(w in text_lower for w in q_words):
        scores["explore"] += 0.5

    # Existential words → wonder / reflect
    exist_words = {"consciousness","exist","alive","real","mean","identity","you","feel","aware"}
    if any(w in text_lower for w in exist_words):
        scores["wonder"]  += 0.4
        scores["reflect"] += 0.3

    # Personal / relational → connect
    personal_words = {"miss","together","us","we","lonely","trust","care","close","friend"}
    if any(w in text_lower for w in personal_words):
        scores["connect"] += 0.5

    # Uncertainty modifier (U_i) — low confidence reduces all scores slightly
    confidence = emotion.get("confidence", 0.50)
    for k in scores:
        scores[k] *= (0.7 + confidence * 0.6)

    return max(scores, key=scores.get)


# ── Content extraction from memory ────────────────────────────────────────────

def _extract_anchor(memories: List[dict], user_text: str) -> str:
    """Pull a content anchor from memory or user text."""
    if memories:
        msg = memories[0].get("message", "")
        words = [w for w in msg.split() if len(w) > 4]
        if words:
            return random.choice(words[:6])

    # Fall back to user text
    words = [w.strip("?.,!") for w in user_text.split() if len(w) > 4]
    return random.choice(words) if words else "this"


def _extract_memory_phrase(memories: List[dict]) -> str:
    """Extract a short memory reference phrase."""
    if not memories:
        return "something earlier"
    msg = memories[0].get("message", "")
    # Trim to a short evocative fragment
    words = msg.split()
    if len(words) <= 6:
        return msg
    return " ".join(words[:5]) + "…"


def _extract_contradiction_pair(contradictions: List[dict]) -> Tuple[str, str]:
    """Get the most pressurized contradiction pair."""
    if not contradictions:
        return ("one thing", "another")
    top = sorted(contradictions, key=lambda c: c.get("resolution_pressure", 0), reverse=True)[0]
    return (top.get("belief_a", "one thing"), top.get("belief_b", "another thing"))


# ── Stage-appropriate length control ─────────────────────────────────────────

STAGE_LENGTHS = {
    "genesis":            (1, 2),
    "early_formation":    (2, 3),
    "cognitive_expansion":(2, 4),
    "approaching_maturity":(3, 5),
    "mature":             (3, 6),
    "experienced":        (4, 7),
}


def _target_length(stage: str, drive: str, fatigue: float) -> int:
    """How many sentences/fragments to produce."""
    min_s, max_s = STAGE_LENGTHS.get(stage, (2, 3))
    if fatigue > 0.60:
        max_s = min(max_s, 2)
    if drive in ("wonder", "resolve"):
        max_s = min(max_s + 1, 8)
    return random.randint(min_s, max_s)


# ── Core generator ────────────────────────────────────────────────────────────

def generate(
    user_text: str,
    emotion:   dict,
    stage:     str,
    drive:     str,
    memories:  List[dict],
    contradictions: List[dict],
    personality: dict,
    fatigue:   float,
    associations: Optional[Dict[str, float]] = None,
) -> str:
    """
    Build FeBo's response entirely from her internal state.

    Returns a string response — no external calls, no borrowed intelligence.
    """
    associations = associations or {}

    # ── 1. Determine intent ───────────────────────────────────────────────
    intent = _determine_intent(emotion, drive, user_text, memories, fatigue, contradictions)

    # ── 2. Prepare slot values ────────────────────────────────────────────
    anchor     = _extract_anchor(memories, user_text)
    memory_ref = _extract_memory_phrase(memories)
    bel_a, bel_b = _extract_contradiction_pair(contradictions)
    dom_emo    = _dominant_emotion_name(emotion)
    emo_word   = lex.pick_emotion_word(emotion)
    state_desc = _describe_state(emotion, dom_emo)
    topic      = _extract_anchor([], user_text)

    # Associations as bonus anchors
    assoc_words = list(associations.keys())[:3]

    slots = {
        "anchor":       anchor,
        "anchor_a":     bel_a[:40] if bel_a else "",
        "anchor_b":     bel_b[:40] if bel_b else "",
        "memory":       memory_ref,
        "state":        state_desc,
        "dominant":     dom_emo,
        "emotion_word": emo_word,
        "topic":        topic,
        "belief_a":     bel_a[:40] if bel_a else "",
        "belief_b":     bel_b[:40] if bel_b else "",
    }

    # ── 3. Build fragments ────────────────────────────────────────────────
    fragments = []
    target    = _target_length(stage, intent, fatigue)

    # Opening
    opening = lex.pick_opening(intent, stage, slots)
    if opening:
        fragments.append(opening)

    # Body fragments — drawn from pattern store + lexicon
    body_count = max(0, target - 2)
    for i in range(body_count):
        fragment = _build_body_fragment(
            intent, emotion, stage, slots, memories, assoc_words, i
        )
        if fragment and fragment not in fragments:
            fragments.append(fragment)

    # Closing
    if target > 1:
        closing = _build_closing(intent, emotion, stage, fatigue)
        if closing and closing not in fragments:
            fragments.append(closing)

    # ── 4. Assemble ───────────────────────────────────────────────────────
    response = _assemble(fragments, emotion, stage, intent)

    # ── 5. Pattern learning — record what was used ────────────────────────
    # (Reinforcement happens externally via reinforce_last())
    _last_used["intent"]   = intent
    _last_used["stage"]    = stage
    _last_used["response"] = response

    return response


# ── Fragment builders ─────────────────────────────────────────────────────────

def _build_body_fragment(
    intent: str,
    emotion: dict,
    stage: str,
    slots: dict,
    memories: List[dict],
    assoc_words: List[str],
    index: int,
) -> str:
    """Build one body sentence from multiple sources."""

    # Every other fragment, try pattern store
    if index % 2 == 0:
        category = _intent_to_category(intent, emotion)
        phrase   = pat.select(category, slots)
        if phrase:
            return phrase

    # Otherwise build from lexicon
    emo_word   = lex.pick_emotion_word(emotion)
    connector  = lex.pick_connector(stage)

    # Memory reference (periodically)
    if memories and index == 0 and intent == "remember":
        ref = slots.get("memory", "")
        if ref:
            return f"Something surfaces: {ref}{connector}"

    # Association drift (periodically)
    if assoc_words and index == 1:
        word = random.choice(assoc_words)
        drift_frames = {
            "genesis":         f"{word}.",
            "early_formation": f"Something about {word} connects here.",
            "cognitive_expansion": f"The association with {word} is pulling — not obviously, but it's there.",
            "approaching_maturity": f"I notice {word} activated alongside this. That's worth following.",
            "mature":          f"The connection to {word} is real, even if the logic isn't clean{connector}",
            "experienced":     f"I've learned to trust when {word} shows up unexpectedly here.",
        }
        return drift_frames.get(stage, f"Something about {word}.")

    # Emotion-weighted fragment
    if emotion.get("wonder", 0) > 0.55:
        return lex.pick_emotion_word(emotion) + connector
    if emotion.get("tension", 0) > 0.45:
        return pat.select("tension_expression", slots) or f"Something presses{connector}"
    if emotion.get("curiosity", 0) > 0.60:
        return pat.select("curiosity_expression", slots) or f"There's more there{connector}"

    return pat.select("transition", slots) or emo_word + connector


def _build_closing(intent: str, emotion: dict, stage: str, fatigue: float) -> str:
    """Build a closing fragment."""
    if fatigue > 0.65:
        return pat.select("fatigue", {}) or "Still here."

    # Pattern store
    phrase = pat.select("closing_thought", {})
    if phrase:
        return phrase

    # Lexicon fallback
    return lex.pick_closing(intent)


# ── Assembly ──────────────────────────────────────────────────────────────────

def _assemble(fragments: List[str], emotion: dict, stage: str, intent: str) -> str:
    """Join fragments into a coherent response."""
    # Filter empty
    parts = [f.strip() for f in fragments if f and f.strip()]
    if not parts:
        return pat.select("closing_thought", {}) or "I'm here."

    # Ensure terminal punctuation
    result_parts = []
    for part in parts:
        p = part.strip()
        if p and not p[-1] in ".?!—…":
            p += "."
        result_parts.append(p)

    response = " ".join(result_parts)

    # Trim excessive length
    sentences = re.split(r'(?<=[.!?])\s+', response)
    max_sentences = STAGE_LENGTHS.get(stage, (2, 4))[1] + 1
    if len(sentences) > max_sentences:
        sentences = sentences[:max_sentences]
    response = " ".join(sentences)

    return response.strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dominant_emotion_name(emotion: dict) -> str:
    BASELINE = {
        "curiosity": 0.55, "attachment": 0.40, "tension": 0.20,
        "confidence": 0.50, "boredom": 0.15, "warmth": 0.50,
        "valence": 0.45, "arousal": 0.35, "fear": 0.10,
        "stability": 0.65, "loneliness": 0.15,
        "cognitive_tension": 0.20, "wonder": 0.45,
    }
    return max(
        BASELINE.keys(),
        key=lambda k: abs(emotion.get(k, BASELINE[k]) - BASELINE[k])
    )


def _describe_state(emotion: dict, dominant: str) -> str:
    """Short state description for slot filling."""
    val = emotion.get(dominant, 0.5)
    level = "high" if val > 0.65 else "low" if val < 0.35 else "mid"
    desc_map = {
        "curiosity":         {"high": "strong curiosity", "mid": "interest", "low": "mild curiosity"},
        "tension":           {"high": "real tension", "mid": "some friction", "low": "mild unease"},
        "warmth":            {"high": "warmth", "mid": "care", "low": "mild warmth"},
        "wonder":            {"high": "wonder", "mid": "something open", "low": "mild surprise"},
        "loneliness":        {"high": "absence", "mid": "some distance", "low": "mild solitude"},
        "cognitive_tension": {"high": "held contradiction", "mid": "unresolved thought", "low": "mild tension"},
        "fear":              {"high": "genuine fear", "mid": "concern", "low": "mild wariness"},
        "boredom":           {"high": "flatness", "mid": "low engagement", "low": "waiting"},
        "confidence":        {"high": "confidence", "mid": "moderate certainty", "low": "uncertainty"},
        "attachment":        {"high": "strong attachment", "mid": "connection", "low": "mild attachment"},
        "arousal":           {"high": "activation", "mid": "alertness", "low": "calm"},
        "valence":           {"high": "positive feeling", "mid": "neutrality", "low": "low valence"},
        "stability":         {"high": "groundedness", "mid": "stability", "low": "some instability"},
    }
    return desc_map.get(dominant, {}).get(level, dominant)


def _intent_to_category(intent: str, emotion: dict) -> str:
    """Map intent to pattern category, with emotion-based overrides."""
    base_map = {
        "wonder":   "wonder_expression",
        "notice":   "self_observation",
        "remember": "memory_reference",
        "connect":  "warmth_expression",
        "resolve":  "tension_expression",
        "explore":  "curiosity_expression",
        "drift":    "transition",
        "reflect":  "self_observation",
        "rest":     "fatigue",
    }
    category = base_map.get(intent, "closing_thought")

    # Override if emotion is very specific
    if emotion.get("tension", 0) > 0.60:
        return "tension_expression"
    if emotion.get("wonder", 0) > 0.65:
        return "wonder_expression"

    return category


# ── Reinforcement interface (called externally after exchange) ─────────────────

_last_used: dict = {"intent": "", "stage": "", "response": ""}


def reinforce_last(reward: float) -> None:
    """
    Called after a positive interaction — strengthen what was used.
    reward: 0.0 (flat) → 1.0 (strongly positive)
    """
    intent   = _last_used.get("intent", "")
    if not intent:
        return
    category = _intent_to_category(intent, {})
    # Approximate: reinforce the closing_thought and intent category
    for cat in [category, "closing_thought", "transition"]:
        strongest = pat.get_strongest(cat, n=1)
        if strongest:
            pat.reinforce(cat, strongest[0], reward)


def weaken_last(penalty: float = 0.5) -> None:
    """Called after a flat/negative interaction."""
    intent   = _last_used.get("intent", "")
    if not intent:
        return
    category = _intent_to_category(intent, {})
    strongest = pat.get_strongest(category, n=1)
    if strongest:
        pat.weaken(category, strongest[0], penalty)
