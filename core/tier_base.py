"""Base classes and types for Vorlix automation tiers.

Agentic: tiers now have built-in sub-agent spawning, delegation, and
parallel execution through AgenticAutomationTier.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.orchestrator import Orchestrator


class TierResult(Enum):
    SUCCESS = auto()
    FAILED = auto()
    BLOCKED = auto()
    NEEDS_HUMAN = auto()
    RETRY = auto()


@dataclass
class TierRequest:
    tool: str
    arguments: dict
    max_retries: int = 3
    reasoning: str = ""
    confidence: float = 1.0


@dataclass
class TierResponse:
    result: TierResult
    data: Any = None
    message: str = ""


@dataclass
class HumanHelpRequired:
    reason: str
    memory_snapshot: str
    ai_suggestion: str
    todo_resume_point: str


class AutomationTier:
    """Base class for all automation tiers."""

    def __init__(self, name: str):
        self.name = name

    async def execute(self, request: TierRequest) -> TierResponse:
        raise NotImplementedError("Subclasses must implement execute()")

    def is_within_guardrails(self, request: TierRequest) -> bool:
        """Return True if the request passes guardrail checks."""
        return True


class AgenticAutomationTier(AutomationTier):
    """Agentic tier — any tier can spawn sub-agents, delegate, and run parallel tasks.

    Usage:
        class MyTier(AgenticAutomationTier):
            def __init__(self):
                super().__init__("MyTier")

            async def execute(self, request):
                # Spawn a sub-agent inline
                agent = await self.spawn_agent("time.now")
                result = await self.collect(agent.id)
                ...
    """

    def __init__(self, name: str):
        super().__init__(name)
        self._orch_ref: Optional['Orchestrator'] = None

    def bind_orchestrator(self, orch: 'Orchestrator'):
        """Give this tier access to the orchestrator's agentic runtime."""
        self._orch_ref = orch

    async def spawn_agent(self, goal: str, tools: Optional[List[str]] = None) -> Any:
        """Spawn a sub-agent from within a tier. Returns the SubAgent."""
        if self._orch_ref is None:
            raise RuntimeError(
                "Tier has no orchestrator reference. Call bind_orchestrator() first, "
                "or pass an orchestrator to the constructor."
            )
        return self._orch_ref.spawn_agent(goal, tools, parent_id=self.name)

    async def parallel(self, requests: List[TierRequest]) -> List[TierResponse]:
        """Run multiple tool requests concurrently."""
        if self._orch_ref is None:
            raise RuntimeError("No orchestrator reference. Call bind_orchestrator() first.")
        from core.tier_base import TierResponse as TR
        results = await self._orch_ref.parallel_dispatch(requests)
        return [r if isinstance(r, TR) else TR(TierResult.NEEDS_HUMAN, message=str(r)) for r in results]

    async def delegate(self, tool: str, arguments: dict, reasoning: str = "") -> TierResponse:
        """Delegate a tool call to the orchestrator (goes through full dispatch)."""
        if self._orch_ref is None:
            raise RuntimeError("No orchestrator reference. Call bind_orchestrator() first.")
        req = TierRequest(tool=tool, arguments=arguments, reasoning=reasoning, confidence=1.0)
        result = await self._orch_ref.dispatch(req)
        if isinstance(result, TierResponse):
            return result
        return TierResponse(result=TierResult.NEEDS_HUMAN, message=str(result))

    async def collect(self, agent_id: str, timeout: float = 30) -> dict:
        """Wait for a sub-agent to complete and return its result."""
        if self._orch_ref is None:
            raise RuntimeError("No orchestrator reference.")
        async def _wait():
            while True:
                info = self._orch_ref.list_agents(agent_id)
                if info.get("status") not in ("spawned", "running"):
                    return info
                await asyncio.sleep(0.1)
        import asyncio
        try:
            return await asyncio.wait_for(_wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return self._orch_ref.list_agents(agent_id)
