"""Global workspace (blackboard architecture) for conscious content.
Centralizes shared information accessible to all cognitive modules.
"""

from typing import Any, Dict
import threading
from core.logging_config import get_logger

logger = get_logger("consciousness.blackboard")


class GlobalWorkspace:
    """Implements global workspace for conscious information sharing."""

    def __init__(self) -> None:
        """Initialize global workspace."""
        self.contents: Dict[str, Any] = {}
        self._lock = threading.RLock()
        logger.debug("GlobalWorkspace initialized")

    def publish(self, key: str, value: Any) -> None:
        """
        Publish content to global workspace.

        Args:
            key: Content key/identifier
            value: Content value
        """
        try:
            with self._lock:
                self.contents[key] = value
                logger.debug(f"Published to workspace: {key}")
        except Exception as e:
            logger.error(f"Error publishing to workspace: {e}")

    def get_contents(self) -> Dict[str, Any]:
        """
        Get all workspace contents (thread-safe).

        Returns:
            Dictionary of workspace contents
        """
        try:
            with self._lock:
                return dict(self.contents)
        except Exception as e:
            logger.error(f"Error reading workspace: {e}")
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get specific workspace content.

        Args:
            key: Content key
            default: Default value if not found

        Returns:
            Content value or default
        """
        try:
            with self._lock:
                return self.contents.get(key, default)
        except Exception as e:
            logger.error(f"Error retrieving workspace content: {e}")
            return default

    def clear(self) -> None:
        """Clear all workspace contents."""
        try:
            with self._lock:
                self.contents.clear()
                logger.debug("Workspace cleared")
        except Exception as e:
            logger.error(f"Error clearing workspace: {e}")
