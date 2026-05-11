"""
Theory of Mind - FeBo's social cognition system.

Implements:
- Modeling beliefs of others
- Predicting intentions
- Simulating emotional states
- Understanding perspective taking
"""

import time
import threading
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

from core.logging_config import get_logger

logger = get_logger("consciousness.theory_of_mind")


@dataclass
class MentalModel:
    """Model of another agent's mental state."""
    
    agent_id: str
    name: Optional[str] = None
    
    # Beliefs about the agent
    beliefs: Dict[str, Any] = field(default_factory=dict)
    
    # Known preferences
    preferences: Dict[str, float] = field(default_factory=dict)
    
    # Estimated emotional state
    estimated_emotion_valence: float = 0.5
    estimated_emotion_arousal: float = 0.5
    
    # Trust level
    trust: float = 0.5
    
    # Interaction history
    recent_interactions: List[str] = field(default_factory=list)
    interaction_count: int = 0
    
    # Last updated
    last_updated: float = field(default_factory=time.time)


class TheoryOfMind:
    """Models user mental states, beliefs, and preferences."""

    def __init__(self) -> None:
        """Initialize theory of mind."""
        self._lock = threading.RLock()
        self.models: Dict[str, MentalModel] = {}
        self.user_beliefs: Dict[str, int] = {}  # Legacy support
        self.user_preferences: list = []  # Legacy support
        logger.debug("TheoryOfMind initialized")

    def update(self, user_utterance: str) -> None:
        """
        Update user model based on utterance.

        Args:
            user_utterance: User input text
        """
        try:
            with self._lock:
                # Legacy word frequency tracking
                words = user_utterance.lower().split()
                for word in words:
                    if len(word) > 3:  # Filter out short words
                        self.user_beliefs[word] = self.user_beliefs.get(word, 0) + 1
                
                # Update modern user model
                self.update_model("default_user", interaction=user_utterance)
                
                logger.debug(f"Updated theory of mind from utterance")
        except Exception as e:
            logger.error(f"Error updating theory of mind: {e}")

    def predict_belief(self, topic: str) -> bool:
        """
        Predict if user believes in a topic.

        Args:
            topic: Topic to check belief about

        Returns:
            True if user appears to believe in topic
        """
        try:
            topic_lower = topic.lower()
            words = topic_lower.split()
            total_mentions = sum(self.user_beliefs.get(w, 0) for w in words)
            return total_mentions > 2
        except Exception as e:
            logger.error(f"Error predicting belief: {e}")
            return False
    
    def update_model(
        self,
        agent_id: str,
        name: Optional[str] = None,
        interaction: Optional[str] = None,
        valence: float = 0.5,
        arousal: float = 0.5
    ) -> MentalModel:
        """
        Update mental model of an agent.
        
        Args:
            agent_id: Unique identifier
            name: Optional human name
            interaction: Recent interaction to record
            valence: Estimated emotional valence
            arousal: Estimated arousal
            
        Returns:
            Updated MentalModel
        """
        try:
            with self._lock:
                if agent_id not in self.models:
                    self.models[agent_id] = MentalModel(agent_id=agent_id, name=name)
                
                model = self.models[agent_id]
                
                if name:
                    model.name = name
                
                model.estimated_emotion_valence = max(0, min(1, valence))
                model.estimated_emotion_arousal = max(0, min(1, arousal))
                
                if interaction:
                    model.recent_interactions.append(interaction)
                    if len(model.recent_interactions) > 20:
                        model.recent_interactions.pop(0)
                    model.interaction_count += 1
                
                model.last_updated = time.time()
                
                logger.debug(f"Model updated for {agent_id}: valence={valence:.2f}, arousal={arousal:.2f}")
                return model
                
        except Exception as e:
            logger.error(f"Error updating model for {agent_id}: {e}")
            raise
    
    def get_model(self, agent_id: str) -> Optional[MentalModel]:
        """Get mental model of an agent."""
        try:
            with self._lock:
                return self.models.get(agent_id)
        except Exception as e:
            logger.error(f"Error retrieving model: {e}")
            return None
    
    def predict_reaction(self, agent_id: str, statement: str) -> str:
        """
        Predict how an agent would react to a statement.
        
        Args:
            agent_id: Agent identifier
            statement: Proposed statement
            
        Returns:
            Predicted reaction
        """
        try:
            model = self.get_model(agent_id)
            if not model:
                return "neutral"  # Unknown agent
            
            # Simple heuristic prediction
            if model.estimated_emotion_valence > 0.7:
                return "positive"
            elif model.estimated_emotion_valence < 0.3:
                return "negative"
            else:
                return "neutral"
                
        except Exception as e:
            logger.error(f"Error predicting reaction: {e}")
            return "uncertain"
    
    def infer_belief(self, agent_id: str, topic: str) -> Optional[Any]:
        """
        Infer what an agent believes about a topic.
        
        Args:
            agent_id: Agent identifier
            topic: Topic
            
        Returns:
            Inferred belief or None
        """
        try:
            model = self.get_model(agent_id)
            if not model:
                return None
            
            return model.beliefs.get(topic)
            
        except Exception as e:
            logger.error(f"Error inferring belief: {e}")
            return None
    
    def record_belief(self, agent_id: str, topic: str, belief: Any) -> None:
        """Record a belief we've inferred about an agent."""
        try:
            model = self.get_model(agent_id)
            if model:
                model.beliefs[topic] = belief
                logger.debug(f"Recorded belief for {agent_id} on {topic}")
        except Exception as e:
            logger.error(f"Error recording belief: {e}")
    
    def update_trust(self, agent_id: str, delta: float) -> float:
        """
        Update trust level for an agent.
        
        Args:
            agent_id: Agent identifier
            delta: Change in trust (-1 to 1)
            
        Returns:
            New trust level
        """
        try:
            model = self.get_model(agent_id)
            if model:
                model.trust = max(0, min(1, model.trust + delta))
                logger.debug(f"Trust updated for {agent_id}: {model.trust:.2f}")
                return model.trust
            return 0.5
        except Exception as e:
            logger.error(f"Error updating trust: {e}")
            return 0.5
    
    def perspective_take(self, agent_id: str) -> Dict[str, Any]:
        """
        Take the perspective of another agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Perspective summary
        """
        try:
            model = self.get_model(agent_id)
            if not model:
                return {}
            
            return {
                "emotional_state": {
                    "valence": model.estimated_emotion_valence,
                    "arousal": model.estimated_emotion_arousal
                },
                "likely_concerns": list(model.beliefs.keys()),
                "trust_level": model.trust,
                "interaction_history_length": model.interaction_count
            }
            
        except Exception as e:
            logger.error(f"Error in perspective taking: {e}")
            return {}


# Global instance
_theory_of_mind: Optional[TheoryOfMind] = None


def get_theory_of_mind() -> TheoryOfMind:
    """Get or create global theory of mind instance."""
    global _theory_of_mind
    if _theory_of_mind is None:
        _theory_of_mind = TheoryOfMind()
    return _theory_of_mind
