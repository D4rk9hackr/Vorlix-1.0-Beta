"""Time Awareness tier — time.now, reminder.create, reminder.list, reminder.cancel."""
import asyncio
import json
import os
import platform
import subprocess
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.tier_base import AgenticAutomationTier, TierRequest, TierResponse, TierResult
from core.human_override import HumanOverride
from core.ledger import Ledger


class TimeRemindersTier(AgenticAutomationTier):
    """Lightweight time awareness and reminder scheduling tier."""

    def __init__(self, workspace_dir: str = "./workspace"):
        super().__init__("TimeRemindersTier")
        self.workspace_dir = workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)
        self.reminders_path = os.path.join(workspace_dir, "reminders.json")
        self.ledger = Ledger(workspace_dir)
        self.human_override = HumanOverride()
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._load_and_reschedule()

    # ------------------------------------------------------------------
    # Platform notification helpers
    # ------------------------------------------------------------------
    def _notify(self, message: str) -> bool:
        """Fire a system notification. Returns True if a notifier was found."""
        system = platform.system()
        try:
            if system == "Linux":
                # Try notify-send first, then plyer
                try:
                    subprocess.run(
                        ["notify-send", "Vorlix Reminder", message],
                        check=True, capture_output=True, timeout=5,
                    )
                    return True
                except (FileNotFoundError, subprocess.CalledProcessError):
                    pass
                try:
                    from plyer import notification
                    notification.notify(title="Vorlix Reminder", message=message, timeout=10)
                    return True
                except Exception:
                    pass

            elif system == "Windows":
                try:
                    from win10toast import ToastNotifier
                    ToastNotifier().show_toast("Vorlix Reminder", message, duration=10)
                    return True
                except Exception:
                    pass
                try:
                    from plyer import notification
                    notification.notify(title="Vorlix Reminder", message=message, timeout=10)
                    return True
                except Exception:
                    pass

            elif system == "Darwin":  # macOS
                script = f'display notification "{message}" with title "Vorlix Reminder"'
                subprocess.run(
                    ["osascript", "-e", script],
                    check=True, capture_output=True, timeout=5,
                )
                return True

            elif system == "Linux" and os.environ.get("TERMUX_VERSION"):
                # Termux
                subprocess.run(
                    ["termux-notification", "--title", "Vorlix Reminder", "--content", message],
                    check=True, capture_output=True, timeout=5,
                )
                return True

        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_reminders(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.reminders_path):
            return []
        try:
            with open(self.reminders_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _save_reminders(self, reminders: List[Dict[str, Any]]) -> None:
        with open(self.reminders_path, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=2)

    def _load_and_reschedule(self) -> None:
        """On startup, re-register any future reminders."""
        reminders = self._load_reminders()
        now = datetime.now(timezone.utc)
        kept = []
        for r in reminders:
            trigger = datetime.fromisoformat(r["trigger_time"])
            if trigger > now:
                self._schedule(r)
                kept.append(r)
            elif r.get("repeat") != "none":
                # Re-calculate next occurrence for repeating reminders
                next_trigger = self._next_occurrence(trigger, r.get("repeat"), r.get("days_of_week", []))
                if next_trigger and next_trigger > now:
                    r["trigger_time"] = next_trigger.isoformat()
                    self._schedule(r)
                    kept.append(r)
        self._save_reminders(kept)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------
    def _next_occurrence(self, last: datetime, repeat: str, days_of_week: List[int]) -> Optional[datetime]:
        """Calculate the next trigger time for a repeating reminder."""
        if repeat == "daily":
            return last + timedelta(days=1)
        elif repeat == "weekly":
            if not days_of_week:
                return last + timedelta(weeks=1)
            # days_of_week: 1=Sunday, 2=Monday, ... 7=Saturday
            current_dow = last.isoweekday() % 7 + 1  # Convert to 1=Sunday format
            sorted_days = sorted(days_of_week)
            # Find next day
            for d in sorted_days:
                if d > current_dow:
                    delta = d - current_dow
                    return last + timedelta(days=delta)
            # Wrap around to first day of next week
            delta = (7 - current_dow) + sorted_days[0]
            return last + timedelta(days=delta)
        return None

    def _schedule(self, reminder: Dict[str, Any]) -> None:
        """Schedule a background timer for a reminder."""
        rid = reminder["id"]
        trigger = datetime.fromisoformat(reminder["trigger_time"])
        now = datetime.now(timezone.utc)
        delay = max(0, (trigger - now).total_seconds())

        def _fire():
            self._notify(reminder["message"])
            # Handle repeat
            if reminder.get("repeat") != "none":
                next_trigger = self._next_occurrence(
                    trigger, reminder["repeat"], reminder.get("days_of_week", [])
                )
                if next_trigger:
                    reminder["trigger_time"] = next_trigger.isoformat()
                    self._schedule(reminder)
                    with self._lock:
                        current = self._load_reminders()
                        for i, r in enumerate(current):
                            if r["id"] == rid:
                                current[i] = dict(reminder)
                                break
                        self._save_reminders(current)
            else:
                # Remove one-off reminder
                with self._lock:
                    current = self._load_reminders()
                    current = [r for r in current if r["id"] != rid]
                    self._save_reminders(current)

        timer = threading.Timer(delay, _fire)
        timer.daemon = True
        timer.start()
        with self._lock:
            self._timers[rid] = timer

    def _cancel_timer(self, rid: str) -> None:
        with self._lock:
            timer = self._timers.pop(rid, None)
            if timer:
                timer.cancel()

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------
    async def execute(self, request: TierRequest) -> TierResponse:
        tool = request.tool
        args = request.arguments

        if tool == "time.now":
            return self._time_now(args)
        elif tool == "reminder.create":
            return self._reminder_create(args, request.reasoning)
        elif tool == "reminder.list":
            return self._reminder_list(args)
        elif tool == "reminder.cancel":
            return self._reminder_cancel(args)
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unknown tool: {tool}",
            )

    def _time_now(self, args: dict) -> TierResponse:
        now = datetime.now().astimezone()
        return TierResponse(
            result=TierResult.SUCCESS,
            data={
                "iso": now.isoformat(),
                "timezone": str(now.tzinfo),
            },
            message="Current local time retrieved.",
        )

    def _reminder_create(self, args: dict, reasoning: str) -> TierResponse:
        # Human override check
        if self.human_override.is_overridden():
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Human override is active — cannot create reminders while frozen.",
            )

        message = args.get("message", "").strip()
        trigger_time_str = args.get("trigger_time", "").strip()
        repeat = args.get("repeat", "none")
        days_of_week = args.get("days_of_week", [])

        if not message:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Missing required argument: message",
            )

        if not trigger_time_str:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Missing required argument: trigger_time",
            )

        try:
            trigger_time = datetime.fromisoformat(trigger_time_str)
        except ValueError:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Invalid trigger_time format. Use ISO 8601.",
            )

        # Ensure timezone-aware
        if trigger_time.tzinfo is None:
            trigger_time = trigger_time.replace(tzinfo=datetime.now().astimezone().tzinfo)

        now = datetime.now(timezone.utc)
        if repeat == "none" and trigger_time <= now:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="invalid trigger time",
            )

        rid = str(uuid.uuid4())
        reminder = {
            "id": rid,
            "message": message,
            "trigger_time": trigger_time.isoformat(),
            "repeat": repeat,
            "days_of_week": days_of_week,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist
        reminders = self._load_reminders()
        reminders.append(reminder)
        self._save_reminders(reminders)

        # Schedule
        self._schedule(reminder)

        # Log to memory.md
        self.ledger.write_memory(
            current_thought=f"Scheduled reminder '{message}' for {trigger_time.isoformat()} (reasoning: {reasoning})",
            blockers="None",
            recovery_route=f"Reminder will fire at {trigger_time.isoformat()}. Cancel with reminder.cancel if needed.",
        )

        return TierResponse(
            result=TierResult.SUCCESS,
            data={"reminder_id": rid, "scheduled_for": trigger_time.isoformat()},
            message=f"Reminder scheduled: {message} at {trigger_time.isoformat()}",
        )

    def _reminder_list(self, args: dict) -> TierResponse:
        reminders = self._load_reminders()
        return TierResponse(
            result=TierResult.SUCCESS,
            data=reminders,
            message=f"{len(reminders)} reminder(s) scheduled.",
        )

    def _reminder_cancel(self, args: dict) -> TierResponse:
        rid = args.get("reminder_id", "").strip()
        if not rid:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Missing required argument: reminder_id",
            )

        reminders = self._load_reminders()
        found = any(r["id"] == rid for r in reminders)
        if not found:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"No reminder found with id: {rid}",
            )

        self._cancel_timer(rid)
        reminders = [r for r in reminders if r["id"] != rid]
        self._save_reminders(reminders)

        return TierResponse(
            result=TierResult.SUCCESS,
            data={"cancelled_id": rid},
            message=f"Reminder {rid} cancelled.",
        )
