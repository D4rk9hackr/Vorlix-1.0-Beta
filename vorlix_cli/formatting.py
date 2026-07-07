"""Output formatting utilities for Vorlix CLI."""


def format_result(status: str, message: str = "", data: dict | None = None) -> str:
    parts = [f"  Status: {status}"]
    if message:
        parts.append(f"  Message: {message}")
    if data:
        import json
        parts.append(f"  Data: {json.dumps(data, indent=4)}")
    return "\n".join(parts)


def format_todo(index: int, line: str) -> str:
    return f"  [{index}] {line}"


def format_skill(name: str, description: str = "", tools: list[str] | None = None) -> str:
    parts = [f"  📦 {name}"]
    if description:
        parts.append(f"     {description}")
    if tools:
        parts.append(f"     Tools: {', '.join(tools)}")
    return "\n".join(parts)
