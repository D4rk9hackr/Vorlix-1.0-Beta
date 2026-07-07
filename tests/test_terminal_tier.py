"""Unit tests for TerminalTier."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_base import TierRequest, TierResult
from tiers.terminal_tier import TerminalTier


class TestTerminalTier:
    def setup_method(self):
        self.tier = TerminalTier()

    def test_successful_command(self):
        req = TierRequest(
            tool="terminal.run_command",
            arguments={"command": "echo hello", "execution_timeout_ms": 5000},
            reasoning="Testing command execution.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.SUCCESS, f"Expected SUCCESS, got {result.result}"
        assert "hello" in result.data.get("stdout", ""), f"Expected 'hello' in stdout, got {result.data}"

    def test_destructive_command_blocked(self):
        req = TierRequest(
            tool="terminal.run_command",
            arguments={"command": "rm -rf /", "execution_timeout_ms": 5000},
            reasoning="Testing destructive command block.",
            confidence=0.95,
        )
        assert not self.tier.is_within_guardrails(req), "Destructive command should be blocked by guardrails"

    def test_empty_command_blocked(self):
        req = TierRequest(
            tool="terminal.run_command",
            arguments={"command": ""},
            reasoning="Testing empty command.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED for empty command, got {result.result}"

    def test_timeout_handling(self):
        req = TierRequest(
            tool="terminal.run_command",
            arguments={"command": "sleep 10", "execution_timeout_ms": 500},
            reasoning="Testing timeout handling.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED for timeout, got {result.result}"
        assert "timed out" in result.message.lower(), f"Expected timeout message, got {result.message}"

    def test_unknown_tool_blocked(self):
        req = TierRequest(
            tool="terminal.unknown_tool",
            arguments={},
            reasoning="Testing unknown tool.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED for unknown tool, got {result.result}"

    def test_multiple_destructive_patterns(self):
        destructive_commands = [
            "rm -rf /*",
            "rm -rf ~",
            "format C:",
            "dd if=/dev/zero of=/dev/sda",
            "drop database testdb",
            ":(){ :|:& };:",
            "shutdown -s -t 0",
            "chmod -R 0 /",
            "mv /* /dev/null",
        ]
        for cmd in destructive_commands:
            req = TierRequest(
                tool="terminal.run_command",
                arguments={"command": cmd},
                reasoning="Testing destructive pattern.",
                confidence=0.95,
            )
            assert not self.tier.is_within_guardrails(req), f"Command should be blocked: {cmd}"
