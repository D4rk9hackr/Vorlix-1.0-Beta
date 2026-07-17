"""Example stub tier for testing the orchestrator."""
from core.tier_base import AgenticAutomationTier, TierRequest, TierResponse, TierResult


class ExampleStubTier(AgenticAutomationTier):
    """A stub tier that succeeds on 'stub.echo' and blocks everything else."""

    def __init__(self):
        super().__init__("ExampleStubTier")

    def is_within_guardrails(self, request: TierRequest) -> bool:
        # Block anything with 'dangerous' in the tool name
        if "dangerous" in request.tool.lower():
            return False
        return True

    async def execute(self, request: TierRequest) -> TierResponse:
        if request.tool == "stub.echo":
            return TierResponse(
                result=TierResult.SUCCESS,
                data=request.arguments.get("message", "echo"),
                message="Echo successful",
            )
        elif request.tool == "stub.needs_human":
            return TierResponse(
                result=TierResult.NEEDS_HUMAN,
                message="This tool always needs a human.",
            )
        elif request.tool == "stub.retry_once":
            if not hasattr(self, "_retry_count"):
                self._retry_count = 0
            self._retry_count += 1
            if self._retry_count < 2:
                return TierResponse(
                    result=TierResult.RETRY,
                    message="Retrying...",
                )
            return TierResponse(
                result=TierResult.SUCCESS,
                data="retry succeeded",
                message="Retry succeeded on second attempt",
            )
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unknown tool: {request.tool}",
            )
