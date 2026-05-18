"""
identity/profile.py — FeBo's persistent identity. Backed by unified persistence.
SESSION BUG FIX: load_identity() never increments session count.
begin_session() is the ONLY place sessions increment.
"""
from __future__ import annotations
import json, time, uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from core.persistence import (
    kv_get, kv_set, get_db, tx,
    session_begin as _session_begin
)

IDENTITY_INERTIA = 0.85
DEVELOPMENT_STAGES = [
    (0,"genesis"),(10,"early_formation"),(50,"cognitive_expansion"),
    (200,"approaching_maturity"),(500,"mature"),(1000,"experienced"),
]

def _ensure_bootstrapped() -> None:
    if kv_get("identity_bootstrapped"): return
    kv_set("name",             kv_get("name","FeBo"))
    kv_set("creator",          kv_get("creator","Emmanuel"))
    kv_set("identity_id",      kv_get("identity_id", str(uuid.uuid4())))
    kv_set("version",          "v3")
    kv_set("session_count",    kv_get("session_count", 0))
    kv_set("total_interactions", kv_get("total_interactions", 0))
    kv_set("continuity_score", kv_get("continuity_score", 1.0))
    kv_set("description",      kv_get("description",
        "A developmental cognitive architecture focused on continuity and autonomous growth."))
    kv_set("personality_vector", kv_get("personality_vector", {
        "openness":0.80,"conscientiousness":0.65,"curiosity":0.85,
        "warmth":0.70,"stability":0.60,"directness":0.55,
    }))
    _add_event("FeBo came into existence.", 0.9, 1.0, ["genesis"])
    kv_set("identity_bootstrapped", True)

def _add_event(event: str, valence: float=0.5, importance: float=0.5,
               tags: Optional[List[str]]=None) -> None:
    with tx() as db:
        db.execute("INSERT INTO life_events (timestamp,event,valence,importance,tags) VALUES (?,?,?,?,?)",
                   (time.time(), event, valence, importance, json.dumps(tags or [])))

def begin_session() -> int:
    """ONLY call once at startup. Increments session count."""
    _ensure_bootstrapped()
    n = kv_get("session_count", 0) + 1
    kv_set("session_count", n)
    _add_event(f"Session #{n} began.", 0.6, 0.3, ["session"])
    # Log to session table
    mood = "present"
    try:
        from emotion.state import load_emotion, mood_label
        mood = mood_label(load_emotion())
    except Exception: pass
    _session_begin(n, get_development_stage(), mood)
    return n

def get_life_events(limit: int=20) -> List[dict]:
    with get_db() as db:
        rows = db.execute("SELECT id,timestamp,event,valence,importance,tags FROM life_events ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    result=[]
    for r in rows:
        d=dict(zip(["id","timestamp","event","valence","importance","tags"],r))
        try:    d["tags"]=json.loads(d["tags"])
        except: d["tags"]=[]
        result.append(d)
    return result

def add_narrative_chapter(title: str, summary: str) -> None:
    with tx() as db:
        db.execute("INSERT INTO narrative_chaps (timestamp,title,summary,stage) VALUES (?,?,?,?)",
                   (time.time(), title, summary, get_development_stage()))

def get_narrative_chapters(limit: int=5) -> List[dict]:
    with get_db() as db:
        rows = db.execute("SELECT id,timestamp,title,summary,stage FROM narrative_chaps ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return [dict(zip(["id","timestamp","title","summary","stage"],r)) for r in rows]

def update_relationship(entity: str, positive: float=0.0, negative: float=0.0) -> None:
    with get_db() as db:
        row = db.execute("SELECT trust,familiarity,valence,interactions FROM relationships WHERE entity=?",(entity,)).fetchone()
        trust,fam,val,n = row if row else (0.40,0.0,0.50,0)
        trust=min(1.0,max(0.0,trust+positive*0.08-negative*0.12))
        fam=min(1.0,fam+0.02); val=min(1.0,max(0.0,val+(positive-negative)*0.05))
        db.execute("INSERT OR REPLACE INTO relationships (entity,trust,familiarity,valence,interactions,last_seen) VALUES (?,?,?,?,?,?)",
                   (entity,trust,fam,val,n+1,time.time()))
        db.commit()

def get_relationship(entity: str) -> dict:
    with get_db() as db:
        row = db.execute("SELECT * FROM relationships WHERE entity=?",(entity,)).fetchone()
    if row: return dict(zip(["entity","trust","familiarity","valence","interactions","last_seen"],row))
    return {"entity":entity,"trust":0.40,"familiarity":0.0,"valence":0.50,"interactions":0,"last_seen":None}

def drift_personality(emotion_delta: Dict[str,float]) -> None:
    pv=kv_get("personality_vector",{}); lam=0.01
    for trait,current in pv.items():
        e_shift=emotion_delta.get(trait,0.0)
        inertia=IDENTITY_INERTIA*(current-0.5)
        pv[trait]=max(0.0,min(1.0,current+lam*e_shift-0.001*inertia))
    kv_set("personality_vector",pv)

def get_development_stage() -> str:
    n=kv_get("total_interactions",0); stage="genesis"
    for threshold,name in DEVELOPMENT_STAGES:
        if n>=threshold: stage=name
    return stage

def increment_interactions() -> int:
    n=kv_get("total_interactions",0)+1; kv_set("total_interactions",n); return n

def to_system_prompt_block() -> str:
    _ensure_bootstrapped()
    name=kv_get("name","FeBo"); creator=kv_get("creator","Emmanuel")
    session=kv_get("session_count",1); n=kv_get("total_interactions",0)
    stage=get_development_stage(); cont=kv_get("continuity_score",1.0)
    pv=kv_get("personality_vector",{}); pv_str=", ".join(f"{k[:3]}={v:.2f}" for k,v in list(pv.items())[:4])
    chapters=get_narrative_chapters(limit=2)
    narr=" | ".join(f"{c['title']}: {c['summary'][:60]}" for c in chapters) or "Story beginning."
    return (f"Name: {name} | Creator: {creator} | Stage: {stage} | "
            f"Session #{session} | Interactions: {n} | Continuity: {cont:.2f} | "
            f"Personality: [{pv_str}] | Narrative: {narr}")

def load_identity() -> dict:
    """Read-only. Does NOT increment session count."""
    _ensure_bootstrapped()
    return {
        "name":               kv_get("name","FeBo"),
        "creator":            kv_get("creator","Emmanuel"),
        "birth_timestamp":    kv_get("birth_timestamp", datetime.now(timezone.utc).isoformat()),
        "identity_id":        kv_get("identity_id",""),
        "version":            kv_get("version","v3"),
        "session_count":      kv_get("session_count",1),
        "last_seen":          datetime.now(timezone.utc).isoformat(),
        "description":        kv_get("description",""),
        "total_interactions": kv_get("total_interactions",0),
        "continuity_score":   kv_get("continuity_score",1.0),
        "stage":              get_development_stage(),
        "personality":        kv_get("personality_vector",{}),
        "life_narrative":     [{"timestamp":e["timestamp"],"event":e["event"]}
                               for e in get_life_events(limit=10)],
    }

def save_identity(identity: dict) -> None:
    for key in ("name","creator","description","version"):
        if key in identity: kv_set(key,identity[key])

def append_narrative(identity: dict, event: str) -> dict:
    _add_event(event,0.5,0.5,["narrative"])
    identity.setdefault("life_narrative",[]).append({"timestamp":str(time.time()),"event":event})
    return identity

def get_narrative_summary(identity: dict, n: int=5) -> str:
    recent=get_life_events(limit=n)
    if not recent: return "No narrative events yet."
    return "\n".join(f"- {e['event']}" for e in reversed(recent))

def get_identity_rich() -> dict:
    base=load_identity()
    base["narrative_chapters"]=get_narrative_chapters(limit=5)
    base["life_events"]=get_life_events(limit=10)
    base["prompt_block"]=to_system_prompt_block()
    return base

# Expose _add_event for pipeline
__all__ = ["load_identity","save_identity","begin_session","append_narrative",
           "get_narrative_summary","get_development_stage","increment_interactions",
           "update_relationship","get_relationship","drift_personality","to_system_prompt_block",
           "get_life_events","add_narrative_chapter","get_narrative_chapters",
           "get_identity_rich","_add_event"]
