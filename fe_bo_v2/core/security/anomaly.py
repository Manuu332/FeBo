"""
Real-time anomaly detection using lightweight autoencoder.
Analyzes network flows and system metrics for intrusion detection.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
from typing import List, Optional

from core.logging_config import get_logger

logger = get_logger("security.anomaly")


class Autoencoder(nn.Module):
    """Simple autoencoder for anomaly detection."""

    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        """
        Initialize autoencoder architecture.

        Args:
            input_dim: Input feature dimension
            hidden_dim: Hidden layer dimension
        """
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU()
        )
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, input_dim),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through encoder-decoder."""
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


class AnomalyDetector:
    """Detects anomalies using reconstruction error from autoencoder."""

    def __init__(self, input_dim: int = 10, hidden_dim: int = 5, buffer_size: int = 1000) -> None:
        """
        Initialize anomaly detector.

        Args:
            input_dim: Feature vector dimension
            hidden_dim: Hidden layer size
            buffer_size: Size of training buffer
        """
        try:
            device_str = "cuda" if torch.cuda.is_available() else "cpu"
            self.device = torch.device(device_str)
            logger.info(f"Anomaly detector using device: {self.device}")
            
            self.model = Autoencoder(input_dim, hidden_dim).to(self.device)
            self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
            self.buffer: deque = deque(maxlen=buffer_size)
            self.threshold: Optional[float] = None
            self.trained = False
            logger.debug(f"AnomalyDetector initialized: input_dim={input_dim}, hidden_dim={hidden_dim}")
        except Exception as e:
            logger.error(f"Failed to initialize anomaly detector: {e}", exc_info=True)
            raise

    def update_threshold(self, percent: float = 0.99) -> None:
        """
        Update anomaly threshold based on buffer data.

        Args:
            percent: Percentile threshold (higher = more sensitive)
        """
        try:
            if len(self.buffer) < 100:
                logger.debug(f"Insufficient data for threshold update ({len(self.buffer)} samples)")
                return

            errors = [
                self._reconstruction_error(torch.tensor(x, dtype=torch.float32))
                for x in self.buffer
            ]
            self.threshold = np.percentile(errors, percent * 100)
            logger.debug(f"Anomaly threshold updated to {self.threshold:.4f}")
        except Exception as e:
            logger.error(f"Error updating threshold: {e}")

    def _reconstruction_error(self, x: torch.Tensor) -> float:
        """
        Calculate reconstruction error for sample.

        Args:
            x: Input sample tensor

        Returns:
            Reconstruction error value
        """
        try:
            with torch.no_grad():
                x = x.to(self.device).unsqueeze(0)
                reconstructed = self.model(x)
                loss = nn.MSELoss()(reconstructed, x)
            return loss.item()
        except Exception as e:
            logger.error(f"Error computing reconstruction error: {e}")
            return 0.0

    def train_step(self, batch: List[List[float]]) -> float:
        """
        Train model on a batch of data.

        Args:
            batch: Batch of feature vectors

        Returns:
            Training loss value
        """
        try:
            batch_tensor = torch.tensor(batch, dtype=torch.float32).to(self.device)
            self.optimizer.zero_grad()
            reconstructed = self.model(batch_tensor)
            loss = nn.MSELoss()(reconstructed, batch_tensor)
            loss.backward()
            self.optimizer.step()
            self.trained = True
            return loss.item()
        except Exception as e:
            logger.error(f"Error in training step: {e}")
            return 0.0

    def predict(self, sample: List[float]) -> bool:
        """
        Predict if sample is anomalous.

        Args:
            sample: Feature vector to test

        Returns:
            True if anomalous, False if normal
        """
        try:
            if not self.trained:
                return False

            error = self._reconstruction_error(torch.tensor(sample, dtype=torch.float32))
            
            if self.threshold is None:
                return error > np.percentile([0.1, 0.2, 0.3], 99)  # fallback threshold
            
            return error > self.threshold
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            return False

