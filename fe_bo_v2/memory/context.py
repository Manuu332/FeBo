import re

from memory.memory import add_episode

context_data = {"last_input": None,
                "last_intent": None,
                "last_response": None,
                "last_trace": None,
                "topic": None,
                "last_subject": None,
                "user_state": None,
                "turns": [],
                "user_name": None,
                "likes": None
                }

MAX_TURNS = 12

STATE_PATTERNS = {
    "confused": ["confused", "don't understand", "dont understand", "lost", "don't get", "dont get"],
    "stuck": ["stuck", "blocked", "can't figure", "cant figure"],
    "tired": ["tired", "exhausted", "burned out", "burnt out"],
    "focused": ["focused", "ready", "let's go", "lets go"],
}

def reset_context():
    context_data.update({
        "last_input": None,
        "last_intent": None,
        "last_response": None,
        "last_trace": None,
        "topic": None,
        "last_subject": None,
        "user_state": None,
        "turns": [],
        "user_name": None,
        "likes": None,
    })

def update_context(user_input, intent, response=None):
    context_data["last_input"] = user_input
    context_data["last_intent"] = intent

    if context_data.get("turns") is None:
        context_data["turns"] = []

    topic = infer_topic(user_input, intent)
    if topic:
        context_data["topic"] = topic
        context_data["last_subject"] = topic

    user_state = infer_user_state(user_input)
    if user_state:
        context_data["user_state"] = user_state

    if response is not None:
        context_data["last_response"] = response
        context_data["turns"].append({"user": user_input, 
                                      "intent": intent, 
                                      "response": response,
                                      "topic": context_data.get("topic"),
                                      "user_state": context_data.get("user_state"),
                                      })
        if len(context_data["turns"]) > MAX_TURNS:
            context_data["turns"] = context_data["turns"][-MAX_TURNS:]
        add_episode(user_input, intent, response, context_data.get("topic"))

def get_recent_turns(limit=3):
    turns = context_data.get("turns") or []
    return turns[-limit:]

def set_topic(topic):
    context_data["topic"] = topic
    context_data["last_subject"] = topic

def get_topic():
    return context_data.get("topic")

def get_user_state():
    return context_data.get("user_state")

def get_last_subject():
    return context_data.get("last_subject") or context_data.get("topic")

def set_context(key, value):
    context_data[key] = value

def get_context(key):
    return context_data.get(key)

def set_trace(trace):
    context_data["last_trace"] = trace

def get_trace():
    return context_data.get("last_trace")

def infer_topic(user_input, intent):
    text = user_input.lower().strip()

    if intent == "memory":
        patterns = [
            r"\bi (?:like|love|prefer)\s+(.+)$",
            r"\bmy goal is\s+(.+)$",
            r"\bi want to\s+(.+)$",
            r"\bi need to\s+(.+)$",
            r"\b(?:add task|add todo|todo|remind me to)\s+(.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return _clean_topic(match.group(1))
        
    if intent == "tools":
        return "calculation"

    if intent == "knowledge":
        patterns = [
            r"\b(?:what do you know about|what facts? about|knowledge about)\s+(.+)$",
            r"^(?:remember that\s+)?(.+?)\s+(?:depends? on|requires|needs|supports?|helps|enables|conflicts? with|blocks?|causes?|leads to|is)\s+(.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return _clean_topic(match.group(1))

    if intent in {"planning", "reasoning"}:
        patterns = [
            r"\b(?:plan|break down|explain|compare|should i|what if)\s+(.+)$",
            r"\b(?:what should i do about|how should i handle|how do i handle)\s+(.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return _clean_topic(match.group(1))
    
    return context_data.get("topic")

def infer_user_state(user_input):
    text = user_input.lower()

    for state, phrases in STATE_PATTERNS.items():
        if any(phrase in text for phrase in phrases):
            return state

    return None

def _clean_topic(topic):
    topic = re.sub(r"[?.!]+$", "", topic.strip())
    topic = re.sub(r"^(about|on|for)\s+", "", topic)
    return topic or None
