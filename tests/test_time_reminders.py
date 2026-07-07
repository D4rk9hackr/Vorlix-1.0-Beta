"""Unit tests for TimeRemindersTier."""
import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_base import TierRequest, TierResult
from tiers.time_reminders_tier import TimeRemindersTier


class TestTimeRemindersTier(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tier = TimeRemindersTier(workspace_dir=self.tmpdir)

    def tearDown(self):
        # Cancel all timers
        for timer in list(self.tier._timers.values()):
            timer.cancel()
        # Clean up files
        for f in ["reminders.json", "memory.md", "todo.md"]:
            path = os.path.join(self.tmpdir, f)
            if os.path.exists(path):
                os.remove(path)
        os.rmdir(self.tmpdir)

    # --- Test 1: time.now returns valid ISO string ---
    def test_time_now_returns_iso(self):
        req = TierRequest(
            tool="time.now",
            arguments={},
            reasoning="Testing time.now returns a valid ISO datetime.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        self.assertEqual(result.result, TierResult.SUCCESS)
        self.assertIn("iso", result.data)
        self.assertIn("timezone", result.data)
        # Verify ISO format is parseable
        parsed = datetime.fromisoformat(result.data["iso"])
        self.assertIsInstance(parsed, datetime)
        print(f"  time.now -> {result.data['iso']} ({result.data['timezone']})")

    # --- Test 2: reminder.create with past trigger_time returns BLOCKED ---
    def test_reminder_create_past_time_blocked(self):
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        req = TierRequest(
            tool="reminder.create",
            arguments={
                "message": "This should be blocked",
                "trigger_time": past_time,
                "repeat": "none",
            },
            reasoning="Testing that past trigger times are rejected.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        self.assertEqual(result.result, TierResult.BLOCKED)
        self.assertEqual(result.message, "invalid trigger time")
        print(f"  Past reminder correctly BLOCKED: {result.message}")

    # --- Test 3: reminder.cancel on nonexistent id returns BLOCKED not exception ---
    def test_reminder_cancel_nonexistent_blocked(self):
        req = TierRequest(
            tool="reminder.cancel",
            arguments={"reminder_id": "does-not-exist-12345"},
            reasoning="Testing cancel on nonexistent ID returns BLOCKED.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        self.assertEqual(result.result, TierResult.BLOCKED)
        self.assertIn("No reminder found", result.message)
        print(f"  Nonexistent cancel correctly BLOCKED: {result.message}")

    # --- Test 4: reminder.create + reminder.list + reminder.cancel round-trip ---
    def test_reminder_round_trip(self):
        future_time = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        # Create
        create_req = TierRequest(
            tool="reminder.create",
            arguments={
                "message": "Test reminder",
                "trigger_time": future_time,
                "repeat": "none",
            },
            reasoning="Testing full reminder lifecycle.",
            confidence=0.95,
        )
        create_result = asyncio.run(self.tier.execute(create_req))
        self.assertEqual(create_result.result, TierResult.SUCCESS)
        rid = create_result.data["reminder_id"]
        print(f"  Created reminder: {rid}")

        # List
        list_req = TierRequest(
            tool="reminder.list",
            arguments={},
            reasoning="Listing reminders to verify creation.",
            confidence=0.95,
        )
        list_result = asyncio.run(self.tier.execute(list_req))
        self.assertEqual(list_result.result, TierResult.SUCCESS)
        self.assertEqual(len(list_result.data), 1)
        self.assertEqual(list_result.data[0]["id"], rid)
        print(f"  Listed {len(list_result.data)} reminder(s)")

        # Cancel
        cancel_req = TierRequest(
            tool="reminder.cancel",
            arguments={"reminder_id": rid},
            reasoning="Cancelling the test reminder.",
            confidence=0.95,
        )
        cancel_result = asyncio.run(self.tier.execute(cancel_req))
        self.assertEqual(cancel_result.result, TierResult.SUCCESS)
        print(f"  Cancelled reminder: {rid}")

        # Verify list is empty
        list_result2 = asyncio.run(self.tier.execute(list_req))
        self.assertEqual(len(list_result2.data), 0)
        print(f"  Verified list is empty after cancel")

    # --- Test 5: HumanOverride blocks reminder creation ---
    def test_human_override_blocks_creation(self):
        self.tier.human_override.freeze()
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        req = TierRequest(
            tool="reminder.create",
            arguments={
                "message": "Should be blocked by override",
                "trigger_time": future_time,
                "repeat": "none",
            },
            reasoning="Testing HumanOverride blocks reminder creation.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        self.assertEqual(result.result, TierResult.BLOCKED)
        self.assertIn("Human override", result.message)
        self.tier.human_override.resume()
        print(f"  HumanOverride correctly blocked creation: {result.message}")

    # --- Test 6: Memory.md is written on reminder creation ---
    def test_memory_written_on_create(self):
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        req = TierRequest(
            tool="reminder.create",
            arguments={
                "message": "Memory test reminder",
                "trigger_time": future_time,
                "repeat": "none",
            },
            reasoning="Testing that creation is logged to memory.md.",
            confidence=0.95,
        )
        asyncio.run(self.tier.execute(req))
        memory = self.tier.ledger.read_memory()
        self.assertIn("Memory test reminder", memory)
        self.assertIn("Scheduled reminder", memory)
        print(f"  memory.md contains creation log: OK")

    # --- Test 7: Repeating weekly reminder with days_of_week ---
    def test_weekly_reminder(self):
        # Schedule for next Monday at 9 AM
        now = datetime.now(timezone.utc)
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = now + timedelta(days=days_until_monday)
        next_monday = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)

        req = TierRequest(
            tool="reminder.create",
            arguments={
                "message": "Weekly Monday reminder",
                "trigger_time": next_monday.isoformat(),
                "repeat": "weekly",
                "days_of_week": [2],  # Monday = 2 (1=Sunday)
            },
            reasoning="Testing weekly repeating reminder.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        self.assertEqual(result.result, TierResult.SUCCESS)
        print(f"  Weekly reminder scheduled for {next_monday.isoformat()}: OK")


if __name__ == "__main__":
    unittest.main(verbosity=2)
