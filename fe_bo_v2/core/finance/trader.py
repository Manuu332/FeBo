"""Paper trading system for safe financial strategy testing.
Simulates trading without using real money.
"""

import time
import random
import threading
from collections import deque
from typing import Dict, Optional, List, Any, Tuple

from core.lifecycle import lifecycle
from core.logging_config import get_logger

logger = get_logger("finance.trader")


class PaperTrader:
    """Paper trading system for testing trading strategies."""

    def __init__(self, initial_balance: float = 100000) -> None:
        """
        Initialize paper trader.

        Args:
            initial_balance: Starting virtual capital
        """
        try:
            self.balance = initial_balance
            self.initial_balance = initial_balance
            self.positions: Dict[str, float] = {}
            self.history: deque = deque(maxlen=100)
            self.sentiment: Optional[Dict[str, float]] = None
            self._shutdown_event = lifecycle.get_shutdown_event()
            self.thread: Optional[threading.Thread] = None
            logger.info(f"PaperTrader initialized with balance: ${initial_balance:,.2f}")
        except Exception as e:
            logger.error(f"Failed to initialize PaperTrader: {e}", exc_info=True)
            raise

    def start(self) -> None:
        """Start automated trading loop."""
        if self.thread and self.thread.is_alive():
            logger.warning("PaperTrader already running")
            return

        try:
            self.thread = threading.Thread(target=self._loop, daemon=True, name="PaperTrader")
            self.thread.start()
            logger.info("PaperTrader started")
        except Exception as e:
            logger.error(f"Failed to start PaperTrader: {e}", exc_info=True)
            raise

    def _loop(self) -> None:
        """Trading loop - executes trades periodically."""
        logger.debug("Trading loop started")
        
        while not self._shutdown_event.is_set():
            try:
                time.sleep(3600)  # Every hour
                self.simulate_trade()
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")

    def update_sentiment(self, sentiment_scores: Dict[str, float]) -> None:
        """
        Update sentiment data for trading decisions.

        Args:
            sentiment_scores: Sentiment analysis results
        """
        try:
            self.sentiment = sentiment_scores
            logger.debug(f"Sentiment updated: {sentiment_scores}")
        except Exception as e:
            logger.error(f"Error updating sentiment: {e}")

    def simulate_trade(self) -> None:
        """Execute simulated trade based on sentiment."""
        try:
            if not self.sentiment:
                logger.debug("No sentiment data for trading")
                return

            positive = self.sentiment.get("positive", 0)
            negative = self.sentiment.get("negative", 0)

            if positive > 0.6 and "stock" not in self.positions:
                # BUY
                amount = self.balance * 0.1
                price = random.uniform(100, 200)
                shares = amount / price
                self.positions["stock"] = shares
                self.balance -= amount
                self.history.append(("BUY", price, shares, time.time()))
                logger.info(f"Trade: BUY {shares:.2f} shares @ ${price:.2f}")
            elif negative > 0.6 and "stock" in self.positions:
                # SELL
                price = random.uniform(90, 210)
                proceeds = self.positions["stock"] * price
                self.balance += proceeds
                self.history.append(("SELL", price, self.positions["stock"], time.time()))
                logger.info(f"Trade: SELL {self.positions['stock']:.2f} shares @ ${price:.2f}")
                del self.positions["stock"]
        except Exception as e:
            logger.error(f"Error in simulate_trade: {e}")

    def summary(self) -> str:
        """
        Get trading summary.

        Returns:
            Summary string
        """
        try:
            total_value = self.balance
            for symbol, shares in self.positions.items():
                total_value += shares * random.uniform(100, 200)
            
            profit = total_value - self.initial_balance
            profit_pct = (profit / self.initial_balance) * 100 if self.initial_balance else 0
            
            recent = list(self.history)[-3:] if self.history else []
            return (
                f"Trading Summary:\n"
                f"  Balance: ${self.balance:.2f}\n"
                f"  Total Value: ${total_value:.2f}\n"
                f"  P&L: ${profit:.2f} ({profit_pct:.1f}%)\n"
                f"  Positions: {self.positions}\n"
                f"  Recent Trades: {recent}"
            )
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Error generating trading summary"

    def stop(self) -> None:
        """Stop trading loop gracefully."""
        logger.info("Stopping PaperTrader")
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning("PaperTrader thread did not terminate cleanly")
            else:
                logger.debug("PaperTrader thread stopped")
