"""Unit tests for SystemQueryTier."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_base import TierRequest, TierResult
from tiers.system_query_tier import SystemQueryTier


class TestSystemQueryTier:
    def setup_method(self):
        self.tier = SystemQueryTier()
        pass

    def test_unknown_tool_blocked(self):
        req = TierRequest(
            tool="system.invalid",
            arguments={},
            reasoning="Testing unknown tool.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED, got {result.result}"

    def test_window_focus_nonexistent_blocked(self):
        req = TierRequest(
            tool="window.focus",
            arguments={"title_contains": "__NONEXISTENT_WINDOW_ZZZ__"},
            reasoning="Testing focus on nonexistent window.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED for nonexistent window, got {result.result}"
        assert "No window found" in result.message or "not installed" in result.message, f"Expected block message, got {result.message}"

    def test_window_resize_no_title_blocked(self):
        req = TierRequest(
            tool="window.resize",
            arguments={"width": 800, "height": 600},
            reasoning="Testing resize without title.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED, got {result.result}"

    def test_process_list_missing_psutil(self):
        """If psutil is missing, process.list should return BLOCKED with helpful message."""
        req = TierRequest(
            tool="process.list",
            arguments={},
            reasoning="Testing process list without psutil.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        if not self.tier._psutil_available:
            assert result.result == TierResult.BLOCKED, f"Expected BLOCKED without psutil, got {result.result}"
        else:
            assert result.result == TierResult.SUCCESS, f"Expected SUCCESS with psutil, got {result.result}"
