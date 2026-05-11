"""Episodic memory - stores experiences and interactions.
Maintains history of user interactions and responses.
"""

import sqlite3
import time
import threading
from pathlib import Path
from typing import List, Tuple

from core.logging_config import get_logger

logger = get_logger("memory.episodic")

EPISODE_DB = Path("memory/episodes.db")
EPISODE_DB.parent.mkdir(parents=True, exist_ok=True)


class EpisodicMemory:
    """Stores and retrieves episodic memories of interactions."""

    def __init__(self) -> None:
        """Initialize episodic memory database."""
        try:
            self._lock = threading.RLock()
            self.db = sqlite3.connect(str(EPISODE_DB), check_same_thread=False, timeout=10.0)
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS episodes "
                "(id INTEGER PRIMARY KEY, timestamp REAL, user TEXT, response TEXT, emotion_vals TEXT)"
            )
            self.db.commit()
            logger.debug("EpisodicMemory initialized")
        except Exception as e:
            logger.error(f"Failed to initialize episodic memory: {e}", exc_info=True)
            raise

    def store(self, user_input: str, response: str, emotion_vals: List[float]) -> None:
        """
        Store an interaction episode.

        Args:
            user_input: User's input text
            response: Agent's response text
            emotion_vals: Associated emotion values
        """
        try:
            with self._lock:
                self.db.execute(
                    "INSERT INTO episodes (timestamp, user, response, emotion_vals) VALUES (?, ?, ?, ?)",
                    (time.time(), user_input, response, str(emotion_vals))
                )
                self.db.commit()
                logger.debug("Episode stored")
        except Exception as e:
            logger.error(f"Error storing episode: {e}")

    def recent(self, limit: int = 10) -> List[Tuple[str, str]]:
        """
        Retrieve recent episodes.

        Args:
            limit: Maximum number of episodes to retrieve

        Returns:
            List of (user_input, response) tuples
        """
        try:
            with self._lock:
                cur = self.db.execute(
                    "SELECT user, response FROM episodes ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Error retrieving episodes: {e}")
            return []

    def close(self) -> None:
        """Close database connection."""
        try:
            with self._lock:
                if self.db:
                    self.db.close()
                    logger.debug("Episodic memory database closed")
        except Exception as e:
            logger.error(f"Error closing episodic memory: {e}")


# Global episodic memory instance
try:
    episodic = EpisodicMemory()
except Exception as e:
    logger.critical(f"Failed to initialize global episodic memory: {e}")
    raise
