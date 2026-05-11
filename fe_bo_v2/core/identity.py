"""
Identity management for FeBo - maintains self-concept, life events, and narrative memory.
Persists to SQLite and Chroma vector database.
"""

import sqlite3
import json
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import chromadb
except ImportError:
    chromadb = None

from core.logging_config import get_logger

logger = get_logger("identity")

# Ensure BIRTH_TIME_FILE is a Path
BIRTH_PATH = Path("memory/birth_time.txt")


class Identity:
    """Manages FeBo's identity, beliefs, and life narrative."""

    def __init__(self) -> None:
        """Initialize identity database and vector stores."""
        self._db_lock = threading.RLock()
        self._db_path = Path("memory/identity.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.db = sqlite3.connect(str(self._db_path), check_same_thread=False, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to connect to identity database: {e}")
            raise

        self._init_db()

        # Initialize Chroma if available
        self.chroma = None
        self.narrative_collection = None
        if chromadb:
            try:
                chroma_path = Path("memory/chroma")
                chroma_path.mkdir(parents=True, exist_ok=True)
                self.chroma = chromadb.PersistentClient(path=str(chroma_path))
                self.narrative_collection = self.chroma.get_or_create_collection("narrative")
            except Exception as e:
                logger.warning(f"Failed to initialize Chroma: {e}. Continuing without vector store.")
        else:
            logger.debug("Chroma not available, vector storage disabled")

        self._init_birth()

    def _init_db(self) -> None:
        """Initialize database schema if needed."""
        with self._db_lock:
            try:
                self.db.execute(
                    "CREATE TABLE IF NOT EXISTS identity (key TEXT PRIMARY KEY, value TEXT)"
                )
                self.db.execute(
                    "CREATE TABLE IF NOT EXISTS life_events "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL, event TEXT, emotion_valence REAL)"
                )
                self.db.commit()
            except Exception as e:
                logger.error(f"Database initialization error: {e}")
                raise

    def _init_birth(self) -> None:
        """Initialize birth time if not already set."""
        if not self.get("birth_time"):
            try:
                if BIRTH_PATH.exists():
                    with open(BIRTH_PATH, "r") as f:
                        birth = float(f.read().strip())
                else:
                    birth = time.time()
                    BIRTH_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(BIRTH_PATH, "w") as f:
                        f.write(str(birth))
                self.set("birth_time", birth)
                self.set("name", "FeBo")
                self.set("creator", "Emmanuel")
                self.add_life_event("I was born.", emotion_valence=0.8)
                logger.info("Identity initialized")
            except Exception as e:
                logger.error(f"Failed to initialize birth time: {e}")
                raise

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve identity attribute.

        Args:
            key: Attribute key
            default: Default value if key not found

        Returns:
            Attribute value or default
        """
        with self._db_lock:
            try:
                cur = self.db.execute("SELECT value FROM identity WHERE key = ?", (key,))
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
                return default
            except Exception as e:
                logger.error(f"Error getting identity key '{key}': {e}")
                return default

    def set(self, key: str, value: Any) -> None:
        """
        Set identity attribute.

        Args:
            key: Attribute key
            value: Attribute value to store
        """
        with self._db_lock:
            try:
                self.db.execute(
                    "REPLACE INTO identity (key, value) VALUES (?, ?)",
                    (key, json.dumps(value))
                )
                self.db.commit()
            except Exception as e:
                logger.error(f"Error setting identity key '{key}': {e}")
                raise

    def add_life_event(self, event: str, emotion_valence: float = 0.0) -> None:
        """
        Record a life event in memory.

        Args:
            event: Description of the event
            emotion_valence: Emotional valence (-1 to 1)
        """
        ts = time.time()
        with self._db_lock:
            try:
                self.db.execute(
                    "INSERT INTO life_events (timestamp, event, emotion_valence) VALUES (?, ?, ?)",
                    (ts, event, emotion_valence)
                )
                self.db.commit()
            except Exception as e:
                logger.error(f"Error recording life event: {e}")

        # Also store in vector database if available
        if self.narrative_collection:
            try:
                self.narrative_collection.add(
                    documents=[event],
                    metadatas=[{"timestamp": ts, "valence": emotion_valence}],
                    ids=[f"event_{ts}"]
                )
            except Exception as e:
                logger.warning(f"Failed to store event in vector memory: {e}")

    def get_recent_events(self, limit: int = 10) -> List[Tuple[float, str, float]]:
        """
        Get recent life events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of (timestamp, event, emotion_valence) tuples
        """
        with self._db_lock:
            try:
                cur = self.db.execute(
                    "SELECT timestamp, event, emotion_valence FROM life_events "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
                return cur.fetchall()
            except Exception as e:
                logger.error(f"Error retrieving recent events: {e}")
                return []

    def get_self_summary(self) -> str:
        """
        Get a text summary of identity.

        Returns:
            Self-summary string
        """
        try:
            name = self.get("name", "FeBo")
            birth = self.get("birth_time", time.time())
            age_seconds = time.time() - birth
            age_hours = age_seconds / 3600
            trust = self.get("trust_in_creator", 0.9)
            return (
                f"I am {name}, born {age_hours:.1f} hours ago. "
                f"Trust in creator: {trust:.2f}."
            )
        except Exception as e:
            logger.error(f"Error generating self summary: {e}")
            return "I am FeBo, recently initialized."

    def close(self) -> None:
        """Close database connection gracefully."""
        try:
            with self._db_lock:
                if self.db:
                    self.db.close()
                    logger.debug("Identity database closed")
        except Exception as e:
            logger.error(f"Error closing identity database: {e}")


# Global identity instance
try:
    identity = Identity()
except Exception as e:
    logger.critical(f"Failed to initialize global identity: {e}")
    raise

