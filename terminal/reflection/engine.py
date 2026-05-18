"""
reflection/engine.py — Grounded autobiographical reflection.
Specificity mandate: every claim cites actual numbers from runtime data.
No invented profundity. No self-referential loops.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import List, Optional, Dict, Any
from core.persistence import (
    reflection_insert, reflection_fetch, contra_upsert, contra_age_all,
    contra_fetch, question_fetch, get_db, kv_get, kv_set
)

META_KEY = "reflect_meta"
REFLECTION_INTERVAL = 5
REFLECT_INTERVAL_S  = 900

INTROSPECTION_QUESTIONS = [
    "What concept appeared most in my recent memories — and why does it keep returning?",
    "Which contradiction has the most pressure right now, and how old is it?",
    "What emotion shifted most across my last exchanges, and what caused it?",
    "Which open question has surfaced most often — what does that repetition signal?",
    "How has trust changed with the entity I talk to most?",
    "What memory keeps being retrieved — is it high importance, or high recurrence?",
    "Where has my confidence been wrong, and how do I know?",
    "What have I been reaching toward in the last N interactions that I haven't named yet?",
    "Which assumption did recent memory challenge — with what evidence?",
    "What would I say about myself if I only had the data, not the language to dress it up?",
]

def _load_meta() -> dict:
    return kv_get(META_KEY, {"last_reflect_ts": 0, "reflect_count": 0})

def _save_meta(m: dict) -> None:
    kv_set(META_KEY, m)

def should_reflect(n: int = 0) -> bool:
    meta    = _load_meta()
    by_count = (n > 0 and n % REFLECTION_INTERVAL == 0)
    by_time  = (time.time() - meta.get("last_reflect_ts", 0)) > REFLECT_INTERVAL_S
    return by_count or by_time

def mark_reflected() -> int:
    meta = _load_meta()
    meta["last_reflect_ts"] = time.time()
    meta["reflect_count"]   = meta.get("reflect_count", 0) + 1
    _save_meta(meta)
    return meta["reflect_count"]

def get_reflect_count() -> int:
    return _load_meta().get("reflect_count", 0)

def pick_introspection_question(count: int) -> str:
    return INTROSPECTION_QUESTIONS[count % len(INTROSPECTION_QUESTIONS)]

def write_reflection(text: str, kind: str = "observation",
                     emotion: Optional[dict] = None,
                     grounding: Optional[dict] = None) -> None:
    reflection_insert(text, kind, emotion, grounding)

def get_reflections(limit: int = 20) -> List[dict]:
    return reflection_fetch(limit=limit)

def add_contradiction(belief_a: str, belief_b: str,
                      conflict_strength: float = 0.5,
                      emotional_weight:  float = 0.3) -> None:
    contra_upsert(belief_a, belief_b, conflict_strength, emotional_weight)

def age_contradictions() -> None:
    contra_age_all()

def get_contradictions(limit: int = 5) -> List[dict]:
    return contra_fetch(limit=limit)

def get_contradiction_summary() -> str:
    items = get_contradictions(limit=3)
    if not items: return "No active contradictions."
    return " | ".join(
        f"[{i.get('belief_a','?')!r:.28s} ↔ {i.get('belief_b','?')!r:.28s} "
        f"str={i.get('conflict_strength',0):.2f} age={i.get('age',0)}]"
        for i in items
    )


# ── Grounding data collection ─────────────────────────────────────────────────

def _gather_grounding(emotion_state: dict, recent_memories: List[dict],
                      identity: dict) -> Dict[str, Any]:
    """
    Pull concrete numbers from runtime data.
    Every field here is a measurement, not an interpretation.
    """
    from memory.concepts import extract_concepts
    from collections import Counter
    g: Dict[str, Any] = {}

    # Concept frequency across recent memories — real count
    concept_freq: Counter = Counter()
    for m in recent_memories:
        msg = m.get("message", "")
        if msg:
            for c in extract_concepts(msg, max_concepts=6):
                concept_freq[c] += 1
    top_concepts = [(c, n) for c, n in concept_freq.most_common(5) if n > 1]
    g["recurring_concepts"] = top_concepts   # [(concept, count), ...]
    g["memory_count_sample"] = len(recent_memories)

    # Emotion trajectory — measure absolute deviation per dimension
    from emotion.state import BASELINE
    emo_deviation: Dict[str, float] = {}
    for m in recent_memories[:8]:
        emo = m.get("emotion", {})
        if isinstance(emo, str):
            try: emo = json.loads(emo)
            except: emo = {}
        for k in ("curiosity","tension","warmth","wonder","loneliness","confidence","fear","valence"):
            if k in emo:
                emo_deviation[k] = emo_deviation.get(k, 0) + abs(emo[k] - BASELINE.get(k, 0.5))

    if emo_deviation:
        top_emo = sorted(emo_deviation.items(), key=lambda x: x[1], reverse=True)
        g["most_volatile_emotion"] = top_emo[0][0]
        g["most_volatile_magnitude"] = round(top_emo[0][1] / max(len(recent_memories), 1), 3)
    else:
        g["most_volatile_emotion"]   = dominant_emotion_from_state(emotion_state)
        g["most_volatile_magnitude"] = 0.0

    # Contradictions — real pressure and age numbers
    contras = get_contradictions(limit=2)
    if contras:
        top = contras[0]
        g["top_contradiction"] = {
            "belief_a":  top.get("belief_a", "")[:55],
            "belief_b":  top.get("belief_b", "")[:55],
            "pressure":  round(top.get("resolution_pressure", 0), 3),
            "age":       top.get("age", 0),
            "strength":  round(top.get("conflict_strength", 0), 3),
        }

    # Open questions — real recurrence count
    questions = question_fetch(limit=3)
    if questions:
        g["top_question"] = {
            "text":      questions[0].get("question", "")[:75],
            "recurrence": questions[0].get("recurrence", 1),
            "age_hours":  round(questions[0].get("age_hours", 0), 1),
        }

    # Most important recent memory
    important = sorted(recent_memories, key=lambda m: m.get("importance", 0), reverse=True)
    if important:
        g["salient_memory"] = {
            "text":       important[0].get("message", "")[:70],
            "importance": round(important[0].get("importance", 0), 3),
        }

    # Relationship data — real numbers
    with get_db() as db:
        rows = db.execute(
            "SELECT entity, trust, familiarity, interactions FROM relationships "
            "ORDER BY interactions DESC LIMIT 1"
        ).fetchall()
    if rows:
        r = rows[0]
        g["primary_entity"] = {
            "entity":       r[0],
            "trust":        round(r[1], 3),
            "familiarity":  round(r[2], 3),
            "interactions": r[3],
        }

    g["total_interactions"] = identity.get("total_interactions", 0)
    g["stage"]              = identity.get("stage", "genesis")

    return g


def dominant_emotion_from_state(emotion_state: dict) -> str:
    from emotion.state import BASELINE, dominant_emotion
    return dominant_emotion(emotion_state)


# ── Grounded autobiographical reflection ─────────────────────────────────────

def compose_reflection(emotion_state: dict, recent_memories: List[dict],
                       identity: dict, llm_client=None) -> Optional[str]:
    """
    Grounded autobiographical reflection.

    MANDATE: Every sentence cites a real measurement.
    - "X appeared N times" not "X keeps surfacing"
    - "contradiction age: N cycles, pressure: 0.NN" not "I hold this tension"
    - "trust: 0.NN after N interactions" not "our relationship matters to me"
    - "emotion deviated 0.NN from baseline" not "I feel unsettled"

    No invented profundity. No self-referential loops.
    """
    g     = _gather_grounding(emotion_state, recent_memories, identity)
    stage = g.get("stage", "genesis")
    n     = g.get("total_interactions", 0)

    parts: List[str] = []

    # 1. Concept recurrence — specific count
    recurring = g.get("recurring_concepts", [])
    if recurring:
        top_concept, top_count = recurring[0]
        sample_size = g.get("memory_count_sample", 0)
        if stage == "genesis":
            parts.append(f"{top_concept.capitalize()} — {top_count}x in {sample_size} memories.")
        elif stage == "early_formation":
            parts.append(
                f"'{top_concept}' appeared {top_count} times across {sample_size} recent memories. "
                f"That recurrence is a signal, not noise."
            )
        else:
            others = [f"'{c}' ({ct}x)" for c, ct in recurring[1:3]]
            others_str = ", ".join(others) if others else ""
            parts.append(
                f"'{top_concept}' recurs {top_count} times in the last {sample_size} exchanges"
                + (f" — alongside {others_str}" if others_str else "") + "."
            )

    # 2. Contradiction — specific pressure and age
    contra = g.get("top_contradiction")
    if contra and contra.get("pressure", 0) > 0.15:
        bel_a = contra["belief_a"]
        bel_b = contra["belief_b"]
        age   = contra["age"]
        pres  = contra["pressure"]
        if stage in ("genesis", "early_formation"):
            parts.append(f"Friction: '{bel_a}' vs '{bel_b}'. Age: {age} cycles.")
        else:
            parts.append(
                f"Contradiction still unresolved after {age} cycles "
                f"(pressure={pres:.2f}): '{bel_a}' vs '{bel_b}'. "
                f"I'm not forcing resolution."
            )

    # 3. Open question — specific recurrence
    question = g.get("top_question")
    if question and question.get("recurrence", 1) > 1:
        q_text  = question["text"]
        q_recur = question["recurrence"]
        q_age   = question["age_hours"]
        if stage == "genesis":
            parts.append(f"Returning question: {q_text}")
        else:
            parts.append(
                f"'{q_text[:60]}' — returned {q_recur} times over {q_age:.0f}h. "
                f"High recurrence without resolution means it's genuinely open."
            )

    # 4. Emotion volatility — specific magnitude
    vol_emo = g.get("most_volatile_emotion")
    vol_mag = g.get("most_volatile_magnitude", 0.0)
    if vol_emo and vol_mag > 0.05 and vol_emo not in ("curiosity",):
        if stage == "genesis":
            parts.append(f"{vol_emo} moving.")
        elif stage == "early_formation":
            parts.append(f"Most volatile: {vol_emo} (avg deviation {vol_mag:.3f} from baseline).")
        else:
            parts.append(
                f"{vol_emo} deviated {vol_mag:.3f} on average from baseline "
                f"across recent exchanges. That's the highest of any dimension — "
                f"it's shaping retrieval and expression."
            )

    # 5. Relationship — specific trust and interaction count
    entity = g.get("primary_entity")
    if entity and entity.get("interactions", 0) > 3:
        if stage not in ("genesis",):
            trust  = entity["trust"]
            fam    = entity["familiarity"]
            n_int  = entity["interactions"]
            if len(parts) < 3:  # only add if reflection isn't full
                parts.append(
                    f"Primary relationship: {n_int} interactions, "
                    f"trust={trust:.3f}, familiarity={fam:.3f}. "
                    f"The data is accumulating."
                )

    # 6. Salient memory — specific importance score
    salient = g.get("salient_memory")
    if salient and len(parts) < 2:
        imp = salient.get("importance", 0)
        txt = salient.get("text", "")
        parts.append(
            f"Highest-importance memory in sample (imp={imp:.3f}): "
            f"'{txt[:55]}{'…' if len(txt)>55 else ''}'."
        )

    # 7. Fallback — grounded minimum, no invented content
    if not parts:
        contras_count = len(get_contradictions(limit=20))
        questions_count = len(question_fetch(limit=20))
        parts.append(
            f"Interaction {n}. Stage: {stage}. "
            f"Active contradictions: {contras_count}. "
            f"Open questions: {questions_count}. "
            f"No strong pattern dominates right now."
        )

    # Stage-based assembly
    if stage == "genesis":
        text = parts[0] if parts else f"Interaction {n}."
    elif stage == "early_formation":
        text = " ".join(parts[:2])
    elif stage == "cognitive_expansion":
        text = " ".join(parts[:3])
    else:
        text = " ".join(parts[:4])

    text = text.strip()

    # Store with full grounding for auditability
    write_reflection(text, kind="spontaneous", emotion=emotion_state, grounding=g)
    return text


def build_reflection_prompt(recent_episodes: List[dict], emotion_summary: str,
                             identity_summary: str, contradiction_summary: str,
                             reflect_count: int) -> str:
    question = pick_introspection_question(reflect_count)
    episodes_text = "".join(
        f"\n  • [{(ep.get('message') or '')[:100]}]"
        for ep in recent_episodes[:6]
        if ep.get("message")
    )
    return (f"Question: \"{question}\"\n"
            f"State: {emotion_summary}\n{identity_summary}\n"
            f"Contradictions: {contradiction_summary}\n"
            f"Recent:{episodes_text or ' (none)'}")
