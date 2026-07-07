"""Orchestrator — routes TierRequests through registered tiers."""
from collections import deque
from typing import List, Optional

from core.tier_base import (
    AutomationTier,
    TierRequest,
    TierResponse,
    TierResult,
    HumanHelpRequired,
)
from core.ledger import Ledger
from core.human_override import HumanOverride


class Orchestrator:
    """Routes requests to the appropriate tier with retry, guardrail, and escalation logic."""

    def __init__(
        self,
        tiers: Optional[List[AutomationTier]] = None,
        max_retries_per_tier: int = 3,
        min_confidence: float = 0.7,
    ):
        self.tiers = tiers or []
        self.max_retries_per_tier = max_retries_per_tier
        self.min_confidence = min_confidence
        self.ledger = Ledger()
        self.human_override = HumanOverride()
        self._recent_requests: deque = deque(maxlen=5)

    def register_tier(self, tier: AutomationTier) -> None:
        self.tiers.append(tier)

    async def dispatch(self, request: TierRequest) -> TierResponse | HumanHelpRequired:
        # --- Human override check ---
        if self.human_override.is_overridden():
            return HumanHelpRequired(
                reason="Human override is active — all automation frozen.",
                memory_snapshot=self.ledger.read_memory(),
                ai_suggestion="Wait for the human to resume or provide manual input.",
                todo_resume_point=request.tool,
            )

        # --- Fix 4: Loop detection ---
        signature = (request.tool, str(sorted(request.arguments.items())))
        if list(self._recent_requests).count(signature) >= 2:
            self.ledger.write_memory(
                current_thought=f"Loop detected: repeated identical request for {request.tool}",
                blockers="Infinite loop detected — same request signature seen 3+ times",
                recovery_route="Escalating to human to break the loop.",
            )
            self.ledger.add_todo(f"Loop detected on {request.tool} — human review required.")
            return HumanHelpRequired(
                reason=f"Repeated identical request detected ({request.tool}) — stopping before an infinite loop.",
                memory_snapshot=self.ledger.read_memory(),
                ai_suggestion="This exact action has been attempted multiple times with no progress. Try a different approach, or ask the human directly.",
                todo_resume_point=request.tool,
            )
        self._recent_requests.append(signature)

        # --- Fix 5: Confidence gate + required reasoning ---
        if not request.reasoning.strip():
            self.ledger.write_memory(
                current_thought=f"Request rejected for {request.tool}: no reasoning provided.",
                blockers="Missing required reasoning string.",
                recovery_route="Resubmit with reasoning explaining the intent.",
            )
            self.ledger.add_todo(f"Rejected {request.tool}: missing reasoning.")
            return HumanHelpRequired(
                reason="Request rejected: no reasoning provided. Every action must state why it's being taken.",
                memory_snapshot=self.ledger.read_memory(),
                ai_suggestion="Resubmit the request with a `reasoning` string explaining the intent.",
                todo_resume_point=request.tool,
            )

        if request.confidence < self.min_confidence:
            self.ledger.write_memory(
                current_thought=f"Request for {request.tool} rejected: confidence {request.confidence:.2f} below threshold {self.min_confidence:.2f}",
                blockers=f"Confidence too low ({request.confidence:.2f}) for '{request.tool}'",
                recovery_route="Human confirmation required before proceeding.",
            )
            self.ledger.add_todo(f"Low confidence on {request.tool}: human confirmation needed.")
            return HumanHelpRequired(
                reason=f"Confidence too low ({request.confidence:.2f}) for '{request.tool}' — asking before acting.",
                memory_snapshot=self.ledger.read_memory(),
                ai_suggestion=f"Intended action: {request.reasoning}. Confirm before proceeding.",
                todo_resume_point=request.tool,
            )

        # --- Try tiers in order ---
        for tier in self.tiers:
            # Guardrail check
            if not tier.is_within_guardrails(request):
                self.ledger.write_memory(
                    current_thought=f"Guardrail blocked {request.tool} in {tier.name}",
                    blockers=f"Guardrail violation in {tier.name}",
                    recovery_route="Escalating to human — this request violates safety guardrails.",
                )
                self.ledger.add_todo(f"Guardrail block on {request.tool} in {tier.name}")
                return HumanHelpRequired(
                    reason=f"Guardrail blocked {request.tool} in {tier.name}",
                    memory_snapshot=self.ledger.read_memory(),
                    ai_suggestion="This request violates safety guardrails. Review and resubmit with a safe alternative.",
                    todo_resume_point=request.tool,
                )

            # --- Fix 1: Respect per-request max_retries ---
            effective_retries = min(request.max_retries, self.max_retries_per_tier)

            for attempt in range(effective_retries):
                # --- Fix 2: Catch unexpected exceptions from tier.execute() ---
                try:
                    result = await tier.execute(request)
                except Exception as exc:
                    self.ledger.write_memory(
                        current_thought=f"{tier.name} raised an unexpected exception: {exc!r}",
                        blockers=f"Unhandled exception in {tier.name}",
                        recovery_route="Escalating to human - this is a bug, not an expected failure.",
                    )
                    self.ledger.add_todo(f"Exception in {tier.name}: {exc}")
                    return HumanHelpRequired(
                        reason=f"{tier.name} raised an unexpected exception: {exc}",
                        memory_snapshot=self.ledger.read_memory(),
                        ai_suggestion="This looks like a bug in the tier implementation, not a normal failure. Check logs.",
                        todo_resume_point=request.tool,
                    )

                if result.result == TierResult.SUCCESS:
                    return result
                elif result.result == TierResult.NEEDS_HUMAN:
                    # --- Fix 3: Write to memory.md at every failure/block/escalation point ---
                    self.ledger.write_memory(
                        current_thought=f"{tier.name} returned NEEDS_HUMAN for {request.tool}",
                        blockers=result.message,
                        recovery_route="Escalating to human — tier explicitly requested human intervention.",
                    )
                    self.ledger.add_todo(f"NEEDS_HUMAN from {tier.name} for {request.tool}: {result.message}")
                    return HumanHelpRequired(
                        reason=result.message,
                        memory_snapshot=self.ledger.read_memory(),
                        ai_suggestion="The tier explicitly requested human intervention. Review the situation.",
                        todo_resume_point=request.tool,
                    )
                elif result.result == TierResult.BLOCKED:
                    # --- Fix 3: Write to memory.md at every failure/block/escalation point ---
                    self.ledger.write_memory(
                        current_thought=f"{tier.name} returned BLOCKED for {request.tool}",
                        blockers=result.message,
                        recovery_route="Try next tier or escalate to human.",
                    )
                    self.ledger.add_todo(f"BLOCKED from {tier.name} for {request.tool}: {result.message}")
                    break  # Move to next tier
                elif result.result == TierResult.RETRY:
                    continue  # Retry this tier
            else:
                # Retries exhausted for this tier
                # --- Fix 3: Write to memory.md at every failure/block/escalation point ---
                self.ledger.write_memory(
                    current_thought=f"Retries exhausted for {request.tool} in {tier.name}",
                    blockers=f"All {effective_retries} attempts failed in {tier.name}",
                    recovery_route="Escalating to human — tier exhausted all retries.",
                )
                self.ledger.add_todo(f"Retries exhausted for {request.tool} in {tier.name}")
                return HumanHelpRequired(
                    reason=f"Retries exhausted for {request.tool} in {tier.name}",
                    memory_snapshot=self.ledger.read_memory(),
                    ai_suggestion="All retry attempts failed. Review the tier logs and consider manual intervention.",
                    todo_resume_point=request.tool,
                )

        # All tiers exhausted
        # --- Fix 3: Write to memory.md at every failure/block/escalation point ---
        self.ledger.write_memory(
            current_thought=f"All tiers exhausted for {request.tool}",
            blockers="No tier could handle the request.",
            recovery_route="Escalating to human — no tier available or capable.",
        )
        self.ledger.add_todo(f"All tiers exhausted for {request.tool}")
        return HumanHelpRequired(
            reason=f"All tiers exhausted for {request.tool}",
            memory_snapshot=self.ledger.read_memory(),
            ai_suggestion="No tier was able to handle this request. Check if the required skill is activated.",
            todo_resume_point=request.tool,
        )
