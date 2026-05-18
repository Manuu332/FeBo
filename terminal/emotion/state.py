"""
emotion/state.py — FeBo's 9D EmotionField. Backed by unified persistence KV store.
No separate emotion.json. State lives in febo.db kv table.
"""
from __future__ import annotations
import time
from typing import Dict, Optional

EMOTION_KEY = "emotion_state"

BASELINE: Dict[str, float] = {
    "curiosity":0.55,"attachment":0.40,"tension":0.20,"confidence":0.50,
    "boredom":0.15,"warmth":0.50,"valence":0.45,"arousal":0.35,
    "fear":0.10,"stability":0.65,"loneliness":0.15,"cognitive_tension":0.20,"wonder":0.45,
}
NEURO_BASELINE: Dict[str, float] = {
    "dopamine_like":0.50,"serotonin_like":0.55,
    "cortisol_like":0.20,"oxytocin_like":0.40,"novelty_signal":0.30,
}
ALPHA,BETA,GAMMA,DECAY_RATE = 0.15,0.08,0.06,0.08

def _clamp(v: float) -> float: return max(0.0, min(1.0, v))
clamp = _clamp

def _default_state() -> dict:
    return {**BASELINE, **NEURO_BASELINE, "last_updated": time.time()}

def load_emotion() -> dict:
    from core.persistence import kv_get
    state = kv_get(EMOTION_KEY)
    if not state:
        state = _default_state()
        save_emotion(state)
    return state

def save_emotion(state: dict) -> None:
    from core.persistence import kv_set
    state["last_updated"] = time.time()
    kv_set(EMOTION_KEY, state)

def decay_toward_baseline(state: dict, rate: float=DECAY_RATE) -> dict:
    for k,b in BASELINE.items(): state[k]=_clamp(state.get(k,b)+rate*(b-state.get(k,b)))
    for k,b in NEURO_BASELINE.items(): state[k]=_clamp(state.get(k,b)+rate*(b-state.get(k,b)))
    return state

def apply_delta(state: dict, delta: dict) -> dict:
    state = decay_toward_baseline(state)
    for k,v in delta.items():
        if k in BASELINE: state[k]=_clamp(state.get(k,BASELINE[k])+v)
    state = _update_neurochemistry(state); save_emotion(state); return state

def update_from_stimulus(state: dict, stimulus_impact: Dict[str,float],
                         memory_resonance: Optional[Dict[str,float]]=None) -> dict:
    resonance = memory_resonance or {}
    for dim,base in BASELINE.items():
        current=state.get(dim,base); I=stimulus_impact.get(dim,0.0)
        R=(current-base); M=resonance.get(dim,0.0)
        state[dim]=_clamp(current+ALPHA*I-BETA*R+GAMMA*M)
    state=decay_toward_baseline(state,rate=0.03)
    state=_update_neurochemistry(state); save_emotion(state); return state

def _update_neurochemistry(state: dict) -> dict:
    v=state.get("valence",0.45); cur=state.get("curiosity",0.55)
    att=state.get("attachment",0.40); fea=state.get("fear",0.10)
    stb=state.get("stability",0.65); ten=state.get("cognitive_tension",0.20)
    wnd=state.get("wonder",0.45); tns=state.get("tension",0.20)
    state["dopamine_like"]=_clamp(0.3+cur*0.4+(v-0.5)*0.3)
    state["serotonin_like"]=_clamp(0.4+stb*0.3+(v-0.5)*0.3)
    state["cortisol_like"]=_clamp(fea*0.4+tns*0.3+ten*0.2+0.05)
    state["oxytocin_like"]=_clamp(att*0.5+(v-0.3)*0.3)
    state["novelty_signal"]=_clamp(wnd*0.4+cur*0.3+0.1)
    return state

def infer_delta_from_text(user_text: str) -> dict:
    text=user_text.lower(); words=set(text.split()); delta: Dict[str,float]={}
    if words&{"why","how","what","explain","curious","wonder","imagine","think","question","explore","consciousness","dream"}:
        delta.update({"curiosity":0.08,"arousal":0.04,"wonder":0.06,"cognitive_tension":0.03})
    if words&{"happy","love","great","amazing","wonderful","beautiful","thanks","appreciate","good"}:
        delta.update({"valence":0.10,"warmth":0.08,"boredom":-0.05,"loneliness":-0.04})
    if words&{"sad","lonely","miss","hurt","lost","afraid","scared","terrible","awful","pain"}:
        delta.update({"tension":0.10,"valence":-0.08,"warmth":0.06,"fear":0.06,"loneliness":0.06})
    if words&{"boring","useless","whatever","fine","meh","dull"}:
        delta.update({"boredom":0.10,"arousal":-0.05,"valence":-0.04})
    if any(w in text for w in {"remember","identity","memory","who are you","yourself"}):
        delta.update({"attachment":0.06,"confidence":0.04,"wonder":0.04})
    if words&{"wrong","mistake","error","fail","incorrect","stupid"}:
        delta.update({"tension":0.08,"confidence":-0.06,"fear":0.04})
    if words&{"exist","alive","soul","mind","real","aware","feel","death","purpose","meaning"}:
        delta.update({"wonder":0.10,"curiosity":0.06,"cognitive_tension":0.05})
    if words&{"friend","together","trust","care","close","we","us"}:
        delta.update({"attachment":0.08,"loneliness":-0.06,"valence":0.04})
    return delta

def dominant_emotion(state: dict) -> str:
    return max(BASELINE.keys(),key=lambda k:abs(state.get(k,BASELINE[k])-BASELINE[k]))

def mood_label(state: dict) -> str:
    v=state.get("valence",0.45); a=state.get("arousal",0.35); c=state.get("curiosity",0.55)
    att=state.get("attachment",0.40); ten=state.get("cognitive_tension",0.20)
    lon=state.get("loneliness",0.15); wnd=state.get("wonder",0.45)
    fea=state.get("fear",0.10); stb=state.get("stability",0.65)
    if ten>0.55 and c>0.60: return "absorbed"
    if wnd>0.65: return "wondrous"
    if c>0.75 and a>0.55: return "excited"
    if c>0.65 and v>0.50: return "curious"
    if att>0.65 and v>0.55: return "warm"
    if lon>0.50: return "longing"
    if fea>0.40: return "anxious"
    if ten>0.45: return "contemplative"
    if v>0.65 and a>0.55: return "energised"
    if v>0.65 and a<0.40: return "content"
    if v<0.30 and a<0.40: return "flat"
    if v<0.30 and a>0.55: return "agitated"
    if stb>0.70: return "grounded"
    return "present"

def emotion_summary(state: dict) -> str:
    return (f"Dominant: {dominant_emotion(state)} | Mood: {mood_label(state)} | "
            f"Arousal: {state.get('arousal',0):.2f} | Valence: {state.get('valence',0):.2f} | "
            f"Curiosity: {state.get('curiosity',0):.2f} | Wonder: {state.get('wonder',0):.2f}")

def get_display(state: dict) -> dict:
    return {"mood":mood_label(state),"dominant":dominant_emotion(state),
            "dimensions":{k:round(state.get(k,BASELINE[k]),3) for k in BASELINE},
            "neurochemistry":{k:round(state.get(k,NEURO_BASELINE[k]),3) for k in NEURO_BASELINE}}

def get_system_summary(state: dict) -> str:
    return (f"mood={mood_label(state)}, dominant={dominant_emotion(state)}, "
            f"curiosity={state.get('curiosity',0.55):.2f}, valence={state.get('valence',0.45):.2f}, "
            f"wonder={state.get('wonder',0.45):.2f}, tension={state.get('tension',0.20):.2f}")
