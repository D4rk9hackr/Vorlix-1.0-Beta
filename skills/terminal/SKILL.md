# Terminal

## Name
Terminal

## Description
Executes direct shell/terminal commands to open applications, edit files, or run scripts. Instant, near-zero resource use.

## When to use it
- Opening applications or files
- Running shell scripts
- File operations (copy, move, edit)
- System administration tasks
- Any task that can be done via command line

## Tools

### `terminal.run_command`
Executes a shell command and returns stdout/stderr.

```json
{
  "tool": "terminal.run_command",
  "arguments": {
    "command": "string",
    "run_as_admin": "boolean (optional)",
    "execution_timeout_ms": "integer (optional, default 30000)"
  }
}
```

- Destructive commands (`rm -rf /`, `format`, `drop database`, etc.) are hard-blocked by guardrails.
- On missing-dependency errors, logs what's needed.

## Resource Cost
Lightweight. No heavy dependencies. RAM footprint: <10 MB. Uses stdlib `subprocess` + `asyncio`.
