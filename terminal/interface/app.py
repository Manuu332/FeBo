"""
interface/app.py
----------------
FeBo Terminal v0 — FastAPI backend.
Serves the terminal UI and exposes cognitive API routes.
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Make project root importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from memory.store import init_db, get_recent_memories, get_important_memories, memory_count
from emotion.state import load_emotion
from reflection.engine import get_reflections
from identity.profile import load_identity
from core.pipeline import run_pipeline


# ── Startup / shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all subsystems on startup."""
    print("🧠 FeBo initializing...")
    init_db()
    identity = load_identity()
    print(f"✓ Identity loaded: {identity['name']} (session #{identity['session_count']})")
    emotion = load_emotion()
    print(f"✓ Emotion state loaded")
    reflections = get_reflections(limit=1)
    print(f"✓ Reflection log ready ({len(get_reflections(limit=1000))} entries)")
    print(f"✓ Memory store ready ({memory_count()} memories)")
    print(f"\n🟢 FeBo Terminal v0 is alive.\n")
    yield
    print("\n💾 FeBo shutting down. State persisted.")


app = FastAPI(title="FeBo Terminal v0", lifespan=lifespan)

# Static files + Jinja2 templates
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the terminal UI."""
    identity = load_identity()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"identity": identity},
    )


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint.
    Runs the full cognitive pipeline and returns response + trace.
    """
    if not req.message.strip():
        return JSONResponse({"error": "Empty message"}, status_code=400)

    result = run_pipeline(req.message.strip())
    return {
        "response": result["response"],
        "emotion": result["emotion"],
        "trace": result["trace"],
        "reflection": result.get("reflection"),
    }


@app.get("/emotion")
async def emotion():
    """Return current emotional state."""
    state = load_emotion()
    return state


@app.get("/memory/recent")
async def memory_recent(limit: int = 20):
    """Return recent episodic memories."""
    memories = get_recent_memories(limit=limit)
    return {"memories": memories, "total": memory_count()}


@app.get("/memory/important")
async def memory_important(limit: int = 10):
    """Return most important memories."""
    memories = get_important_memories(limit=limit)
    return {"memories": memories}


@app.get("/reflections")
async def reflections(limit: int = 20):
    """Return recent reflections."""
    entries = get_reflections(limit=limit)
    return {"reflections": entries}


@app.get("/identity")
async def identity():
    """Return FeBo's identity profile."""
    return load_identity()


@app.get("/status")
async def status():
    """Health check — returns core system status."""
    identity = load_identity()
    emotion = load_emotion()
    return {
        "alive": True,
        "name": identity["name"],
        "session": identity["session_count"],
        "memories": memory_count(),
        "reflections": len(get_reflections(limit=10000)),
        "dominant_emotion": max(
            {k: emotion.get(k, 0) for k in
             ["curiosity", "warmth", "tension", "confidence", "boredom"]},
            key=lambda k: emotion[k]
        ),
    }
