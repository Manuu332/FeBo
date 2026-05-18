"""
interface/app.py — FeBo Terminal v3. No globals. RuntimeState owns all session state.
"""
from __future__ import annotations
import asyncio, json, sys, time
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=False)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core.persistence import get_db, db_stats, concept_top
from core.runtime_state import get_runtime
from memory.store import init_db, get_recent_memories, get_important_memories, memory_count, get_association_graph_sample
from memory.quality import get_tier_stats, run_maintenance
from emotion.state import load_emotion, save_emotion, decay_toward_baseline, get_display, mood_label
from reflection.engine import (get_reflections, write_reflection, mark_reflected, age_contradictions,
                                get_reflect_count, should_reflect, compose_reflection, get_contradictions)
from identity.profile import load_identity, get_identity_rich, to_system_prompt_block, get_development_stage, begin_session
from core.pipeline import run_pipeline, stream_pipeline
from core.fatigue import tick as fat_tick, get_state as fat_state, is_sleeping, get_summary as fat_summary
from core.curiosity import get_summary as curiosity_summary, get_open_questions, get_interests
from core.dream import get_dream_summary
from language.patterns import get_pattern_stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    rt = get_runtime()
    print("\n🧠 FeBo Terminal v3 — autonomous, unified persistence…")
    get_db()
    init_db()

    if not rt.session_started:
        session_n = begin_session()
        rt.begin_session(session_n)
        print(f"   ✓ Session #{session_n} began")

    identity = load_identity()
    emo      = load_emotion()
    fat_s    = fat_state()
    stage    = get_development_stage()
    stats    = db_stats()

    print(f"   ✓ Identity: {identity['name']} | Stage: {stage} | Session #{identity['session_count']}")
    print(f"   ✓ Emotion:  mood={mood_label(emo)}")
    print(f"   ✓ Memory:   {stats['episodes_hot']} hot | {stats['episodes_warm']} warm | {stats['episodes_cold']} cold")
    print(f"   ✓ Concepts: {stats['concepts']} indexed | {stats['associations']} associations")
    print(f"   ✓ Runtime:  {rt.get_status()}")
    print(f"\n🟢 FeBo speaks for herself.\n")

    asyncio.create_task(_background_loop())
    yield
    print("\n💾 FeBo shutting down. All state in febo.db.")


app = FastAPI(title="FeBo Terminal v3 — Autonomous", lifespan=lifespan)
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR    = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ChatRequest(BaseModel):
    message: str
    history: list = []
    entity:  str  = "user"


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        return JSONResponse({"error": "Empty message"}, status_code=400)
    def _gen():
        yield from stream_pipeline(req.message.strip(), req.history, req.entity)
    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.get("/emotion")
async def emotion(): return load_emotion()

@app.get("/memory/recent")
async def memory_recent(limit: int = 20):
    return {"memories": get_recent_memories(limit=limit), "total": memory_count()}

@app.get("/memory/important")
async def memory_important(limit: int = 10):
    return {"memories": get_important_memories(limit=limit)}

@app.get("/memory/tiers")
async def memory_tiers(): return get_tier_stats()

@app.get("/memory/concepts")
async def memory_concepts(limit: int = 20):
    return {"concepts": concept_top(limit=limit)}

@app.get("/reflections")
async def reflections(limit: int = 20):
    return {"reflections": get_reflections(limit=limit)}

@app.get("/reflect")
async def reflect_trigger():
    emo=load_emotion(); identity=load_identity(); recent=get_recent_memories(limit=8)
    text = compose_reflection(emo, recent, identity)
    if text: mark_reflected()
    return {"reflection": text or "Nothing surfaced right now.", "timestamp": time.time()}

@app.get("/identity")
async def identity(): return get_identity_rich()

@app.get("/associations")
async def associations(): return get_association_graph_sample(limit=15)

@app.get("/curiosity")
async def curiosity():
    return {"summary": curiosity_summary(), "open_questions": get_open_questions(limit=8),
            "interests": get_interests(limit=10)}

@app.get("/patterns")
async def patterns(): return {"stats": get_pattern_stats()}

@app.get("/dreams")
async def dreams(): return {"summary": get_dream_summary()}

@app.get("/db")
async def db_health(): return db_stats()

@app.get("/runtime")
async def runtime_status():
    """Runtime state — replaces scattered globals."""
    return get_runtime().get_status()

@app.get("/state")
async def state():
    emo=load_emotion(); fat_s=fat_state(); ident=load_identity()
    rt = get_runtime()
    return {"emotion": get_display(emo), "fatigue": fat_summary(fat_s),
            "sleeping": fat_s.get("sleeping", False), "stage": get_development_stage(),
            "session": ident.get("session_count", 1), "interactions": ident.get("total_interactions", 0),
            "memory": db_stats(), "reflect_count": get_reflect_count(),
            "curiosity": curiosity_summary(), "dreams": get_dream_summary(),
            "runtime": rt.get_status()}

@app.get("/status")
async def status():
    ident=load_identity(); emo=load_emotion(); fat_s=fat_state()
    return {"alive": True, "autonomous": True, "name": ident["name"],
            "session": ident["session_count"], "memories": memory_count(),
            "stage": get_development_stage(), "mood": mood_label(emo),
            "fatigue": round(fat_s.get("fatigue",0),3),
            "sleeping": fat_s.get("sleeping",False), "persistence": "unified_febo.db"}

@app.post("/memory/maintain")
async def maintenance():
    report = run_maintenance(hours_since_last=1.0)
    get_runtime().mark_maintenance_done()
    return {"report": report, "tiers": get_tier_stats()}


async def _background_loop():
    """Mid-tick every 15 min. RuntimeState owns scheduling decisions."""
    while True:
        await asyncio.sleep(900)
        try:
            emo = load_emotion()
            emo = decay_toward_baseline(emo, rate=0.04)
            save_emotion(emo)
            fat_tick(message_processed=False, emotion=emo)
            age_contradictions()
            rt = get_runtime()
            if rt.should_run_maintenance(interval_hours=4.0):
                run_maintenance(hours_since_last=4.0)
                rt.mark_maintenance_done()
        except Exception:
            pass


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    identity = load_identity()
    return templates.TemplateResponse(request, "index.html", {"identity": identity})
