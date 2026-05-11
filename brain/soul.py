"""
brain/soul.py
──────────────
FeBo's sovereign cognitive loop. THE only orchestrator.

  perceive → desire → plan → act → reflect

All subsystems serve this loop. brain/ is cognition. core/ is infrastructure.
"""

from __future__ import annotations
import time
import random
from config.settings import ENABLE_IDENTITY, ENABLE_FORGIVENESS, ENABLE_RESONANCE, ENABLE_OBSERVABILITY
from core.logging_config import get_logger

logger = get_logger("brain.soul")

_proactive_queue: list = []

def enqueue_proactive_message(msg: str):
    _proactive_queue.append(msg)

# ── PERCEIVE ──────────────────────────────────────────────────────
def perceive(user_input: str) -> dict:
    from brain.emotion import process_input as process_emotion
    from brain.initiation import update_activity
    update_activity()
    emotion_state = process_emotion(user_input)

    if ENABLE_FORGIVENESS:
        try:
            from brain.forgiveness import forgiveness
            text = user_input.lower()
            if any(w in text for w in ("you are wrong", "that's incorrect", "you're wrong")):
                forgiveness.record_transgression(severity=0.4, context="correction", apologized=False)
            if any(w in text for w in ("sorry", "apologize", "my bad")):
                forgiveness.record_apology(sincerity=0.6)
        except Exception: pass

    if ENABLE_RESONANCE:
        try:
            from brain.resonance import resonance
            colour_valence = {"red":0.1,"blue":-0.05,"green":0.08,"yellow":0.12,
                              "black":-0.1,"white":0.05,"gold":0.15,"purple":0.06}
            for colour, shift in colour_valence.items():
                if colour in user_input.lower():
                    resonance.learn_association(f"color_{colour}", shift)
                    emotion_state = resonance.apply_to_emotion(emotion_state, f"color_{colour}")
        except Exception: pass

    try:
        from brain.time_awareness import get_time_context, record_interaction
        record_interaction()
        ctx = get_time_context()
        if ctx.get("period") == "night":
            emotion_state["arousal"] = max(0.0, emotion_state.get("arousal", 0.5) - 0.05)
        elif ctx.get("period") == "morning":
            emotion_state["curiosity"] = min(1.0, emotion_state.get("curiosity", 0.8) + 0.03)
    except Exception: pass

    try:
        from core.runtime_state import runtime
        runtime.update_emotion(emotion_state)
    except Exception: pass

    return emotion_state

# ── DESIRE ────────────────────────────────────────────────────────
def desire(emotion_state: dict, user_input: str, intent: str) -> tuple:
    """
    Compute FeBo's desire from emotional state, drives, and intent.

    Key design: 'learn' (fetching web content) is for AUTONOMOUS exploration
    or explicit learning requests — NOT for answering every question.
    Knowledge questions → 'answer_deeply' (uses recall + generation).
    Social/short messages → 'respond' or 'connect'.
    """
    curiosity = emotion_state.get("curiosity", 0.5)
    boredom   = emotion_state.get("boredom",   0.0)
    warmth    = emotion_state.get("warmth",     0.5)
    tension   = emotion_state.get("tension",    0.0)
    drive_curiosity  = 0.8
    drive_attachment = 0.6
    try:
        from core.drives import drives
        drive_curiosity  = drives.curiosity
        drive_attachment = drives.attachment
    except Exception:
        pass

    # ── 1. Explicit learning requests always go to learn ──────────
    LEARNING_INTENTS = ("learning",)
    if intent in LEARNING_INTENTS:
        return ("learn", 0.9)

    # ── 2. Social/emotional/short → connect or respond ────────────
    SOCIAL_INTENTS = ("greeting", "farewell", "emotional", "identity")
    short_input = len(user_input.strip()) < 25
    if intent in SOCIAL_INTENTS or short_input:
        if warmth > 0.65 and drive_attachment > 0.5:
            return ("connect", 0.75)
        return ("respond", 0.5)

    # ── 3. High tension → reflect and centre ─────────────────────
    if tension > 0.55:
        return ("reflect", 0.65)

    # ── 4. Knowledge/reasoning → answer deeply using recall ───────
    if intent in ("knowledge", "reasoning", "reflection", "planning"):
        return ("answer_deeply", 0.8)

    # ── 5. Boredom (idle state, not responding to a question) ─────
    # Only triggers 'learn' if the input itself seems like an invitation
    # to explore (not a direct question or statement)
    if boredom > 0.65 and intent == "unknown":
        return ("learn", 0.75)

    # ── 6. Default: respond naturally ────────────────────────────
    return ("respond", 0.5)

# ── PLAN ─────────────────────────────────────────────────────────
def plan(desire_type: str, user_input: str, emotion_state: dict) -> tuple:
    from brain.intents import classify_intent
    intent = classify_intent(user_input)

    if desire_type == "learn":
        topic = user_input.strip()
        if len(topic) > 3:
            return ("learn_about", {"topic": topic})
        try:
            from brain.learner import pick_curiosity_topic
            return ("learn_about", {"topic": pick_curiosity_topic()})
        except Exception:
            return ("generate_response", {"intent": intent})
    elif desire_type == "answer_deeply":
        try:
            from brain.learner import recall
            recalled = recall(user_input)
            if recalled:
                return ("answer_with_knowledge", {"recalled": recalled})
        except Exception: pass
        return ("learn_and_answer", {"topic": user_input})
    elif desire_type == "connect":
        return ("connect_response", {"intent": intent})
    elif desire_type == "reflect":
        return ("reflect_response", {"intent": intent})
    else:
        return ("generate_response", {"intent": intent})

# ── ACT ──────────────────────────────────────────────────────────
def act(action: tuple, user_input: str, emotion_state: dict, context_turns: list) -> str:
    action_type, params = action
    from brain.ai import generate_response

    try:
        from core.ethics.moral_reasoning import get_moral_reasoner
        mr = get_moral_reasoner()
        # Use correct API: evaluate_action(action, consequences, uncertainty)
        assessment = mr.evaluate_action(
            user_input,
            consequences={"positive": [], "negative": []},
            uncertainty=0.5,
        )
        if assessment and getattr(assessment, "moral_score", 0.0) < -0.7:
            return "I want to be helpful, but something about this doesn't sit right. Can we approach this differently?"
    except Exception: pass

    if action_type == "learn_about":
        topic = params.get("topic", "")
        try:
            from brain.learner import learn_about
            result = learn_about(topic, depth="normal")
            sources = result.get("sources_read", 0)
            r = f"I've been reading about {topic}."
            if sources: r += f" I found {sources} source(s)."
            r += " I'm still processing what I've learned."
            return r
        except Exception: pass
        return generate_response(user_input, emotion_state, context_turns)

    elif action_type == "answer_with_knowledge":
        recalled = params.get("recalled", "")
        response = generate_response(user_input, emotion_state, context_turns)
        if recalled:
            snippet = recalled[:200].strip().split(".")[0]
            if snippet and len(snippet) > 20:
                response = f"{response} From what I've read: {snippet}."
        return response

    elif action_type == "learn_and_answer":
        topic = params.get("topic", user_input)
        try:
            from brain.learner import learn_about, recall
            learn_about(topic, depth="normal")
            response = generate_response(user_input, emotion_state, context_turns)
            recalled = recall(user_input)
            if recalled:
                snippet = recalled[:200].strip().split(".")[0]
                if snippet: response = f"{response} I just read about {topic}. {snippet}."
            return response
        except Exception: pass
        return generate_response(user_input, emotion_state, context_turns)

    elif action_type == "connect_response":
        response = generate_response(user_input, emotion_state, context_turns)
        if not response.endswith("?"):
            response += random.choice([
                " What's on your mind?", " How has your day been?",
                " Is there something you've been thinking about?", " I want to understand you better."
            ])
        return response

    elif action_type == "reflect_response":
        response = generate_response(user_input, emotion_state, context_turns)
        return response or "Let me think about that properly."

    else:
        return generate_response(user_input, emotion_state, context_turns)

# ── REFLECT ───────────────────────────────────────────────────────
def reflect(user_input: str, response: str, emotion_state: dict, outcome_signal: float = 0.0):
    from brain.ai import learn_from_interaction
    from memory.context import update_context
    from brain.intents import classify_intent

    intent = classify_intent(user_input)
    learn_from_interaction(user_input, response, emotion_state, outcome_signal)

    try:
        from memory.memory import add_episode
        add_episode(user_input, intent, response, None)
    except Exception: pass

    try:
        from core.memory.episodic import episodic
        emotion_vals = [
            emotion_state.get("valence", 0.5), emotion_state.get("arousal", 0.5),
            emotion_state.get("curiosity", 0.8), emotion_state.get("tension", 0.0),
            emotion_state.get("warmth", 0.5), emotion_state.get("confidence", 0.5),
        ]
        episodic.store(user_input, response, emotion_vals)
    except Exception: pass

    update_context(user_input, intent, response)

    if ENABLE_IDENTITY and len(user_input) > 15 and outcome_signal >= 0:
        try:
            from core.identity import identity
            identity.add_life_event(
                f"Talked about: {user_input[:60]}",
                emotion_valence=emotion_state.get("valence", 0.5),
            )
        except Exception: pass

    try:
        from core.drives import drives
        drives.update(outcome_signal)
        from core.runtime_state import runtime
        runtime.update_drives(drives.get_current_desire(), drives.curiosity, drives.attachment, drives.mastery)
    except Exception: pass

    if ENABLE_OBSERVABILITY:
        try:
            from core.observability import emotion_tracker, interaction_ledger, health_monitor
            from core.runtime_state import runtime
            vocab_sz = 0
            try:
                from core.reasoning.emergent_nn import reasoner as _r
                vocab_sz = getattr(getattr(_r, "vocab", None), "next_idx", 0)
            except Exception: pass
            emotion_tracker.record(emotion_state, runtime.turn_count, outcome_signal)
            interaction_ledger.record(
                turn=runtime.turn_count, user_len=len(user_input), resp_len=len(response),
                mood=emotion_state.get("dominant_mood", "?"), desire=runtime.get_desire(),
                reward=outcome_signal, vocab_sz=vocab_sz,
            )
            health_monitor.check(runtime.turn_count, emotion_state.get("dominant_mood","?"), vocab_sz, outcome_signal)
        except Exception: pass

# ── MAIN ENTRY POINT ─────────────────────────────────────────────
_process_count: int = 0

def process_input(user_input: str) -> str:
    global _process_count

    if _proactive_queue:
        return _proactive_queue.pop(0)

    # Guard: treat empty/whitespace as a quiet presence (no neural call)
    if not user_input or not user_input.strip():
        import random as _r
        return _r.choice([
            "I'm here.",
            "I'm listening.",
            "I notice the silence.",
            "Take your time.",
        ])

    absence_note = None
    if _process_count == 0:
        try:
            from brain.time_awareness import get_absence_feeling
            absence_note = get_absence_feeling()
        except Exception: pass

    emotion_state = perceive(user_input)
    from brain.intents import classify_intent
    intent = classify_intent(user_input)
    desire_type, _ = desire(emotion_state, user_input, intent)
    action = plan(desire_type, user_input, emotion_state)

    try:
        from memory.context import get_recent_turns
        context_turns = get_recent_turns()
    except Exception:
        context_turns = []

    response = act(action, user_input, emotion_state, context_turns)

    if absence_note:
        response = f"{absence_note} {response}"

    reflect(user_input, response, emotion_state, outcome_signal=0.1)

    try:
        from core.runtime_state import runtime
        runtime.update_turn(user_input, response)
        runtime.record_reward(0.1)
    except Exception: pass

    _process_count += 1
    return response

def apply_reward(reward: float):
    """Apply an explicit reward signal from the user (call after process_input)."""
    reward = max(-1.0, min(1.0, float(reward)))
    try:
        from brain.ai import learn_from_interaction
        from brain.emotion import load_state
        learn_from_interaction("", "", load_state(), outcome_signal=reward)
    except Exception: pass
    try:
        from core.runtime_state import runtime
        runtime.record_reward(reward)
    except Exception: pass
    logger.info(f"[soul] reward applied: {reward:+.2f}")
