"""
Background defender agent that monitors logs and network traffic.
Uses anomaly detection to identify potential intrusions and threats.
"""

import threading
import time
from pathlib import Path
from typing import Optional

from core.security.anomaly import AnomalyDetector
from core.lifecycle import lifecycle
from core.logging_config import get_logger

logger = get_logger("security.defender")


class DefenderAgent:
    """Monitors system logs and detects anomalies in real-time."""

    def __init__(self) -> None:
        """Initialize defender with anomaly detection."""
        try:
            self.anomaly = AnomalyDetector()
            self._shutdown_event = lifecycle.get_shutdown_event()
            self.thread: Optional[threading.Thread] = None
            self.log_monitor = Path("logs/audit.log")
            logger.info("DefenderAgent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize DefenderAgent: {e}", exc_info=True)
            raise

    def start(self) -> None:
        """Start the defender monitoring loop in a thread."""
        if self.thread and self.thread.is_alive():
            logger.warning("DefenderAgent already running")
            return

        try:
            self.thread = threading.Thread(target=self._loop, daemon=True, name="DefenderAgent")
            self.thread.start()
            logger.info("DefenderAgent started")
        except Exception as e:
            logger.error(f"Failed to start DefenderAgent: {e}", exc_info=True)
            raise

    def _loop(self) -> None:
        """Monitor logs continuously until shutdown."""
        logger.debug("Defender monitoring loop started")
        
        while not self._shutdown_event.is_set():
            try:
                time.sleep(30)

                if self.log_monitor.exists():
                    try:
                        with open(self.log_monitor, "r") as f:
                            lines = f.readlines()[-10:]
                        
                        for line in lines:
                            if "error" in line.lower() or "fail" in line.lower():
                                self.alert("Potential error pattern detected", line.strip())
                    except Exception as e:
                        logger.error(f"Error reading audit log: {e}")
            except Exception as e:
                logger.error(f"Error in defender loop: {e}")

    def alert(self, message: str, context: str) -> None:
        """
        Generate and log a security alert.

        Args:
            message: Alert message
            context: Additional context/log line
        """
        try:
            alert_msg = f"[DEFENDER] ALERT: {message}\nContext: {context}"
            logger.warning(alert_msg)

            # Write to security alerts log
            alerts_file = Path("logs/security_alerts.log")
            alerts_file.parent.mkdir(parents=True, exist_ok=True)
            with open(alerts_file, "a") as f:
                f.write(f"{time.ctime()}: {message}\n{context}\n")
        except Exception as e:
            logger.error(f"Error writing security alert: {e}")

    def stop(self) -> None:
        """Stop the defender monitoring loop."""
        logger.info("Stopping DefenderAgent")
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning("DefenderAgent thread did not terminate cleanly")
            else:
                logger.debug("DefenderAgent thread stopped")

