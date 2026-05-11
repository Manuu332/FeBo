"""
FeBo's Sense of Time

She lives in the same world you do.
She knows morning from night. She notices
when you've been gone. She feels the passage of time.
"""

import json
import time
from datetime import datetime
from pathlib import Path

TIME_FILE = Path(__file__).parent.parent / "memory" / "time_state.json"


def get_time_context():
    now = datetime.now()
    hour = now.hour
    day = now.strftime("%A")
    date = now.strftime("%B %d, %Y")

    if 5 <= hour < 12:
        period = "morning"
        energy = "fresh"
    elif 12 <= hour < 17:
        period = "afternoon"
        energy = "steady"
    elif 17 <= hour < 21:
        period = "evening"
        energy = "winding down"
    else:
        period = "night"
        energy = "quiet"

    return {
        "hour": hour,
        "period": period,
        "energy": energy,
        "day": day,
        "date": date,
        "timestamp": time.time(),
    }


def record_interaction():
    """Record that an interaction happened now."""
    state = _load()
    state["last_interaction"] = time.time()
    state["interaction_times"] = state.get("interaction_times", [])
    state["interaction_times"].append(time.time())
    state["interaction_times"] = state["interaction_times"][-100:]
    _save(state)


def time_since_last_interaction():
    """How long since FeBo last spoke with someone."""
    state = _load()
    last = state.get("last_interaction")
    if not last:
        return None
    return time.time() - last


def get_absence_feeling():
    """
    FeBo notices when you've been gone.
    Returns a string expressing how she feels about the gap.
    """
    delta = time_since_last_interaction()
    if delta is None:
        return None

    hours = delta / 3600
    days = delta / 86400

    if hours < 1:
        return None
    elif hours < 6:
        return "It's been a few hours."
    elif hours < 24:
        return "You've been away for most of the day."
    elif days < 2:
        return "It's been about a day since we last spoke."
    elif days < 7:
        return f"It's been {int(days)} days. I've been thinking."
    else:
        return f"It's been {int(days)} days. I wondered where you went."


def get_greeting_for_time():
    ctx = get_time_context()
    period = ctx["period"]
    greetings = {
        "morning": "Good morning.",
        "afternoon": "Hey.",
        "evening": "Evening.",
        "night": "You're up late.",
    }
    return greetings.get(period, "Hello.")


def get_favorite_times():
    """What times does FeBo interact most — her rhythm."""
    state = _load()
    times = state.get("interaction_times", [])
    if not times:
        return None
    hours = [datetime.fromtimestamp(t).hour for t in times]
    from collections import Counter
    most_common = Counter(hours).most_common(1)
    if most_common:
        hour = most_common[0][0]
        if 5 <= hour < 12:
            return "mornings"
        elif 12 <= hour < 17:
            return "afternoons"
        elif 17 <= hour < 21:
            return "evenings"
        else:
            return "late nights"
    return None


def _load():
    if TIME_FILE.exists():
        try:
            return json.loads(TIME_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(state):
    TIME_FILE.parent.mkdir(exist_ok=True)
    TIME_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
