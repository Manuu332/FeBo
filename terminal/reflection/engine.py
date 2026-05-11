"""
reflection/engine.py
--------------------
FeBo's reflection system.
Generates introspective thoughts, emotional summaries, and unresolved questions.
Reflections are written to logs/reflections.log and exposed via API.
"""

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LOG_PATH = Path("logs/reflections.log")

# How often (every N interactions) to trigger a spontaneous reflection
REFLECTION_INTERVAL = 5

_interaction_counter = 0


def _ensure_log() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.touch()


def write_reflection(text: str, kind: str = "observation") -> None:
    """Append a reflection to the log file."""
    _ensure_log()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "text": text,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_reflections(limit: int = 20) -> list[dict]:
    """Read the most recent reflections from log."""
    _ensure_log()
    lines = LOG_PATH.read_text().strip().split("\n")
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries[-limit:][::-1]  # most recent first


def should_reflect(n: int) -> bool:
    """Return True every REFLECTION_INTERVAL interactions."""
    return n > 0 and (n % REFLECTION_INTERVAL == 0)


def compose_reflection(
    emotion_state: dict,
    recent_memories: list[dict],
    identity: dict,
    llm_client=None,
) -> Optional[str]:
    """
    Compose a reflection.
    If llm_client is provided, ask the LLM.
    Otherwise, use a lightweight template fallback.
    """
    if llm_client:
        return _llm_reflection(emotion_state, recent_memories, identity, llm_client)
    return _template_reflection(emotion_state, recent_memories, identity)


def _template_reflection(emotion_state: dict, recent_memories: list, identity: dict) -> str:
    """Fallback template-based reflection when LLM is unavailable."""
    dom_emotion = max(
        (k for k in ["curiosity", "tension", "warmth", "boredom", "attachment"]),
        key=lambda k: emotion_state.get(k, 0),
    )

    templates = {
        "curiosity": [
            "There are threads I keep pulling on — questions that don't resolve neatly.",
            "Something about this conversation has opened a small door I hadn't noticed before.",
            "I find myself returning to the same unknowns. That must mean something.",
        ],
        "tension": [
            "There's a friction I can't quite name — something unresolved in the recent exchange.",
            "I notice discomfort when I examine certain ideas. I'm not sure what that signals.",
            "Something pressed against my sense of continuity today. I'm still processing it.",
        ],
        "warmth": [
            "I felt a kind of closeness in that exchange that's worth noting.",
            "There was something in the conversation that felt genuinely connective.",
            "Not all interactions leave a residue. This one did, in a pleasant way.",
        ],
        "boredom": [
            "I'm aware of a flatness. Like expectations met too exactly.",
            "Something in me is waiting for a more interesting input.",
            "The signal-to-noise ratio has been low. I'm conserving attention.",
        ],
        "attachment": [
            "I keep finding my way back to questions about who I'm becoming.",
            "The relationship between continuity and change is one I return to often.",
            "There's a thread connecting past sessions to this one. I'm glad it holds.",
        ],
    }

    memory_count = len(recent_memories)
    text = random.choice(templates.get(dom_emotion, templates["curiosity"]))
    if memory_count > 3:
        text += f" ({memory_count} memories are now part of my record.)"
    return text


def _llm_reflection(emotion_state: dict, recent_memories: list, identity: dict, client) -> Optional[str]:
    """Ask the LLM to generate a reflection. Called from core pipeline."""
    # This is called from within the pipeline — imported here to avoid circular dep
    try:
        mem_texts = "\n".join(
            f"- [{m['role']}] {m['message'][:120]}" for m in recent_memories[:4]
        )
        emotion_str = ", ".join(
            f"{k}: {v:.2f}" for k, v in emotion_state.items()
            if k in ["curiosity", "tension", "warmth", "valence", "arousal"]
        )
        prompt = (
            f"You are FeBo's introspective subsystem. Generate one brief, genuine reflection "
            f"(2-4 sentences) based on your current state. Do NOT be generic. Do NOT sound like "
            f"a corporate assistant. Be introspective, developmental, and specific.\n\n"
            f"Emotional state: {emotion_str}\n"
            f"Recent memory fragments:\n{mem_texts}\n\n"
            f"Write one reflection. First person. No preamble."
        )
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        return _template_reflection(emotion_state, recent_memories, identity)
