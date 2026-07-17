"""Orchestrator — routes TierRequests through registered tiers.

Agentic: the orchestrator can spawn sub-agents, run parallel dispatches,
and auto-decompose complex goals into multi-agent workflows.
"""
import asyncio
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.tier_base import (
    AutomationTier,
    TierRequest,
    TierResponse,
    TierResult,
    HumanHelpRequired,
)
from core.ledger import Ledger
from core.human_override import HumanOverride


class SubAgent:
    """A lightweight sub-agent spawned by the orchestrator.

    Runs a goal by breaking it into tool calls and dispatching through
    the parent orchestrator. Sub-agents can themselves spawn sub-agents.
    """

    def __init__(self, agent_id: str, goal: str, tools: List[str],
                 orchestrator: 'Orchestrator', parent_id: Optional[str] = None):
        self.id = agent_id
        self.goal = goal
        self.tools = tools
        self._orch = orchestrator
        self.parent_id = parent_id
        self.status = "spawned"
        self.result: Any = None
        self.error: Optional[str] = None
        self._log: List[str] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: Optional[str] = None

    def log(self, entry: str):
        self._log.append(f"[{datetime.now(timezone.utc).isoformat()}] {entry}")

    async def run(self):
        self.status = "running"
        self.log(f"Goal: {self.goal[:200]}")
        allowed = set(self.tools) if self.tools != ["*"] else None
        try:
            self.result = await self._execute(self.goal, allowed)
            self.status = "completed"
            self.completed_at = datetime.now(timezone.utc).isoformat()
            self.log(f"Done: {str(self.result)[:300]}")
        except Exception as e:
            self.error = str(e)
            self.status = "failed"
            self.completed_at = datetime.now(timezone.utc).isoformat()
            self.log(f"Failed: {e}")

    async def _execute(self, goal: str, allowed: Optional[set]) -> list:
        results = []
        for line in goal.split("\n"):
            line = line.strip()
            if not line:
                continue
            tokens = line.split()
            tool = tokens[0] if tokens else ""
            if allowed and tool not in allowed:
                self.log(f"Skipping {tool} — not in allowed set")
                continue
            args = {}
            i = 1
            while i < len(tokens):
                t = tokens[i]
                if t.startswith("--") and i + 1 < len(tokens):
                    args[t[2:]] = tokens[i + 1]
                    i += 2
                elif "=" in t:
                    k, v = t.split("=", 1)
                    args[k] = v
                    i += 1
                else:
                    i += 1
            req = TierRequest(
                tool=tool, arguments=args,
                reasoning=f"Sub-agent {self.id}: {goal[:100]}",
                confidence=1.0,
            )
            r = await self._orch.dispatch(req)
            entry = {"tool": tool}
            if isinstance(r, TierResponse):
                entry["status"] = r.result.name
                entry["message"] = r.message
                entry["data"] = r.data
                if r.result in (TierResult.FAILED, TierResult.BLOCKED):
                    self.log(f"{tool} → {r.result.name}: {r.message}")
                    results.append(entry)
                    break
            else:
                entry["status"] = "NEEDS_HUMAN"
                entry["message"] = str(r)
                results.append(entry)
                break
            results.append(entry)
        return results

    def to_dict(self) -> dict:
        return {
            "id": self.id, "goal": self.goal[:200], "tools": self.tools,
            "status": self.status, "error": self.error,
            "parent_id": self.parent_id,
            "log": self._log[-5:], "created_at": self.created_at,
            "completed_at": self.completed_at, "result": self.result,
        }


class Orchestrator:
    """Routes requests to tiers. Now agentic: spawns sub-agents, parallel dispatch, goal decomposition."""

    def __init__(
        self,
        tiers: Optional[List[AutomationTier]] = None,
        max_retries_per_tier: int = 3,
        min_confidence: float = 0.7,
        max_agents: int = 10,
    ):
        self.tiers = tiers or []
        self.max_retries_per_tier = max_retries_per_tier
        self.min_confidence = min_confidence
        self.ledger = Ledger()
        self.human_override = HumanOverride()
        self._recent_requests: deque = deque(maxlen=5)
        # Agentic runtime
        self._max_agents = max_agents
        self._agents: Dict[str, SubAgent] = {}

    def register_tier(self, tier: AutomationTier) -> None:
        self.tiers.append(tier)
        # Auto-bind agentic tiers to this orchestrator
        if hasattr(tier, 'bind_orchestrator'):
            tier.bind_orchestrator(self)

    # ------------------------------------------------------------------
    # Standard dispatch (unchanged)
    # ------------------------------------------------------------------

    async def dispatch(self, request: TierRequest) -> TierResponse | HumanHelpRequired:
        # Agentic goal — auto-decompose into sub-agents
        if request.tool == "agentic.goal":
            goal = request.arguments.get("goal", request.reasoning)
            tools_raw = request.arguments.get("tools")
            tools = [t.strip() for t in tools_raw.split(",") if t.strip()] if tools_raw else None
            return await self.agentic_dispatch(goal, tools)

        if self.human_override.is_overridden():
            return HumanHelpRequired(
                reason="Human override is active — all automation frozen.",
                memory_snapshot=self.ledger.read_memory(),
                ai_suggestion="Wait for the human to resume or provide manual input.",
                todo_resume_point=request.tool,
            )

        # Loop detection
        signature = (request.tool, str(sorted(request.arguments.items())))
        if list(self._recent_requests).count(signature) >= 2:
            self.ledger.write_memory(
                current_thought=f"Loop detected: repeated identical request for {request.tool}",
                blockers="Infinite loop detected — same request signature seen 3+ times",
                recovery_route="Escalating to human to break the loop.",
            )
            self.ledger.add_todo(f"Loop detected on {request.tool} — human review required.")
            return HumanHelpRequired(
                reason=f"Repeated identical request detected ({request.tool}) — stopping before an infinite loop.",
                memory_snapshot=self.ledger.read_memory(),
                ai_suggestion="This exact action has been attempted multiple times with no progress. Try a different approach, or ask the human directly.",
                todo_resume_point=request.tool,
            )
        self._recent_requests.append(signature)

        # Reasoning gate
        if not request.reasoning.strip():
            self.ledger.write_memory(
                current_thought=f"Request rejected for {request.tool}: no reasoning provided.",
                blockers="Missing required reasoning string.",
                recovery_route="Resubmit with reasoning explaining the intent.",
            )
            self.ledger.add_todo(f"Rejected {request.tool}: missing reasoning.")
            return HumanHelpRequired(
                reason="Request rejected: no reasoning provided. Every action must state why it's being taken.",
                memory_snapshot=self.ledger.read_memory(),
                ai_suggestion="Resubmit the request with a `reasoning` string explaining the intent.",
                todo_resume_point=request.tool,
            )

        if request.confidence < self.min_confidence:
            self.ledger.write_memory(
                current_thought=f"Request for {request.tool} rejected: confidence {request.confidence:.2f} below threshold {self.min_confidence:.2f}",
                blockers=f"Confidence too low ({request.confidence:.2f}) for '{request.tool}'",
                recovery_route="Human confirmation required before proceeding.",
            )
            self.ledger.add_todo(f"Low confidence on {request.tool}: human confirmation needed.")
            return HumanHelpRequired(
                reason=f"Confidence too low ({request.confidence:.2f}) for '{request.tool}' — asking before acting.",
                memory_snapshot=self.ledger.read_memory(),
                ai_suggestion=f"Intended action: {request.reasoning}. Confirm before proceeding.",
                todo_resume_point=request.tool,
            )

        # Try tiers in order
        for tier in self.tiers:
            if not tier.is_within_guardrails(request):
                self.ledger.write_memory(
                    current_thought=f"Guardrail blocked {request.tool} in {tier.name}",
                    blockers=f"Guardrail violation in {tier.name}",
                    recovery_route="Escalating to human — this request violates safety guardrails.",
                )
                self.ledger.add_todo(f"Guardrail block on {request.tool} in {tier.name}")
                return HumanHelpRequired(
                    reason=f"Guardrail blocked {request.tool} in {tier.name}",
                    memory_snapshot=self.ledger.read_memory(),
                    ai_suggestion="This request violates safety guardrails. Review and resubmit with a safe alternative.",
                    todo_resume_point=request.tool,
                )

            effective_retries = min(request.max_retries, self.max_retries_per_tier)
            for attempt in range(effective_retries):
                try:
                    result = await tier.execute(request)
                except Exception as exc:
                    self.ledger.write_memory(
                        current_thought=f"{tier.name} raised an unexpected exception: {exc!r}",
                        blockers=f"Unhandled exception in {tier.name}",
                        recovery_route="Escalating to human - this is a bug, not an expected failure.",
                    )
                    self.ledger.add_todo(f"Exception in {tier.name}: {exc}")
                    return HumanHelpRequired(
                        reason=f"{tier.name} raised an unexpected exception: {exc}",
                        memory_snapshot=self.ledger.read_memory(),
                        ai_suggestion="This looks like a bug in the tier implementation, not a normal failure. Check logs.",
                        todo_resume_point=request.tool,
                    )

                if result.result == TierResult.SUCCESS:
                    return result
                elif result.result == TierResult.FAILED:
                    self.ledger.write_memory(
                        current_thought=f"{tier.name} returned FAILED for {request.tool}",
                        blockers=result.message,
                        recovery_route="Try next tier or escalate to human.",
                    )
                    self.ledger.add_todo(f"FAILED from {tier.name} for {request.tool}: {result.message}")
                    break
                elif result.result == TierResult.NEEDS_HUMAN:
                    self.ledger.write_memory(
                        current_thought=f"{tier.name} returned NEEDS_HUMAN for {request.tool}",
                        blockers=result.message,
                        recovery_route="Escalating to human — tier explicitly requested human intervention.",
                    )
                    self.ledger.add_todo(f"NEEDS_HUMAN from {tier.name} for {request.tool}: {result.message}")
                    return HumanHelpRequired(
                        reason=result.message,
                        memory_snapshot=self.ledger.read_memory(),
                        ai_suggestion="The tier explicitly requested human intervention. Review the situation.",
                        todo_resume_point=request.tool,
                    )
                elif result.result == TierResult.BLOCKED:
                    self.ledger.write_memory(
                        current_thought=f"{tier.name} returned BLOCKED for {request.tool}",
                        blockers=result.message,
                        recovery_route="Try next tier or escalate to human.",
                    )
                    self.ledger.add_todo(f"BLOCKED from {tier.name} for {request.tool}: {result.message}")
                    break
                elif result.result == TierResult.RETRY:
                    continue
            else:
                self.ledger.write_memory(
                    current_thought=f"Retries exhausted for {request.tool} in {tier.name}",
                    blockers=f"All {effective_retries} attempts failed in {tier.name}",
                    recovery_route="Escalating to human — tier exhausted all retries.",
                )
                self.ledger.add_todo(f"Retries exhausted for {request.tool} in {tier.name}")
                return HumanHelpRequired(
                    reason=f"Retries exhausted for {request.tool} in {tier.name}",
                    memory_snapshot=self.ledger.read_memory(),
                    ai_suggestion="All retry attempts failed. Review the tier logs and consider manual intervention.",
                    todo_resume_point=request.tool,
                )

        self.ledger.write_memory(
            current_thought=f"All tiers exhausted for {request.tool}",
            blockers="No tier could handle the request.",
            recovery_route="Escalating to human — no tier available or capable.",
        )
        self.ledger.add_todo(f"All tiers exhausted for {request.tool}")
        return HumanHelpRequired(
            reason=f"All tiers exhausted for {request.tool}",
            memory_snapshot=self.ledger.read_memory(),
            ai_suggestion="No tier was able to handle this request. Check if the required skill is activated.",
            todo_resume_point=request.tool,
        )

    # ==================================================================
    # Agentic capabilities
    # ==================================================================

    def spawn_agent(self, goal: str, tools: Optional[List[str]] = None,
                    parent_id: Optional[str] = None) -> SubAgent:
        """Spawn a sub-agent bound to this orchestrator."""
        if len(self._agents) >= self._max_agents:
            raise RuntimeError(f"Max agents ({self._max_agents}) reached")
        agent_id = str(uuid.uuid4())[:8]
        agent = SubAgent(agent_id, goal, tools or ["*"], self, parent_id=parent_id)
        self._agents[agent_id] = agent
        # Start the agent if an event loop is running (usually True in async dispatch)
        try:
            asyncio.create_task(agent.run())
        except RuntimeError:
            # No running event loop (sync test context) — agent stays "spawned"
            pass
        return agent

    async def parallel_dispatch(self, requests: List[TierRequest]) -> List[TierResponse | HumanHelpRequired]:
        """Dispatch multiple requests concurrently."""
        return await asyncio.gather(*[self.dispatch(r) for r in requests])

    async def agentic_dispatch(self, goal: str, tools: Optional[List[str]] = None) -> TierResponse:
        """Auto-decompose a complex goal into sub-agents and collect results.

        Splits the goal by newlines or ';' into sub-tasks, spawns a sub-agent
        for each, waits for all to complete, and returns synthesized results.
        """
        if not goal.strip():
            return TierResponse(result=TierResult.BLOCKED, message="Empty goal")

        # Split into sub-tasks
        sub_tasks = []
        for part in goal.replace(";", "\n").split("\n"):
            part = part.strip()
            if part:
                sub_tasks.append(part)

        if len(sub_tasks) == 1:
            # Single task — spawn one agent
            agent = self.spawn_agent(sub_tasks[0], tools)
            agent_id = agent.id
        else:
            # Multiple sub-tasks — spawn one agent per sub-task
            agents = []
            for task in sub_tasks:
                agent = self.spawn_agent(task, tools)
                agents.append(agent.id)

        # Collect results
        async def _wait_for(aid: str):
            agent = self._agents.get(aid)
            if not agent:
                return
            while agent.status in ("spawned", "running"):
                await asyncio.sleep(0.1)

        if len(sub_tasks) == 1:
            await _wait_for(agent_id)
            agent = self._agents[agent_id]
            return TierResponse(
                result=TierResult.SUCCESS if agent.status == "completed" else TierResult.FAILED,
                data=agent.to_dict(),
                message=f"Goal {'completed' if agent.status == 'completed' else 'failed'}: {agent.error or ''}",
            )
        else:
            await asyncio.gather(*[_wait_for(aid) for aid in agents])
            results = [self._agents[aid].to_dict() for aid in agents]
            all_ok = all(r["status"] == "completed" for r in results)
            return TierResponse(
                result=TierResult.SUCCESS if all_ok else TierResult.FAILED,
                data={"sub_agents": results},
                message=f"{sum(1 for r in results if r['status'] == 'completed')}/{len(results)} sub-tasks completed",
            )

    def list_agents(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """List spawned sub-agents."""
        if agent_id:
            agent = self._agents.get(agent_id)
            return agent.to_dict() if agent else {"error": f"Agent {agent_id} not found"}
        return {
            "count": len(self._agents),
            "max": self._max_agents,
            "agents": [a.to_dict() for a in self._agents.values()],
        }

    def kill_agent(self, agent_id: str) -> bool:
        """Remove a sub-agent."""
        return self._agents.pop(agent_id, None) is not None
