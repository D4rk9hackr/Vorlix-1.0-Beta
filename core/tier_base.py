"""Base classes and types for Vorlix automation tiers."""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class TierResult(Enum):
    SUCCESS = auto()
    BLOCKED = auto()
    NEEDS_HUMAN = auto()
    RETRY = auto()


@dataclass
class TierRequest:
    tool: str
    arguments: dict
    max_retries: int = 3
    reasoning: str = ""
    confidence: float = 1.0


@dataclass
class TierResponse:
    result: TierResult
    data: Any = None
    message: str = ""


@dataclass
class HumanHelpRequired:
    reason: str
    memory_snapshot: str
    ai_suggestion: str
    todo_resume_point: str


class AutomationTier:
    """Base class for all automation tiers."""

    def __init__(self, name: str):
        self.name = name

    async def execute(self, request: TierRequest) -> TierResponse:
        raise NotImplementedError("Subclasses must implement execute()")

    def is_within_guardrails(self, request: TierRequest) -> bool:
        """Return True if the request passes guardrail checks."""
        return True
