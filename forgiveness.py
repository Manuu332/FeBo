"""
FeBo tracks betrayals, apologies, and decides when to forgive.
"""

import json
import time
from pathlib import Path

FORGIVENESS_FILE = Path(__file__).parent.parent / "memory" / "forgiveness.json"

class ForgivenessSystem:
    def __init__(self):
        self.transgressions = []  # list of {time, severity, context, forgiven}
        self.resentment = 0.0      # 0..1
        self._load()

    def _load(self):
        if FORGIVENESS_FILE.exists():
            try:
                with open(FORGIVENESS_FILE, "r") as f:
                    data = json.load(f)
                    self.transgressions = data.get("transgressions", [])
                    self.resentment = data.get("resentment", 0.0)
            except Exception:
                pass

    def _save(self):
        FORGIVENESS_FILE.parent.mkdir(exist_ok=True)
        with open(FORGIVENESS_FILE, "w") as f:
            json.dump({
                "transgressions": self.transgressions,
                "resentment": self.resentment
            }, f, indent=2)

    def record_transgression(self, severity, context, apologized=False):
        entry = {
            "time": time.time(),
            "severity": severity,   # 0..1
            "context": context,
            "apologized": apologized,
            "forgiven": False
        }
        self.transgressions.append(entry)
        self.resentment = min(1.0, self.resentment + severity * 0.3)
        self._save()

    def record_apology(self, sincerity=0.7):
        # Reduces resentment based on sincerity
        reduction = sincerity * 0.4
        self.resentment = max(0.0, self.resentment - reduction)
        # Mark recent transgressions as forgiven if resentment low
        for t in self.transgressions:
            if not t["forgiven"] and t["time"] > time.time() - 86400:
                t["forgiven"] = True
        self._save()

    def should_forgive(self, transgression):
        # She decides based on severity, context, her mood, and relationship
        from brain.emotion import load_state
        state = load_state()
        current_warmth = state.get("warmth", 0.5)
        if transgression["apologized"]:
            threshold = 0.6
        else:
            threshold = 0.3
        # Higher warmth makes her more forgiving
        decision = (current_warmth > threshold) or (transgression["severity"] < 0.2)
        return decision

    def get_moral_mood(self):
        if self.resentment > 0.6:
            return "resentful"
        elif self.resentment > 0.3:
            return "slightly hurt"
        else:
            return "at peace"

# Global instance
forgiveness = ForgivenessSystem()
