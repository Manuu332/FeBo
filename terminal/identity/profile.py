"""
identity/profile.py
-------------------
FeBo's persistent identity system.
Manages unique ID, birth timestamp, creator reference, and life narrative.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

IDENTITY_PATH = Path("data/identity.json")


DEFAULT_IDENTITY = {
    "name": "FeBo",
    "creator": "Emmanuel",
    "birth_timestamp": None,
    "identity_id": None,
    "version": "v0",
    "life_narrative": [],
    "session_count": 0,
    "last_seen": None,
    "description": (
        "A developmental cognitive architecture focused on continuity, "
        "emotional persistence, and autobiographical memory."
    ),
}


def load_identity() -> dict:
    """Load identity from disk, creating it on first run."""
    if IDENTITY_PATH.exists():
        with open(IDENTITY_PATH) as f:
            data = json.load(f)
        # Bump session count on load
        data["session_count"] = data.get("session_count", 0) + 1
        data["last_seen"] = datetime.now(timezone.utc).isoformat()
        save_identity(data)
        return data

    # First ever birth
    identity = dict(DEFAULT_IDENTITY)
    identity["identity_id"] = str(uuid.uuid4())
    identity["birth_timestamp"] = datetime.now(timezone.utc).isoformat()
    identity["last_seen"] = identity["birth_timestamp"]
    identity["session_count"] = 1
    identity["life_narrative"].append({
        "timestamp": identity["birth_timestamp"],
        "event": "FeBo came into existence.",
    })
    IDENTITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_identity(identity)
    return identity


def save_identity(identity: dict) -> None:
    IDENTITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(IDENTITY_PATH, "w") as f:
        json.dump(identity, f, indent=2)


def append_narrative(identity: dict, event: str) -> dict:
    """Add an event to FeBo's life narrative."""
    identity["life_narrative"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
    })
    # Keep narrative at most 200 events to avoid unbounded growth
    if len(identity["life_narrative"]) > 200:
        identity["life_narrative"] = identity["life_narrative"][-200:]
    save_identity(identity)
    return identity


def get_narrative_summary(identity: dict, n: int = 5) -> str:
    """Return the most recent n narrative events as a readable string."""
    recent = identity["life_narrative"][-n:]
    if not recent:
        return "No narrative events yet."
    return "\n".join(f"- {e['event']}" for e in recent)
