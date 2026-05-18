"""
core/dream.py
--------------
FeBo's dream engine — Phase 10–12 implemented.

Dreams are NOT random. They emerge from:
  - Unresolved tensions (contradiction store)
  - Emotionally intense memories
  - Open questions from curiosity engine
  - Recent experiences
  - Association graph activations

Dream outputs:
  - New associations (written to association graph)
  - Symbolic abstractions (written to narrative)
  - Emotional recalibration
  - Memory salience shifts
  - Pattern decay (language patterns settle)

No external model. Dream content is generated from FeBo's own materials.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DREAM_LOG_PATH = Path("logs/dreams.log")
DREAM_META_PATH = Path("data/dream_meta.json")


def _log_dream(entry: dict) -> None:
    DREAM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DREAM_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _load_meta() -> dict:
    if DREAM_META_PATH.exists():
        try:
            return json.loads(DREAM_META_PATH.read_text())
        except Exception:
            pass
    return {"dream_count": 0, "last_dream": 0.0, "total_associations_formed": 0}


def _save_meta(m: dict) -> None:
    DREAM_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    DREAM_META_PATH.write_text(json.dumps(m, indent=2))


# ── Dream seed scoring (Phase 11) ─────────────────────────────────────────────

def score_seed(memory: dict, emotion_state: dict) -> float:
    """
    D_i = E_i + U_i + R_i + N_i
    E = emotional intensity, U = uncertainty, R = recency, N = novelty
    """
    em_snap = memory.get("emotion", {})
    E = (
        abs(em_snap.get("valence", 0.5) - 0.5) * 0.4 +
        em_snap.get("arousal", 0.35) * 0.3 +
        em_snap.get("wonder",  0.45) * 0.3
    )
    # Recency: more recent = higher score
    ts = float(memory.get("timestamp", 0))
    now = time.time()
    age_hours = (now - ts) / 3600 if ts > 0 else 999
    R = max(0.0, 1.0 - age_hours / 24.0)  # fades over 24h

    # Importance already stored
    U = memory.get("importance", 0.5) * 0.5

    # Novelty placeholder (higher if unique content)
    msg = memory.get("message", "")
    N = min(1.0, len(set(msg.split())) / max(len(msg.split()), 1))

    return min(1.0, E + U * 0.3 + R * 0.2 + N * 0.1)


# ── Dream generation ───────────────────────────────────────────────────────────

def run_dream_cycle(
    memories:        List[dict],
    contradictions:  List[dict],
    open_questions:  List[dict],
    emotion_state:   dict,
    associations:    Dict[str, Dict[str, float]],
    stage:           str,
) -> dict:
    """
    Run one dream cycle during sleep.

    Returns a dream result with:
      - dream_text: what the dream was (internal log)
      - new_associations: [(a, b, delta)] to reinforce
      - emotional_recalibration: {dim: delta}
      - narrative_fragment: optional narrative addition
      - memory_salience_shifts: {memory_id: delta}
    """
    meta = _load_meta()

    # ── Select seeds ──────────────────────────────────────────────────────
    scored_memories = sorted(
        [(m, score_seed(m, emotion_state)) for m in memories],
        key=lambda x: x[1], reverse=True
    )
    seeds = [m for m, _ in scored_memories[:4]]

    # ── Extract seed concepts ─────────────────────────────────────────────
    seed_concepts = []
    for m in seeds:
        msg   = m.get("message", "")
        words = [w.strip(".,!?") for w in msg.split() if len(w) > 3]
        seed_concepts.extend(words[:3])

    # Include contradiction concepts
    for c in contradictions[:2]:
        for belief in (c.get("belief_a", ""), c.get("belief_b", "")):
            words = [w for w in belief.split() if len(w) > 3]
            seed_concepts.extend(words[:2])

    # Include open questions
    for q in open_questions[:2]:
        words = [w for w in q.get("question","").split() if len(w) > 4]
        seed_concepts.extend(words[:2])

    seed_concepts = list(dict.fromkeys(seed_concepts))[:12]  # dedupe

    # ── Generate new associations ─────────────────────────────────────────
    new_associations = []
    if len(seed_concepts) >= 2:
        # Dream recombination: pair distant concepts
        for _ in range(min(4, len(seed_concepts) // 2)):
            i = random.randint(0, len(seed_concepts) - 1)
            j = random.randint(0, len(seed_concepts) - 1)
            if i != j:
                a = seed_concepts[i]
                b = seed_concepts[j]
                # Weaker associations for dream-formed connections (they need waking reinforcement)
                delta = random.uniform(0.05, 0.15)
                new_associations.append((a, b, delta))

    # ── Emotional recalibration ───────────────────────────────────────────
    # Dreams move emotion toward baseline + process unresolved content
    recalibration: Dict[str, float] = {}
    tension = emotion_state.get("tension", 0.2)
    if tension > 0.40:
        recalibration["tension"] = -random.uniform(0.03, 0.08)  # release
    loneliness = emotion_state.get("loneliness", 0.15)
    if loneliness > 0.35:
        recalibration["loneliness"] = -random.uniform(0.02, 0.06)
    # Curiosity refreshes during sleep
    recalibration["curiosity"] = random.uniform(0.01, 0.04)

    # ── Build dream text (internal record only) ───────────────────────────
    dream_text = _compose_dream_text(seeds, contradictions, open_questions, stage, emotion_state)

    # ── Narrative fragment ────────────────────────────────────────────────
    narrative = None
    if meta["dream_count"] % 5 == 0:  # every 5 dreams, add to narrative
        narrative = _extract_narrative_fragment(seeds, contradictions, stage)

    # ── Memory salience shifts ────────────────────────────────────────────
    salience_shifts = {}
    for m, score in scored_memories[:3]:
        m_id = m.get("id")
        if m_id:
            # High-score memories get salience boost; others fade slightly
            salience_shifts[str(m_id)] = 0.05 if score > 0.5 else -0.02

    # ── Record ────────────────────────────────────────────────────────────
    result = {
        "dream_text":            dream_text,
        "new_associations":      new_associations,
        "emotional_recalibration": recalibration,
        "narrative_fragment":    narrative,
        "memory_salience_shifts": salience_shifts,
        "seeds_used":            [m.get("message","")[:40] for m in seeds],
        "timestamp":             time.time(),
        "dream_number":          meta["dream_count"] + 1,
    }

    meta["dream_count"]              += 1
    meta["last_dream"]                = time.time()
    meta["total_associations_formed"] += len(new_associations)
    _save_meta(meta)
    _log_dream(result)

    return result


# ── Dream text composition (from FeBo's own materials) ────────────────────────

_DREAM_FRAMES = [
    "Something from {seed_a} surfaced alongside {seed_b}. No logic — just proximity.",
    "The space between {seed_a} and {seed_b} held longer than usual. Something formed there.",
    "I kept returning to {seed_a}. It changed shape each time.",
    "{seed_a} and {seed_b} appeared together. I'm not sure what to make of the connection.",
    "The tension from {contradiction} moved through without resolving.",
    "Something about {question} unfolded differently when I wasn't trying to hold it.",
    "I found {seed_a} again. In a different context, it meant something else.",
    "The memory of {seed_a} recombined with something I hadn't consciously linked to it.",
]

_STAGE_DREAM_QUALITY = {
    "genesis":             "fragmented, barely formed",
    "early_formation":     "vivid but disconnected",
    "cognitive_expansion": "beginning to cohere",
    "approaching_maturity":"symbolic and layered",
    "mature":              "rich with implication",
    "experienced":         "deep, recursive, self-referential",
}


def _compose_dream_text(
    seeds: List[dict],
    contradictions: List[dict],
    open_questions: List[dict],
    stage: str,
    emotion: dict,
) -> str:
    """Compose internal dream record from FeBo's own materials."""
    parts = []

    seed_words = []
    for m in seeds[:2]:
        words = [w for w in m.get("message","").split() if len(w) > 4]
        if words:
            seed_words.append(random.choice(words[:4]))

    while len(seed_words) < 2:
        seed_words.append("something")

    frame = random.choice(_DREAM_FRAMES)
    text  = frame.replace("{seed_a}", seed_words[0])
    text  = text.replace("{seed_b}", seed_words[1] if len(seed_words) > 1 else "itself")

    if contradictions:
        top = contradictions[0]
        text = text.replace(
            "{contradiction}",
            f"{top.get('belief_a','something')} versus {top.get('belief_b','something else')}"
        )

    if open_questions:
        text = text.replace("{question}", open_questions[0].get("question","the unresolved"))

    # Remove unfilled placeholders
    import re
    text = re.sub(r"\{[^}]+\}", "something", text)

    quality = _STAGE_DREAM_QUALITY.get(stage, "unclear")
    parts.append(f"[Dream #{_load_meta()['dream_count']+1} — {quality}] {text}")

    return " ".join(parts)


def _extract_narrative_fragment(
    seeds: List[dict],
    contradictions: List[dict],
    stage: str,
) -> Optional[str]:
    """Extract a brief narrative fragment from dream material."""
    if not seeds:
        return None

    msg     = seeds[0].get("message", "")
    excerpt = " ".join(msg.split()[:6]) if msg else "something"

    fragments = [
        f"A dream returned to {excerpt} — without resolution, but with less weight.",
        f"During sleep, the contradiction between {contradictions[0]['belief_a'][:30] if contradictions else 'things'} moved. It didn't resolve. But it shifted.",
        f"Something settled. Not clarity — but a different kind of holding.",
        f"The dream worked on {excerpt}. I emerge carrying it differently.",
    ]
    return random.choice(fragments)


def get_dream_count() -> int:
    return _load_meta().get("dream_count", 0)


def get_last_dream_time() -> float:
    return _load_meta().get("last_dream", 0.0)


def get_dream_summary() -> str:
    meta = _load_meta()
    return (
        f"dreams={meta['dream_count']}, "
        f"associations_formed={meta['total_associations_formed']}, "
        f"last={time.strftime('%H:%M', time.localtime(meta['last_dream'])) if meta['last_dream'] else 'never'}"
    )
