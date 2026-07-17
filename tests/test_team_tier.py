"""Tests for Team Agent tier — sub-agent spawning and management."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tiers.team_tier import TeamAgentTier
from core.tier_base import TierRequest, TierResponse, TierResult
from core.orchestrator import Orchestrator, SubAgent


class TestSubAgent:
    def test_sub_agent_initial_state(self):
        agent = SubAgent("test1", "do something", ["*"], Orchestrator())
        assert agent.id == "test1"
        assert agent.goal == "do something"
        assert agent.status == "spawned"
        assert agent.result is None

    def test_sub_agent_to_dict(self):
        agent = SubAgent("test2", "my goal", ["tool.a", "tool.b"], Orchestrator())
        d = agent.to_dict()
        assert d["id"] == "test2"
        assert d["tools"] == ["tool.a", "tool.b"]
        assert d["status"] == "spawned"

    def test_sub_agent_log(self):
        agent = SubAgent("test3", "goal", ["*"], Orchestrator())
        agent.log("hello")
        assert len(agent._log) == 1
        assert "hello" in agent._log[0]


def _run(coro):
    return asyncio.run(coro)


class TestTeamAgentTier:
    def test_spawn_requires_goal(self):
        tier = TeamAgentTier()
        req = TierRequest(tool="subagent.spawn", arguments={}, reasoning="test")
        result = _run(tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "goal" in result.message.lower()

    def test_spawn_no_goal(self):
        tier = TeamAgentTier()
        req = TierRequest(tool="subagent.spawn", arguments={"goal": ""}, reasoning="test")
        result = _run(tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_spawn_success(self):
        tier = TeamAgentTier()
        req = TierRequest(
            tool="subagent.spawn",
            arguments={"goal": "time.now", "tools": "*"},
            reasoning="test spawn",
        )
        result = _run(tier.execute(req))
        assert result.result == TierResult.SUCCESS
        assert "sub-agent" in result.message.lower()
        assert "id" in result.data

    def test_unknown_tool_blocked(self):
        tier = TeamAgentTier()
        req = TierRequest(tool="subagent.nonexistent", arguments={}, reasoning="test")
        result = _run(tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_max_agents_limit(self):
        orch = Orchestrator(max_agents=2)
        tier = TeamAgentTier(orchestrator=orch)
        for i in range(2):
            req = TierRequest(
                tool="subagent.spawn",
                arguments={"goal": "time.now", "tools": "*"},
                reasoning="test",
            )
            result = _run(tier.execute(req))
            assert result.result == TierResult.SUCCESS
        req = TierRequest(
            tool="subagent.spawn",
            arguments={"goal": "time.now", "tools": "*"},
            reasoning="test",
        )
        result = _run(tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "max" in result.message.lower()

    def test_list_agents(self):
        tier = TeamAgentTier()
        req = TierRequest(tool="subagent.list", arguments={}, reasoning="test")
        result = _run(tier.execute(req))
        assert result.result == TierResult.SUCCESS

    def test_kill_nonexistent(self):
        tier = TeamAgentTier()
        req = TierRequest(
            tool="subagent.kill",
            arguments={"agent_id": "nonexistent"},
            reasoning="test",
        )
        result = _run(tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_ask_nonexistent(self):
        tier = TeamAgentTier()
        req = TierRequest(
            tool="subagent.ask",
            arguments={"agent_id": "nonexistent", "task": "do something"},
            reasoning="test",
        )
        result = _run(tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_ask_missing_args(self):
        tier = TeamAgentTier()
        req = TierRequest(tool="subagent.ask", arguments={}, reasoning="test")
        result = _run(tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_collect_with_no_running_agents(self):
        tier = TeamAgentTier()
        req = TierRequest(tool="subagent.collect", arguments={}, reasoning="test")
        result = _run(tier.execute(req))
        assert result.result == TierResult.SUCCESS

    def test_spawn_then_list(self):
        """Spawn an agent then verify it appears in list."""
        tier = TeamAgentTier()
        req = TierRequest(
            tool="subagent.spawn",
            arguments={"goal": "time.now", "tools": "*"},
            reasoning="test",
        )
        result = _run(tier.execute(req))
        assert result.result == TierResult.SUCCESS
        agent_id = result.data["id"]

        list_req = TierRequest(tool="subagent.list", arguments={}, reasoning="test")
        list_result = _run(tier.execute(list_req))
        assert list_result.result == TierResult.SUCCESS
        ids = [a["id"] for a in list_result.data["agents"]]
        assert agent_id in ids

    def test_spawn_then_kill(self):
        """Spawn an agent then kill it."""
        tier = TeamAgentTier()
        req = TierRequest(
            tool="subagent.spawn",
            arguments={"goal": "time.now", "tools": "*"},
            reasoning="test",
        )
        result = _run(tier.execute(req))
        agent_id = result.data["id"]

        kill_req = TierRequest(
            tool="subagent.kill",
            arguments={"agent_id": agent_id},
            reasoning="test",
        )
        kill_result = _run(tier.execute(kill_req))
        assert kill_result.result == TierResult.SUCCESS


class TestAgenticOrchestrator:
    def test_spawn_agent(self):
        orch = Orchestrator()
        agent = orch.spawn_agent("time.now")
        assert agent.id is not None
        assert agent.status in ("spawned", "running")
        assert agent in orch._agents.values()

    def test_spawn_agent_max_limit(self):
        orch = Orchestrator(max_agents=1)
        orch.spawn_agent("time.now")
        import pytest
        with pytest.raises(RuntimeError, match="max|reached"):
            orch.spawn_agent("too many")

    def test_list_agents(self):
        orch = Orchestrator()
        info = orch.list_agents()
        assert "agents" in info
        assert info["count"] == 0

    def test_list_agents_with_spawned(self):
        orch = Orchestrator()
        orch.spawn_agent("time.now")
        info = orch.list_agents()
        assert info["count"] == 1

    def test_list_specific_agent(self):
        orch = Orchestrator()
        agent = orch.spawn_agent("time.now")
        info = orch.list_agents(agent.id)
        assert info["id"] == agent.id

    def test_kill_agent(self):
        orch = Orchestrator()
        agent = orch.spawn_agent("time.now")
        assert orch.kill_agent(agent.id) is True
        assert orch.kill_agent("nonexistent") is False

    def test_agentic_goal_tool(self):
        orch = Orchestrator()
        req = TierRequest(
            tool="agentic.goal",
            arguments={"goal": "time.now"},
            reasoning="test agentic goal",
        )
        result = _run(orch.dispatch(req))
        assert result.result == TierResult.SUCCESS

    def test_agentic_goal_empty(self):
        orch = Orchestrator()
        req = TierRequest(
            tool="agentic.goal",
            arguments={"goal": ""},
            reasoning="",
        )
        result = _run(orch.dispatch(req))
        assert result.result == TierResult.BLOCKED

    def test_agentic_goal_multiline(self):
        """Multi-line goal spawns multiple sub-agents."""
        orch = Orchestrator()
        goal = "time.now\ntime.now"
        req = TierRequest(
            tool="agentic.goal",
            arguments={"goal": goal},
            reasoning="multi-line test",
        )
        result = _run(orch.dispatch(req))
        assert result.result == TierResult.SUCCESS
        assert "sub_agents" in result.data
        assert len(result.data["sub_agents"]) == 2
