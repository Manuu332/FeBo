"""
memory/quality.py
------------------
FeBo's memory quality system.

Manages three-tier memory architecture (Phase 15):
  HOT   — recent episodes, full detail, fast retrieval   (<= 500 episodes)
  WARM  — summarised episode clusters, medium detail      (extractive summary)
  COLD  — compressed long-term archive, symbolic only     (concept + themes)

Operations:
  - Importance decay: importance falls over time unless reinforced
  - Pruning: remove low-importance old episodes from hot tier
  - Summarisation: compress pruned hot episodes into warm tier
  - Archival: compress old warm summaries into cold tier
  - Retrieval routing: query all tiers, ranked by relevance

No external model. Summarization is extractive (memory/concepts.py).
"""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional, Tuple

from core.persistence import (
    get_db, tx, episode_fetch_recent, episode_fetch_important,
    episode_search, episode_count, episode_update_importance,
    db_stats
)
from memory.concepts import extract_concepts, extractive_summary, score_concepts_for_retrieval

# ── Tier thresholds ───────────────────────────────────────────────────────────
HOT_MAX_EPISODES      = 500    # above this, prune to warm
WARM_MAX_SUMMARIES    = 100    # above this, archive to cold
PRUNE_MIN_IMPORTANCE  = 0.25   # below this after age decay, eligible for pruning
PRUNE_AGE_HOURS       = 72     # only prune episodes older than this
DECAY_RATE_PER_HOUR   = 0.001  # slow importance decay


# ── Importance decay ──────────────────────────────────────────────────────────

def decay_importance(hours_elapsed: float = 1.0) -> int:
    """
    Apply time-based importance decay to hot episodes.
    High-importance memories decay slower (their floor is higher).
    Returns number of episodes affected.
    """
    with tx() as db:
        # Decay: importance *= (1 - rate * hours) but floor at importance * 0.3
        result = db.execute("""
            UPDATE episodes
            SET importance = MAX(importance * 0.30, importance - ? * importance)
            WHERE archived = 0
              AND timestamp < ?
        """, (DECAY_RATE_PER_HOUR * hours_elapsed,
               time.time() - PRUNE_AGE_HOURS * 3600))
        return result.rowcount


# ── Pruning ───────────────────────────────────────────────────────────────────

def prune_to_warm(force: bool = False) -> int:
    """
    Move low-importance old episodes from hot to warm tier via summarisation.
    Only runs when hot tier exceeds HOT_MAX_EPISODES, or force=True.

    Returns number of episodes pruned.
    """
    hot_count = episode_count(hot_only=True)
    if not force and hot_count <= HOT_MAX_EPISODES:
        return 0

    excess = max(50, hot_count - HOT_MAX_EPISODES)
    cutoff = time.time() - PRUNE_AGE_HOURS * 3600

    with get_db() as db:
        candidates = db.execute("""
            SELECT id, timestamp, role, message, emotion, importance, tags
            FROM episodes
            WHERE archived=0
              AND importance < ?
              AND timestamp < ?
            ORDER BY importance ASC, timestamp ASC
            LIMIT ?
        """, (PRUNE_MIN_IMPORTANCE, cutoff, excess)).fetchall()

    if not candidates:
        return 0

    episodes = [dict(c) for c in candidates]
    ids      = [e["id"] for e in episodes]

    # Summarise into warm tier
    _summarise_to_warm(episodes)

    # Mark as archived
    with tx() as db:
        placeholders = ",".join("?" * len(ids))
        db.execute(f"UPDATE episodes SET archived=1 WHERE id IN ({placeholders})", ids)

    return len(ids)


def _summarise_to_warm(episodes: List[dict]) -> None:
    """Create a warm-tier summary from a batch of hot episodes."""
    if not episodes:
        return

    texts       = [e.get("message","") for e in episodes if e.get("message")]
    timestamps  = [float(e.get("timestamp", 0)) for e in episodes]
    period_start = min(timestamps) if timestamps else 0.0
    period_end   = max(timestamps) if timestamps else 0.0

    # Emotion averages
    valences  = []
    arousals  = []
    for e in episodes:
        emo = e.get("emotion", {})
        if isinstance(emo, str):
            try: emo = json.loads(emo)
            except: emo = {}
        if emo.get("valence") is not None: valences.append(float(emo["valence"]))
        if emo.get("arousal") is not None: arousals.append(float(emo["arousal"]))

    avg_valence = sum(valences) / len(valences) if valences else 0.45
    avg_arousal = sum(arousals) / len(arousals) if arousals else 0.35

    # Extract key concepts for seeding the summary
    all_concepts = []
    for text in texts:
        all_concepts.extend(extract_concepts(text, max_concepts=5))
    from collections import Counter
    top_concepts = [c for c, _ in Counter(all_concepts).most_common(8)]

    summary = extractive_summary(texts, max_sentences=3, key_concepts=top_concepts)
    themes  = json.dumps(top_concepts[:6])

    with tx() as db:
        db.execute("""
            INSERT INTO episodes_warm
                (created_at, period_start, period_end, summary, themes,
                 avg_valence, avg_arousal, episode_count)
            VALUES (?,?,?,?,?,?,?,?)
        """, (time.time(), period_start, period_end, summary, themes,
               avg_valence, avg_arousal, len(episodes)))


# ── Warm → Cold archival ──────────────────────────────────────────────────────

def archive_warm_to_cold() -> int:
    """
    Compress old warm summaries into cold storage.
    Runs when warm tier exceeds WARM_MAX_SUMMARIES.
    Returns number of summaries archived.
    """
    with get_db() as db:
        warm_count = db.execute("SELECT COUNT(*) FROM episodes_warm").fetchone()[0]

    if warm_count <= WARM_MAX_SUMMARIES:
        return 0

    excess = warm_count - WARM_MAX_SUMMARIES
    cutoff = time.time() - 7 * 24 * 3600  # older than 7 days

    with get_db() as db:
        candidates = db.execute("""
            SELECT * FROM episodes_warm
            WHERE created_at < ?
            ORDER BY created_at ASC
            LIMIT ?
        """, (cutoff, excess)).fetchall()

    if not candidates:
        return 0

    warm_episodes = [dict(c) for c in candidates]
    ids           = [w["id"] for w in warm_episodes]

    # Compress: extract key themes only
    all_summaries = [w.get("summary","") for w in warm_episodes]
    all_themes    = []
    for w in warm_episodes:
        try:
            themes = json.loads(w.get("themes","[]"))
            all_themes.extend(themes)
        except Exception:
            pass

    from collections import Counter
    top_themes = [c for c, _ in Counter(all_themes).most_common(10)]
    compressed = extractive_summary(all_summaries, max_sentences=2)

    timestamps   = [float(w.get("period_start",0)) for w in warm_episodes]
    ts_ends      = [float(w.get("period_end",0)) for w in warm_episodes]
    period_start = min(timestamps) if timestamps else 0.0
    period_end   = max(ts_ends)    if ts_ends    else 0.0

    with tx() as db:
        db.execute("""
            INSERT INTO episodes_cold (archived_at, period_start, period_end, compressed, episode_count)
            VALUES (?,?,?,?,?)
        """, (time.time(), period_start, period_end,
               json.dumps({"summary": compressed, "themes": top_themes}),
               len(warm_episodes)))
        placeholders = ",".join("?" * len(ids))
        db.execute(f"DELETE FROM episodes_warm WHERE id IN ({placeholders})", ids)

    return len(ids)


# ── Retrieval across all tiers ────────────────────────────────────────────────

def retrieve_relevant(
    user_input: str,
    limit:      int = 4,
) -> List[dict]:
    """
    Retrieve the most relevant memories across hot, warm, and cold tiers.
    Uses concept-based scoring rather than keyword LIKE alone.
    """
    query_concepts = extract_concepts(user_input, max_concepts=8)
    results: List[dict] = []
    seen_ids: set = set()

    # ── Hot tier ──────────────────────────────────────────────────────────
    # 1. Concept-matched search on top concepts
    for concept in query_concepts[:5]:
        for ep in episode_search(concept, limit=3):
            if ep["id"] not in seen_ids:
                ep_concepts = extract_concepts(ep.get("message",""), max_concepts=8)
                ep["_relevance"] = score_concepts_for_retrieval(query_concepts, ep_concepts)
                results.append(ep)
                seen_ids.add(ep["id"])

    # 2. Spreading activation from memory store
    from memory.store import get_activation_for
    activated = get_activation_for(query_concepts[:6])
    for concept in list(activated.keys())[:4]:
        for ep in episode_search(concept, limit=2):
            if ep["id"] not in seen_ids:
                ep_concepts = extract_concepts(ep.get("message",""), max_concepts=8)
                relevance   = score_concepts_for_retrieval(query_concepts, ep_concepts)
                ep["_relevance"] = relevance * activated.get(concept, 0.5)
                results.append(ep)
                seen_ids.add(ep["id"])

    # 3. Fallback: important memories
    if len(results) < limit:
        for ep in episode_fetch_important(limit=limit):
            if ep["id"] not in seen_ids:
                ep["_relevance"] = ep.get("importance", 0.5) * 0.5
                results.append(ep)
                seen_ids.add(ep["id"])

    # Sort by relevance * importance
    results.sort(
        key=lambda e: e.get("_relevance", 0) * 0.7 + e.get("importance", 0.5) * 0.3,
        reverse=True
    )
    hot = results[:limit]

    # ── Warm tier ─────────────────────────────────────────────────────────
    warm = _retrieve_warm(query_concepts, limit=2)

    # ── Merge ─────────────────────────────────────────────────────────────
    combined = hot + warm
    return combined[:limit + 2]   # allow a couple extra for caller to filter


def _retrieve_warm(query_concepts: List[str], limit: int = 2) -> List[dict]:
    """Search warm tier summaries for concept match."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM episodes_warm ORDER BY created_at DESC LIMIT 20"
        ).fetchall()

    if not rows:
        return []

    scored = []
    for row in rows:
        d = dict(row)
        try:    themes = json.loads(d.get("themes","[]"))
        except: themes = []
        relevance = score_concepts_for_retrieval(query_concepts, themes)
        if relevance > 0.1:
            d["_relevance"]  = relevance
            d["_tier"]       = "warm"
            d["message"]     = d.get("summary","")  # normalise field name
            d["role"]        = "archive"
            scored.append(d)

    scored.sort(key=lambda x: x["_relevance"], reverse=True)
    return scored[:limit]


# ── Full maintenance cycle ────────────────────────────────────────────────────

def run_maintenance(hours_since_last: float = 1.0) -> dict:
    """
    Run full memory maintenance cycle.
    Called periodically (background loop) or during sleep.

    Returns dict of actions taken.
    """
    report = {
        "decayed":   0,
        "pruned":    0,
        "archived":  0,
        "assoc_pruned": 0,
    }

    # 1. Decay importance
    report["decayed"]  = decay_importance(hours_elapsed=hours_since_last)

    # 2. Prune hot to warm if needed
    report["pruned"]   = prune_to_warm()

    # 3. Archive warm to cold if needed
    report["archived"] = archive_warm_to_cold()

    # 4. Prune weak associations
    from core.persistence import assoc_prune
    report["assoc_pruned"] = assoc_prune(min_strength=0.03)

    return report


def get_tier_stats() -> dict:
    """Return counts across all memory tiers."""
    stats = db_stats()
    return {
        "hot":   stats["episodes_hot"],
        "warm":  stats["episodes_warm"],
        "cold":  stats["episodes_cold"],
        "total": stats["episodes_hot"] + stats["episodes_warm"] + stats["episodes_cold"],
    }
