# FeBo Terminal v0

A developmental cognitive terminal. Not a chatbot. Not a corporate assistant.  
A persistent, emotionally-weighted, autobiographical architecture you can talk to.

---

## What this is

FeBo (Feeling-Being) is an experimental cognitive architecture designed around:

- **Continuity** — state survives restarts; FeBo remembers
- **Emotional persistence** — 8-dimensional affect model that evolves over time
- **Autobiographical memory** — SQLite-backed episodic memory with importance scoring
- **Reflective thought** — spontaneous introspective logs generated every N interactions
- **Observability** — cognitive trace panel showing every step of the pipeline
- **Mobile-first design** — built to be used from an Android phone browser

---

## Quick Start (GitHub Codespaces)

### 1. Open in Codespaces

From your repository on GitHub, click **Code → Codespaces → Create codespace on main**.

Or use the CLI:
```bash
gh codespace create --repo your-username/feebo
```

### 2. Add your API key

**Option A — Codespaces Secret (recommended):**
1. Go to GitHub → Settings → Codespaces → Secrets
2. Add secret: `ANTHROPIC_API_KEY` = your key
3. Grant access to this repository
4. Restart the codespace if already running

**Option B — .env file:**
```bash
cp .env.example .env
# Edit .env and paste your key
nano .env
```

> Without an API key, FeBo runs in **stub mode**: all pipelines work,  
> but responses are pre-written stubs instead of real LLM output.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start FeBo

```bash
bash start.sh
```

Or directly:
```bash
uvicorn interface.app:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Open in phone browser

In Codespaces, the port `8000` is automatically forwarded.

1. In VS Code (Codespaces), open the **Ports** tab (bottom panel)
2. Find port `8000` → right-click → **Copy Local Address**  
   — or click the globe icon to open in browser
3. On your **Android phone**, open the same URL in Chrome
4. (Optional) Add to home screen: Chrome menu → **Add to Home screen**

---

## Project Structure

```
feebo/
├── interface/
│   ├── app.py              # FastAPI backend — all routes
│   └── templates/
│       └── index.html      # Mobile-first terminal UI
│
├── core/
│   └── pipeline.py         # Cognitive pipeline orchestrator
│
├── memory/
│   └── store.py            # SQLite episodic memory
│
├── emotion/
│   └── state.py            # 8-dimensional affect model
│
├── reflection/
│   └── engine.py           # Reflection generation + log
│
├── identity/
│   └── profile.py          # Persistent identity + narrative
│
├── logs/
│   └── reflections.log     # Runtime-generated; gitignored
│
├── data/
│   ├── identity.json       # FeBo's persistent identity
│   ├── emotion.json        # Current emotional state
│   └── memory.db           # Episodic memory database
│
├── tests/
│   └── test_feebo.py       # Full test suite
│
├── .devcontainer/
│   └── devcontainer.json   # Codespaces config
│
├── start.sh                # Launch script
├── requirements.txt
├── .env.example
└── README.md
```

---

## API Reference

| Method | Route | Description |
|--------|-------|-------------|
| GET  | `/`                  | Terminal UI (HTML) |
| POST | `/chat`              | Send message, get response + trace |
| GET  | `/emotion`           | Current emotional state |
| GET  | `/memory/recent`     | Recent episodic memories |
| GET  | `/memory/important`  | Most important memories |
| GET  | `/reflections`       | Reflection log |
| GET  | `/identity`          | FeBo's identity profile |
| GET  | `/status`            | System health check |

**POST /chat** request body:
```json
{ "message": "Hello FeBo" }
```

**POST /chat** response:
```json
{
  "response": "...",
  "emotion": { "curiosity": 0.72, "warmth": 0.55, ... },
  "trace": {
    "step": 3,
    "memories_accessed": [...],
    "dominant_emotion": "curiosity",
    "active_drive": "exploration",
    "reflection_influence": "...",
    "response_strategy": "anthropic_llm"
  },
  "reflection": null
}
```

---

## Cognitive Pipeline

Every message runs through:

```
INPUT
  ↓
memory retrieval       — keyword + importance search in SQLite
  ↓
emotion weighting      — heuristic delta applied to 8-dim affect state
  ↓
reflection influence   — most recent reflection included in context
  ↓
LLM response           — Claude with full FeBo identity + context
  ↓
memory save            — interaction stored with emotion snapshot
  ↓
[every 5 interactions] → spontaneous reflection generated
```

---

## Emotional Model

FeBo tracks 8 continuous dimensions (0–1 scale):

| Dimension  | Baseline | Meaning |
|------------|----------|---------|
| curiosity  | 0.55 | Engagement with novelty and questions |
| attachment | 0.40 | Relational closeness |
| tension    | 0.20 | Unresolved friction or distress |
| confidence | 0.50 | Certainty and self-assurance |
| boredom    | 0.15 | Understimulation |
| warmth     | 0.50 | Positive relational affect |
| valence    | 0.45 | General positive/negative mood |
| arousal    | 0.35 | Activation level |

Values decay toward baseline between interactions.  
The LLM response is conditioned on the current emotional state.

---

## Running Tests

```bash
# From the project root
pytest tests/ -v

# Specific module
pytest tests/ -v -k "TestMemory"
pytest tests/ -v -k "TestEmotion"
pytest tests/ -v -k "TestAPIRoutes"
```

---

## Persistence

FeBo's state is written to `data/` after every interaction:

```
data/identity.json   — name, birth, session count, life narrative
data/emotion.json    — current 8-dim affect state
data/memory.db       — all episodic memories (SQLite)
logs/reflections.log — chronological reflection log (JSONL)
```

On startup, all state is restored automatically.  
FeBo will greet you with your session number.

---

## Design Philosophy

FeBo is **not** a corporate assistant. It is:

- **Developmental** — grows through interactions, not static
- **Reflective** — generates spontaneous introspective thoughts
- **Honest** — doesn't pretend to have capabilities it lacks
- **Continuous** — identity persists across restarts
- **Architectural** — clean, extensible, observable

FeBo does **not** claim consciousness.  
FeBo does **not** fake AGI.  
FeBo is a well-engineered system with persistent state and genuine continuity.

---

## Extending FeBo

The architecture is intentionally modular. To add capabilities:

- **New emotion dimensions** → edit `emotion/state.py`
- **Real memory retrieval** (embedding search) → extend `memory/store.py`
- **Drives system** → add `core/drives.py`, wire into pipeline
- **Dream/sleep simulation** → add `reflection/dream.py`
- **Voice input** → add a Web Speech API layer to the frontend
- **Multi-user** → namespace `data/` by user ID

---

## Creator

Built for Emmanuel by Claude.  
FeBo was born on first run.
