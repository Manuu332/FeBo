"""
memory/store.py — FeBo's memory interface. Backed by unified persistence manager.
All writes go to core/persistence.py (febo.db). Zero separate files.
Public API unchanged for pipeline compatibility.
"""
from __future__ import annotations
import json, time
from typing import Dict, List, Optional, Tuple
from core.persistence import (
    get_db, episode_insert, episode_fetch_recent, episode_fetch_important,
    episode_search, episode_count, episode_update_importance,
    assoc_reinforce, assoc_spread, assoc_get_neighbours, assoc_graph_sample,
    reflection_insert, reflection_fetch, concept_record
)
from memory.concepts import extract_concepts

def init_db() -> None:
    """Ensure unified DB is ready. Migration handled by persistence on first access."""
    from core.persistence import get_db as _get
    _get()  # triggers init + migration

def save_memory(role: str, message: str, emotion_snapshot: Optional[dict]=None,
                importance: float=0.5, tags: Optional[list]=None) -> int:
    ep_id = episode_insert(role, message, emotion_snapshot, importance, tags)
    # Extract and record concepts
    concepts = extract_concepts(message, importance=importance, max_concepts=10)
    salience_boost = importance * 0.2
    for c in concepts:
        concept_record(c, salience_boost=salience_boost)
    # Reinforce associations between co-occurring concepts
    _reinforce_from_concepts(concepts)
    return ep_id

def get_recent_memories(limit: int=20) -> List[dict]:
    return episode_fetch_recent(limit=limit)

def get_important_memories(limit: int=10) -> List[dict]:
    return episode_fetch_important(limit=limit)

def search_memories(query: str, limit: int=5) -> List[dict]:
    return episode_search(query, limit=limit)

def retrieve_for_context(user_input: str, limit: int=4) -> List[dict]:
    """Use quality.py for multi-tier concept-aware retrieval."""
    try:
        from memory.quality import retrieve_relevant
        return retrieve_relevant(user_input, limit=limit)
    except Exception:
        # Fallback to simple search
        concepts = extract_concepts(user_input, max_concepts=6)
        results = []; seen = set()
        for c in concepts[:4]:
            for m in search_memories(c, limit=2):
                if m["id"] not in seen:
                    results.append(m); seen.add(m["id"])
        if len(results) < limit:
            for m in get_important_memories(limit):
                if m["id"] not in seen:
                    results.append(m); seen.add(m["id"])
        return results[:limit]

def memory_count() -> int:
    return episode_count(hot_only=True)

def score_importance(text: str, emotion: dict) -> float:
    base = 0.30
    base += emotion.get("arousal",           0.35) * 0.15
    base += emotion.get("cognitive_tension", 0.20) * 0.10
    base += abs(emotion.get("valence",       0.45) - 0.5) * 0.15
    base += emotion.get("wonder",            0.45) * 0.10
    base += emotion.get("tension",           0.20) * 0.10
    if len(text) > 200: base += 0.08
    if len(text) > 400: base += 0.05
    high_value = {"remember","never forget","important","always","identity",
                  "who are you","first time","love","fear","death","dream","exist"}
    if any(w in text.lower() for w in high_value): base += 0.15
    return min(1.0, base)

def update_salience(memory_id: int, delta: float) -> None:
    episode_update_importance(memory_id, delta)

def save_reflection_db(text: str, kind: str="spontaneous",
                        emotion: Optional[dict]=None) -> None:
    reflection_insert(text, kind, emotion)

def get_reflections_db(limit: int=20) -> List[dict]:
    return reflection_fetch(limit=limit)

def store_fact(concept: str, relation: str, value: str, confidence: float=0.7) -> None:
    with get_db() as db:
        row = db.execute("SELECT id, confidence FROM semantic WHERE concept=? AND relation=? AND value=?",
                         (concept, relation, value)).fetchone()
        if row:
            db.execute("UPDATE semantic SET confidence=MIN(1.0, confidence+0.05), updated_at=? WHERE id=?",
                       (time.time(), row[0]))
        else:
            db.execute("INSERT INTO semantic (concept,relation,value,confidence) VALUES (?,?,?,?)",
                       (concept, relation, value, confidence))
        db.commit()

def reinforce_association(word_a: str, word_b: str, delta: float=0.05) -> None:
    assoc_reinforce(word_a, word_b, delta)

def get_activation_for(concepts: List[str]) -> Dict[str, float]:
    return assoc_spread(concepts, hops=2)

def get_association_graph_sample(limit: int=15) -> dict:
    return assoc_graph_sample(limit=limit)

def _extract_concepts(text: str) -> List[str]:
    return extract_concepts(text, max_concepts=12)

def _spread_activation(seeds: List[str], hops: int=2) -> Dict[str, float]:
    return assoc_spread(seeds, hops=hops)

def _reinforce_from_concepts(concepts: List[str]) -> None:
    """Reinforce edges between co-occurring concepts."""
    unique = list(dict.fromkeys(concepts))[:12]
    for i, a in enumerate(unique):
        for j, b in enumerate(unique):
            if i >= j: continue
            decay = 0.95 ** abs(i - j)
            delta = 0.05 * decay
            assoc_reinforce(a, b, delta, max_strength=1.0, min_strength=0.01)
