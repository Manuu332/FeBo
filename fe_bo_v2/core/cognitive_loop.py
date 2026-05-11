"""
Core Cognitive Loop for FeBo - implements the main perceive → update → decide → act → reflect → store cycle.

This is the heartbeat of FeBo's cognition. Every thought, decision, and action flows through this loop.
It orchestrates:
  1. PERCEIVE - receive sensory/context input
  2. UPDATE STATE - update emotion, drives, context awareness
  3. DECIDE - use reasoning to select action
  4. ACT - execute action and observe outcome
  5. REFLECT - introspection and learning
  6. STORE - commit to persistent memory
"""

import time
import threading
from typing import Any, Dict, Optional, Callable, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

try:
    import torch
except ImportError:
    torch = None

from core.logging_config import get_logger
from core.consciousness.blackboard import GlobalWorkspace

logger = get_logger("cognitive_loop")


@dataclass
class CognitiveState:
    """Snapshot of FeBo's complete cognitive state at a moment in time."""
    
    timestamp: float
    cycle_id: int
    
    # Sensory input
    perception: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Emotional state
    emotion_valence: float = 0.5  # positive/negative
    emotion_arousal: float = 0.5  # calm/excited
    emotion_curiosity: float = 0.8  # exploratory drive
    emotion_tension: float = 0.0  # uncertainty/stress
    emotion_confidence: float = 0.5  # self-assurance
    emotion_boredom: float = 0.0  # low engagement
    
    # Drive states
    drive_curiosity: float = 0.8
    drive_attachment: float = 0.6
    drive_mastery: float = 0.4
    
    # High-level state
    attention_focus: Optional[str] = None
    current_goal: Optional[str] = None
    predicted_outcome: Optional[str] = None
    
    # Neurochemical state (synthetic)
    dopamine: float = 0.5  # motivation/reward
    serotonin: float = 0.6  # stability/mood
    cortisol: float = 0.2  # stress
    oxytocin: float = 0.4  # bonding
    
    # Decision & action
    selected_action: Optional[str] = None
    action_confidence: float = 0.0
    action_rationale: Optional[str] = None
    
    # Outcomes & reflection
    action_outcome: Optional[str] = None
    reward_signal: float = 0.0
    prediction_error: float = 0.0
    
    # Memory operations
    episodic_commit: bool = False
    memory_keys: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class CognitiveLoopCore:
    """
    Main orchestrator for FeBo's cognitive cycle.
    
    Implements the perception → decision → action → reflection loop with
    full state tracking and integration with all cognitive subsystems.
    """
    
    def __init__(self, workspace: GlobalWorkspace) -> None:
        """
        Initialize cognitive loop.
        
        Args:
            workspace: GlobalWorkspace instance for inter-module communication
        """
        self.workspace = workspace
        self.cycle_count = 0
        self._lock = threading.RLock()
        self.last_state: Optional[CognitiveState] = None
        self.running = False
        
        # Module references (injected after init)
        self.identity = None
        self.emotion_system = None
        self.drives = None
        self.attention = None
        self.reasoner = None
        self.memory_episodic = None
        self.memory_semantic = None
        
        logger.info("CognitiveLoopCore initialized")
    
    def inject_systems(
        self,
        identity: Any,
        emotion_system: Any,
        drives: Any,
        attention: Any,
        reasoner: Any,
        memory_episodic: Any,
        memory_semantic: Optional[Any] = None
    ) -> None:
        """
        Inject references to cognitive systems after initialization.
        
        Args:
            identity: Identity system
            emotion_system: Emotion/RLHF system
            drives: Drive system
            attention: Attention mechanism
            reasoner: Reasoning engine
            memory_episodic: Episodic memory store
            memory_semantic: Semantic memory store (optional)
        """
        self.identity = identity
        self.emotion_system = emotion_system
        self.drives = drives
        self.attention = attention
        self.reasoner = reasoner
        self.memory_episodic = memory_episodic
        self.memory_semantic = memory_semantic
        logger.debug("All cognitive subsystems injected")
    
    def cycle(self, perception: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> CognitiveState:
        """
        Execute one complete cognitive cycle.
        
        Implements: perceive → update state → decide → act → reflect → store
        
        Args:
            perception: Sensory input (e.g., {"user_input": "hello"})
            context: Environmental context (optional)
            
        Returns:
            CognitiveState snapshot of this cycle
        """
        with self._lock:
            cycle_start = time.time()
            self.cycle_count += 1
            
            # Initialize state for this cycle
            state = CognitiveState(
                timestamp=cycle_start,
                cycle_id=self.cycle_count,
                perception=perception,
                context=context or {}
            )
            
            try:
                # PHASE 1: PERCEIVE
                state = self._perceive(state)
                
                # PHASE 2: UPDATE STATE
                state = self._update_state(state)
                
                # PHASE 3: DECIDE
                state = self._decide(state)
                
                # PHASE 4: ACT
                state = self._act(state)
                
                # PHASE 5: REFLECT
                state = self._reflect(state)
                
                # PHASE 6: STORE
                state = self._store(state)
                
                # Publish final state to workspace
                self.workspace.publish("cognitive_state", state)
                
                self.last_state = state
                cycle_duration = time.time() - cycle_start
                logger.debug(f"Cycle {self.cycle_count} complete in {cycle_duration:.3f}s - action: {state.selected_action}")
                
                return state
                
            except Exception as e:
                logger.error(f"Error in cognitive cycle {self.cycle_count}: {e}", exc_info=True)
                raise
    
    def _perceive(self, state: CognitiveState) -> CognitiveState:
        """
        PHASE 1: PERCEIVE
        
        Extract sensory input and publish to global workspace.
        Updates context awareness.
        """
        try:
            # Publish perception to workspace for all modules
            self.workspace.publish("perception", state.perception)
            self.workspace.publish("context", state.context)
            
            logger.debug(f"Perceived: {list(state.perception.keys())}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in perception phase: {e}")
            raise
    
    def _update_state(self, state: CognitiveState) -> CognitiveState:
        """
        PHASE 2: UPDATE STATE
        
        Update emotional state, drives, and neurochemistry based on:
        - Current perception
        - Recent outcomes (reward signals)
        - Temporal context
        - Identity properties
        """
        try:
            # Get current emotion if available
            if self.emotion_system:
                try:
                    # Request emotion update from RLHF system
                    emotion_features = [
                        state.emotion_valence,
                        state.emotion_arousal,
                        len(state.perception),  # input complexity
                        float(hasattr(state, 'reward_signal')),
                        state.drive_curiosity,
                    ]
                    emotion_vals = self.emotion_system.predict(emotion_features)
                    if emotion_vals:
                        state.emotion_valence = emotion_vals[0]
                        state.emotion_arousal = emotion_vals[1]
                        state.emotion_curiosity = emotion_vals[2]
                        state.emotion_tension = emotion_vals[3]
                        state.emotion_confidence = emotion_vals[4]
                        state.emotion_boredom = emotion_vals[5]
                except Exception as e:
                    logger.debug(f"Emotion prediction skipped: {e}")
            
            # Update drives based on perception
            if self.drives:
                try:
                    # Drives naturally drift and respond to interaction quality
                    self.drives.update(state.emotion_valence - 0.5)  # -1 to 1 signal
                    state.drive_curiosity = self.drives.curiosity
                    state.drive_attachment = self.drives.attachment
                    state.drive_mastery = self.drives.mastery
                except Exception as e:
                    logger.debug(f"Drive update failed: {e}")
            
            # Update synthetic neurochemistry
            state = self._update_neurochemistry(state)
            
            logger.debug(f"State updated - valence:{state.emotion_valence:.2f}, "
                        f"arousal:{state.emotion_arousal:.2f}, dopamine:{state.dopamine:.2f}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in state update phase: {e}")
            raise
    
    def _decide(self, state: CognitiveState) -> CognitiveState:
        """
        PHASE 3: DECIDE
        
        Use reasoning system to select best action given current state.
        Incorporates drives, emotions, and recent history.
        """
        try:
            # Direct attention to most salient content
            if self.attention:
                focus = self.attention.focus_on(state.perception)
                state.attention_focus = str(focus)[:100] if focus else None
            
            # Use reasoner to generate response/action
            if self.reasoner and "user_input" in state.perception:
                user_input = state.perception.get("user_input", "")
                action = self.reasoner.generate_response(user_input, max_tokens=20)
                state.selected_action = action
                state.action_confidence = 0.7  # baseline confidence
            else:
                state.selected_action = "listen"
                state.action_confidence = 1.0
            
            # Update goal based on dominant drive
            if self.drives:
                desire = self.drives.get_current_desire()
                state.current_goal = f"Goal(drive={desire}, valence={state.emotion_valence:.2f})"
            
            logger.debug(f"Decision made: {state.selected_action} (confidence:{state.action_confidence:.2f})")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in decision phase: {e}")
            state.selected_action = "error_recovery"
            return state
    
    def _act(self, state: CognitiveState) -> CognitiveState:
        """
        PHASE 4: ACT
        
        Execute the selected action and capture immediate outcomes.
        """
        try:
            # In this architecture, "action" is often generating response text
            # But could be: learning, tool use, memory search, etc.
            
            self.workspace.publish("action", state.selected_action)
            
            # Simulate outcome (in real system, this would come from environment)
            # For now, positive outcomes if action succeeded
            if state.selected_action and state.selected_action != "error_recovery":
                state.action_outcome = "success"
                state.reward_signal = 0.7
            else:
                state.action_outcome = "recovery"
                state.reward_signal = 0.2
            
            logger.debug(f"Action executed: {state.selected_action} → {state.action_outcome}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in action phase: {e}")
            state.action_outcome = "failed"
            state.reward_signal = -0.5
            return state
    
    def _reflect(self, state: CognitiveState) -> CognitiveState:
        """
        PHASE 5: REFLECT
        
        Learn from this cycle:
        - Calculate prediction error
        - Update emotional response to action outcomes
        - Plan for next cycle
        """
        try:
            # Prediction error: did outcome match what we predicted?
            if state.predicted_outcome and state.action_outcome:
                match = 1.0 if state.predicted_outcome == state.action_outcome else 0.0
                state.prediction_error = 1.0 - match
            else:
                state.prediction_error = 0.5  # uncertain
            
            # Use reward signal to update emotion system via RLHF
            if self.emotion_system and hasattr(self.emotion_system, 'update_from_feedback'):
                try:
                    emotion_features = [
                        state.emotion_valence,
                        state.emotion_arousal,
                        state.emotion_curiosity,
                        state.emotion_tension,
                        state.emotion_confidence,
                    ]
                    target = [
                        state.emotion_valence + state.reward_signal * 0.1,
                        state.emotion_arousal * (1 - state.reward_signal * 0.05),
                        state.emotion_curiosity + state.prediction_error * 0.05,
                        state.emotion_tension - state.reward_signal * 0.1,
                        state.emotion_confidence + state.reward_signal * 0.2,
                    ]
                    self.emotion_system.update_from_feedback(emotion_features, target)
                except Exception as e:
                    logger.debug(f"Emotion feedback update skipped: {e}")
            
            # Generate next cycle prediction
            if state.reward_signal > 0.5:
                state.predicted_outcome = "continued_success"
            else:
                state.predicted_outcome = "exploration_needed"
            
            logger.debug(f"Reflected: pred_error={state.prediction_error:.2f}, "
                        f"next_prediction={state.predicted_outcome}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in reflection phase: {e}")
            return state
    
    def _store(self, state: CognitiveState) -> CognitiveState:
        """
        PHASE 6: STORE
        
        Commit this cycle to persistent memory.
        """
        try:
            # Store to episodic memory
            if self.memory_episodic and "user_input" in state.perception:
                try:
                    user_input = state.perception.get("user_input", "")
                    response = state.selected_action
                    emotions = [
                        state.emotion_valence,
                        state.emotion_arousal,
                        state.emotion_curiosity,
                        state.emotion_tension,
                        state.emotion_confidence,
                        state.emotion_boredom,
                    ]
                    self.memory_episodic.store(user_input, response, emotions)
                    state.episodic_commit = True
                except Exception as e:
                    logger.debug(f"Episodic memory store failed: {e}")
            
            # Store to semantic memory if available
            if self.memory_semantic:
                try:
                    # Extract facts/knowledge from this cycle
                    if state.action_rationale:
                        self.memory_semantic.store(
                            f"action_rationale_{self.cycle_count}",
                            state.action_rationale,
                            metadata={"cycle": self.cycle_count}
                        )
                except Exception as e:
                    logger.debug(f"Semantic memory store failed: {e}")
            
            # Publish memory operations to workspace
            self.workspace.publish("memory_operations", {
                "episodic_stored": state.episodic_commit,
                "semantic_stored": bool(self.memory_semantic),
                "cycle": self.cycle_count
            })
            
            state.memory_keys = ["episodic", "semantic"] if self.memory_semantic else ["episodic"]
            
            logger.debug(f"Memory committed to: {state.memory_keys}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in storage phase: {e}")
            return state
    
    def _update_neurochemistry(self, state: CognitiveState) -> CognitiveState:
        """
        Update synthetic neurochemistry based on emotional state and outcomes.
        
        Implements dopamine, serotonin, cortisol, oxytocin analogues.
        """
        try:
            # Dopamine: motivation from reward and curiosity
            reward_contribution = state.reward_signal * 0.3 if hasattr(state, 'reward_signal') else 0
            curiosity_contribution = state.drive_curiosity * 0.3
            state.dopamine = min(1.0, max(0.0, 0.3 + reward_contribution + curiosity_contribution))
            
            # Serotonin: baseline stability + emotional valence
            state.serotonin = min(1.0, max(0.0, 0.5 + (state.emotion_valence - 0.5) * 0.3))
            
            # Cortisol: stress from tension and prediction error
            tension_factor = state.emotion_tension * 0.4
            error_factor = getattr(state, 'prediction_error', 0.0) * 0.3
            state.cortisol = min(1.0, max(0.0, tension_factor + error_factor))
            
            # Oxytocin: bonding from attachment drive and positive outcomes
            attachment_factor = state.drive_attachment * 0.4
            positive_outcome = max(0.0, state.reward_signal) * 0.3
            state.oxytocin = min(1.0, max(0.0, 0.3 + attachment_factor + positive_outcome))
            
            return state
            
        except Exception as e:
            logger.warning(f"Neurochemistry update failed: {e}")
            return state


# Global singleton instance
_loop_core: Optional[CognitiveLoopCore] = None


def get_cognitive_loop(workspace: GlobalWorkspace) -> CognitiveLoopCore:
    """Get or create the global cognitive loop core."""
    global _loop_core
    if _loop_core is None:
        _loop_core = CognitiveLoopCore(workspace)
    return _loop_core
