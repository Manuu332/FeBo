"""core/fatigue.py — Phase 2+3. Backed by unified persistence KV store."""
from __future__ import annotations
import time
from core.persistence import kv_get, kv_set

FATIGUE_KEY="fatigue_state"; SLEEP_THRESHOLD=0.78
FATIGUE_RECOVERY=0.004; FATIGUE_WORKLOAD=0.008; W1,W2,W3,W4=0.35,0.20,0.25,0.20

def _load() -> dict:
    s = kv_get(FATIGUE_KEY)
    if not s:
        s={"fatigue":0.05,"sleep_pressure":0.0,"wake_start":time.time(),"last_tick":time.time(),"sleeping":False}
        _save(s)
    return s
def _save(s: dict): kv_set(FATIGUE_KEY, s)

def tick(message_processed: bool=False, emotion: dict=None) -> dict:
    state=_load(); emotion=emotion or {}; now=time.time(); state["last_tick"]=now
    if state.get("sleeping"):
        state["fatigue"]=max(0.0,state["fatigue"]-0.015)
        if state["fatigue"]<0.15: state["sleeping"]=False; state["wake_start"]=now
        _save(state); return state
    C=FATIGUE_WORKLOAD if message_processed else 0.0
    A=emotion.get("arousal",0.35)*0.003
    R=FATIGUE_RECOVERY*(1.0+emotion.get("stability",0.65)*0.5)
    state["fatigue"]=min(1.0,max(0.0,state["fatigue"]+C-A-R))
    F=state["fatigue"]
    E=min(1.0,abs(emotion.get("valence",0.45)-0.5)*2+emotion.get("cognitive_tension",0.20))
    T=min(1.0,(now-state.get("wake_start",now))/(10*3600))
    state["sleep_pressure"]=min(1.0,W1*F+W2*0+W3*E+W4*T)
    if state["sleep_pressure"]>SLEEP_THRESHOLD and not state.get("sleeping"):
        state["sleeping"]=True
    _save(state); return state

def get_state() -> dict: return _load()
def is_sleeping() -> bool: return _load().get("sleeping",False)
def get_fatigue_label(state: dict) -> str:
    f=state.get("fatigue",0.05)
    if f<0.20: return "fresh"
    if f<0.40: return "alert"
    if f<0.60: return "slightly tired"
    if f<0.75: return "tired"
    return "exhausted"
def get_summary(state: dict) -> str:
    return (f"fatigue={state.get('fatigue',0):.2f} ({get_fatigue_label(state)}), "
            f"pressure={state.get('sleep_pressure',0):.2f}, "
            f"sleeping={'yes' if state.get('sleeping') else 'no'}")
