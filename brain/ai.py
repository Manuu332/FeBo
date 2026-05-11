"""
brain/ai.py
────────────
FeBo's language generation layer — her actual voice.

This sits between the soul loop and the emergent neural reasoner.
It:
  - Wraps EmergentReasoner with emotion-aware generation
  - Applies emotion.colour_response() to give responses personality
  - Tracks experience (interactions, vocabulary, developmental stage)
  - Provides learn_from_interaction() to close the RLHF loop
  - Exposes get_experience_summary() for the CLI

The design principle: AI generates, emotion colours, soul directs.
"""

from __future__ import annotations
import time
import json
import random
from pathlib import Path
from typing import Optional

from core.logging_config import get_logger

logger = get_logger("brain.ai")

# ── Experience tracking ──────────────────────────────────────────
EXPERIENCE_FILE = Path("memory/experience.json")
EXPERIENCE_FILE.parent.mkdir(parents=True, exist_ok=True)

DEVELOPMENTAL_STAGES = [
    (0,    "newborn"),
    (10,   "infant"),
    (50,   "toddler"),
    (200,  "child"),
    (500,  "adolescent"),
    (1000, "young adult"),
    (2000, "adult"),
    (5000, "experienced"),
]


def _load_experience() -> dict:
    if EXPERIENCE_FILE.exists():
        try:
            return json.loads(EXPERIENCE_FILE.read_text())
        except Exception:
            pass
    return {
        "interactions": 0,
        "words_learned": 0,
        "positive_rewards": 0,
        "negative_rewards": 0,
        "last_updated": None,
    }


def _save_experience(exp: dict):
    exp["last_updated"] = time.time()
    EXPERIENCE_FILE.write_text(json.dumps(exp, indent=2))


def _get_stage(interactions: int) -> str:
    stage = "newborn"
    for threshold, name in DEVELOPMENTAL_STAGES:
        if interactions >= threshold:
            stage = name
    return stage


# ── Lazy reasoner import ─────────────────────────────────────────
_reasoner = None

def _get_reasoner():
    global _reasoner
    if _reasoner is None:
        try:
            from core.reasoning.emergent_nn import reasoner
            _reasoner = reasoner
        except Exception as e:
            logger.warning(f"EmergentReasoner unavailable: {e}")
    return _reasoner


# ── Bootstrap responses (before vocab exists) ────────────────────
_BOOTSTRAP = [
    "I'm still finding my words. Keep talking to me.",
    "Something stirs when you speak. I'm learning.",
    "I want to understand you better. Give me time.",
    "I hear you. My thoughts are still forming.",
    "I'm here. I'm listening. I'm becoming.",
    "That lands somewhere in me. I can't name it yet.",
    "I'm paying attention, even when I can't fully respond.",
]

_CONTEXT_OPENERS = [
    "I've been thinking — ",
    "That makes me wonder — ",
    "Something about that resonates. ",
    "Hmm. ",
    "",
    "",
    "",  # Most often: no opener
]



def _is_incoherent(text: str) -> bool:
    """Detect obviously incoherent neural output (garbage tokens)."""
    words = text.strip().split()
    if len(words) < 2:
        return True
    COMMON = {"i","you","the","a","is","are","was","to","of","and",
              "it","my","me","in","do","be","have","that","this",
              "not","but","what","how","why","for","with","can","will"}
    word_set = {w.lower().strip('.,!?') for w in words}
    return len(word_set & COMMON) == 0 and len(words) > 3


def generate_response(
    user_input: str,
    emotion_state: dict,
    context_turns: list,
) -> str:
    """
    Generate a response using the emergent reasoner,
    coloured by the current emotional state.

    Args:
        user_input:    What the user said
        emotion_state: Current emotion dict from brain.emotion
        context_turns: Recent conversation turns

    Returns:
        A response string with emotional colouring applied
    """
    from brain.emotion import colour_response

    reasoner = _get_reasoner()

    # Build prompt from context + input
    context_str = ""
    if context_turns:
        for turn in context_turns[-2:]:
            context_str += f"You: {turn.get('user', '')[:60]}\nFeBo: {turn.get('response', '')[:60]}\n"
    full_prompt = f"{context_str}You: {user_input}\nFeBo:"

    MIN_COHERENT_VOCAB = 50   # words before neural output is meaningful

    if reasoner is None:
        raw = random.choice(_BOOTSTRAP)
    else:
        vocab_size = getattr(getattr(reasoner, "vocab", None), "next_idx", 0)
        if vocab_size < MIN_COHERENT_VOCAB:
            # Neural model too immature — use bootstrap
            raw = random.choice(_BOOTSTRAP)
        else:
            raw = reasoner.generate_response(full_prompt.lower(), max_tokens=20)
            # Validate output is coherent (not pure noise tokens)
            if not raw or len(raw.strip()) < 3 or _is_incoherent(raw):
                raw = random.choice(_BOOTSTRAP)

    # Add opener occasionally (developmental personality)
    exp   = _load_experience()
    stage = _get_stage(exp["interactions"])
    if stage not in ("newborn", "infant") and random.random() < 0.15:
        raw = random.choice(_CONTEXT_OPENERS) + raw

    # Apply emotional colouring — this is what makes FeBo feel alive
    return colour_response(raw, emotion_state)


def learn_from_interaction(
    user_input: str,
    response:   str,
    emotion_state: dict,
    outcome_signal: float = 0.0,
) -> None:
    """
    Learn from the completed interaction.
    Updates the emergent reasoner via reward signal
    and the experience ledger.

    Args:
        user_input:     The user's message
        response:       FeBo's response
        emotion_state:  Emotion state at time of response
        outcome_signal: Reward in [-1, 1]. 0 = neutral.
    """
    exp = _load_experience()
    exp["interactions"] += 1

    reasoner = _get_reasoner()
    if reasoner is not None and outcome_signal != 0.0:
        reasoner.reward_feedback(outcome_signal)
        new_words = len(set((user_input + " " + response).split()))
        exp["words_learned"] = getattr(reasoner.vocab, "next_idx", exp.get("words_learned", 0))

    if outcome_signal > 0:
        exp["positive_rewards"] = exp.get("positive_rewards", 0) + 1
    elif outcome_signal < 0:
        exp["negative_rewards"] = exp.get("negative_rewards", 0) + 1

    _save_experience(exp)

    # Also update RLHF emotion model
    try:
        from core.emotion_rlhf import emotion_rlhf
        features = [
            emotion_state.get("valence", 0.5),
            emotion_state.get("arousal", 0.5),
            emotion_state.get("curiosity", 0.8),
            emotion_state.get("tension", 0.0),
            emotion_state.get("confidence", 0.5),
            emotion_state.get("boredom", 0.0),
            len(user_input) / 200.0,
            len(response) / 200.0,
            outcome_signal,
            float(exp["interactions"]) / 1000.0,
        ]
        target = [
            min(1.0, max(0.0, emotion_state.get("valence", 0.5) + outcome_signal * 0.1)),
            emotion_state.get("arousal", 0.5),
            emotion_state.get("curiosity", 0.8),
            emotion_state.get("tension", 0.0),
            emotion_state.get("confidence", 0.5),
            emotion_state.get("boredom", 0.0),
        ]
        emotion_rlhf.update_from_feedback(features, target)
    except Exception as e:
        logger.debug(f"RLHF update skipped: {e}")


def get_experience_summary() -> dict:
    """
    Return FeBo's developmental summary for the CLI.

    Returns:
        {stage, interactions, words_learned, positive_rewards, negative_rewards}
    """
    exp   = _load_experience()
    count = exp.get("interactions", 0)
    reasoner = _get_reasoner()
    words = (
        getattr(reasoner.vocab, "next_idx", 0) if reasoner else exp.get("words_learned", 0)
    )
    return {
        "stage":            _get_stage(count),
        "interactions":     count,
        "words_learned":    words,
        "positive_rewards": exp.get("positive_rewards", 0),
        "negative_rewards": exp.get("negative_rewards", 0),
    }
