"""Human override system — freeze/resume automation."""
import threading
from typing import Optional


class HumanOverride:
    """Global human override state."""

    _instance: Optional['HumanOverride'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._overridden = False
        return cls._instance

    def is_overridden(self) -> bool:
        """Return True if a human has frozen all automation."""
        return self._overridden

    def freeze(self) -> None:
        """Freeze all automation immediately."""
        self._overridden = True

    def resume(self) -> None:
        """Resume automation (requires confirmation)."""
        self._overridden = False
