"""brain/intents.py — Intent classifier for soul.py."""
from __future__ import annotations
import re

_INTENT_MAP: list[tuple[str, list[str]]] = [
    ("greeting",   ["hello", "hi ", "hey", "hey ", "good morning", "good evening", "howdy", "greetings"]),
    ("farewell",   ["bye", "goodbye", "see you", "later", "goodnight", "exit", "quit"]),
    ("identity",   ["who are you", "what are you", "are you conscious", "your name",
                    "about yourself", "introduce yourself", "what's your name"]),
    ("emotional",  ["how do you feel", "how are you feeling", "how are you",
                    "are you happy", "are you okay", "your mood", "your emotion"]),
    ("memory",     ["remember", "do you recall", "what did i say", "last time",
                    "add to memory", "save this", "note that", "remind me"]),
    ("knowledge",  ["tell me about", "what is", "what are", "explain", "define",
                    "do you know about", "facts about"]),
    ("reasoning",  ["why ", "how come", "think about", "reason", "analyse", "analyze",
                    "compare", "difference between", "what if", "suppose"]),
    ("planning",   ["plan", "should i", "what should i", "help me decide", "steps to",
                    "how do i", "how should i", "break down"]),
    ("learning",   ["learn about", "read about", "research", "study", "look up",
                    "find out about", "teach yourself"]),
    ("creative",   ["write", "create", "compose", "poem", "story", "imagine", "design",
                    "invent", "make up"]),
    ("reflection", ["what have you been thinking", "your thoughts", "introspect",
                    "reflect on", "dream about", "consciousness"]),
    ("unknown",    []),
]

def classify_intent(user_input: str) -> str:
    if not user_input or not user_input.strip():
        return "unknown"
    text = user_input.lower().strip()

    # Tools: math expressions first (before knowledge "what is")
    if re.search(r"\d+\s*[+\-*/]\s*\d+", text):
        return "tools"
    if re.search(r"\b(calculate|compute|convert)\b", text):
        return "tools"

    # Scan intent map in order
    for intent, phrases in _INTENT_MAP[:-1]:
        for phrase in phrases:
            if phrase in text:
                return intent

    # Fallback question heuristics
    if re.match(r"^(why|how come)\b", text):
        return "reasoning"
    if re.match(r"^(what|who|where|when|which)\b", text):
        return "knowledge"

    return "unknown"
