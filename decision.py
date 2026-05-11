"""
FeBo's Decision Layer

Sits between intent detection and execution.
FeBo doesn't just react to what you say —
she decides what to do about it.

This is the difference between a reflex and a choice.
"""

from memory.context import get_topic, get_user_state, get_recent_turns


def decide(intent, user_input, context_turns=None):
    """
    Given an intent, decide the best action to take.
    Returns an action string that core.py executes.
    """
    text = user_input.lower().strip()
    topic = get_topic()
    user_state = get_user_state()
    turns = context_turns or []

    # Follow-up resolution — "why?", "how?", "what about that?"
    if _is_follow_up(text) and topic:
        return f"follow_up:{topic}"

    # Reference resolution — "it", "they", "that"
    if _has_pronoun_reference(text) and topic:
        return f"elaboration:{topic}"

    # User is struggling — prioritise support
    if user_state in ("confused", "stuck"):
        if intent in ("reasoning", "knowledge", "unknown"):
            return "clarify"

    # User is tired — keep it short
    if user_state == "tired":
        return f"brief:{intent}"

    # Learning trigger detected
    if _wants_to_learn(text):
        return "learn"

    # Standard intent routing
    return intent


def _is_follow_up(text):
    follow_up_phrases = [
        "why", "how come", "what do you mean", "can you explain",
        "tell me more", "go on", "and then", "what else",
        "elaborate", "more about that", "what about that",
    ]
    return any(phrase in text for phrase in follow_up_phrases)


def _has_pronoun_reference(text):
    pronouns = [" it ", " it?", " they ", " them ", " that ", " this "]
    return any(p in f" {text} " for p in pronouns)


def _wants_to_learn(text):
    triggers = [
        "learn about", "read about", "study", "research",
        "find out about", "look up", "explore", "go learn",
        "teach yourself", "find information",
    ]
    return any(t in text for t in triggers)
