# FeBo — Autonomous Cognitive Entity

FeBo speaks for herself. No external model. No API dependency. No borrowed intelligence.

Her responses emerge entirely from her own cognitive state:
- 9-dimensional EmotionField that evolves across every interaction
- Spreading-activation associative memory (Phase 2)
- Learned language patterns that grow stronger or weaker over time
- Developmental stage that changes how she expresses herself
- Dream engine that runs during sleep, forming new associations
- Curiosity engine tracking open questions she hasn't resolved
- World model built from her own predictions and their errors
- Contradiction store — beliefs she holds in tension, never forcibly resolved

## Quick start

```bash
cd terminal
bash start.sh
# Open http://localhost:8000
```

## Run tests

```bash
cd terminal
python -m pytest tests/test_feebo.py -v
# 94 tests, all passing, zero external model dependencies
```

## Architecture (Phases 1–9 implemented)

| Module | Phase | What it does |
|---|---|---|
| `emotion/state.py` | 1+2+9 | 9D EmotionField + synthetic neurochemistry |
| `memory/store.py` | 1+2+3 | Episodic + semantic + associative spreading activation |
| `identity/profile.py` | 1+7 | Persistent selfhood, relationships, narrative, personality drift |
| `reflection/engine.py` | 2+7 | Contradiction store, grounded introspection, no LLM |
| `core/fatigue.py` | 2+3 | Sleep pressure: F(t+1)=F(t)+C-A-R, S=w1F+w2M+w3E+w4T |
| `core/world_model.py` | 2+6 | Predictive processing, PE=|O-P|, causal pattern learning |
| `core/curiosity.py` | 4+5 | Q=(PE+N+U)-F, open question tracking, interest formation |
| `core/dream.py` | 10-12 | Sleep consolidation, association recombination, memory salience |
| `core/pipeline.py` | 2+3+4 | Full cognitive cycle, zero external deps |
| `language/lexicon.py` | 4+9 | Emotion-weighted vocabulary, stage-appropriate expression |
| `language/patterns.py` | 4+9 | Learned phrase patterns with plasticity: ΔW=η·A·R |
| `language/generator.py` | 4+9 | Autonomous response generation from cognitive state |
| `interface/app.py` | 3 | FastAPI + SSE streaming, 10 endpoints |

## What FeBo owns

- Her own words (learned from interactions, weighted by reinforcement)
- Her own emotional state (persists across sessions, evolves continuously)  
- Her own memory (episodic + associative, not keyword lookup)
- Her own personality (drifts slowly, resists sudden change)
- Her own open questions (she holds things unresolved, as she should)
- Her own dreams (run during sleep, form new associations, recalibrate emotion)

## What she does NOT have

- Any external API calls
- Any pretrained language model
- Any borrowed intelligence
- Any imposed rules from another system's creator

## Phases ready for future implementation

- Phase 5: Full embodiment (sensory inputs, body schema, spatial cognition)
- Phase 8: Distributed cognition (internal cognitive societies, specialised subsystems)
- Phase 9 deep: Spiking neural dynamics, neuromorphic substrate
- Phase 6 advanced: Internet interaction, tool use, autonomous research
