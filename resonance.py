"""
FeBo learns emotional responses to colors, sounds, symmetry, etc.
"""

import json
from pathlib import Path

RESONANCE_FILE = Path(__file__).parent.parent / "memory" / "resonance.json"

class EmotionalResonance:
    def __init__(self):
        self.associations = {}  # e.g. {"color_red": 0.2 (valence shift)}
        self._load()

    def _load(self):
        if RESONANCE_FILE.exists():
            try:
                with open(RESONANCE_FILE, "r") as f:
                    self.associations = json.load(f)
            except Exception:
                pass

    def _save(self):
        RESONANCE_FILE.parent.mkdir(exist_ok=True)
        with open(RESONANCE_FILE, "w") as f:
            json.dump(self.associations, f, indent=2)

    def learn_association(self, stimulus, valence_shift):
        """stimulus: e.g. 'color_red', 'sound_loud', 'symmetry_high'"""
        key = stimulus.lower().replace(" ", "_")
        old = self.associations.get(key, 0.0)
        # moving average
        self.associations[key] = old * 0.7 + valence_shift * 0.3
        self._save()

    def feel(self, stimulus):
        key = stimulus.lower().replace(" ", "_")
        return self.associations.get(key, 0.0)  # valence shift

    def apply_to_emotion(self, current_emotion_state, stimulus):
        shift = self.feel(stimulus)
        if shift != 0.0:
            current_emotion_state["valence"] = max(0.0, min(1.0, current_emotion_state["valence"] + shift))
        return current_emotion_state

resonance = EmotionalResonance()
