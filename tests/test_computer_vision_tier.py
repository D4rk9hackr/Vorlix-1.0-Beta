"""Unit tests for ComputerVisionTier (mocked)."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_base import TierRequest, TierResult
from tiers.computer_vision_tier import ComputerVisionTier


class TestComputerVisionTier:
    def setup_method(self):
        self.tier = ComputerVisionTier()

    def test_unknown_tool_blocked(self):
        req = TierRequest(
            tool="cv.invalid",
            arguments={},
            reasoning="Testing unknown tool.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED, got {result.result}"

    def test_click_target_no_template_blocked(self):
        req = TierRequest(
            tool="computer_vision.click_target",
            arguments={},
            reasoning="Testing click without template.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED, got {result.result}"

    def test_track_target_no_template_blocked(self):
        req = TierRequest(
            tool="computer_vision.track_target",
            arguments={},
            reasoning="Testing track without template.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED, got {result.result}"

    def test_click_target_missing_deps_graceful(self):
        """If dependencies aren't installed, should return BLOCKED not crash."""
        req = TierRequest(
            tool="computer_vision.click_target",
            arguments={"template_image": "test.png", "confidence_threshold": 0.8},
            reasoning="Testing graceful missing dependency handling.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        # Either missing dependency (BLOCKED) or template not found (BLOCKED)
        assert result.result == TierResult.BLOCKED, f"Expected BLOCKED, got {result.result}"
