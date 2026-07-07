"""Smoke test for Phase 0 — validates all 5 fixes in the orchestrator."""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_base import TierRequest, TierResponse, TierResult, HumanHelpRequired
from core.orchestrator import Orchestrator
from tiers.example_stub_tier import ExampleStubTier


async def run_smoke_tests():
    print("=" * 60)
    print("VORLIX PHASE 0 SMOKE TEST")
    print("=" * 60)

    # Setup
    stub = ExampleStubTier()
    orch = Orchestrator(tiers=[stub], max_retries_per_tier=3, min_confidence=0.7)

    passed = 0
    failed = 0

    # --- Test 1: Successful dispatch with reasoning and confidence ---
    print("[TEST 1] Successful dispatch with reasoning + confidence")
    req = TierRequest(
        tool="stub.echo",
        arguments={"message": "hello world"},
        reasoning="Testing the echo stub tier to verify basic dispatch works.",
        confidence=0.95,
    )
    result = await orch.dispatch(req)
    if isinstance(result, TierResponse) and result.result == TierResult.SUCCESS:
        print("  PASS: " + str(result.data))
        passed += 1
    else:
        print("  FAIL: " + str(result))
        failed += 1

    # --- Test 2: Missing reasoning (Fix 5) ---
    print("[TEST 2] Missing reasoning should be rejected")
    req = TierRequest(
        tool="stub.echo",
        arguments={"message": "no reason"},
        reasoning="",
        confidence=0.95,
    )
    result = await orch.dispatch(req)
    if isinstance(result, HumanHelpRequired) and "no reasoning" in result.reason.lower():
        print("  PASS: Correctly rejected -- " + result.reason)
        passed += 1
    else:
        print("  FAIL: " + str(result))
        failed += 1

    # --- Test 3: Low confidence (Fix 5) ---
    print("[TEST 3] Low confidence should be rejected")
    req = TierRequest(
        tool="stub.echo",
        arguments={"message": "low confidence"},
        reasoning="Testing low confidence rejection.",
        confidence=0.5,
    )
    result = await orch.dispatch(req)
    if isinstance(result, HumanHelpRequired) and "confidence too low" in result.reason.lower():
        print("  PASS: Correctly rejected -- " + result.reason)
        passed += 1
    else:
        print("  FAIL: " + str(result))
        failed += 1

    # --- Test 4: Guardrail block (Fix 3 -- writes to memory) ---
    print("[TEST 4] Guardrail block + memory write")
    req = TierRequest(
        tool="stub.dangerous_action",
        arguments={},
        reasoning="Testing guardrail block.",
        confidence=0.9,
    )
    result = await orch.dispatch(req)
    if isinstance(result, HumanHelpRequired):
        print("  PASS: Guardrail blocked -- " + result.reason)
        passed += 1
    else:
        print("  FAIL: " + str(result))
        failed += 1

    # --- Test 5: Loop detection (Fix 4) ---
    print("[TEST 5] Loop detection -- 3 identical requests")
    req = TierRequest(
        tool="stub.echo",
        arguments={"message": "loop test"},
        reasoning="Testing loop detection.",
        confidence=0.95,
    )
    r1 = await orch.dispatch(req)
    r2 = await orch.dispatch(req)
    r3 = await orch.dispatch(req)
    if isinstance(r3, HumanHelpRequired) and "infinite loop" in r3.reason.lower():
        print("  PASS: Loop detected -- " + r3.reason)
        passed += 1
    else:
        print("  FAIL: r3=" + str(r3))
        failed += 1

    # --- Test 6: NEEDS_HUMAN escalation (Fix 3 -- writes to memory) ---
    print("[TEST 6] NEEDS_HUMAN escalation + memory write")
    orch2 = Orchestrator(tiers=[stub], max_retries_per_tier=3, min_confidence=0.7)
    req = TierRequest(
        tool="stub.needs_human",
        arguments={},
        reasoning="Testing NEEDS_HUMAN path.",
        confidence=0.9,
    )
    result = await orch2.dispatch(req)
    if isinstance(result, HumanHelpRequired) and "needs a human" in result.reason.lower():
        print("  PASS: Escalated to human -- " + result.reason)
        passed += 1
    else:
        print("  FAIL: " + str(result))
        failed += 1

    # --- Test 7: Retry logic (Fix 1 -- respects per-request max_retries) ---
    print("[TEST 7] Retry logic with per-request max_retries")
    orch3 = Orchestrator(tiers=[stub], max_retries_per_tier=5, min_confidence=0.7)
    req = TierRequest(
        tool="stub.retry_once",
        arguments={},
        reasoning="Testing retry with custom max_retries=1 (should fail).",
        confidence=0.9,
        max_retries=1,
    )
    result = await orch3.dispatch(req)
    if isinstance(result, HumanHelpRequired) and "retries exhausted" in result.reason.lower():
        print("  PASS: Retries exhausted as expected -- " + result.reason)
        passed += 1
    else:
        print("  FAIL: " + str(result))
        failed += 1

    # --- Test 8: Retry success with sufficient max_retries ---
    print("[TEST 8] Retry success with sufficient max_retries")
    orch4 = Orchestrator(tiers=[stub], max_retries_per_tier=5, min_confidence=0.7)
    req = TierRequest(
        tool="stub.retry_once",
        arguments={},
        reasoning="Testing retry with sufficient max_retries=3.",
        confidence=0.9,
        max_retries=3,
    )
    result = await orch4.dispatch(req)
    if isinstance(result, TierResponse) and result.result == TierResult.SUCCESS:
        print("  PASS: Retry succeeded -- " + str(result.data))
        passed += 1
    else:
        print("  FAIL: " + str(result))
        failed += 1

    # --- Test 9: All tiers exhausted ---
    print("[TEST 9] All tiers exhausted")
    orch5 = Orchestrator(tiers=[], max_retries_per_tier=3, min_confidence=0.7)
    req = TierRequest(
        tool="stub.echo",
        arguments={"message": "no tiers"},
        reasoning="Testing empty tier list.",
        confidence=0.9,
    )
    result = await orch5.dispatch(req)
    if isinstance(result, HumanHelpRequired) and "all tiers exhausted" in result.reason.lower():
        print("  PASS: All tiers exhausted -- " + result.reason)
        passed += 1
    else:
        print("  FAIL: " + str(result))
        failed += 1

    # --- Test 10: Memory.md was written at escalation points ---
    print("[TEST 10] Memory.md contains escalation entries")
    memory = orch.ledger.read_memory()
    memory2 = orch2.ledger.read_memory()
    has_guardrail = "Guardrail blocked" in memory
    has_loop = "Loop detected" in memory
    has_needs_human = "NEEDS_HUMAN" in memory2
    if (has_guardrail or has_loop) and has_needs_human:
        print("  PASS: memory.md contains expected escalation entries")
        passed += 1
    else:
        print("  FAIL: memory.md missing expected entries")
        print("  orch memory (guardrail/loop):")
        print(memory[:800])
        print("  orch2 memory (needs_human):")
        print(memory2[:400])
        failed += 1

    # --- Summary ---
    print("=" * 60)
    print("RESULTS: " + str(passed) + " passed, " + str(failed) + " failed")
    print("=" * 60)

    if failed > 0:
        print("SOME TESTS FAILED -- Phase 0 NOT complete.")
        return 1
    else:
        print("ALL TESTS PASSED -- Phase 0 COMPLETE.")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_smoke_tests())
    sys.exit(exit_code)
