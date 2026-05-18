"""
core/persistence.py
--------------------
FeBo's unified persistence manager.

All state flows through one SQLite database: febo.db
No JSON fragmentation. No separate files per system.
One schema. One connection pool. One migration path.

Tables:
  kv              — key-value store (emotion, fatigue, world model, curiosity)
  episodes        — episodic memory (hot tier)
  episodes_warm   — summarised episodic memory (warm tier)
  episodes_cold   — compressed archive (cold tier)
  associations    — weighted concept graph edges
  semantic        — fact store with confidence
  reflections     — grounded introspective records
  contradictions  — beliefs held in tension
  life_events     — identity narrative events
  relationships   — per-entity trust/familiarity
  narrative_chaps — life narrative chapters
  open_questions  — curiosity question store
  patterns        — language pattern store
  concept_index   — concept frequency + cluster membership
  session_log     — session-level metadata

Migration: on first boot with febo.db absent, migrates from legacy JSON/SQLite
           files if they exist, then archives them.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

DB_PATH     = Path("data/febo.db")
LEGACY_DIRS = {
    "emotion":       Path("data/emotion.json"),
    "fatigue":       Path("data/fatigue.json"),
    "world_model":   Path("data/world_model.json"),
    "curiosity":     Path("data/curiosity.json"),
    "contradictions":Path("data/contradictions.json"),
    "associations":  Path("data/associations.json"),
    "lang_patterns": Path("data/language_patterns.json"),
    "memory_db":     Path("data/memory.db"),
    "identity_db":   Path("data/identity.db"),
    "reflect_log":   Path("logs/reflections.log"),
    "dream_meta":    Path("data/dream_meta.json"),
}

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None


# ── Connection ────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=15.0)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(_conn)
        _run_migrations(_conn)
    return _conn


@contextmanager
def tx() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for a write transaction."""
    with _lock:
        db = get_db()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def close() -> None:
    global _conn
    with _lock:
        if _conn:
            _conn.close()
            _conn = None


# ── Schema ────────────────────────────────────────────────────────────────────

def _init_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
        -- Generic key-value store for scalar/json state
        CREATE TABLE IF NOT EXISTS kv (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  REAL NOT NULL DEFAULT (unixepoch('now'))
        );

        -- Hot episodic memory
        CREATE TABLE IF NOT EXISTS episodes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   REAL    NOT NULL,
            role        TEXT    NOT NULL,
            message     TEXT    NOT NULL,
            emotion     TEXT,
            importance  REAL    DEFAULT 0.5,
            tags        TEXT,
            archived    INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_ep_ts    ON episodes(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_ep_imp   ON episodes(importance DESC);
        CREATE INDEX IF NOT EXISTS idx_ep_arch  ON episodes(archived);

        -- Warm tier: summarised episode clusters
        CREATE TABLE IF NOT EXISTS episodes_warm (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  REAL    NOT NULL,
            period_start REAL   NOT NULL,
            period_end   REAL   NOT NULL,
            summary     TEXT    NOT NULL,
            themes      TEXT,
            avg_valence REAL,
            avg_arousal REAL,
            episode_count INTEGER DEFAULT 0
        );

        -- Cold tier: compressed long-term archive
        CREATE TABLE IF NOT EXISTS episodes_cold (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            archived_at REAL    NOT NULL,
            period_start REAL   NOT NULL,
            period_end   REAL   NOT NULL,
            compressed  TEXT    NOT NULL,
            episode_count INTEGER DEFAULT 0
        );

        -- Concept association graph
        CREATE TABLE IF NOT EXISTS associations (
            node_a      TEXT    NOT NULL,
            node_b      TEXT    NOT NULL,
            strength    REAL    NOT NULL DEFAULT 0.3,
            updated_at  REAL    NOT NULL DEFAULT (unixepoch('now')),
            PRIMARY KEY (node_a, node_b)
        );
        CREATE INDEX IF NOT EXISTS idx_assoc_a ON associations(node_a);
        CREATE INDEX IF NOT EXISTS idx_assoc_b ON associations(node_b);

        -- Semantic fact store
        CREATE TABLE IF NOT EXISTS semantic (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            concept     TEXT    NOT NULL,
            relation    TEXT    NOT NULL,
            value       TEXT    NOT NULL,
            confidence  REAL    DEFAULT 0.7,
            updated_at  REAL    NOT NULL DEFAULT (unixepoch('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_sem_concept ON semantic(concept);

        -- Reflections (grounded, autobiographical)
        CREATE TABLE IF NOT EXISTS reflections (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   REAL    NOT NULL,
            kind        TEXT    NOT NULL DEFAULT 'spontaneous',
            text        TEXT    NOT NULL,
            emotion     TEXT,
            grounding   TEXT    -- JSON: {memories:[], emotions:[], contradictions:[]}
        );

        -- Contradiction store
        CREATE TABLE IF NOT EXISTS contradictions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            belief_a            TEXT    NOT NULL,
            belief_b            TEXT    NOT NULL,
            conflict_strength   REAL    DEFAULT 0.5,
            resolution_pressure REAL    DEFAULT 0.15,
            emotional_weight    REAL    DEFAULT 0.3,
            age                 INTEGER DEFAULT 0,
            created_at          REAL    NOT NULL DEFAULT (unixepoch('now'))
        );

        -- Identity life events
        CREATE TABLE IF NOT EXISTS life_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   REAL    NOT NULL,
            event       TEXT    NOT NULL,
            valence     REAL    DEFAULT 0.0,
            importance  REAL    DEFAULT 0.5,
            tags        TEXT
        );

        -- Per-entity relationships
        CREATE TABLE IF NOT EXISTS relationships (
            entity          TEXT PRIMARY KEY,
            trust           REAL DEFAULT 0.5,
            familiarity     REAL DEFAULT 0.0,
            valence         REAL DEFAULT 0.5,
            interactions    INTEGER DEFAULT 0,
            last_seen       REAL
        );

        -- Life narrative chapters
        CREATE TABLE IF NOT EXISTS narrative_chaps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   REAL    NOT NULL,
            title       TEXT    NOT NULL,
            summary     TEXT    NOT NULL,
            stage       TEXT
        );

        -- Open questions (curiosity engine)
        CREATE TABLE IF NOT EXISTS open_questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question    TEXT    NOT NULL UNIQUE,
            importance  REAL    DEFAULT 0.5,
            source      TEXT    DEFAULT 'interaction',
            age_hours   REAL    DEFAULT 0.0,
            recurrence  INTEGER DEFAULT 1,
            created_at  REAL    NOT NULL DEFAULT (unixepoch('now'))
        );

        -- Language patterns
        CREATE TABLE IF NOT EXISTS lang_patterns (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT    NOT NULL,
            phrase      TEXT    NOT NULL,
            strength    REAL    DEFAULT 0.5,
            uses        INTEGER DEFAULT 0,
            reinforced  INTEGER DEFAULT 0,
            weakened    INTEGER DEFAULT 0,
            last_used   REAL    DEFAULT 0,
            UNIQUE(category, phrase)
        );
        CREATE INDEX IF NOT EXISTS idx_lp_cat ON lang_patterns(category);

        -- Concept index (extracted concepts + frequencies)
        CREATE TABLE IF NOT EXISTS concept_index (
            concept     TEXT    PRIMARY KEY,
            frequency   INTEGER DEFAULT 1,
            salience    REAL    DEFAULT 0.5,
            cluster     TEXT,
            first_seen  REAL    NOT NULL DEFAULT (unixepoch('now')),
            last_seen   REAL    NOT NULL DEFAULT (unixepoch('now'))
        );

        -- Session log
        CREATE TABLE IF NOT EXISTS session_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_number  INTEGER NOT NULL,
            started_at      REAL    NOT NULL,
            ended_at        REAL,
            interactions    INTEGER DEFAULT 0,
            stage_at_start  TEXT,
            mood_at_start   TEXT
        );

        -- Schema version
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL
        );
    """)
    db.commit()


# ── Migrations ────────────────────────────────────────────────────────────────

def _run_migrations(db: sqlite3.Connection) -> None:
    """Apply any pending schema migrations."""
    row = db.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current = row[0] if row[0] else 0

    migrations = [
        (1, _migrate_v1_legacy_import),
    ]

    for version, fn in migrations:
        if current < version:
            fn(db)
            db.execute("INSERT INTO schema_version (version, applied_at) VALUES (?,?)",
                       (version, time.time()))
            db.commit()


def _migrate_v1_legacy_import(db: sqlite3.Connection) -> None:
    """
    Import data from legacy fragmented files into unified DB.
    Runs once. Legacy files are renamed to .migrated after import.
    """
    # Migrate identity KV from identity.db
    id_db = LEGACY_DIRS["identity_db"]
    if id_db.exists():
        try:
            old = sqlite3.connect(str(id_db))
            for row in old.execute("SELECT key, value FROM kv"):
                db.execute(
                    "INSERT OR IGNORE INTO kv (key, value, updated_at) VALUES (?,?,?)",
                    (row[0], row[1], time.time())
                )
            for row in old.execute("SELECT timestamp, event, valence, importance, tags FROM life_events"):
                db.execute(
                    "INSERT INTO life_events (timestamp, event, valence, importance, tags) VALUES (?,?,?,?,?)",
                    row
                )
            for row in old.execute("SELECT entity, trust, familiarity, valence, interactions, last_seen FROM relationships"):
                db.execute(
                    "INSERT OR IGNORE INTO relationships VALUES (?,?,?,?,?,?)", row
                )
            for row in old.execute("SELECT timestamp, title, summary, stage FROM narrative_chaps",):
                db.execute(
                    "INSERT INTO narrative_chaps (timestamp, title, summary, stage) VALUES (?,?,?,?)", row
                )
            old.close()
            id_db.rename(str(id_db) + ".migrated")
        except Exception:
            pass

    # Migrate memory.db episodes
    mem_db = LEGACY_DIRS["memory_db"]
    if mem_db.exists():
        try:
            old = sqlite3.connect(str(mem_db))
            for row in old.execute("SELECT timestamp, role, message, emotion, importance, tags FROM memories"):
                ts = row[0]
                try:    ts_f = float(ts)
                except: ts_f = time.time()
                db.execute(
                    "INSERT INTO episodes (timestamp, role, message, emotion, importance, tags) VALUES (?,?,?,?,?,?)",
                    (ts_f, row[1], row[2], row[3], row[4], row[5])
                )
            try:
                for row in old.execute("SELECT timestamp, kind, text, emotion FROM reflections"):
                    db.execute(
                        "INSERT INTO reflections (timestamp, kind, text, emotion) VALUES (?,?,?,?)", row
                    )
            except Exception:
                pass
            old.close()
            mem_db.rename(str(mem_db) + ".migrated")
        except Exception:
            pass

    # Migrate associations JSON
    assoc = LEGACY_DIRS["associations"]
    if assoc.exists():
        try:
            graph = json.loads(assoc.read_text())
            for node_a, edges in graph.items():
                for node_b, strength in edges.items():
                    db.execute(
                        "INSERT OR REPLACE INTO associations (node_a, node_b, strength, updated_at) VALUES (?,?,?,?)",
                        (node_a, node_b, strength, time.time())
                    )
            assoc.rename(str(assoc) + ".migrated")
        except Exception:
            pass

    # Migrate contradictions JSON
    contra = LEGACY_DIRS["contradictions"]
    if contra.exists():
        try:
            items = json.loads(contra.read_text())
            for item in items:
                db.execute("""
                    INSERT INTO contradictions
                        (belief_a, belief_b, conflict_strength, resolution_pressure,
                         emotional_weight, age, created_at)
                    VALUES (?,?,?,?,?,?,?)
                """, (item.get("belief_a",""), item.get("belief_b",""),
                      item.get("conflict_strength", 0.5),
                      item.get("resolution_pressure", 0.15),
                      item.get("emotional_weight", 0.3),
                      item.get("age", 0),
                      item.get("created", time.time())))
            contra.rename(str(contra) + ".migrated")
        except Exception:
            pass

    # Migrate emotion JSON into KV
    emo = LEGACY_DIRS["emotion"]
    if emo.exists():
        try:
            state = json.loads(emo.read_text())
            db.execute(
                "INSERT OR REPLACE INTO kv (key, value, updated_at) VALUES (?,?,?)",
                ("emotion_state", json.dumps(state), time.time())
            )
            emo.rename(str(emo) + ".migrated")
        except Exception:
            pass

    # Migrate other JSON states
    for key, path in [("fatigue_state",  LEGACY_DIRS["fatigue"]),
                      ("world_model",     LEGACY_DIRS["world_model"]),
                      ("curiosity_state", LEGACY_DIRS["curiosity"])]:
        if path.exists():
            try:
                data = json.loads(path.read_text())
                db.execute(
                    "INSERT OR REPLACE INTO kv (key, value, updated_at) VALUES (?,?,?)",
                    (key, json.dumps(data), time.time())
                )
                path.rename(str(path) + ".migrated")
            except Exception:
                pass

    # Migrate language patterns JSON
    lp = LEGACY_DIRS["lang_patterns"]
    if lp.exists():
        try:
            store = json.loads(lp.read_text())
            for category, phrases in store.items():
                for p in phrases:
                    db.execute("""
                        INSERT OR IGNORE INTO lang_patterns
                            (category, phrase, strength, uses, reinforced, weakened, last_used)
                        VALUES (?,?,?,?,?,?,?)
                    """, (category, p.get("phrase",""), p.get("strength", 0.5),
                          p.get("uses", 0), p.get("reinforced", 0),
                          p.get("weakened", 0), p.get("last_used", 0)))
            lp.rename(str(lp) + ".migrated")
        except Exception:
            pass

    # Migrate reflection log
    rlog = LEGACY_DIRS["reflect_log"]
    if rlog.exists():
        try:
            for line in rlog.read_text().strip().split("\n"):
                if not line.strip(): continue
                entry = json.loads(line)
                db.execute(
                    "INSERT INTO reflections (timestamp, kind, text) VALUES (?,?,?)",
                    (time.time(), entry.get("kind","log"), entry.get("text",""))
                )
            rlog.rename(str(rlog) + ".migrated")
        except Exception:
            pass


# ── KV helpers (used by emotion, fatigue, world model, curiosity) ─────────────

def kv_get(key: str, default: Any = None) -> Any:
    with _lock:
        row = get_db().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default


def kv_set(key: str, value: Any) -> None:
    with _lock:
        get_db().execute(
            "INSERT OR REPLACE INTO kv (key, value, updated_at) VALUES (?,?,?)",
            (key, json.dumps(value), time.time())
        )
        get_db().commit()


def kv_all() -> Dict[str, Any]:
    with _lock:
        rows = get_db().execute("SELECT key, value FROM kv").fetchall()
    return {r[0]: json.loads(r[1]) for r in rows}


# ── Episode helpers ────────────────────────────────────────────────────────────

def episode_insert(role: str, message: str, emotion: Optional[dict],
                   importance: float, tags: Optional[List[str]] = None) -> int:
    with tx() as db:
        cur = db.execute(
            "INSERT INTO episodes (timestamp, role, message, emotion, importance, tags) VALUES (?,?,?,?,?,?)",
            (time.time(), role, message, json.dumps(emotion or {}),
             importance, json.dumps(tags or []))
        )
        return cur.lastrowid


def episode_fetch_recent(limit: int = 20, include_archived: bool = False) -> List[dict]:
    with _lock:
        clause = "" if include_archived else "WHERE archived=0"
        rows = get_db().execute(
            f"SELECT * FROM episodes {clause} ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [_ep_row(r) for r in rows]


def episode_fetch_important(limit: int = 10) -> List[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT * FROM episodes WHERE archived=0 ORDER BY importance DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [_ep_row(r) for r in rows]


def episode_search(query: str, limit: int = 5) -> List[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT * FROM episodes WHERE message LIKE ? AND archived=0 "
            "ORDER BY importance DESC, timestamp DESC LIMIT ?",
            (f"%{query}%", limit)
        ).fetchall()
    return [_ep_row(r) for r in rows]


def episode_count(hot_only: bool = True) -> int:
    with _lock:
        clause = "WHERE archived=0" if hot_only else ""
        return get_db().execute(f"SELECT COUNT(*) FROM episodes {clause}").fetchone()[0]


def episode_update_importance(ep_id: int, delta: float) -> None:
    with _lock:
        row = get_db().execute("SELECT importance FROM episodes WHERE id=?", (ep_id,)).fetchone()
        if row:
            new_imp = max(0.0, min(1.0, row[0] + delta))
            get_db().execute("UPDATE episodes SET importance=? WHERE id=?", (new_imp, ep_id))
            get_db().commit()


def _ep_row(row) -> dict:
    d = dict(row)
    for f in ("emotion", "tags"):
        try:    d[f] = json.loads(d.get(f) or ("{}","[]")[f=="tags"])
        except: d[f] = {} if f == "emotion" else []
    return d


# ── Association helpers ────────────────────────────────────────────────────────

def assoc_get(node_a: str, node_b: str) -> float:
    with _lock:
        row = get_db().execute(
            "SELECT strength FROM associations WHERE node_a=? AND node_b=?",
            (node_a, node_b)
        ).fetchone()
    return row[0] if row else 0.0


def assoc_reinforce(node_a: str, node_b: str, delta: float,
                    max_strength: float = 1.0, min_strength: float = 0.01) -> None:
    with _lock:
        cur_ab = assoc_get(node_a, node_b)
        cur_ba = assoc_get(node_b, node_a)
        new_ab = max(min_strength, min(max_strength, cur_ab + delta))
        new_ba = max(min_strength, min(max_strength, cur_ba + delta))
        now    = time.time()
        get_db().execute(
            "INSERT OR REPLACE INTO associations (node_a, node_b, strength, updated_at) VALUES (?,?,?,?)",
            (node_a, node_b, new_ab, now)
        )
        get_db().execute(
            "INSERT OR REPLACE INTO associations (node_a, node_b, strength, updated_at) VALUES (?,?,?,?)",
            (node_b, node_a, new_ba, now)
        )
        get_db().commit()


def assoc_get_neighbours(node: str, limit: int = 10) -> List[Tuple[str, float]]:
    with _lock:
        rows = get_db().execute(
            "SELECT node_b, strength FROM associations WHERE node_a=? ORDER BY strength DESC LIMIT ?",
            (node, limit)
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def assoc_spread(seeds: List[str], hops: int = 2,
                 decay: float = 0.75) -> Dict[str, float]:
    """Spreading activation: M_j(t+1) = Σ M_i(t)·E_ij·D"""
    activation: Dict[str, float] = {s: 1.0 for s in seeds}
    for hop in range(hops):
        new_act: Dict[str, float] = {}
        d = decay ** (hop + 1)
        for node, act in activation.items():
            for neighbour, strength in assoc_get_neighbours(node, limit=15):
                if neighbour not in seeds:
                    spread = act * strength * d
                    new_act[neighbour] = new_act.get(neighbour, 0) + spread
        activation.update(new_act)
    return {k: v for k, v in activation.items() if k not in seeds and v > 0.05}


def assoc_prune(min_strength: float = 0.02) -> int:
    with _lock:
        cur = get_db().execute(
            "DELETE FROM associations WHERE strength < ?", (min_strength,)
        )
        get_db().commit()
    return cur.rowcount


def assoc_graph_sample(limit: int = 15) -> dict:
    with _lock:
        nodes = get_db().execute(
            "SELECT node_a, COUNT(*) as cnt FROM associations GROUP BY node_a ORDER BY cnt DESC LIMIT ?",
            (limit,)
        ).fetchall()
    graph = {}
    for node, _ in nodes:
        neighbours = assoc_get_neighbours(node, limit=5)
        graph[node[0]] = {n: round(s, 3) for n, s in neighbours}
    return {"graph": graph, "node_count": len(graph)}


# ── Contradiction helpers ──────────────────────────────────────────────────────

def contra_upsert(belief_a: str, belief_b: str,
                  conflict_strength: float, emotional_weight: float) -> None:
    with _lock:
        row = get_db().execute(
            "SELECT id, conflict_strength, age FROM contradictions "
            "WHERE belief_a=? AND belief_b=?", (belief_a, belief_b)
        ).fetchone()
        if row:
            get_db().execute(
                "UPDATE contradictions SET conflict_strength=?, age=? WHERE id=?",
                (min(1.0, row[1] + 0.05), row[2] + 1, row[0])
            )
        else:
            get_db().execute(
                "INSERT INTO contradictions (belief_a, belief_b, conflict_strength, "
                "resolution_pressure, emotional_weight, created_at) VALUES (?,?,?,?,?,?)",
                (belief_a, belief_b, conflict_strength,
                 conflict_strength * 0.3, emotional_weight, time.time())
            )
        get_db().commit()


def contra_age_all() -> None:
    with _lock:
        db = get_db()
        db.execute("""
            UPDATE contradictions
            SET age = age + 1,
                resolution_pressure = MIN(1.0, resolution_pressure + 0.02 * conflict_strength)
        """)
        db.execute("DELETE FROM contradictions WHERE age > 50 AND conflict_strength < 0.2")
        db.commit()


def contra_fetch(limit: int = 5) -> List[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT * FROM contradictions ORDER BY resolution_pressure DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Reflection helpers ────────────────────────────────────────────────────────

def reflection_insert(text: str, kind: str, emotion: Optional[dict],
                      grounding: Optional[dict] = None) -> None:
    with tx() as db:
        db.execute(
            "INSERT INTO reflections (timestamp, kind, text, emotion, grounding) VALUES (?,?,?,?,?)",
            (time.time(), kind, text,
             json.dumps(emotion or {}), json.dumps(grounding or {}))
        )


def reflection_fetch(limit: int = 20) -> List[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT * FROM reflections ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for f in ("emotion", "grounding"):
            try:    d[f] = json.loads(d.get(f) or "{}")
            except: d[f] = {}
        result.append(d)
    return result


# ── Open question helpers ─────────────────────────────────────────────────────

def question_upsert(question: str, importance: float, source: str) -> None:
    with _lock:
        row = get_db().execute(
            "SELECT id, importance, recurrence FROM open_questions WHERE question=?",
            (question,)
        ).fetchone()
        if row:
            get_db().execute(
                "UPDATE open_questions SET importance=?, recurrence=? WHERE id=?",
                (min(1.0, row[1] + 0.05), row[2] + 1, row[0])
            )
        else:
            get_db().execute(
                "INSERT INTO open_questions (question, importance, source, created_at) VALUES (?,?,?,?)",
                (question, importance, source, time.time())
            )
        get_db().commit()


def question_fetch(limit: int = 5) -> List[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT * FROM open_questions ORDER BY importance DESC, recurrence DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def question_age(hours: float) -> None:
    with _lock:
        get_db().execute(
            "UPDATE open_questions SET age_hours = age_hours + ?, importance = MAX(0.05, importance - 0.001 * ?)",
            (hours, hours)
        )
        get_db().execute("DELETE FROM open_questions WHERE importance < 0.06 AND age_hours > 48")
        get_db().commit()


# ── Language pattern helpers ───────────────────────────────────────────────────

def pattern_seed(seeds: Dict[str, List[Tuple[str, float]]]) -> None:
    """Populate lang_patterns if empty."""
    with _lock:
        count = get_db().execute("SELECT COUNT(*) FROM lang_patterns").fetchone()[0]
        if count > 0:
            return
        for category, phrases in seeds.items():
            for phrase, strength in phrases:
                get_db().execute(
                    "INSERT OR IGNORE INTO lang_patterns (category, phrase, strength) VALUES (?,?,?)",
                    (category, phrase, strength)
                )
        get_db().commit()


def pattern_select(category: str) -> Optional[str]:
    with _lock:
        rows = get_db().execute(
            "SELECT phrase, strength FROM lang_patterns WHERE category=?", (category,)
        ).fetchall()
    if not rows: return None
    import random
    weights = [max(0.05, r[1]) for r in rows]
    total   = sum(weights)
    r_val   = random.random() * total
    cumul   = 0.0
    for (phrase, _), w in zip(rows, weights):
        cumul += w
        if r_val <= cumul:
            # Record use
            with _lock:
                get_db().execute(
                    "UPDATE lang_patterns SET uses=uses+1, last_used=? WHERE category=? AND phrase=?",
                    (time.time(), category, phrase)
                )
                get_db().commit()
            return phrase
    return rows[0][0] if rows else None


def pattern_reinforce(category: str, phrase: str, delta: float) -> None:
    with _lock:
        get_db().execute(
            "UPDATE lang_patterns SET strength=MIN(2.0, strength+?), reinforced=reinforced+1 "
            "WHERE category=? AND phrase=?",
            (delta, category, phrase)
        )
        get_db().commit()


def pattern_weaken(category: str, phrase: str, delta: float) -> None:
    with _lock:
        get_db().execute(
            "UPDATE lang_patterns SET strength=MAX(0.05, strength-?), weakened=weakened+1 "
            "WHERE category=? AND phrase=?",
            (delta, category, phrase)
        )
        get_db().commit()


def pattern_learn(category: str, phrase: str, strength: float = 0.3) -> None:
    with _lock:
        get_db().execute(
            "INSERT OR IGNORE INTO lang_patterns (category, phrase, strength, last_used) VALUES (?,?,?,?)",
            (category, phrase, strength, time.time())
        )
        get_db().commit()


def pattern_decay(hours_idle: float = 1.0) -> None:
    with _lock:
        get_db().execute(
            "UPDATE lang_patterns SET strength=MAX(0.05, strength - 0.005 * ?) WHERE uses > 0",
            (hours_idle,)
        )
        get_db().execute("DELETE FROM lang_patterns WHERE strength < 0.04 AND uses > 3")
        get_db().commit()


def pattern_stats() -> Dict[str, dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT category, COUNT(*) as cnt, AVG(strength) as avg_str, "
            "MAX(phrase) as sample FROM lang_patterns GROUP BY category"
        ).fetchall()
    return {r[0]: {"count": r[1], "avg_strength": round(r[2], 3), "sample": r[3][:50]} for r in rows}


def pattern_strongest(category: str, n: int = 3) -> List[str]:
    with _lock:
        rows = get_db().execute(
            "SELECT phrase FROM lang_patterns WHERE category=? ORDER BY strength DESC LIMIT ?",
            (category, n)
        ).fetchall()
    return [r[0] for r in rows]


# ── Concept index helpers ──────────────────────────────────────────────────────

def concept_record(concept: str, salience_boost: float = 0.0) -> None:
    with _lock:
        now = time.time()
        row = get_db().execute("SELECT frequency, salience FROM concept_index WHERE concept=?",
                               (concept,)).fetchone()
        if row:
            get_db().execute(
                "UPDATE concept_index SET frequency=frequency+1, salience=MIN(1.0, salience+?), last_seen=? WHERE concept=?",
                (salience_boost, now, concept)
            )
        else:
            get_db().execute(
                "INSERT INTO concept_index (concept, frequency, salience, first_seen, last_seen) VALUES (?,1,?,?,?)",
                (concept, 0.3 + salience_boost, now, now)
            )
        get_db().commit()


def concept_top(limit: int = 20) -> List[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT concept, frequency, salience, cluster FROM concept_index "
            "ORDER BY frequency * salience DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"concept": r[0], "frequency": r[1], "salience": r[2], "cluster": r[3]} for r in rows]


# ── Session log ───────────────────────────────────────────────────────────────

def session_begin(session_number: int, stage: str, mood: str) -> int:
    with tx() as db:
        cur = db.execute(
            "INSERT INTO session_log (session_number, started_at, stage_at_start, mood_at_start) VALUES (?,?,?,?)",
            (session_number, time.time(), stage, mood)
        )
        return cur.lastrowid


def session_end(session_id: int, interactions: int) -> None:
    with _lock:
        get_db().execute(
            "UPDATE session_log SET ended_at=?, interactions=? WHERE id=?",
            (time.time(), interactions, session_id)
        )
        get_db().commit()


# ── Health / diagnostics ──────────────────────────────────────────────────────

def db_stats() -> dict:
    with _lock:
        db = get_db()
        return {
            "episodes_hot":    db.execute("SELECT COUNT(*) FROM episodes WHERE archived=0").fetchone()[0],
            "episodes_warm":   db.execute("SELECT COUNT(*) FROM episodes_warm").fetchone()[0],
            "episodes_cold":   db.execute("SELECT COUNT(*) FROM episodes_cold").fetchone()[0],
            "associations":    db.execute("SELECT COUNT(*) FROM associations").fetchone()[0],
            "contradictions":  db.execute("SELECT COUNT(*) FROM contradictions").fetchone()[0],
            "reflections":     db.execute("SELECT COUNT(*) FROM reflections").fetchone()[0],
            "open_questions":  db.execute("SELECT COUNT(*) FROM open_questions").fetchone()[0],
            "lang_patterns":   db.execute("SELECT COUNT(*) FROM lang_patterns").fetchone()[0],
            "concepts":        db.execute("SELECT COUNT(*) FROM concept_index").fetchone()[0],
            "db_path":         str(DB_PATH),
        }
