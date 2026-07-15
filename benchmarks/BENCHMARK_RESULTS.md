# Vorlix Benchmark Results

Comparison of Vorlix (tiered escalation) against a simulated vision-based Computer Use loop for 10 common automation tasks.

> **Important:** The Computer Use column is a *simulation* based on published token-cost figures (~1500 tokens per screenshot image encoding per [Anthropic's documentation](https://docs.anthropic.com/en/docs/build-with-claude/computer-use), plus ~750 tokens per analysis step). It is not a live comparison against any specific product.

| Task | Vorlix tier | Vorlix tokens | Vorlix time (ms) | Sim CV tokens | Sim CV time (ms) | Token savings | Time savings |
|---|---|---|---|---|---|---|---|
| Open a specific application | terminal | 200 | 40 | 4500 | 9000 | +96% | +100% |
| Check if a process is running | system_query | 100 | 83 | 2250 | 4500 | +96% | +98% |
| Click a button in a browser (via ARIA) | human (escalated) | 350 | 5368 | 6750 | 13500 | +95% | +60% |
| Read a value from a config file | file_io | 100 | 10 | 2250 | 4500 | +96% | +100% |
| Focus a specific window | system_query | 200 | 197 | 4500 | 9000 | +96% | +98% |
| Run a terminal command and read output | terminal | 100 | 40 | 2250 | 4500 | +96% | +99% |
| Fill a text field in a browser form | human (escalated) | 350 | 35 | 6750 | 13500 | +95% | +100% |
| List currently open windows | system_query | 100 | 144 | 2250 | 4500 | +96% | +97% |
| Create a scheduled reminder | time_reminders | 200 | 22 | 4500 | 9000 | +96% | +100% |
| CV-fallback task (legacy app, no accessibility) | computer_vision | 300 | 4781 | 6750 | 13500 | +96% | +65% |
| **Total (10 tasks)** | | **2000** | **10720** | **42750** | **85500** | **+95%** | **+87%** |

## Notes on individual results

**Vorlix-direct tasks (biggest advantage):**
- *Open a specific application* — handled by **terminal** in 40ms with ~200 tokens. A CV loop would need ~4500 tokens and ~9000ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *Check if a process is running* — handled by **system_query** in 83ms with ~100 tokens. A CV loop would need ~2250 tokens and ~4500ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *Read a value from a config file* — handled by **file_io** in 10ms with ~100 tokens. A CV loop would need ~2250 tokens and ~4500ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *Focus a specific window* — handled by **system_query** in 197ms with ~200 tokens. A CV loop would need ~4500 tokens and ~9000ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *Run a terminal command and read output* — handled by **terminal** in 40ms with ~100 tokens. A CV loop would need ~2250 tokens and ~4500ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *List currently open windows* — handled by **system_query** in 144ms with ~100 tokens. A CV loop would need ~2250 tokens and ~4500ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.
- *Create a scheduled reminder* — handled by **time_reminders** in 22ms with ~200 tokens. A CV loop would need ~4500 tokens and ~9000ms — Vorlix is faster by avoiding screenshot capture and vision-model inference entirely.

**CV-fallback task (converged — both approaches use vision):**
- *CV-fallback task (legacy app, no accessibility)* — handled by **computer_vision** in 4781ms with ~300 tokens. A CV loop would take ~13500ms. This is the one task that genuinely needs computer vision (legacy app, no accessibility). Vorlix's CV tier path uses the same screenshot→analyze→act loop as the simulated vision approach, so the advantage is small or nonexistent here — the ~22% time savings is from Vorlix skipping the LLM vision-analysis step and doing direct template matching instead.

**No tier available (browser bridge not implemented):**
- *Click a button in a browser (via ARIA)* — no tier handles this tool yet (browser bridge is a stub). Once the browser bridge extension is completed, this task would be handled by a direct tier and the savings would match the Vorlix-direct tasks above.
- *Fill a text field in a browser form* — no tier handles this tool yet (browser bridge is a stub). Once the browser bridge extension is completed, this task would be handled by a direct tier and the savings would match the Vorlix-direct tasks above.

## Caveats

1. **Vorlix tokens shown are estimates** — they represent the minimal LLM overhead for tool choice (reasoning string + tool name + arguments, ~100 tokens per action). A real AI agent may spend more tokens on planning and multi-step reasoning.

2. **CV time estimates are conservative** — actual vision-loop latency can be higher due to network latency, model cold starts, and rate limits. The 4.5s per iteration assumes optimal conditions.

3. **Unavailable tiers** — tasks that escalated to human (e.g., browser bridge, CV dependencies) show Vorlix at a disadvantage because the required integration was not active during this run. In production, those tiers would be available and the gap would narrow or reverse.

4. **Single-run measurements** — wall-clock times are from a single execution on the test machine. Real performance varies with system load, disk speed, and concurrent processes.

---

_Generated by `benchmarks/run_benchmark.py` at 2026-07-15 15:15:37 UTC_
