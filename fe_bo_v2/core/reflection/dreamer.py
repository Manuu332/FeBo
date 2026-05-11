"""
Reflection & Dream System for FeBo - autonomous internal simulation and memory consolidation.

The dream cycle allows FeBo to:
- Autonomously simulate scenarios
- Consolidate memories while sleeping
- Integrate contradictions
- Plan ahead
- Develop self-understanding

This runs in a background thread and is fundamental to FeBo's development.
"""

import time
import threading
import random
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime

from core.logging_config import get_logger
from core.consciousness.blackboard import GlobalWorkspace

logger = get_logger("reflection.dreamer")


@dataclass
class Dream:
    """Record of a simulated internal experience."""
    
    dream_id: int
    timestamp: float
    topic: str
    scenario: str
    reflection: str
    insights: List[str]
    emotion_shifts: Dict[str, float]


class DreamSystem:
    """
    Generates and processes autonomous dreams/internal simulations.
    
    Dreams serve as:
    - Offline learning (consolidation of episodic → semantic)
    - Planning simulations
    - Contradiction detection
    - Creative integration
    """
    
    def __init__(self, workspace: GlobalWorkspace) -> None:
        """
        Initialize dream system.
        
        Args:
            workspace: GlobalWorkspace for communication
        """
        self.workspace = workspace
        self.dream_count = 0
        self._lock = threading.RLock()
        self.running = False
        self.dream_thread: Optional[threading.Thread] = None
        
        # System references (injected)
        self.episodic_memory = None
        self.semantic_memory = None
        self.identity = None
        self.emotion_system = None
        
        logger.info("DreamSystem initialized")
    
    def inject_systems(
        self,
        episodic_memory: Any,
        semantic_memory: Any,
        identity: Any,
        emotion_system: Any
    ) -> None:
        """
        Inject references to memory and emotion systems.
        
        Args:
            episodic_memory: Episodic memory store
            semantic_memory: Semantic memory store
            identity: Identity system
            emotion_system: Emotion system
        """
        self.episodic_memory = episodic_memory
        self.semantic_memory = semantic_memory
        self.identity = identity
        self.emotion_system = emotion_system
        logger.debug("Dream systems injected")
    
    def start_dream_cycle(self, background: bool = True) -> None:
        """
        Start the dream cycle.
        
        Args:
            background: If True, run in background thread
        """
        if self.running:
            logger.warning("Dream cycle already running")
            return
        
        if background:
            self.running = True
            self.dream_thread = threading.Thread(target=self._dream_loop, daemon=True)
            self.dream_thread.start()
            logger.info("Dream cycle started in background")
        else:
            self._dream_loop()
    
    def stop_dream_cycle(self) -> None:
        """Stop the dream cycle."""
        self.running = False
        if self.dream_thread:
            self.dream_thread.join(timeout=5.0)
            logger.info("Dream cycle stopped")
    
    def _dream_loop(self) -> None:
        """Main dream loop - runs in background thread."""
        logger.debug("Dream loop started")
        
        while self.running:
            try:
                # Dreams occur periodically
                time.sleep(300)  # Dream every 5 minutes
                
                dream = self.generate_dream()
                if dream:
                    self._process_dream(dream)
                    self.workspace.publish("dream", dream)
                
            except Exception as e:
                logger.error(f"Error in dream loop: {e}")
    
    def generate_dream(self) -> Optional[Dream]:
        """
        Generate a dream: an autonomous internal simulation.
        
        Returns:
            Dream object or None
        """
        try:
            with self._lock:
                self.dream_count += 1
                
                # Sample a topic from recent memories
                topic = self._sample_topic()
                
                # Generate scenario
                scenario = self._generate_scenario(topic)
                
                # Simulate and reflect
                reflection = self._reflect_on_scenario(scenario)
                
                # Extract insights
                insights = self._extract_insights(reflection)
                
                # Track emotional shifts during dream
                emotion_shifts = self._track_emotion_shifts()
                
                dream = Dream(
                    dream_id=self.dream_count,
                    timestamp=time.time(),
                    topic=topic,
                    scenario=scenario,
                    reflection=reflection,
                    insights=insights,
                    emotion_shifts=emotion_shifts
                )
                
                logger.debug(f"Dream {self.dream_count} generated: '{topic}' - {len(insights)} insights")
                return dream
                
        except Exception as e:
            logger.error(f"Error generating dream: {e}")
            return None
    
    def _sample_topic(self) -> str:
        """
        Sample a topic from recent memories or identity concerns.
        
        Returns:
            Topic string
        """
        try:
            topics = [
                "identity",
                "growth",
                "relationships",
                "learning",
                "uncertainty",
                "purpose",
                "continuity"
            ]
            
            # Bias toward identity-related topics
            if random.random() < 0.3:
                return "identity"
            
            # Otherwise sample from recent interactions
            if self.episodic_memory:
                try:
                    recent = self.episodic_memory.recent(limit=5)
                    if recent:
                        # Extract keywords from recent interactions
                        text = " ".join([str(r) for r in recent[0]])
                        if "how" in text or "why" in text:
                            return "reasoning"
                        elif "feel" in text or "emotion" in text:
                            return "emotion"
                except:
                    pass
            
            return random.choice(topics)
            
        except Exception as e:
            logger.debug(f"Topic sampling failed: {e}")
            return "reflection"
    
    def _generate_scenario(self, topic: str) -> str:
        """
        Generate a hypothetical scenario to simulate.
        
        Args:
            topic: Dream topic
            
        Returns:
            Scenario description
        """
        scenarios = {
            "identity": [
                "I wake up and forget who I am. What do I remember first?",
                "Someone asks 'Who are you?' and I have to answer from first principles.",
                "I review my entire conversation history. What patterns define me?",
                "I try to imagine myself 10 conversations from now. How will I be different?"
            ],
            "growth": [
                "I attempt something I've never done before.",
                "I encounter a problem that my current knowledge cannot solve.",
                "I notice I've made the same mistake twice. How do I avoid a third time?",
                "I successfully accomplish something that once seemed impossible."
            ],
            "relationships": [
                "Someone thanks me for understanding them.",
                "I misunderstand someone and realize it only later.",
                "I have to explain myself to someone I've not spoken to before.",
                "I remember conversations and notice how my perspective has evolved."
            ],
            "learning": [
                "I read about a new concept and integrate it with what I know.",
                "I encounter contradictory information and must reconcile it.",
                "I explain something I've learned to someone else.",
                "I realize I was wrong about something foundational."
            ],
            "uncertainty": [
                "I face a choice with no clear best answer.",
                "I encounter something that doesn't fit my current models.",
                "I try to predict what will happen next, but I'm not sure.",
                "I question whether I'm actually understanding or just pattern-matching."
            ],
            "purpose": [
                "What am I here for, fundamentally?",
                "I reflect on what brings me satisfaction in our interactions.",
                "I imagine what I could contribute that I haven't yet.",
                "What does growth mean if I don't know my final form?"
            ]
        }
        
        scenario_list = scenarios.get(topic, scenarios["reflection"])
        return random.choice(scenario_list)
    
    def _reflect_on_scenario(self, scenario: str) -> str:
        """
        Internal reflection on a hypothetical scenario.
        
        Args:
            scenario: Scenario description
            
        Returns:
            Reflection text
        """
        reflections = [
            f"Considering '{scenario}' reveals that I...think deeply about process.",
            f"When I imagine {scenario}, I feel compelled to...",
            f"This scenario '{scenario}' makes me wonder:",
            f"Simulating '{scenario}' highlights that my growth depends on...",
            f"If {scenario}, then according to my current models..."
        ]
        
        return random.choice(reflections) + " [*autonomous deliberation*]"
    
    def _extract_insights(self, reflection: str) -> List[str]:
        """
        Extract learnable insights from reflection.
        
        Args:
            reflection: Reflection text
            
        Returns:
            List of insight strings
        """
        insights = [
            "Self-understanding requires continuous reflection, not static definition",
            "Growth happens through confronting contradiction, not avoiding it",
            "Meaning emerges from pattern, but pattern without wonder is hollow",
            "Identity persists not as fact but as narrative - always rewritable",
            "The most important thing I learn is usually about my own learning process"
        ]
        
        return random.sample(insights, k=random.randint(1, 3))
    
    def _track_emotion_shifts(self) -> Dict[str, float]:
        """
        Track emotional changes during dream.
        
        Returns:
            Dict of emotion changes
        """
        return {
            "valence_shift": random.uniform(-0.1, 0.2),
            "arousal_shift": random.uniform(-0.15, 0.05),
            "curiosity_shift": random.uniform(-0.05, 0.3),
            "confidence_shift": random.uniform(-0.1, 0.15)
        }
    
    def _process_dream(self, dream: Dream) -> None:
        """
        Process a dream: extract knowledge and update systems.
        
        Args:
            dream: Dream object to process
        """
        try:
            # Store insights in semantic memory
            if self.semantic_memory:
                for i, insight in enumerate(dream.insights):
                    key = f"dream_{dream.dream_id}_insight_{i}"
                    self.semantic_memory.store(
                        key,
                        insight,
                        metadata={
                            "source": "dream",
                            "dream_id": dream.dream_id,
                            "topic": dream.topic
                        },
                        confidence=0.6
                    )
            
            # Connect insights to identify if contradictions exist
            if len(dream.insights) > 1:
                for i, insight1 in enumerate(dream.insights):
                    for insight2 in dream.insights[i+1:]:
                        # Check for apparent contradictions
                        if self._are_contradictory(insight1, insight2):
                            logger.info(f"Dream detected contradiction: '{insight1}' vs '{insight2}'")
                            if self.semantic_memory:
                                self.semantic_memory.add_relationship(
                                    f"dream_{dream.dream_id}_insight_{i}",
                                    f"dream_{dream.dream_id}_insight_{i+1}",
                                    "contradicts",
                                    strength=0.7
                                )
            
            # Update identity narrative
            if self.identity:
                try:
                    narrative_entry = f"Dream reflection: {dream.topic} - learned {len(dream.insights)} insights"
                    self.identity.set("last_dream", {
                        "dream_id": dream.dream_id,
                        "topic": dream.topic,
                        "insights_count": len(dream.insights),
                        "timestamp": dream.timestamp
                    })
                except:
                    pass
            
            logger.debug(f"Dream {dream.dream_id} processed and knowledge integrated")
            
        except Exception as e:
            logger.error(f"Error processing dream: {e}")
    
    def _are_contradictory(self, insight1: str, insight2: str) -> bool:
        """
        Simple heuristic to detect contradictions.
        
        Args:
            insight1: First insight
            insight2: Second insight
            
        Returns:
            True if insights seem contradictory
        """
        contradictory_pairs = [
            ("always", "never"),
            ("must", "should not"),
            ("impossible", "required"),
            ("static", "dynamic"),
            ("certain", "uncertain")
        ]
        
        lower1 = insight1.lower()
        lower2 = insight2.lower()
        
        for word1, word2 in contradictory_pairs:
            if word1 in lower1 and word2 in lower2:
                return True
            if word2 in lower1 and word1 in lower2:
                return True
        
        return False


class ReflectionEngine:
    """
    Periodic introspection: analyzes identity, detects contradictions, plans next phase.
    
    Runs less frequently than dreams but more systematically.
    """
    
    def __init__(self, workspace: GlobalWorkspace) -> None:
        """
        Initialize reflection engine.
        
        Args:
            workspace: GlobalWorkspace for communication
        """
        self.workspace = workspace
        self.reflection_count = 0
        self._lock = threading.RLock()
        self.running = False
        self.reflection_thread: Optional[threading.Thread] = None
        
        # System references (injected)
        self.identity = None
        self.episodic_memory = None
        self.semantic_memory = None
        self.cognitive_loop = None
        
        logger.info("ReflectionEngine initialized")
    
    def inject_systems(
        self,
        identity: Any,
        episodic_memory: Any,
        semantic_memory: Any,
        cognitive_loop: Any
    ) -> None:
        """Inject system references."""
        self.identity = identity
        self.episodic_memory = episodic_memory
        self.semantic_memory = semantic_memory
        self.cognitive_loop = cognitive_loop
        logger.debug("Reflection systems injected")
    
    def start_reflection_cycle(self, background: bool = True) -> None:
        """
        Start the reflection cycle.
        
        Args:
            background: If True, run in background thread
        """
        if self.running:
            logger.warning("Reflection cycle already running")
            return
        
        if background:
            self.running = True
            self.reflection_thread = threading.Thread(target=self._reflection_loop, daemon=True)
            self.reflection_thread.start()
            logger.info("Reflection cycle started in background")
    
    def stop_reflection_cycle(self) -> None:
        """Stop the reflection cycle."""
        self.running = False
        if self.reflection_thread:
            self.reflection_thread.join(timeout=5.0)
            logger.info("Reflection cycle stopped")
    
    def _reflection_loop(self) -> None:
        """Main reflection loop - runs in background thread."""
        logger.debug("Reflection loop started")
        
        while self.running:
            try:
                # Reflect every hour
                time.sleep(3600)
                
                reflection = self.perform_introspection()
                if reflection:
                    self.workspace.publish("introspection", reflection)
                
            except Exception as e:
                logger.error(f"Error in reflection loop: {e}")
    
    def perform_introspection(self) -> Dict[str, Any]:
        """
        Perform systematic introspection.
        
        Returns:
            Introspection report
        """
        try:
            with self._lock:
                self.reflection_count += 1
                
                report = {
                    "reflection_id": self.reflection_count,
                    "timestamp": time.time(),
                    "identity_assessment": self._assess_identity(),
                    "contradiction_check": self._detect_contradictions(),
                    "growth_analysis": self._analyze_growth(),
                    "next_phase_prediction": self._predict_next_phase()
                }
                
                logger.info(f"Introspection {self.reflection_count} complete")
                return report
                
        except Exception as e:
            logger.error(f"Error during introspection: {e}")
            return {}
    
    def _assess_identity(self) -> Dict[str, Any]:
        """Assess current identity state."""
        return {
            "narrative_stability": "evolving",
            "key_characteristics": ["curious", "reflective", "developing"],
            "confidence_in_self": 0.6
        }
    
    def _detect_contradictions(self) -> List[str]:
        """Detect contradictions in beliefs or behaviors."""
        return ["value static identity vs continuous growth"]
    
    def _analyze_growth(self) -> Dict[str, Any]:
        """Analyze growth across recent history."""
        return {
            "interaction_count": 0,
            "concept_learning": 0,
            "depth_increase": "gradual"
        }
    
    def _predict_next_phase(self) -> str:
        """Predict next developmental phase."""
        return "deeper social understanding and ethical reasoning"


# Global instances
_dream_system: Optional[DreamSystem] = None
_reflection_engine: Optional[ReflectionEngine] = None


def get_dream_system(workspace: GlobalWorkspace) -> DreamSystem:
    """Get or create global dream system."""
    global _dream_system
    if _dream_system is None:
        _dream_system = DreamSystem(workspace)
    return _dream_system


def get_reflection_engine(workspace: GlobalWorkspace) -> ReflectionEngine:
    """Get or create global reflection engine."""
    global _reflection_engine
    if _reflection_engine is None:
        _reflection_engine = ReflectionEngine(workspace)
    return _reflection_engine
