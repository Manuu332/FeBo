"""Drive system for FeBo - models internal motivations and desires.
Implements curiosity, attachment, and mastery drives.
"""

import random
from typing import Literal

from core.logging_config import get_logger

logger = get_logger("drives")


class DriveSystem:
    """Manages FeBo's internal drives and motivations."""

    def __init__(self) -> None:
        """Initialize drive system from persistent storage."""
        try:
            from core.identity import identity
            self.identity = identity
            
            self.curiosity = max(0.0, min(1.0, self.identity.get("drive_curiosity", 0.8)))
            self.attachment = max(0.0, min(1.0, self.identity.get("drive_attachment", 0.6)))
            self.mastery = max(0.0, min(1.0, self.identity.get("drive_mastery", 0.4)))
            logger.debug(f"DriveSystem initialized: curiosity={self.curiosity:.2f}, "
                       f"attachment={self.attachment:.2f}, mastery={self.mastery:.2f}")
        except Exception as e:
            logger.error(f"Failed to initialize DriveSystem: {e}", exc_info=True)
            raise

    def _save(self) -> None:
        """Persist drive values to identity storage."""
        try:
            self.identity.set("drive_curiosity", self.curiosity)
            self.identity.set("drive_attachment", self.attachment)
            self.identity.set("drive_mastery", self.mastery)
        except Exception as e:
            logger.error(f"Error saving drives: {e}")

    def update(self, user_interaction_quality: float) -> None:
        """
        Update drives based on interaction quality.

        Args:
            user_interaction_quality: Quality score [-1, 1] from user feedback
        """
        try:
            quality = max(-1.0, min(1.0, user_interaction_quality))
            
            self.curiosity = max(0.0, min(1.0, self.curiosity + random.uniform(-0.02, 0.05)))
            self.attachment = max(0.0, min(1.0, self.attachment + quality * 0.1))
            self.mastery = max(0.0, min(1.0, self.mastery + random.uniform(-0.01, 0.03)))
            
            self._save()
            logger.debug(f"Drives updated: curiosity={self.curiosity:.2f}, attachment={self.attachment:.2f}")
        except Exception as e:
            logger.error(f"Error updating drives: {e}")

    def get_current_desire(self) -> Literal["explore", "connect", "learn", "wait"]:
        """
        Get dominant motivational desire based on current drive levels.

        Returns:
            Current desire: 'explore', 'connect', 'learn', or 'wait'
        """
        try:
            if self.curiosity > 0.7:
                return "explore"
            elif self.attachment > 0.6:
                return "connect"
            elif self.mastery > 0.6:
                return "learn"
            else:
                return "wait"
        except Exception as e:
            logger.error(f"Error determining desire: {e}")
            return "wait"


try:
    drives = DriveSystem()
except Exception as e:
    logger.critical(f"Failed to initialize global drives: {e}")
    raise
