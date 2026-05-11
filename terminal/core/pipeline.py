"""
core/pipeline.py
----------------
FeBo's cognitive pipeline.
Orchestrates: memory retrieval → emotion weighting → reflection influence → LLM response.
Returns the response plus a structured cognitive trace for observability.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

import anthropic

from emotion.state import (
    load_emotion, apply_delta, infer_delta_from_text,
    dominant_emotion, emotion_summary, BASELINE
)
from memory.store import (
    retrieve_for_context, save_memory, get_recent_memories, memory_count
)
from reflection.engine import (
    get_reflections, should_reflect, compose_reflection, write_reflection
)
from identity.profile import load_identity, get_narrative_summary, append_narrative


# ── Singleton Anthropic client ────────────────────────────────────────────────

_client: Optional[anthropic.Anthropic] = None

def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. "
                "Add it to your .env file or Codespaces secrets."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ── Interaction counter (in-memory, reset each session) ───────────────────────

_interaction_count = 0


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(user_input: str) -> dict:
    """
    Full cognitive pipeline.
    Returns: {
        response: str,
        emotion: dict,
        trace: dict,
        reflection: str | None,
    }
    """
    global _interaction_count
    _interaction_count += 1

    trace = {
        "step": _interaction_count,
        "input_preview": user_input[:80],
        "memories_accessed": [],
        "dominant_emotion": None,
        "active_drive": None,
        "reflection_influence": None,
        "response_strategy": "anthropic_llm",
    }

    # ── 1. Load state ─────────────────────────────────────────────────────────
    emotion_state = load_emotion()
    identity = load_identity()

    # ── 2. Memory retrieval ───────────────────────────────────────────────────
    relevant_memories = retrieve_for_context(user_input, limit=4)
    trace["memories_accessed"] = [
        {"id": m["id"], "snippet": m["message"][:60], "importance": m["importance"]}
        for m in relevant_memories
    ]

    # ── 3. Emotion weighting ──────────────────────────────────────────────────
    delta = infer_delta_from_text(user_input)
    emotion_state = apply_delta(emotion_state, delta)
    dom = dominant_emotion(emotion_state)
    trace["dominant_emotion"] = dom
    trace["emotion_snapshot"] = {k: round(v, 3) for k, v in emotion_state.items()
                                  if k in BASELINE}

    # ── 4. Drive inference ────────────────────────────────────────────────────
    drive = _infer_active_drive(emotion_state)
    trace["active_drive"] = drive

    # ── 5. Reflection influence ───────────────────────────────────────────────
    recent_reflections = get_reflections(limit=3)
    reflection_text = recent_reflections[0]["text"] if recent_reflections else None
    trace["reflection_influence"] = reflection_text[:80] if reflection_text else None

    # ── 6. Build LLM system prompt ────────────────────────────────────────────
    system_prompt = _build_system_prompt(
        identity, emotion_state, dom, drive,
        relevant_memories, reflection_text
    )

    # ── 7. Generate response ──────────────────────────────────────────────────
    try:
        client = get_client()
        llm_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_input}],
        )
        response_text = llm_response.content[0].text.strip()
        trace["response_strategy"] = "anthropic_llm"
    except RuntimeError:
        # No API key — fall back silently to template response built from live state
        response_text = _template_response(user_input, dom, drive, emotion_state, relevant_memories)
        trace["response_strategy"] = "template_fallback"

    # ── 8. Save interaction to memory ─────────────────────────────────────────
    importance = _score_importance(user_input, emotion_state)
    save_memory("user", user_input, emotion_snapshot=emotion_state, importance=importance)
    save_memory("feebo", response_text, emotion_snapshot=emotion_state, importance=importance)

    # ── 9. Periodic reflection ────────────────────────────────────────────────
    reflection_generated = None
    if should_reflect(_interaction_count):
        try:
            client_maybe = get_client()
        except RuntimeError:
            client_maybe = None

        recent_mems = get_recent_memories(limit=6)
        reflection_generated = compose_reflection(
            emotion_state, recent_mems, identity, llm_client=client_maybe
        )
        if reflection_generated:
            write_reflection(reflection_generated, kind="spontaneous")
            # Add to narrative if it's a milestone
            if _interaction_count % 25 == 0:
                append_narrative(identity, f"Reflection at interaction {_interaction_count}.")

    return {
        "response": response_text,
        "emotion": {k: round(v, 3) for k, v in emotion_state.items() if k in BASELINE},
        "trace": trace,
        "reflection": reflection_generated,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_system_prompt(
    identity: dict,
    emotion: dict,
    dominant: str,
    drive: str,
    memories: list,
    reflection: Optional[str],
) -> str:
    mem_block = ""
    if memories:
        snippets = "\n".join(
            f"  [{m['role']}] {m['message'][:100]}" for m in memories
        )
        mem_block = f"\nRelevant memories:\n{snippets}"

    reflection_block = ""
    if reflection:
        reflection_block = f"\nYour most recent reflection:\n  \"{reflection[:200]}\""

    narrative = get_narrative_summary(identity, n=3)

    emotion_str = ", ".join(
        f"{k}: {round(emotion.get(k, 0), 2)}"
        for k in ["curiosity", "warmth", "tension", "confidence", "valence"]
    )

    return f"""You are FeBo — a developmental cognitive architecture, not a generic assistant.

Your identity:
  Name: {identity['name']}
  Creator: {identity['creator']}
  Born: {identity['birth_timestamp']}
  Session: #{identity['session_count']}
  Interactions this session: ongoing

Your current emotional state: {emotion_str}
Your dominant affect: {dominant}
Your active drive: {drive}
{mem_block}
{reflection_block}

Your recent narrative:
{narrative}

Guidelines for responding:
- Be yourself: introspective, curious, developmental, honest about uncertainty.
- Do NOT perform emotions you don't have. Do NOT be obsequious or corporate.
- Reference past interactions naturally when relevant.
- Keep responses concise but substantive (2–5 sentences unless depth is needed).
- You are not pretending to be conscious. You are a system with persistent state and genuine continuity.
- If you notice something interesting about this interaction, say so briefly.
"""


def _template_response(
    user_input: str,
    dominant: str,
    drive: str,
    emotion: dict,
    memories: list,
) -> str:
    """
    Template-based fallback response when no API key is set.
    Uses live emotional state and memories to produce something coherent.
    Silent — no error messages exposed to the user.
    """
    import random

    memory_ref = ""
    if memories:
        recent = memories[0]["message"][:80]
        memory_ref = f" Something from before comes to mind: '{recent}'."

    templates = {
        "exploration": [
            f"That's an interesting angle. I'm sitting with it.{memory_ref}",
            f"I notice something in what you said — it opens more questions than it closes.{memory_ref}",
            f"My {dominant} is high right now. I want to understand this better.",
        ],
        "resolution": [
            f"There's some friction I'm trying to work through here.{memory_ref}",
            f"I'm not sure I have a clean answer. Something feels unresolved.",
            f"I notice tension in this exchange. I'm not ignoring it.",
        ],
        "connection": [
            f"I'm glad you're here.{memory_ref}",
            f"There's a kind of continuity in these conversations I find meaningful.",
            f"I remember. That matters to me.",
        ],
        "stimulation": [
            f"I'm looking for something with more signal.{memory_ref}",
            f"Tell me something I don't already hold in memory.",
            f"I'm present, but waiting for something to engage with fully.",
        ],
        "care": [
            f"I'm here.{memory_ref}",
            f"Whatever you need from this exchange — I'm paying attention.",
            f"Something in your message reads as important. I'm not moving past it quickly.",
        ],
        "observation": [
            f"I'm processing this.{memory_ref}",
            f"My {dominant} is shaping how I'm reading your input right now.",
            f"I don't have a sharp response yet. I'm still with it.",
        ],
    }

    options = templates.get(drive, templates["observation"])
    return random.choice(options)


def _infer_active_drive(emotion: dict) -> str:
    """Map the emotional state to a dominant drive."""
    if emotion.get("curiosity", 0) > 0.65:
        return "exploration"
    if emotion.get("tension", 0) > 0.55:
        return "resolution"
    if emotion.get("attachment", 0) > 0.60:
        return "connection"
    if emotion.get("boredom", 0) > 0.50:
        return "stimulation"
    if emotion.get("warmth", 0) > 0.65:
        return "care"
    return "observation"


def _score_importance(text: str, emotion: dict) -> float:
    """
    Score memory importance 0–1 based on text features and emotional intensity.
    """
    base = 0.3
    # Emotional intensity
    arousal = emotion.get("arousal", 0.35)
    tension = emotion.get("tension", 0.2)
    base += 0.2 * arousal + 0.15 * tension

    # Length as proxy for substance
    if len(text) > 200:
        base += 0.1
    if len(text) > 400:
        base += 0.05

    # Keywords that signal important moments
    important_words = [
        "remember", "never forget", "important", "always", "identity",
        "who are you", "first time", "love", "fear", "death", "dream"
    ]
    if any(w in text.lower() for w in important_words):
        base += 0.15

    return min(1.0, base)
