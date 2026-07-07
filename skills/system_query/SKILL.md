# System Query

## Name
System Query

## Description
Read-only system introspection tools — lists running processes, checks if a process is running, enumerates windows, focuses and resizes windows.

## When to use it
- Checking what applications are running before acting
- Finding a window by title to interact with it
- Confirming a process started successfully
- Resizing or focusing windows for workflow automation

## Tools

### `process.list`
Lists running processes, optionally filtered by name.

```json
{"tool": "process.list", "arguments": {"name_filter": "string (optional)"}}
```

### `process.is_running`
Checks if a specific process is running.

```json
{"tool": "process.is_running", "arguments": {"name": "string"}}
```

### `window.list`
Lists all open windows with their IDs, desktop numbers, PIDs, and titles.

```json
{"tool": "window.list", "arguments": {}}
```

### `window.focus`
Brings a window to the foreground by matching its title.

```json
{"tool": "window.focus", "arguments": {"title_contains": "string"}}
```

- Respects `HumanOverride.is_overridden()` before acting.

### `window.resize`
Resizes a window to specified dimensions.

```json
{"tool": "window.resize", "arguments": {"title_contains": "string", "width": "integer", "height": "integer"}}
```

- Respects `HumanOverride.is_overridden()` before acting.

## Resource Cost
Lightweight. Requires `psutil` for process tools, `wmctrl` on Linux for window tools. RAM footprint: <15 MB.
