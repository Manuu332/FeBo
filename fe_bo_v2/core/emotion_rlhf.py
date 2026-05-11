"""Emotion modeling with RLHF (Reinforcement Learning from Human Feedback).
Maintains and learns emotional states based on user interactions.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from typing import List

from core.logging_config import get_logger

logger = get_logger("emotion_rlhf")

MODEL_PATH = Path("memory/emotion_model.pt")
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)


class EmotionNet(nn.Module):
    """Neural network for emotion prediction and regulation."""

    def __init__(self, input_dim: int = 10, hidden: int = 32, output_dim: int = 6) -> None:
        """
        Initialize emotion network.

        Args:
            input_dim: Input feature dimension
            hidden: Hidden layer size
            output_dim: Output emotion dimensions
        """
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, output_dim),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through emotion network."""
        return self.net(x)


class EmotionRLHF:
    """Reinforcement learning from human feedback for emotion modeling."""

    def __init__(self) -> None:
        """Initialize emotion RLHF system."""
        try:
            device_str = "cuda" if torch.cuda.is_available() else "cpu"
            self.device = torch.device(device_str)
            self.model = EmotionNet().to(self.device)
            self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
            self.training_steps = 0
            self.load()
            logger.info(f"EmotionRLHF initialized on {self.device}")
        except Exception as e:
            logger.error(f"Failed to initialize EmotionRLHF: {e}", exc_info=True)
            raise

    def load(self) -> None:
        """Load emotion model from disk if available."""
        try:
            if MODEL_PATH.exists():
                checkpoint = torch.load(MODEL_PATH, map_location=self.device)
                self.model.load_state_dict(checkpoint)
                logger.debug("Emotion model loaded from disk")
        except Exception as e:
            logger.warning(f"Could not load emotion model: {e}")

    def save(self) -> None:
        """Save emotion model to disk."""
        try:
            torch.save(self.model.state_dict(), MODEL_PATH)
            logger.debug("Emotion model saved to disk")
        except Exception as e:
            logger.error(f"Failed to save emotion model: {e}")

    def predict(self, features: List[float]) -> List[float]:
        """
        Predict emotional state from features.

        Args:
            features: Input feature vector

        Returns:
            Predicted emotion values [0, 1] for each dimension
        """
        try:
            with torch.no_grad():
                x = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(self.device)
                output = self.model(x).squeeze()
            return output.cpu().tolist()
        except Exception as e:
            logger.error(f"Error in emotion prediction: {e}")
            return [0.5] * 6

    def update_from_feedback(self, features: List[float], target_emotions: List[float]) -> float:
        """
        Update model based on human feedback.

        Args:
            features: Input feature vector
            target_emotions: Target emotion values from feedback

        Returns:
            Training loss value
        """
        try:
            x = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(self.device)
            target = torch.tensor(target_emotions, dtype=torch.float32).to(self.device)
            
            self.optimizer.zero_grad()
            output = self.model(x).squeeze()
            loss = nn.MSELoss()(output, target)
            loss.backward()
            self.optimizer.step()
            
            self.training_steps += 1
            if self.training_steps % 10 == 0:
                self.save()
                logger.debug(f"Emotion model trained: {self.training_steps} steps, loss: {loss.item():.4f}")
            
            return loss.item()
        except Exception as e:
            logger.error(f"Error updating emotion model: {e}", exc_info=True)
            return 0.0


# Global emotion instance
try:
    emotion_rlhf = EmotionRLHF()
except Exception as e:
    logger.critical(f"Failed to initialize global emotion_rlhf: {e}")
    raise
