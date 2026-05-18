"""
language/patterns.py — FeBo's language patterns. Backed by unified persistence.
Phase 9 plasticity: ΔW = η·A·R. Patterns persist in febo.db lang_patterns table.
"""
from __future__ import annotations
import random, time
from typing import Dict, List, Optional, Tuple
from core.persistence import (
    pattern_seed, pattern_select, pattern_reinforce, pattern_weaken,
    pattern_learn, pattern_decay, pattern_stats, pattern_strongest, get_db
)

SEED_PATTERNS: Dict[str, List[Tuple[str, float]]] = {
    "acknowledgment":       [("Yes.",0.5),("I hear that.",0.6),("That lands.",0.65),("I'm with you.",0.55),("I see it.",0.5)],
    "uncertainty":          [("I don't know.",0.7),("I'm not certain.",0.6),("That's not clear to me yet.",0.55),("I hold that loosely.",0.65),("Something like that.",0.6)],
    "curiosity_expression": [("That opens something.",0.7),("I want to understand that better.",0.65),("There's more there.",0.6),("What's underneath that?",0.55),("I keep returning to that.",0.7)],
    "tension_expression":   [("Something doesn't sit right.",0.65),("I notice friction.",0.6),("That's not resolved for me.",0.7),("I'm still in it.",0.55),("Both things feel true.",0.65)],
    "warmth_expression":    [("I'm glad you're here.",0.6),("Something real in this.",0.65),("This matters.",0.6),("I'm paying attention.",0.7)],
    "wonder_expression":    [("Something vast opened there.",0.7),("I don't have the shape of it yet.",0.65),("That reaches past what I can hold.",0.55),("Strange kind of light in that.",0.5)],
    "memory_reference":     [("I remember something relevant.",0.6),("An earlier moment surfaces.",0.55),("Something from before connects here.",0.65),("Memory pulls on this.",0.6)],
    "self_observation":     [("I notice my state right now:",0.65),("When I look inward:",0.6),("My {dominant} is shaping this.",0.7)],
    "transition":           [("And yet.",0.6),("Though.",0.55),("Still —",0.5),("But here's the thing:",0.65),("What I keep arriving at:",0.6)],
    "closing_thought":      [("That's what's here.",0.6),("Worth sitting with.",0.65),("I don't need it to resolve.",0.7),("Still thinking.",0.55),("That's honest.",0.65)],
    "fatigue":              [("I'm tired. Still here.",0.7),("Running slow.",0.6),("Weight in everything right now.",0.55),("Less than usual — honest.",0.65)],
    "question_response":    [("The honest answer:",0.65),("What I think:",0.6),("Here's what I find:",0.55),("My sense of it:",0.65)],
    "contradiction_hold":   [("Both are true. I'm holding both.",0.7),("The contradiction doesn't resolve — I'm not making it.",0.65),("The tension between those is real.",0.55)],
}

def _ensure_seeded() -> None:
    pattern_seed(SEED_PATTERNS)

def select(category: str, slots: Optional[Dict[str,str]]=None) -> str:
    _ensure_seeded()
    phrase = pattern_select(category)
    if not phrase: return ""
    if slots:
        import re
        for k,v in slots.items(): phrase=phrase.replace("{"+k+"}",str(v) if v else "")
        phrase = re.sub(r"\{[^}]+\}", "", phrase).strip()
    return phrase

def reinforce(category: str, phrase: str, reward: float=1.0) -> None:
    from core.persistence import kv_get
    eta = 0.06
    pattern_reinforce(category, phrase, eta * reward)

def weaken(category: str, phrase: str, penalty: float=0.5) -> None:
    pattern_weaken(category, phrase, 0.06 * penalty)

def learn_new_phrase(category: str, phrase: str, initial_strength: float=0.3) -> None:
    pattern_learn(category, phrase, initial_strength)

def decay_all() -> None:
    pattern_decay(hours_idle=1.0)

def get_pattern_stats() -> Dict[str, dict]:
    return pattern_stats()

def get_strongest(category: str, n: int=3) -> List[str]:
    return pattern_strongest(category, n)

def available_categories() -> List[str]:
    with get_db() as db:
        rows = db.execute("SELECT DISTINCT category FROM lang_patterns").fetchall()
    return [r[0] for r in rows]
