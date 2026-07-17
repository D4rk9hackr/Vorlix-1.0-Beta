"""Team Agent tier — sub-agent interface for multi-agent collaboration.

Thin layer over the orchestrator's native agentic runtime. Every agent
spawned here shares the orchestrator's global agent pool, so agents can
be spawned from any tier, the CLI, or the Telegram bot interchangeably.

Tools:
  subagent.spawn   — spawn a sub-agent with a goal and optional tool filter
  subagent.ask     — delegate a task to a running sub-agent
  subagent.list    — list all spawned sub-agents
  subagent.kill    — terminate a sub-agent
  subagent.collect — wait for sub-agent results
"""
import json
from typing import Optional

from core.tier_base import AgenticAutomationTier, TierRequest, TierResponse, TierResult
from core.orchestrator import Orchestrator, SubAgent


class TeamAgentTier(AgenticAutomationTier):
    """Sub-agent interface — uses the orchestrator's global agent pool."""

    def __init__(self, orchestrator: Optional[Orchestrator] = None):
        super().__init__("TeamAgentTier")
        self._orch = orchestrator or Orchestrator()

    def register_orchestrator(self, orch: Orchestrator):
        self._orch = orch

    def bind_orchestrator(self, orch: Orchestrator):
        self._orch = orch

    async def execute(self, request: TierRequest) -> TierResponse:
        tool = request.tool
        args = request.arguments

        if tool == "subagent.spawn":
            return await self._spawn(args, request.reasoning)
        elif tool == "subagent.ask":
            return await self._ask(args)
        elif tool == "subagent.list":
            return self._list(args)
        elif tool == "subagent.kill":
            return await self._kill(args)
        elif tool == "subagent.collect":
            return await self._collect(args)
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unknown tool: {tool}",
            )

    async def _spawn(self, args: dict, reasoning: str) -> TierResponse:
        goal = args.get("goal", "").strip()
        tools_raw = args.get("tools", "*")
        if not goal:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Missing required argument: goal",
            )

        if isinstance(tools_raw, str):
            tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
        elif isinstance(tools_raw, list):
            tools = tools_raw
        else:
            tools = ["*"]

        try:
            agent = self._orch.spawn_agent(goal, tools if tools != ["*"] else None)
            return TierResponse(
                result=TierResult.SUCCESS,
                data=agent.to_dict(),
                message=f"Sub-agent {agent.id} spawned",
            )
        except RuntimeError as e:
            return TierResponse(result=TierResult.BLOCKED, message=str(e))

    async def _ask(self, args: dict) -> TierResponse:
        agent_id = args.get("agent_id", "").strip()
        task = args.get("task", "").strip()
        if not agent_id:
            return TierResponse(result=TierResult.BLOCKED, message="Missing agent_id")
        if not task:
            return TierResponse(result=TierResult.BLOCKED, message="Missing task")

        info = self._orch.list_agents(agent_id)
        if "error" in info:
            return TierResponse(result=TierResult.BLOCKED, message=info["error"])
        if info.get("status") == "completed":
            return TierResponse(result=TierResult.FAILED, message=f"Agent {agent_id} already completed")

        # Execute task through a fresh sub-agent call
        from core.tier_base import TierRequest as TR
        import asyncio
        req = TR(tool="orchestrator.run", arguments={}, reasoning=task, confidence=1.0)
        allowed = set(info.get("tools", [])) if info.get("tools") != ["*"] else None
        agent_obj = next((a for a in self._orch._agents.values() if a.id == agent_id), None)
        if agent_obj:
            result = await agent_obj._execute(task, allowed)
            return TierResponse(
                result=TierResult.SUCCESS,
                data={"agent_id": agent_id, "result": result},
            )
        return TierResponse(result=TierResult.BLOCKED, message=f"Agent {agent_id} not found in pool")

    def _list(self, args: dict) -> TierResponse:
        agent_id = args.get("agent_id", "").strip()
        data = self._orch.list_agents(agent_id) if agent_id else self._orch.list_agents()
        if isinstance(data, dict) and "error" in data:
            return TierResponse(result=TierResult.BLOCKED, message=data["error"])
        return TierResponse(result=TierResult.SUCCESS, data=data)

    async def _kill(self, args: dict) -> TierResponse:
        agent_id = args.get("agent_id", "").strip()
        if not agent_id:
            return TierResponse(result=TierResult.BLOCKED, message="Missing agent_id")
        ok = self._orch.kill_agent(agent_id)
        if not ok:
            return TierResponse(result=TierResult.BLOCKED, message=f"Agent {agent_id} not found")
        return TierResponse(result=TierResult.SUCCESS, data={"agent_id": agent_id})

    async def _collect(self, args: dict) -> TierResponse:
        agent_id = args.get("agent_id", "").strip()
        timeout = float(args.get("timeout", "30"))

        if agent_id:
            info = self._orch.list_agents(agent_id)
            if "error" in info:
                return TierResponse(result=TierResult.BLOCKED, message=info["error"])
            agents_to_wait = [agent_id]
        else:
            all_agents = self._orch.list_agents().get("agents", [])
            agents_to_wait = [a["id"] for a in all_agents if a["status"] in ("spawned", "running")]
            if not agents_to_wait:
                return TierResponse(
                    result=TierResult.SUCCESS,
                    data={"agents": all_agents},
                    message="No running agents",
                )

        import asyncio
        async def _wait(aid: str):
            while True:
                info = self._orch.list_agents(aid)
                if info.get("status") not in ("spawned", "running"):
                    return info
                await asyncio.sleep(0.1)

        try:
            await asyncio.wait_for(
                asyncio.gather(*[_wait(aid) for aid in agents_to_wait]),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            pass

        results = [self._orch.list_agents(aid) for aid in agents_to_wait]
        return TierResponse(
            result=TierResult.SUCCESS,
            data={"agents": results},
        )
