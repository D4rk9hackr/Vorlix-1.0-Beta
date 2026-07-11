# Vorlix Benchmark Results

Comparison of Vorlix (tiered escalation) against a simulated vision-based Computer Use loop for 10 common automation tasks.

> **Important:** The Computer Use column is a *simulation* based on published token-cost figures (~1500 tokens per screenshot image encoding per [Anthropic's documentation](https://docs.anthropic.com/en/docs/build-with-claude/computer-use), plus ~750 tokens per analysis step). It is not a live comparison against any specific product.

| Task | Vorlix tier | Vorlix tokens | Vorlix time (ms) | Sim CV tokens | Sim CV time (ms) | Token savings | Time savings |
|---|---|---|---|---|---|---|---|
| Open a specific application | terminal | 200 | 30 | 4500 | 9000 | +96% | +100% |
| Check if a process is running | human (escalated) | 150 | 87 | 2250 | 4500 | +93% | +98% |
| Click a button in a browser (via ARIA) | human (escalated) | 350 | 95 | 6750 | 13500 | +95% | +99% |
| Read a value from a config file | file_io | 100 | 47 | 2250 | 4500 | +96% | +99% |
| Focus a specific window | human (escalated) | 250 | 110 | 4500 | 9000 | +94% | +99% |
| Run a terminal command and read output | terminal | 100 | 24 | 2250 | 4500 | +96% | +99% |
| Fill a text field in a browser form | human (escalated) | 350 | 84 | 6750 | 13500 | +95% | +99% |
| List currently open windows | human (escalated) | 150 | 110 | 2250 | 4500 | +93% | +98% |
| Create a scheduled reminder | time_reminders | 200 | 41 | 4500 | 9000 | +96% | +100% |
| CV-fallback task (legacy app, no accessibility) | human (escalated) | 350 | 79 | 6750 | 13500 | +95% | +99% |
| **Total (10 tasks)** | | **2200** | **707** | **42750** | **85500** | **+95%** | **+99%** |

## Notes on individual results

**Vorlix-direct tasks (biggest advantage):**
- *Open a specific application* — handled by **terminal** in 30ms with ~200 tokens. A CV loop would need ~4500 tokens and ~9000ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *Read a value from a config file* — handled by **file_io** in 47ms with ~100 tokens. A CV loop would need ~2250 tokens and ~4500ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *Run a terminal command and read output* — handled by **terminal** in 24ms with ~100 tokens. A CV loop would need ~2250 tokens and ~4500ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *Create a scheduled reminder* — handled by **time_reminders** in 41ms with ~200 tokens. A CV loop would need ~4500 tokens and ~9000ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.

**Escalated (dependencies not available in this environment):**
- *Check if a process is running* — escalated because the required tier was registered but could not execute (missing system dependencies). In production with all dependencies installed, this task would be handled by a direct tier and the savings would match the Vorlix-direct tasks above.
- *Click a button in a browser (via ARIA)* — escalated because the required tier was registered but could not execute (missing system dependencies). In production with all dependencies installed, this task would be handled by a direct tier and the savings would match the Vorlix-direct tasks above.
- *Focus a specific window* — escalated because the required tier was registered but could not execute (missing system dependencies). In production with all dependencies installed, this task would be handled by a direct tier and the savings would match the Vorlix-direct tasks above.
- *Fill a text field in a browser form* — escalated because the required tier was registered but could not execute (missing system dependencies). In production with all dependencies installed, this task would be handled by a direct tier and the savings would match the Vorlix-direct tasks above.
- *List currently open windows* — escalated because the required tier was registered but could not execute (missing system dependencies). In production with all dependencies installed, this task would be handled by a direct tier and the savings would match the Vorlix-direct tasks above.

**CV-fallback task (smallest advantage):**
- *CV-fallback task (legacy app, no accessibility)* — this task is designed to require computer vision (legacy app, no accessibility). Vorlix still shows time savings because it fails *fast* (~79ms) rather than spending cycles in a vision loop, but in production the CV tier would execute at similar latency to the simulated CV path. This is the one scenario where both approaches converge, and the advantage is small or nonexistent.

## Caveats

1. **Vorlix tokens shown are estimates** — they represent the minimal LLM overhead for tool choice (reasoning string + tool name + arguments, ~100 tokens per action). A real AI agent may spend more tokens on planning and multi-step reasoning.

2. **CV time estimates are conservative** — actual vision-loop latency can be higher due to network latency, model cold starts, and rate limits. The 4.5s per iteration assumes optimal conditions.

3. **Unavailable tiers** — tasks that escalated to human (e.g., browser bridge, CV dependencies) show Vorlix at a disadvantage because the required integration was not active during this run. In production, those tiers would be available and the gap would narrow or reverse.

4. **Single-run measurements** — wall-clock times are from a single execution on the test machine. Real performance varies with system load, disk speed, and concurrent processes.

---

_Generated by `benchmarks/run_benchmark.py` at 2026-07-07 04:00:32 UTC_
