"""Attention mechanism for conscious focus allocation.
Implements a simple focus system for the global workspace.
"""

from typing import Any, Dict, Optional
from core.logging_config import get_logger

logger = get_logger("consciousness.attention")


class AttentionMechanism:
    """Manages attentional focus in the global workspace."""

    def __init__(self) -> None:
        """Initialize attention mechanism."""
        self.focus: Optional[Any] = None
        logger.debug("AttentionMechanism initialized")

    def focus_on(self, contents: Dict[str, Any]) -> Optional[Any]:
        """
        Direct attention to relevant content.

        Args:
            contents: Workspace contents dictionary

        Returns:
            Focused content or None
        """
        try:
            if isinstance(contents, dict):
                if "user_input" in contents:
                    self.focus = contents["user_input"]
                elif "alert" in contents:
                    self.focus = contents["alert"]
                elif "important" in contents:
                    self.focus = contents["important"]
                else:
                    self.focus = next(iter(contents.values())) if contents else None
            return self.focus
        except Exception as e:
            logger.error(f"Error in attention focus: {e}")
            return None

    def get_focus(self) -> Optional[Any]:
        """
        Get current focus of attention.

        Returns:
            Currently focused content
        """
        return self.focus
