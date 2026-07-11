# Auto-Debugging & Environment Sync

## Name
Auto-Debugging & Environment Sync

## Description
After a terminal command fails (non-zero exit), this skill investigates root cause via read-only file inspection and proposes targeted fixes. No permissions beyond the existing Control Layer — every action is a normal TierRequest subject to confidence gates, guardrails, and human override.

## When to use it
- A terminal command returned a non-zero exit code and you need to diagnose why
- You need to read config files (.env, package.json, etc.) to understand the environment
- You have a hypothesis about the root cause and want to propose a fix
- You need to apply a targeted source-code patch with human confirmation

## Tools

### `file.read`
Read a text file from the project directory. Read-only — no modifications.

```json
{
  "tool": "file.read",
  "arguments": {
    "path": "string",
    "max_lines": "integer (optional, default 200)"
  }
}
```

- Refuses to read outside the project directory.
- Blocks access to common secrets locations (`~/.ssh`, `~/.aws`, `/etc/shadow`, etc.).

### `file.patch`
Apply a targeted text replacement in a file. Write action — always requires human confirmation (even when confidence is above threshold).

```json
{
  "tool": "file.patch",
  "arguments": {
    "path": "string",
    "old_content": "string (exact text to replace)",
    "new_content": "string"
  }
}
```

- Refuses (BLOCKED) if `old_content` does not appear exactly once in the file.
- Always requires `HumanOverride` to not be active.
- Logs the before/after diff to `memory.md` *before* applying the change.
- Reasoning and confidence are enforced by the Orchestrator (confidence gate at 0.7).

## Resource Cost
Lightweight. No heavy dependencies. Uses stdlib `os`, `pathlib`, `difflib`. RAM footprint: <5 MB.
