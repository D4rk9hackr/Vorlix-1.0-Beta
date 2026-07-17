"""Unit tests for BrowserBridgeTier — CDP-based browser control."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_base import TierRequest, TierResult
from tiers.browser_bridge_tier import BrowserBridgeTier


class TestBrowserBridgeTier:
    """Tests BrowserBridgeTier without a running Chrome instance."""

    def setup_method(self):
        self.tier = BrowserBridgeTier()

    def test_unknown_tool_blocked(self):
        """Unknown tool should return BLOCKED."""
        req = TierRequest(
            tool="browser_bridge.invalid",
            arguments={},
            reasoning="Testing unknown tool.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "9222" in result.message or "unknown" in result.message.lower()

    def test_non_bridge_tool_blocked(self):
        """Tools not starting with browser_bridge. should be BLOCKED."""
        req = TierRequest(
            tool="terminal.run_command",
            arguments={},
            reasoning="Testing non-bridge tool.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_navigate_no_browser_graceful(self):
        """Without Chrome running, navigate should return BLOCKED with helpful message."""
        req = TierRequest(
            tool="browser_bridge.navigate",
            arguments={"url": "https://example.com"},
            reasoning="Testing graceful failure.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "9222" in result.message or "chrome" in result.message.lower()

    def test_click_by_text_no_browser_graceful(self):
        """Without Chrome running, click_by_text should return BLOCKED."""
        req = TierRequest(
            tool="browser_bridge.click_by_text",
            arguments={"text": "Submit"},
            reasoning="Testing graceful failure.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_fill_field_no_browser_graceful(self):
        """Without Chrome running, fill_field should return BLOCKED."""
        req = TierRequest(
            tool="browser_bridge.fill_field",
            arguments={"selector": "#input", "value": "hello"},
            reasoning="Testing graceful failure.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_get_text_no_browser_graceful(self):
        """Without Chrome running, get_text should return BLOCKED."""
        req = TierRequest(
            tool="browser_bridge.get_text",
            arguments={},
            reasoning="Testing graceful failure.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_screenshot_no_browser_graceful(self):
        """Without Chrome running, screenshot should return BLOCKED."""
        req = TierRequest(
            tool="browser_bridge.screenshot",
            arguments={},
            reasoning="Testing graceful failure.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_navigate_missing_url_blocked(self):
        """Navigate without URL should be BLOCKED before attempting connection."""
        req = TierRequest(
            tool="browser_bridge.navigate",
            arguments={},
            reasoning="Testing missing URL.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "url" in result.message.lower()

    def test_click_by_text_missing_arg_blocked(self):
        """Click by text without text argument should be BLOCKED."""
        req = TierRequest(
            tool="browser_bridge.click_by_text",
            arguments={},
            reasoning="Testing missing text.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "text" in result.message.lower()
