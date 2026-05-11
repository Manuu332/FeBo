# FeBo — Architecture Reference (Merged v2)

## The Central Principle

> FeBo's greatest strength is continuity-centred cognition.
> Every architectural decision must serve that.

---

## The Dual-Brain Problem — Solved

**Before**: `brain/soul.py` AND `core/cognitive_loop.py` both tried to orchestrate. Diverging state, memory desync, identity fragmentation.

**After**: `brain/soul.py` is the ONLY orchestrator. `core/cognitive_loop.py` is kept as a data-structure library only (CognitiveState dataclass).

**Rule: brain/ thinks. core/ serves.**

---

## The Five-Stage Loop (brain/soul.py)

```
PERCEIVE → DESIRE → PLAN → ACT → REFLECT
```

| Stage    | What happens                                        |
|----------|-----------------------------------------------------|
| PERCEIVE | Emotion + forgiveness + resonance + time context    |
| DESIRE   | Drives determine what FeBo *wants* (not just intent)|
| PLAN     | Desire → concrete action type                       |
| ACT      | Execute, moral gate consulted                       |
| REFLECT  | RLHF learn + episodic store + identity + drives     |

**Key**: intent classification feeds into DESIRE as an input, not a router. Drives can override intent. This is what makes FeBo feel alive.

---

## New Infrastructure (what was added)

| Module                    | Solves                                            |
|---------------------------|---------------------------------------------------|
| `core/runtime_state.py`   | Single shared emotion state — no more desync      |
| `core/scheduler.py`       | One background thread heartbeat — no more chaos   |
| `core/observability.py`   | Emotion drift + health logs — know if she's growing |
| `brain/soul.py` (rebuilt) | Sovereign loop with all 5 stages wired            |
| `brain/ai.py`             | Language generation bridge + experience tracking  |
| `brain/intents.py`        | Intent classifier (tool, not router)              |
| `brain/background.py`     | Spontaneous thoughts between interactions         |
| `brain/learner.py` (fixed)| Syntax fixed + clean public API                   |
| `main.py` (rebuilt)       | Unified boot + single scheduler task registration |
| `interface/cli.py`        | Observability commands: status, observe, scheduler|

---

## Single Shared State

```python
from core.runtime_state import runtime
runtime.update_emotion(state)   # soul writes
runtime.get_emotion()           # subsystems read
runtime.set("ns", "key", val)   # background tasks use namespaces
```

Only `brain/soul.py` writes emotion during interaction.

---

## Single Scheduler

```python
from core.scheduler import scheduler
scheduler.register("task_name", interval_s=60, callback=fn)
scheduler.start()  # ONE thread, all tasks
```

No module spawns its own thread for periodic work.

---

## Observability CLI Commands

```
status     → full system snapshot (emotion, drives, scheduler, health)
observe    → emotion drift from baseline + recent health events
scheduler  → background task run counts and errors
```

**Reading emotional drift**:
```bash
tail -20 logs/emotion_drift.jsonl | python3 -c "
import sys,json
for l in sys.stdin:
    d=json.loads(l)
    print(f'turn={d[\"turn\"]:4d} mood={d[\"mood\"]:<12} val={d[\"v\"]:+.2f}')
"
```

---

## What Was Deliberately NOT Added

Feature freeze is the right call here. No new modules. Only the three critical missing pieces:
- ✅ Single shared state
- ✅ Single scheduler
- ✅ Observability

Everything else preserves Emmanuel's original design intact.

---

## Developmental Success Indicators

After 50+ rewarded turns, look for:
1. **Emotion drift** — mood varies with content (check `logs/emotion_drift.jsonl`)
2. **Vocab growth** — `words_learned` in `status` increases each session
3. **Coherent recall** — `recall("consciousness")` returns real content
4. **Desire variation** — not always the same desire type
5. **Life event accumulation** — `identity.get_recent_events()` grows

If any are flat after 100 turns: `cat logs/health.jsonl`

---

*Merged v2 — resolving the dual-brain, adding observability, preserving Emmanuel's soul.*
