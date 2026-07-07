"""Persistent memory and todo tracking for Vorlix."""
import os
from datetime import datetime
from typing import List, Optional


class Ledger:
    """Tracks memory, todos, and recovery state."""

    def __init__(self, workspace_dir: str = "./workspace"):
        self.workspace_dir = workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)
        self.memory_path = os.path.join(workspace_dir, "memory.md")
        self.todo_path = os.path.join(workspace_dir, "todo.md")

        # Ensure files exist
        for path in (self.memory_path, self.todo_path):
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"# {os.path.basename(path)}\n\n")

    def write_memory(self, current_thought: str, blockers: str, recovery_route: str) -> None:
        """Append a structured memory entry to memory.md."""
        timestamp = datetime.now().isoformat()
        entry = f"""
## [{timestamp}]
**Thought:** {current_thought}

**Blockers:** {blockers}

**Recovery Route:** {recovery_route}

---
"""
        with open(self.memory_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def read_memory(self) -> str:
        """Return the full contents of memory.md."""
        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def add_todo(self, description: str) -> None:
        """Append a todo item to todo.md."""
        timestamp = datetime.now().isoformat()
        entry = f"- [{timestamp}] {description}\n"
        with open(self.todo_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def list_todos(self) -> List[str]:
        """Return all todo lines."""
        try:
            with open(self.todo_path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except FileNotFoundError:
            return []
