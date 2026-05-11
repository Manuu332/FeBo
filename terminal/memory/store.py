"""
memory/store.py
---------------
FeBo's episodic memory system backed by SQLite.
Each memory records the message, an emotion snapshot, and an importance score.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path("data/memory.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                role        TEXT NOT NULL,
                message     TEXT NOT NULL,
                emotion     TEXT,
                importance  REAL DEFAULT 0.5,
                tags        TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_timestamp
            ON memories (timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_importance
            ON memories (importance)
        """)
        conn.commit()


def save_memory(
    role: str,
    message: str,
    emotion_snapshot: Optional[dict] = None,
    importance: float = 0.5,
    tags: Optional[list] = None,
) -> int:
    """Insert a memory and return its row ID."""
    ts = datetime.now(timezone.utc).isoformat()
    emotion_json = json.dumps(emotion_snapshot or {})
    tags_json = json.dumps(tags or [])

    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO memories (timestamp, role, message, emotion, importance, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ts, role, message, emotion_json, importance, tags_json),
        )
        conn.commit()
        return cur.lastrowid


def get_recent_memories(limit: int = 20) -> list[dict]:
    """Return the most recent memories."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_important_memories(limit: int = 10) -> list[dict]:
    """Return the most emotionally important memories."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY importance DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def search_memories(query: str, limit: int = 5) -> list[dict]:
    """Simple keyword search across messages."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM memories
               WHERE message LIKE ?
               ORDER BY importance DESC, timestamp DESC
               LIMIT ?""",
            (f"%{query}%", limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def retrieve_for_context(user_input: str, limit: int = 4) -> list[dict]:
    """
    Retrieve memories relevant to the current input.
    Strategy: keyword match + recent high-importance memories.
    """
    # Extract a few meaningful words (skip short words)
    words = [w for w in user_input.split() if len(w) > 3][:4]

    if words:
        results = []
        seen_ids = set()
        for word in words:
            for m in search_memories(word, limit=2):
                if m["id"] not in seen_ids:
                    results.append(m)
                    seen_ids.add(m["id"])
        if results:
            return results[:limit]

    return get_important_memories(limit)


def memory_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()
    return row["c"]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["emotion"] = json.loads(d.get("emotion") or "{}")
    except Exception:
        d["emotion"] = {}
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except Exception:
        d["tags"] = []
    return d
