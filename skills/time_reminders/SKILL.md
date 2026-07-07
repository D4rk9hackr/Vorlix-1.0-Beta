# Time Awareness

## Name
Time & Reminders

## Description
Provides the AI with knowledge of the current local time and the ability to schedule one-off or repeating reminders that fire system notifications. This tier is lightweight (no heavy dependencies) and operates entirely on local state.

## When to use it
- The AI needs to know what time it is before making a time-sensitive decision.
- The user asks to be reminded of something later.
- A workflow step needs a timed delay or a follow-up notification.

## Tools

### `time.now`
Returns the current date/time in the user's local timezone.

```json
{
  "tool": "time.now",
  "arguments": {}
}
```

Returns `{"iso": "2026-07-06T16:30:18+03:00", "timezone": "Africa/Cairo"}`.

### `reminder.create`
Schedules a one-off or repeating reminder that fires a system notification at the given time.

```json
{
  "tool": "reminder.create",
  "arguments": {
    "message": "string",
    "trigger_time": "ISO 8601 datetime string",
    "repeat": "none | daily | weekly",
    "days_of_week": "array of ints, 1-indexed from Sunday (only used if repeat=weekly)"
  }
}
```

- If `trigger_time` is in the past for a one-off reminder, returns `BLOCKED` with reason `"invalid trigger time"`.
- Respects `HumanOverride.is_overridden()` before creating new reminders.
- Logs every creation to `memory.md` using the request's `reasoning` field.

### `reminder.list`
Lists all currently scheduled reminders (not yet fired or repeating).

```json
{
  "tool": "reminder.list",
  "arguments": {}
}
```

### `reminder.cancel`
Cancels a scheduled reminder by ID.

```json
{
  "tool": "reminder.cancel",
  "arguments": {
    "reminder_id": "string"
  }
}
```

Returns `BLOCKED` if the ID does not exist (not an exception).

## Resource Cost
Lightweight. No heavy dependencies. Uses stdlib (`sched`, `threading`, `datetime`) plus one small platform notification helper (`notify-send` on Linux, `win10toast`/`plyer` on Windows, `osascript` on macOS, `termux-notification` on Termux). RAM footprint: <5 MB.

## Platform Support
| Platform | Notifications | Scheduler |
|----------|----------------|-----------|
| Linux    | `notify-send` or `plyer` | Background `threading.Timer` |
| Windows  | `win10toast` or `plyer`  | Background `threading.Timer` |
| macOS    | `osascript`              | Background `threading.Timer` |
| Termux   | `termux-notification`    | Background `threading.Timer` |
