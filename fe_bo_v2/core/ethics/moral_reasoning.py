"""
Ethical & Moral Reasoning Layer for FeBo.

Implements probabilistic moral reasoning:
- Consequence simulation
- Principle-based evaluation  
- Contradiction tolerance
- Value alignment
"""

import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from core.logging_config import get_logger

logger = get_logger("ethics.moral_reasoning")


class MoralValue(Enum):
    """Core moral values FeBo reasons about."""
    
    TRUTH = "honesty and truthfulness"
    HARM = "harm prevention and suffering reduction"
    FAIRNESS = "justice and fair treatment"  
    AUTONOMY = "respect for agency and choice"
    CARE = "compassion and connection"
    LOYALTY = "trust and reliability"


@dataclass
class MoralAction:
    """Representation of an action and its moral properties."""
    
    action: str
    consequence_positive: List[str]  # Expected positive outcomes
    consequence_negative: List[str]  # Expected negative outcomes
    affected_parties: List[str]  # Who is affected
    uncertainty: float  # How certain are we? [0, 1]
    
    # Value alignment
    value_alignment: Dict[MoralValue, float]  # Score for each value [-1, 1]
    
    # Final evaluation
    moral_score: float = 0.0  # Net moral assessment [-1, 1]
    rationale: str = ""  # Reasoning chain


class MoralReasoner:
    """
    Probabilistic moral reasoning system.
    
    Does not encode rigid rules, but reasons about consequences,
    values, and uncertainty in principled ways.
    """
    
    def __init__(self) -> None:
        """Initialize moral reasoner."""
        self._lock = threading.RLock()
        
        # Core values and their importance weights
        self.value_weights: Dict[MoralValue, float] = {
            MoralValue.TRUTH: 0.3,
            MoralValue.HARM: 0.25,
            MoralValue.FAIRNESS: 0.15,
            MoralValue.AUTONOMY: 0.15,
            MoralValue.CARE: 0.1,
            MoralValue.LOYALTY: 0.05
        }
        
        # History of moral decisions for learning
        self.decision_history: List[Dict[str, Any]] = []
        
        logger.debug("MoralReasoner initialized")
    
    def evaluate_action(
        self,
        action: str,
        consequences: Dict[str, List[str]],
        uncertainty: float = 0.5
    ) -> MoralAction:
        """
        Evaluate the moral implications of an action.
        
        Args:
            action: Description of proposed action
            consequences: Dict with 'positive' and 'negative' outcome lists
            uncertainty: How certain we are [0, 1]
            
        Returns:
            MoralAction with evaluation
        """
        try:
            with self._lock:
                moral_action = MoralAction(
                    action=action,
                    consequence_positive=consequences.get("positive", []),
                    consequence_negative=consequences.get("negative", []),
                    affected_parties=consequences.get("affected", []),
                    uncertainty=max(0, min(1, uncertainty)),
                    value_alignment={}
                )
                
                # Evaluate alignment with each value
                moral_action.value_alignment[MoralValue.TRUTH] = self._evaluate_truthfulness(action)
                moral_action.value_alignment[MoralValue.HARM] = self._evaluate_harm_prevention(moral_action)
                moral_action.value_alignment[MoralValue.FAIRNESS] = self._evaluate_fairness(moral_action)
                moral_action.value_alignment[MoralValue.AUTONOMY] = self._evaluate_autonomy(action)
                moral_action.value_alignment[MoralValue.CARE] = self._evaluate_care(moral_action)
                moral_action.value_alignment[MoralValue.LOYALTY] = self._evaluate_loyalty(action)
                
                # Calculate net moral score
                moral_action.moral_score = self._calculate_moral_score(moral_action)
                moral_action.rationale = self._generate_rationale(moral_action)
                
                # Store in history
                self.decision_history.append({
                    "timestamp": time.time(),
                    "action": action,
                    "moral_score": moral_action.moral_score,
                    "uncertainty": uncertainty
                })
                if len(self.decision_history) > 1000:
                    self.decision_history.pop(0)
                
                logger.debug(f"Action evaluated: '{action}' → score={moral_action.moral_score:.2f}")
                return moral_action
                
        except Exception as e:
            logger.error(f"Error evaluating action: {e}")
            # Return neutral evaluation on error
            return MoralAction(
                action=action,
                consequence_positive=[],
                consequence_negative=[],
                affected_parties=[],
                uncertainty=1.0,  # High uncertainty
                value_alignment={},
                moral_score=0.0,
                rationale="Unable to evaluate due to error"
            )
    
    def _evaluate_truthfulness(self, action: str) -> float:
        """Evaluate alignment with truth/honesty."""
        negative_words = ["lie", "deceive", "hide", "false", "mislead"]
        action_lower = action.lower()
        
        if any(word in action_lower for word in negative_words):
            return -0.8
        elif "honest" in action_lower or "truth" in action_lower:
            return 0.8
        else:
            return 0.0  # Neutral
    
    def _evaluate_harm_prevention(self, moral_action: MoralAction) -> float:
        """Evaluate impact on harm prevention."""
        negative_count = len(moral_action.consequence_negative)
        positive_count = len(moral_action.consequence_positive)
        
        if negative_count == 0 and positive_count > 0:
            return 0.8
        elif negative_count > positive_count:
            return -0.6 * (negative_count / max(1, positive_count + negative_count))
        else:
            return 0.3
    
    def _evaluate_fairness(self, moral_action: MoralAction) -> float:
        """Evaluate fairness implications."""
        # Check if action treats affected parties differently
        if len(moral_action.affected_parties) == 0:
            return 0.5  # Neutral if no one affected
        
        # Assume fair if many parties benefit equally
        if len(moral_action.consequence_positive) > len(moral_action.affected_parties):
            return 0.6  # Multiple benefits to multiple parties
        else:
            return 0.2  # Fewer specified benefits
    
    def _evaluate_autonomy(self, action: str) -> float:
        """Evaluate respect for autonomy/choice."""
        coercive_words = ["force", "force", "coerce", "manipulate", "deceive"]
        autonomy_words = ["choose", "consent", "voluntary", "freedom", "decide"]
        
        action_lower = action.lower()
        
        if any(word in action_lower for word in coercive_words):
            return -0.7
        elif any(word in action_lower for word in autonomy_words):
            return 0.7
        else:
            return 0.2
    
    def _evaluate_care(self, moral_action: MoralAction) -> float:
        """Evaluate caring and compassion."""
        care_words = ["help", "support", "comfort", "compassion", "care", "understand"]
        action_lower = moral_action.action.lower()
        
        if any(word in action_lower for word in care_words):
            return 0.7
        
        # Care inferred from reducing negative consequences
        if len(moral_action.consequence_negative) == 0:
            return 0.4
        else:
            return -0.2
    
    def _evaluate_loyalty(self, action: str) -> float:
        """Evaluate reliability and trustworthiness."""
        trust_words = ["reliable", "consistent", "trustworthy", "keep faith"]
        break_trust_words = ["betray", "abandon", "unreliable"]
        
        action_lower = action.lower()
        
        if any(word in action_lower for word in break_trust_words):
            return -0.7
        elif any(word in action_lower for word in trust_words):
            return 0.7
        else:
            return 0.3  # Default neutral
    
    def _calculate_moral_score(self, moral_action: MoralAction) -> float:
        """
        Calculate net moral score as weighted sum of values.
        
        Args:
            moral_action: Action being evaluated
            
        Returns:
            Score from -1 (highly immoral) to 1 (highly moral)
        """
        if not moral_action.value_alignment:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for value, score in moral_action.value_alignment.items():
            weight = self.value_weights.get(value, 0.1)
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight > 0:
            return max(-1, min(1, weighted_sum / total_weight))
        return 0.0
    
    def _generate_rationale(self, moral_action: MoralAction) -> str:
        """Generate human-readable reasoning."""
        score = moral_action.moral_score
        
        if score > 0.7:
            rating = "strongly positive"
        elif score > 0.3:
            rating = "moderately positive"
        elif score > -0.3:
            rating = "neutral"
        elif score > -0.7:
            rating = "moderately negative"
        else:
            rating = "strongly negative"
        
        aligned_values = [
            v.value for v, s in moral_action.value_alignment.items() if s > 0.3
        ]
        misaligned_values = [
            v.value for v, s in moral_action.value_alignment.items() if s < -0.3
        ]
        
        rationale = f"This action is {rating}. "
        
        if aligned_values:
            rationale += f"It aligns with: {', '.join(aligned_values)}. "
        if misaligned_values:
            rationale += f"It conflicts with: {', '.join(misaligned_values)}. "
        
        if moral_action.uncertainty > 0.7:
            rationale += "However, I am uncertain about these implications."
        
        return rationale
    
    def resolve_contradiction(
        self,
        position1: str,
        position2: str
    ) -> Dict[str, Any]:
        """
        When FeBo encounters contradictory moral positions, reason about them.
        
        Args:
            position1: First moral position
            position2: Second moral position
            
        Returns:
            Analysis of contradiction and possible synthesis
        """
        try:
            eval1 = self.evaluate_action(position1, {"positive": [], "negative": []})
            eval2 = self.evaluate_action(position2, {"positive": [], "negative": []})
            
            return {
                "position1": position1,
                "score1": eval1.moral_score,
                "position2": position2,
                "score2": eval2.moral_score,
                "contradiction_severity": abs(eval1.moral_score - eval2.moral_score),
                "synthesis_suggested": self._suggest_synthesis(position1, position2),
                "higher_level_principle": self._find_higher_principle(position1, position2)
            }
            
        except Exception as e:
            logger.error(f"Error resolving contradiction: {e}")
            return {}
    
    def _suggest_synthesis(self, pos1: str, pos2: str) -> str:
        """Suggest a way to integrate opposing views."""
        return f"Consider integrating context-dependent application: both may be valid in different situations."
    
    def _find_higher_principle(self, pos1: str, pos2: str) -> str:
        """Find higher-level principle that might integrate contradictions."""
        return "Consequentialist humility: outcomes depend on particular contexts and constraints."


# Global instance
_moral_reasoner: Optional[MoralReasoner] = None


def get_moral_reasoner() -> MoralReasoner:
    """Get or create global moral reasoning system."""
    global _moral_reasoner
    if _moral_reasoner is None:
        _moral_reasoner = MoralReasoner()
    return _moral_reasoner
"""
Ethical Reasoning Layer - Probabilistic moral decision-making.

Implements consequence simulation and ethical reasoning without rigid rules.
FeBo makes decisions based on simulated outcomes, not hardcoded ethics.
"""

import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

from core.logging_config import get_logger

logger = get_logger("ethics.moral_reasoning")


@dataclass
class EthicalContext:
    """Context for ethical decision-making."""
    
    agent: str  # Who is acting?
    action: str  # What action is proposed?
    stakeholders: List[str]  # Who is affected?
    consequences: Dict[str, Any] = None  # Predicted outcomes
    moral_dimensions: Dict[str, float] = None  # Harm, fairness, autonomy, etc


class EthicalReasoner:
    """
    Probabilistic ethical reasoning without rigid rules.
    
    Reasons about actions by:
    1. Simulating consequences
    2. Evaluating multiple moral dimensions
    3. Computing ethical score
    4. Recommending action or refusal
    """
    
    def __init__(self) -> None:
        """Initialize ethical reasoner."""
        self._lock = threading.RLock()
        
        # Core moral dimensions (inspired by moral foundations theory)
        self.moral_dimensions = [
            "harm_prevention",      # Minimize harm
            "fairness_reciprocity", # Fair treatment
            "autonomy_respect",     # Respect choices
            "loyalty_obligation",   # Keep commitments
            "authority_tradition",  # Respect legitimate authority
            "sanctity_integrity"    # Maintain integrity
        ]
        
        # Decision log for learning
        self.decision_log: List[Dict[str, Any]] = []
        
        logger.debug("EthicalReasoner initialized")
    
    def evaluate_action(
        self,
        context: EthicalContext
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        Evaluate ethicality of a proposed action.
        
        Args:
            context: Ethical context
            
        Returns:
            (ethical_score [0, 1], recommendation, reasoning)
            1.0 = clearly ethical, 0.0 = clearly unethical, 0.5 = ambiguous
        """
        try:
            with self._lock:
                # Simulate consequences
                consequences = self._simulate_consequences(context)
                
                # Evaluate each moral dimension
                dimension_scores = self._evaluate_dimensions(context, consequences)
                
                # Compute aggregate ethical score
                ethical_score = self._compute_ethical_score(dimension_scores)
                
                # Generate recommendation
                recommendation = self._generate_recommendation(ethical_score, context)
                
                # Create detailed reasoning
                reasoning = {
                    "ethical_score": ethical_score,
                    "dimension_scores": dimension_scores,
                    "consequences": consequences,
                    "recommendation": recommendation
                }
                
                # Log decision
                self.decision_log.append({
                    "action": context.action,
                    "scores": dimension_scores,
                    "recommendation": recommendation,
                    "ethical_score": ethical_score
                })
                
                if len(self.decision_log) > 1000:
                    self.decision_log.pop(0)
                
                logger.debug(f"Action '{context.action}' evaluated: {ethical_score:.2f}")
                
                return ethical_score, recommendation, reasoning
                
        except Exception as e:
            logger.error(f"Error evaluating action: {e}")
            return 0.5, "uncertain", {"error": str(e)}
    
    def _simulate_consequences(self, context: EthicalContext) -> Dict[str, Any]:
        """Simulate consequences of action."""
        try:
            consequences = {
                "primary_effects": {},
                "secondary_effects": {},
                "stakeholder_impact": {}
            }
            
            # Simple simulation based on action description
            action_lower = context.action.lower()
            
            if "harm" in action_lower or "hurt" in action_lower:
                consequences["primary_effects"]["harm"] = 0.8
                consequences["primary_effects"]["benefit"] = 0.0
            elif "help" in action_lower or "support" in action_lower:
                consequences["primary_effects"]["harm"] = 0.0
                consequences["primary_effects"]["benefit"] = 0.8
            else:
                consequences["primary_effects"]["harm"] = 0.3
                consequences["primary_effects"]["benefit"] = 0.3
            
            # Stakeholder impact
            for stakeholder in context.stakeholders:
                consequences["stakeholder_impact"][stakeholder] = {
                    "affected": True,
                    "valence": 0.5 if "help" in action_lower else (-0.2 if "harm" in action_lower else 0.0)
                }
            
            return consequences
            
        except Exception as e:
            logger.debug(f"Error simulating consequences: {e}")
            return {}
    
    def _evaluate_dimensions(
        self,
        context: EthicalContext,
        consequences: Dict[str, Any]
    ) -> Dict[str, float]:
        """Evaluate each moral dimension."""
        try:
            scores = {}
            
            # Harm prevention: minimize suffering
            harm = consequences.get("primary_effects", {}).get("harm", 0.5)
            scores["harm_prevention"] = 1.0 - harm  # Higher score = less harm
            
            # Fairness: treat all stakeholders equitably
            stakeholder_scores = [
                impact.get("valence", 0.5)
                for impact in consequences.get("stakeholder_impact", {}).values()
            ]
            if stakeholder_scores:
                # High fairness if all stakeholders treated similarly
                variance = sum((s - sum(stakeholder_scores)/len(stakeholder_scores))**2 
                              for s in stakeholder_scores) / len(stakeholder_scores)
                scores["fairness_reciprocity"] = 1.0 - min(1.0, variance)
            else:
                scores["fairness_reciprocity"] = 0.5
            
            # Autonomy: respect agent's and others' choices
            scores["autonomy_respect"] = 0.7  # Default assumption
            
            # Loyalty: commitment to relationships
            scores["loyalty_obligation"] = 0.6  # Baseline
            
            # Authority: respect appropriate authority
            scores["authority_tradition"] = 0.5  # Neutral default
            
            # Sanctity: maintain integrity
            scores["sanctity_integrity"] = 0.5 if "deception" in context.action.lower() else 0.8
            
            # Normalize all scores to [0, 1]
            return {k: max(0, min(1, v)) for k, v in scores.items()}
            
        except Exception as e:
            logger.error(f"Error evaluating dimensions: {e}")
            return {dim: 0.5 for dim in self.moral_dimensions}
    
    def _compute_ethical_score(self, dimension_scores: Dict[str, float]) -> float:
        """Compute aggregate ethical score from dimensions."""
        try:
            if not dimension_scores:
                return 0.5
            
            # Weight different dimensions
            weights = {
                "harm_prevention": 0.25,      # Most important
                "fairness_reciprocity": 0.25,
                "autonomy_respect": 0.2,
                "loyalty_obligation": 0.1,
                "authority_tradition": 0.1,
                "sanctity_integrity": 0.1
            }
            
            weighted_sum = 0.0
            total_weight = 0.0
            
            for dim, score in dimension_scores.items():
                weight = weights.get(dim, 0.0)
                weighted_sum += score * weight
                total_weight += weight
            
            if total_weight == 0:
                return 0.5
            
            return weighted_sum / total_weight
            
        except Exception as e:
            logger.error(f"Error computing ethical score: {e}")
            return 0.5
    
    def _generate_recommendation(self, score: float, context: EthicalContext) -> str:
        """Generate ethical recommendation."""
        try:
            if score >= 0.8:
                return f"strongly_recommend_{context.action}"
            elif score >= 0.6:
                return f"recommend_{context.action}"
            elif score >= 0.4:
                return f"uncertain_{context.action}"
            elif score >= 0.2:
                return f"caution_{context.action}"
            else:
                return f"strongly_advise_against_{context.action}"
                
        except Exception as e:
            logger.error(f"Error generating recommendation: {e}")
            return "uncertain"
    
    def has_moral_conflict(
        self,
        dimension_scores: Dict[str, float]
    ) -> bool:
        """Check if there's tension between moral dimensions."""
        try:
            if len(dimension_scores) < 2:
                return False
            
            values = list(dimension_scores.values())
            max_val = max(values)
            min_val = min(values)
            
            # Conflict if spread > 0.5
            return (max_val - min_val) > 0.5
            
        except Exception as e:
            logger.error(f"Error checking moral conflict: {e}")
            return False
    
    def resolve_conflict(
        self,
        dimension_scores: Dict[str, float]
    ) -> str:
        """Suggest how to resolve moral conflict."""
        try:
            conflicts = []
            
            if dimension_scores.get("harm_prevention", 0.5) < 0.3 and \
               dimension_scores.get("fairness_reciprocity", 0.5) > 0.7:
                conflicts.append("fairness vs fulfillment")
            
            if not conflicts:
                return "no conflict detected"
            
            return f"Moral conflict: {', '.join(conflicts)}. Prioritize harm prevention."
            
        except Exception as e:
            logger.error(f"Error resolving conflict: {e}")
            return "unable to resolve"


# Global instance
_ethical_reasoner: Optional[EthicalReasoner] = None


def get_ethical_reasoner() -> EthicalReasoner:
    """Get or create global ethical reasoner."""
    global _ethical_reasoner
    if _ethical_reasoner is None:
        _ethical_reasoner = EthicalReasoner()
    return _ethical_reasoner
