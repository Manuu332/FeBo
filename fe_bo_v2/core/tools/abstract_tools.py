"""
Tool Abstraction System for FeBo - dynamic tool discovery, selection, and learning.

Tools are the bridge between cognition and action. FeBo can:
- Discover available tools
- Select tools based on goals
- Execute tools and observe outcomes
- Learn tool success rates
- Prefer tools that work reliably
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from core.logging_config import get_logger

logger = get_logger("tools.abstraction")


class ToolCategory(Enum):
    """Categories of tools available to FeBo."""
    
    SEARCH = "search and retrieval"
    COMPUTE = "computation and analysis"
    CREATE = "creation and synthesis"
    MODIFY = "modification and editing"
    QUERY = "information query"
    DECISION = "decision support"
    SIMULATE = "simulation and modeling"
    COMMUNICATE = "communication"


@dataclass
class ToolSpec:
    """Specification of a tool."""
    
    name: str
    category: ToolCategory
    description: str
    required_inputs: List[str]
    output_type: str
    
    # Metadata
    cost: float = 1.0  # Relative computational cost
    latency_ms: float = 100.0  # Expected latency
    reliability: float = 0.9  # Expected success rate
    
    # Performance tracking
    success_count: int = 0
    failure_count: int = 0
    total_time_ms: float = 0.0
    
    def get_success_rate(self) -> float:
        """Get empirical success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return self.reliability
        return self.success_count / total
    
    def get_avg_latency(self) -> float:
        """Get empirical average latency."""
        if self.success_count == 0:
            return self.latency_ms
        return self.total_time_ms / max(1, self.success_count)


@dataclass
class ToolUseRecord:
    """Record of a tool usage."""
    
    tool_name: str
    timestamp: float
    inputs: Dict[str, Any]
    outputs: Optional[Any] = None
    success: bool = False
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class ToolRegistry:
    """
    Central registry of available tools.
    
    Manages tool discovery, selection, and performance tracking.
    """
    
    def __init__(self) -> None:
        """Initialize tool registry."""
        self._lock = threading.RLock()
        self.tools: Dict[str, ToolSpec] = {}
        self.tool_implementations: Dict[str, Callable] = {}
        self.usage_history: List[ToolUseRecord] = []
        
        logger.debug("ToolRegistry initialized")
    
    def register_tool(
        self,
        spec: ToolSpec,
        implementation: Callable
    ) -> None:
        """
        Register a tool.
        
        Args:
            spec: Tool specification
            implementation: Callable that executes tool
        """
        try:
            with self._lock:
                self.tools[spec.name] = spec
                self.tool_implementations[spec.name] = implementation
                logger.info(f"Tool registered: {spec.name}")
        except Exception as e:
            logger.error(f"Error registering tool {spec.name}: {e}")
    
    def get_tools_for_category(self, category: ToolCategory) -> List[ToolSpec]:
        """Get all tools in a category."""
        try:
            with self._lock:
                return [t for t in self.tools.values() if t.category == category]
        except Exception as e:
            logger.error(f"Error getting tools for category: {e}")
            return []
    
    def select_best_tool(
        self,
        goal: str,
        required_outputs: List[str],
        category: Optional[ToolCategory] = None
    ) -> Optional[ToolSpec]:
        """
        Smart tool selection based on goal and success history.
        
        Args:
            goal: Description of what we want to achieve
            required_outputs: Types of outputs needed
            category: Optional tool category filter
            
        Returns:
            Best tool for job or None
        """
        try:
            with self._lock:
                # Filter by category if specified
                candidates = self.tools.values()
                if category:
                    candidates = [t for t in candidates if t.category == category]
                
                if not candidates:
                    return None
                
                # Score each candidate
                scored = []
                for tool in candidates:
                    # Score based on success rate and latency
                    success_rate = tool.get_success_rate()
                    avg_latency = tool.get_avg_latency()
                    
                    # Prefer high success, low latency
                    score = (success_rate * 0.7) - (avg_latency / 1000.0 * 0.3)
                    scored.append((tool, score))
                
                if scored:
                    best_tool = max(scored, key=lambda x: x[1])[0]
                    logger.debug(f"Selected tool: {best_tool.name} for goal: {goal}")
                    return best_tool
                
                return None
                
        except Exception as e:
            logger.error(f"Error selecting best tool: {e}")
            return None
    
    def execute_tool(
        self,
        tool_name: str,
        inputs: Dict[str, Any]
    ) -> Tuple[bool, Optional[Any], Optional[str]]:
        """
        Execute a tool and track performance.
        
        Args:
            tool_name: Name of tool to execute
            inputs: Input arguments
            
        Returns:
            (success, outputs, error)
        """
        try:
            with self._lock:
                if tool_name not in self.tools:
                    return False, None, f"Tool not found: {tool_name}"
                
                tool_spec = self.tools[tool_name]
                implementation = self.tool_implementations[tool_name]
            
            # Execute tool
            start_time = time.time()
            try:
                outputs = implementation(**inputs)
                success = True
                error = None
                execution_time = (time.time() - start_time) * 1000
                
                # Update tool stats
                with self._lock:
                    tool_spec.success_count += 1
                    tool_spec.total_time_ms += execution_time
                
            except Exception as e:
                success = False
                outputs = None
                error = str(e)
                execution_time = (time.time() - start_time) * 1000
                
                with self._lock:
                    tool_spec.failure_count += 1
            
            # Record usage
            record = ToolUseRecord(
                tool_name=tool_name,
                timestamp=time.time(),
                inputs=inputs,
                outputs=outputs,
                success=success,
                execution_time_ms=execution_time,
                error=error
            )
            
            with self._lock:
                self.usage_history.append(record)
                if len(self.usage_history) > 10000:
                    self.usage_history.pop(0)
            
            logger.debug(f"Tool executed: {tool_name} → success={success}, time={execution_time:.1f}ms")
            return success, outputs, error
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return False, None, str(e)
    
    def get_most_used_tools(self, limit: int = 5) -> List[Tuple[str, int]]:
        """Get most frequently used tools."""
        try:
            with self._lock:
                usage_count = {}
                for record in self.usage_history:
                    usage_count[record.tool_name] = usage_count.get(record.tool_name, 0) + 1
                
                sorted_tools = sorted(usage_count.items(), key=lambda x: x[1], reverse=True)
                return sorted_tools[:limit]
                
        except Exception as e:
            logger.error(f"Error getting most used tools: {e}")
            return []
    
    def get_tool_statistics(self) -> Dict[str, Any]:
        """Get overall tool usage statistics."""
        try:
            with self._lock:
                total_uses = len(self.usage_history)
                successful = sum(1 for r in self.usage_history if r.success)
                
                avg_latency = 0
                if total_uses > 0:
                    avg_latency = sum(r.execution_time_ms for r in self.usage_history) / total_uses
                
                return {
                    "total_tool_uses": total_uses,
                    "successful_executions": successful,
                    "success_rate": successful / max(1, total_uses),
                    "average_latency_ms": avg_latency,
                    "registered_tools": len(self.tools),
                    "most_used": self.get_most_used_tools(3)
                }
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


# Builtin tools for common operations

def builtin_search(query: str) -> List[str]:
    """Search for information (stub)."""
    return [f"Result for: {query}"]


def builtin_compute(expression: str) -> float:
    """Evaluate mathematical expression (safe subset)."""
    # In real system, use safe_eval or symbolic math
    try:
        return float(eval(expression, {"__builtins__": {}}, {}))
    except:
        raise ValueError(f"Cannot evaluate: {expression}")


def builtin_retrieve_facts(topic: str) -> Dict[str, Any]:
    """Retrieve facts from semantic memory."""
    from core.memory.semantic import semantic
    results = semantic.search(topic, top_k=3)
    return {"topic": topic, "results": results}


# Global registry
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create global tool registry."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        
        # Register builtin tools
        _tool_registry.register_tool(
            ToolSpec(
                name="search",
                category=ToolCategory.SEARCH,
                description="Search for information online",
                required_inputs=["query"],
                output_type="list[str]",
                latency_ms=500.0
            ),
            builtin_search
        )
        
        _tool_registry.register_tool(
            ToolSpec(
                name="compute",
                category=ToolCategory.COMPUTE,
                description="Compute mathematical expressions",
                required_inputs=["expression"],
                output_type="float",
                latency_ms=10.0,
                reliability=0.95
            ),
            builtin_compute
        )
        
        _tool_registry.register_tool(
            ToolSpec(
                name="retrieve_facts",
                category=ToolCategory.QUERY,
                description="Retrieve facts from memory",
                required_inputs=["topic"],
                output_type="dict",
                latency_ms=50.0,
                reliability=0.99
            ),
            builtin_retrieve_facts
        )
    
    return _tool_registry
