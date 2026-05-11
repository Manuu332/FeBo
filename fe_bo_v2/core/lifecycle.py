"""
Lifecycle management for FeBo - handles initialization, shutdown, and resource cleanup.
Implements singleton pattern for application state and graceful shutdown.
"""

import logging
import threading
import signal
import sys
from typing import Callable, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manages application startup, shutdown, and resource cleanup."""

    _instance: Optional["LifecycleManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "LifecycleManager":
        """Implement singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize lifecycle manager if not already done."""
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.shutdown_handlers: List[Callable[[], None]] = []
        self.startup_handlers: List[Callable[[], None]] = []
        self.is_running = False
        self._shutdown_event = threading.Event()
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup handlers for SIGINT and SIGTERM."""
        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def register_startup(self, handler: Callable[[], None]) -> None:
        """Register a function to be called during startup."""
        self.startup_handlers.append(handler)
        logger.debug(f"Registered startup handler: {handler.__name__}")

    def register_shutdown(self, handler: Callable[[], None]) -> None:
        """Register a function to be called during shutdown."""
        self.shutdown_handlers.append(handler)
        logger.debug(f"Registered shutdown handler: {handler.__name__}")

    def startup(self) -> None:
        """Execute all startup handlers."""
        logger.info("Starting FeBo application lifecycle...")
        self.is_running = True
        self._shutdown_event.clear()
        
        for handler in self.startup_handlers:
            try:
                handler()
                logger.debug(f"Startup handler executed: {handler.__name__}")
            except Exception as e:
                logger.error(f"Error in startup handler {handler.__name__}: {e}", exc_info=True)
                raise

        logger.info("Application startup complete")

    def shutdown(self) -> None:
        """Execute all shutdown handlers in reverse order."""
        if not self.is_running:
            logger.warning("Shutdown called but application not running")
            return

        logger.info("Initiating graceful shutdown...")
        self.is_running = False
        self._shutdown_event.set()

        # Execute shutdown handlers in reverse order (LIFO)
        for handler in reversed(self.shutdown_handlers):
            try:
                logger.debug(f"Executing shutdown handler: {handler.__name__}")
                handler()
            except Exception as e:
                logger.error(f"Error in shutdown handler {handler.__name__}: {e}", exc_info=True)

        logger.info("Application shutdown complete")

    def get_shutdown_event(self) -> threading.Event:
        """Get the shutdown event for threads to monitor."""
        return self._shutdown_event

    def wait_shutdown(self) -> None:
        """Block until shutdown signal received."""
        self._shutdown_event.wait()


# Global lifecycle manager instance
lifecycle = LifecycleManager()
