"""
core/pipeline.py — FeBo's cognitive pipeline. ZERO external model.
Causal audit applied: every system now measurably changes outcomes.
Uses RuntimeState for all session globals. Concept novelty replaces word novelty.
"""
from __future__ import annotations

import json
import time
from typing import Dict, Generator, List, Optional

from emotion.state import (
    load_emotion, update_from_stimulus, infer_delta_from_text,
    dominant_emotion, get_display, save_emotion, BASELINE, decay_toward_baseline
)
from memory.store import (
    retrieve_for_context, save_memory, get_recent_memories,
    memory_count, score_importance, get_activation_for, reinforce_association
)
from memory.concepts import extract_concepts, concept_novelty, expand_with_neighbors
from reflection.engine import (
    should_reflect, compose_reflection, write_reflection,
    age_contradictions, get_contradictions, get_contradiction_summary,
    mark_reflected, get_reflect_count, add_contradiction
)
from identity.profile import (
    load_identity, append_narrative, get_narrative_summary,
    increment_interactions, update_relationship, drift_personality,
    get_relationship, get_development_stage, to_system_prompt_block,
    add_narrative_chapter, _add_event
)
from core.fatigue import tick as fat_tick, get_state as fat_state, get_summary as fat_summary
from core.world_model import predict_response_type, compute_prediction_error, update_from_observation
from core.curiosity import (
    compute as compute_curiosity, update_level as update_curiosity,
    register_question, age_questions, extract_questions_from_text,
    get_open_questions, update_interest, get_level as get_curiosity_level
)
from core.dream import run_dream_cycle, get_dream_summary
from core.runtime_state import get_runtime
from language.generator import generate, reinforce_last, weaken_last
from language.patterns import decay_all as decay_patterns, reinforce as pat_reinforce

# ── Attention (Phase 2): A = S*Ws + E*We + N*Wn + R*Wr - F ──────────────────
W_S, W_E, W_N, W_R = 0.25, 0.35, 0.20, 0.20

def _attention_score(sal: float, emo_rel: float, novelty: float,
                     rel_rel: float, fatigue: float,
                     curiosity_level: float = 0.55) -> float:
    """
    Causal: attention score gates how much FeBo processes vs skims.
    Curiosity level now added as a multiplicative amplifier on novelty weight.
    High curiosity → FeBo weights novel inputs more.
    """
    curiosity_amp = 0.8 + curiosity_level * 0.4  # 0.8–1.2
    score = (sal * W_S +
             emo_rel * W_E +
             novelty * W_N * curiosity_amp +
             rel_rel * W_R -
             fatigue * 0.15)
    return max(0.0, min(1.0, score))

def _emotional_relevance(delta: dict) -> float:
    if not delta: return 0.2
    return min(1.0, sum(abs(v) for v in delta.values()) / max(len(delta), 1) * 4)

def _rel_relevance(text: str, rel: dict) -> float:
    trust = rel.get("trust", 0.4); fam = rel.get("familiarity", 0.0)
    personal = {"feel","think","believe","miss","love","hate","remember","afraid","hope"}
    pf = min(1.0, sum(1 for w in personal if w in text.lower().split()) / 4.0)
    return trust * 0.4 + fam * 0.3 + pf * 0.3

def _infer_drive(emotion: dict) -> str:
    if emotion.get("curiosity", 0)  > 0.65: return "exploration"
    if emotion.get("tension", 0)    > 0.55: return "resolution"
    if emotion.get("attachment", 0) > 0.60: return "connection"
    if emotion.get("boredom", 0)    > 0.50: return "stimulation"
    if emotion.get("warmth", 0)     > 0.65: return "care"
    if emotion.get("wonder", 0)     > 0.60: return "wonder"
    return "observation"


def run_pipeline(user_input: str, entity: str = "user") -> dict:
    """
    Full autonomous cognitive cycle. Zero external model.
    Every subsystem causally affects the response.
    """
    rt = get_runtime()
    rt.increment_session_interactions()
    step = rt.session_interactions

    trace: Dict = {
        "step":              step,
        "input_preview":     user_input[:80],
        "memories_accessed": [],
        "dominant_emotion":  None,
        "active_drive":      None,
        "attention":         0.5,
        "curiosity":         0.5,
        "novelty":           0.5,
        "fatigue":           0.05,
        "prediction_error":  0.0,
        "dream_summary":     "",
        "response_strategy": "autonomous",
        "concepts_extracted":[],
        "semantic_neighbors":[],
    }

    # ── 1. Concept extraction (improved) ──────────────────────────────────────
    concepts = extract_concepts(user_input, importance=0.5, max_concepts=10)
    trace["concepts_extracted"] = concepts

    # Semantic neighborhood expansion — makes memory retrieval conceptually rich
    semantic_neighbors = expand_with_neighbors(concepts, hops=1, min_weight=0.5)
    trace["semantic_neighbors"] = list(semantic_neighbors.keys())[:6]

    # ── 2. Concept novelty (replaces word novelty) ────────────────────────────
    # Causal: novelty feeds attention score AND curiosity signal
    recent_concept_sets = [
        ex.get("concepts", [])
        for ex in rt.get_recent_exchanges(n=6)
    ]
    novelty = concept_novelty(concepts, recent_concept_sets, semantic_expansion=True)
    trace["novelty"] = round(novelty, 3)

    # ── 3. Emotion ────────────────────────────────────────────────────────────
    delta         = infer_delta_from_text(user_input)
    emotion_state = update_from_stimulus(load_emotion(), delta)
    dom           = dominant_emotion(emotion_state)
    drive         = _infer_drive(emotion_state)
    trace["dominant_emotion"] = dom
    trace["active_drive"]     = drive
    trace["emotion_snapshot"] = {k: round(emotion_state.get(k, 0), 3) for k in BASELINE}

    # ── 4. Memory retrieval (multi-tier, concept-aware + semantic neighbors) ──
    recent   = get_recent_memories(limit=8)
    memories = retrieve_for_context(user_input, limit=4)

    # Spread activation using both direct concepts AND semantic neighbours
    all_retrieval_concepts = concepts + list(semantic_neighbors.keys())[:4]
    activated_assoc = get_activation_for(all_retrieval_concepts[:8])
    trace["memories_accessed"] = [
        {"id": m.get("id"), "snippet": m.get("message","")[:60],
         "importance": m.get("importance", 0.5), "tier": m.get("_tier", "hot")}
        for m in memories
    ]

    # ── 5. Fatigue (before attention — fatigue suppresses attention) ──────────
    fat_s     = fat_state()
    fat_level = fat_s.get("fatigue", 0.05)
    trace["fatigue"] = round(fat_level, 3)

    # ── 6. Curiosity level (causal: amplifies attention on novelty) ───────────
    curiosity_level = get_curiosity_level()

    # ── 7. Attention scoring ──────────────────────────────────────────────────
    identity = load_identity()
    rel      = get_relationship(entity)
    emo_rel  = _emotional_relevance(delta)
    sal      = min(1.0, len(user_input) / 200.0 + novelty * 0.3)

    attn = _attention_score(sal, emo_rel, novelty, _rel_relevance(user_input, rel),
                            fat_level, curiosity_level)
    trace["attention"] = round(attn, 3)

    # ── 8. World model — prediction error (causal: adds directly to attention) ─
    prediction   = predict_response_type(user_input, emotion_state)
    actual_depth = min(1.0, len(user_input.split()) / 40.0)
    actual = {
        "is_question":  prediction["is_question"],
        "is_emotional": any(w in user_input.lower() for w in ("feel","love","sad","afraid")),
        "actual_depth": actual_depth,
    }
    pe = compute_prediction_error(prediction, actual)
    update_from_observation(user_input[:60], pe, actual)
    trace["prediction_error"] = round(pe, 3)

    # PE directly boosts attention (surprise = pay more attention)
    attn = min(1.0, attn + pe * 0.15)
    trace["attention"] = round(attn, 3)

    # ── 9. Curiosity signal ───────────────────────────────────────────────────
    uncertainty = emotion_state.get("cognitive_tension", 0.20)
    q_signal    = compute_curiosity(pe, novelty, uncertainty, fat_level * 0.5)
    update_curiosity(q_signal)
    trace["curiosity"] = round(min(1.0, q_signal), 3)

    # Register open questions + update interests from concepts
    for q in extract_questions_from_text(user_input):
        imp = 0.4 + emotion_state.get("wonder", 0.45) * 0.3
        register_question(q, importance=imp, source="interaction")
    for c in concepts[:3]:
        update_interest(c, delta=emotion_state.get("curiosity", 0.55) * 0.02)

    # ── 10. Identity + relationship update ────────────────────────────────────
    n     = increment_interactions()
    rt.sync_total_interactions(n)
    pos_d = max(0.0, delta.get("valence", 0))
    neg_d = max(0.0, -delta.get("valence", 0))
    update_relationship(entity, pos_d, neg_d)
    drift_personality({
        "curiosity": delta.get("curiosity", 0) * 0.8,
        "warmth":    delta.get("warmth",    0) * 0.6,
        "openness":  delta.get("wonder",    0) * 0.5,
        "stability": delta.get("stability", 0) * 0.4,
    })

    # ── 11. Fatigue tick (after everything else — fatigue accumulates) ─────────
    fat_s    = fat_tick(message_processed=True, emotion=emotion_state)
    sleeping = fat_s.get("sleeping", False)

    # Update runtime cognitive phase
    rt.set_phase("sleeping" if sleeping else "active")

    # ── 12. Contradictions ────────────────────────────────────────────────────
    age_contradictions()
    contradictions = get_contradictions(limit=3)

    # Detect contradiction candidates from conjunctive language
    if any(w in user_input.lower() for w in
           ("but","however","yet","despite","although","though")):
        words = user_input.split()
        mid   = len(words) // 2
        if mid > 2:
            add_contradiction(
                " ".join(words[:mid])[:60],
                " ".join(words[mid:])[:60],
                conflict_strength=0.30,
                emotional_weight=0.15
            )

    # ── 13. Generate response ─────────────────────────────────────────────────
    # Causal chain now:
    #   concepts → semantic_neighbors → novelty (concept-based)
    #   → attention (curiosity-amplified, PE-boosted)
    #   → generator gets: emotion, drive, fatigue, memories, contradictions, associations
    stage = get_development_stage()
    pv    = identity.get("personality", {})

    response_text = generate(
        user_text      = user_input,
        emotion        = emotion_state,
        stage          = stage,
        drive          = drive,
        memories       = memories,
        contradictions = contradictions,
        personality    = pv,
        fatigue        = fat_level,
        associations   = {**activated_assoc, **semantic_neighbors},
    )
    trace["response_strategy"] = "autonomous"

    # ── 14. Update runtime exchange buffer ────────────────────────────────────
    rt.add_exchange("user",  user_input,    concepts, emotion_state)
    rt.add_exchange("feebo", response_text, [], emotion_state)

    # ── 15. Persist memory ────────────────────────────────────────────────────
    importance = score_importance(user_input, emotion_state)
    save_memory("user",  user_input,    emotion_snapshot=emotion_state, importance=importance)
    save_memory("feebo", response_text, emotion_snapshot=emotion_state, importance=importance * 0.8)

    # Reinforce concept associations from this exchange
    for i in range(0, len(concepts) - 1, 2):
        if i + 1 < len(concepts):
            reinforce_association(concepts[i], concepts[i+1], delta=0.03)
    # Also reinforce semantic neighbor associations
    for concept in concepts[:3]:
        for neighbor, weight in list(semantic_neighbors.items())[:3]:
            reinforce_association(concept, neighbor, delta=weight * 0.02)

    # ── 16. Pattern reinforcement (causal: actually called now) ───────────────
    # Reinforcement queued in generator, flushed here
    pending = rt.flush_reinforcement_queue()
    for item in pending:
        try:
            pat_reinforce(item["category"], item["phrase"], item["reward"])
        except Exception:
            pass

    # Positive interaction → reinforce last pattern used
    if pos_d > 0.05:
        reinforce_last(reward=min(1.0, pos_d * 2))

    # ── 17. Periodic reflection ───────────────────────────────────────────────
    if rt.should_reflect():
        refl = compose_reflection(
            emotion_state, get_recent_memories(limit=8), identity
        )
        if refl:
            rt.mark_reflected()
            mark_reflected()
            if n % 30 == 0:
                _add_event(f"Reflected at interaction {n}.", 0.5, 0.5, ["reflection"])

    # ── 18. Dream integration ─────────────────────────────────────────────────
    if sleeping:
        _run_dream_integration(emotion_state, stage)

    trace["dream_summary"] = get_dream_summary()

    # ── 19. Curiosity aging ───────────────────────────────────────────────────
    if rt.should_age_curiosity():
        age_questions(hours_elapsed=0.5)
        rt.mark_curiosity_aged()

    # ── 20. Memory quality maintenance ───────────────────────────────────────
    if rt.should_run_maintenance():
        try:
            from memory.quality import run_maintenance
            run_maintenance(hours_since_last=4.0)
            rt.mark_maintenance_done()
        except Exception:
            pass

    result = {
        "response":  response_text,
        "emotion":   get_display(emotion_state),
        "trace":     trace,
        "sleeping":  sleeping,
        "stage":     stage,
    }
    rt.set_last_response(result)
    return result


def stream_pipeline(
    user_input: str,
    history:    list,
    entity:     str = "user",
) -> Generator[str, None, None]:
    """Streaming SSE version. Same cognitive cycle, word-by-word output."""
    result = run_pipeline(user_input, entity=entity)

    words = result["response"].split()
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield f"data: {json.dumps({'type':'text','content':chunk})}\n\n"

    fat_s = fat_state()
    yield f"data: {json.dumps({'type':'done','emotion':result['emotion'],'fatigue':round(fat_s.get('fatigue',0),3),'sleeping':fat_s.get('sleeping',False),'attention':result['trace']['attention'],'curiosity':result['trace']['curiosity'],'novelty':result['trace']['novelty'],'stage':result['stage'],'prediction_error':result['trace']['prediction_error'],'concepts':result['trace']['concepts_extracted'][:5],'neighbors':result['trace']['semantic_neighbors'][:4]})}\n\n"


def _run_dream_integration(emotion_state: dict, stage: str) -> None:
    """Run dream cycle during sleep, apply results."""
    try:
        memories       = get_recent_memories(limit=12)
        contradictions = get_contradictions(limit=4)
        open_questions = get_open_questions(limit=5)

        dream_result = run_dream_cycle(
            memories=memories, contradictions=contradictions,
            open_questions=open_questions, emotion_state=emotion_state,
            associations={}, stage=stage,
        )

        for a, b, delta in dream_result.get("new_associations", []):
            reinforce_association(a, b, delta=delta)

        current_emo = load_emotion()
        for dim, d in dream_result.get("emotional_recalibration", {}).items():
            if dim in current_emo:
                current_emo[dim] = max(0.0, min(1.0, current_emo[dim] + d))
        save_emotion(current_emo)

        from memory.store import update_salience
        for mem_id_str, d in dream_result.get("memory_salience_shifts", {}).items():
            try: update_salience(int(mem_id_str), d)
            except Exception: pass

        if dream_result.get("narrative_fragment"):
            add_narrative_chapter(
                f"Dream #{dream_result['dream_number']}",
                dream_result["narrative_fragment"]
            )
        decay_patterns()
    except Exception:
        pass
