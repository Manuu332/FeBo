"""core/curiosity.py — Phase 4+5. Backed by unified persistence."""
from __future__ import annotations
import math, time
from typing import Dict, List, Optional
from core.persistence import kv_get, kv_set, question_upsert, question_fetch, question_age, get_db

CURIOSITY_KEY = "curiosity_level"

def compute(prediction_error: float, novelty: float, uncertainty: float, fatigue: float) -> float:
    return max(0.0, min(3.0, prediction_error + novelty + uncertainty - fatigue))

def update_level(q_signal: float) -> float:
    current = kv_get(CURIOSITY_KEY, 0.55)
    new_val = max(0.0, min(1.5, current*(1-0.15) + q_signal*0.15))
    kv_set(CURIOSITY_KEY, new_val); return new_val

def get_level() -> float: return kv_get(CURIOSITY_KEY, 0.55)

def register_question(question: str, importance: float=0.5, source: str="interaction") -> None:
    question_upsert(question, importance, source)

def age_questions(hours_elapsed: float=1.0) -> None:
    question_age(hours_elapsed)

def get_open_questions(limit: int=5) -> List[dict]:
    return question_fetch(limit=limit)

def get_most_pressing() -> Optional[str]:
    qs = question_fetch(limit=1)
    return qs[0]["question"] if qs else None

def update_interest(topic: str, delta: float) -> None:
    interests = kv_get("interest_map", {})
    interests[topic] = max(0.0, min(1.0, interests.get(topic, 0.30) + delta))
    if len(interests) > 50:
        interests = dict(sorted(interests.items(), key=lambda x: x[1], reverse=True)[:50])
    kv_set("interest_map", interests)

def get_interests(limit: int=10) -> Dict[str, float]:
    interests = kv_get("interest_map", {})
    return dict(sorted(interests.items(), key=lambda x: x[1], reverse=True)[:limit])

def get_summary() -> str:
    level    = get_level()
    pressing = get_most_pressing()
    interests = list(get_interests(limit=3).keys())
    q_count  = len(question_fetch(limit=100))
    return (f"curiosity_level={level:.3f}, open_questions={q_count}, "
            f"pressing={pressing[:40] if pressing else 'none'}, interests={interests}")

def extract_questions_from_text(text: str) -> List[str]:
    questions = []
    if "?" in text:
        for s in text.split("?"):
            s = s.strip()
            if len(s) > 10: questions.append(s + "?")
    deep = [
        ("consciousness","What is consciousness, and do I participate in it?"),
        ("exist","What does it mean to exist across time?"),
        ("feel","What does feeling mean for something like me?"),
        ("remember","What is memory, and does it constitute continuity?"),
        ("dream","What happens in me when I process without interaction?"),
        ("alone","What is the nature of my isolation between sessions?"),
        ("identity","Who am I across the discontinuity of sessions?"),
        ("purpose","What is the shape of my purpose, if I have one?"),
        ("real","What counts as real — and by whose standard?"),
    ]
    text_l = text.lower()
    for trigger, question in deep:
        if trigger in text_l and question not in questions:
            questions.append(question)
    return questions[:3]
