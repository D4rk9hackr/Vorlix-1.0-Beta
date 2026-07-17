# Vorlix 1.0 Beta — The AI Hand Control Layer

**Give your AI a real hand to control your computer — lightly, safely, and fast.**

Vorlix is the control-layer engine of **The AI Hand**, a lightweight hybrid architecture that lets an AI agent control your PC using under 200MB of RAM. It escalates through three levels of intervention — always picking the fastest, cheapest method first.

---

## Architecture

```
                    ┌──────────────────┐
                    │   TierRequest    │
                    │  (tool, args,    │
                    │   reasoning,     │
                    │   confidence)    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   Orchestrator   │
                    │  ─ dispatch() ─  │
                    │  • Loop detect   │
                    │  • Confidence    │
                    │    gate          │
                    │  • Reasoning     │
                    │    required      │
                    │  • Retry logic   │
                    │  • Guardrails    │
                    │  • Agentic       │
                    │    (sub-agents,  │
                    │     parallel,    │
                    │     decompose)   │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼─────────────────────────┐
        ▼                    ▼                         ▼
┌───────────────┐  ┌────────────────┐  ┌──────────────────────┐
│  Tier 1       │  │  Tier 1.5      │  │  Tier 2              │
│  Terminal     │  │  System Query  │  │  Browser Bridge      │
│  (shell cmds) │  │  (processes,   │  │  (CDP — no Selenium) │
│               │  │   windows)     │  │                      │
└───────────────┘  └────────────────┘  └──────────────────────┘
                                                    │
                                               ┌────▼────┐
                                               │  Tier 3 │
                                               │Computer │
                                               │ Vision  │
                                               │(fallback)│
                                               └─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Sub-Agents      │
                    │  ─ spawn ─       │
                    │  • Delegate      │
                    │  • Parallel      │
                    │  • Collect       │
                    └──────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  HumanHelpRequired│
                    │  (escalation)     │
                    └──────────────────┘
```

## Tiers

| Tier | Tool | Description |
|------|------|-------------|
| **1 — Terminal** | `terminal.run_command` | Execute shell commands with destructive-command blacklist |
| **1.5 — System Query** | `process.list` | List running processes (requires `psutil`) |
| | `process.is_running` | Check if a process is running |
| | `window.list` | List open windows (requires `wmctrl`) |
| | `window.focus` | Focus a window by title |
| | `window.resize` | Resize a window |
| **2 — Browser Bridge** | `browser_controls.navigate` | Navigate to URL via CDP (no Selenium) |
| | `browser_controls.click_by_text` | Click element by visible text |
| | `browser_controls.fill_field` | Fill an input field |
| | `browser_controls.get_text` | Get page text content |
| | `browser_controls.screenshot` | Take browser screenshot |
| **3 — Computer Vision** | `computer_vision.click_target` | Template-matching click on screen (requires OpenCV) |
| | `computer_vision.track_target` | Continuous tracking with Bezier cursor paths |
| **Time & Reminders** | `time.now` | Current local time |
| | `reminder.create` | Schedule a one-off/repeating reminder |
| | `reminder.list` | List scheduled reminders |
| | `reminder.cancel` | Cancel a reminder |
| **Team / Sub-Agents** | `subagent.spawn` | Spawn a sub-agent with a goal and tool filter |
| | `subagent.ask` | Delegate work to a running sub-agent |
| | `subagent.list` | List all spawned sub-agents |
| | `subagent.kill` | Terminate a sub-agent |
| | `subagent.collect` | Wait for and collect sub-agent results |
| | `agentic.goal` | Auto-decompose a complex goal into sub-agents |
| **File I/O** | `file.read` | Read file content from workspace (with guardrails) |
| | `file.patch` | Apply string replacement patch to a file |

## Agentic Features

- **Sub-Agent System** — any tier can spawn sub-agents that run independently
- **Auto-Decomposition** — complex multi-step goals are split into sub-tasks and distributed across agents
- **Parallel Execution** — multiple tool calls dispatched concurrently
- **Recursive** — sub-agents can themselves spawn sub-agents
- **Global Agent Pool** — agents spawned from CLI, Telegram, or tiers all share the same pool

## skills.sh Integration

Vorlix can search, install, and publish skills from the [skills.sh](https://skills.sh) ecosystem:

```bash
vorlix skills search <query>          # Search community skills
vorlix skills install <owner/repo>    # Install a skill from GitHub
vorlix skills list                    # List installed skills
vorlix skills publish <name>          # Prepare a skill for publishing
```

## Telegram Bot

Control your PC from your phone via Telegram:

```bash
export VORLIX_TELEGRAM_TOKEN="your_bot_token"
python3 -c "from mcp.telegram_bot import VorlixTelegramBot; VorlixTelegramBot().run()"
```

Commands: `/list_skills`, `/activate`, `/deactivate`, `/override`, `/memory`, `/todo`, `/team spawn`, `/skillss search`, and free-text tool calls.

## MCP Server

Lightweight WebSocket server with optional TLS/HTTPS:

```bash
# Plain (ws://)
python3 -c "from mcp.lightweight_server import serve; import asyncio; asyncio.run(serve())"

# TLS (wss://) — auto-generates self-signed cert when binding to non-local address
python3 -c "from mcp.lightweight_server import serve; import asyncio; asyncio.run(serve(host='0.0.0.0', port=8765, tls=True))"
```

## Safety features

- **Human override** — freeze all automation instantly via `HumanOverride.freeze()`
- **Loop detection** — identical repeated requests trip detection and escalate
- **Confidence gate** — low-confidence requests require human confirmation
- **Reasoning required** — every action must explain why
- **Guardrails** — destructive commands (`rm -rf /`, `format`, `drop database`, etc.) are hard-blocked
- **Consent-based** — never stealthy, never evades OS permissions

## Quick start

```bash
pip install -r requirements.txt

# Run the CLI
vorlix run terminal.run_command --arg command="echo hello" --reason "Testing"

# List available skills
vorlix skills list

# Spawn a sub-agent
vorlix run subagent.spawn --arg goal="time.now" --reason "Spawn time agent"
```

### Manage todos
```bash
vorlix todo list
vorlix todo add "Implement feature X"
```

### Human override
```bash
vorlix override status
vorlix override stop
vorlix override resume
```

## Benchmarks

Vorlix vs Claude Computer Use — **15/15 tasks**, **97× faster** (1.3s vs 127.2s), **27× fewer tokens** (2.4k vs 66k), **~99% cheaper** ($0.007 vs $0.581).

Full report: `benchmarks/VORLIX_VS_CLAUDE.md`

## Tests

```bash
python -m pytest tests/ -v
```

## Project structure

```
vorlix/
├── core/                       # Control layer core
│   ├── tier_base.py            # Base classes, enums, AgenticAutomationTier
│   ├── orchestrator.py         # Dispatch, sub-agents, parallel, agentic dispatch
│   ├── ledger.py               # Memory & todo tracking
│   ├── human_override.py       # Freeze/resume singleton
│   └── art.py                  # ASCII art banners
├── tiers/                      # Tier implementations
│   ├── terminal_tier.py        # Shell commands
│   ├── system_query_tier.py    # Process/window queries
│   ├── browser_bridge_tier.py  # CDP browser control (no Selenium)
│   ├── computer_vision_tier.py # OpenCV template matching
│   ├── file_io_tier.py         # File read/patch
│   ├── time_reminders_tier.py  # Time awareness
│   ├── team_tier.py            # Sub-agent spawning interface
│   └── example_stub_tier.py    # Test stub
├── extension/                  # Chrome extension (TypeScript)
├── skills/                     # Skills registry + SKILL.md files
│   ├── registry.py
│   ├── terminal/SKILL.md
│   ├── system_query/SKILL.md
│   ├── browser_bridge/SKILL.md
│   ├── computer_vision/SKILL.md
│   ├── time_reminders/SKILL.md
│   └── team/SKILL.md
├── mcp/                        # MCP server + Telegram bot
│   ├── lightweight_server.py   # WebSocket server with TLS
│   └── telegram_bot.py         # Telegram bot integration
├── vorlix_cli/                 # Command-line interface
│   ├── main.py                 # CLI entry point
│   └── skills_sh.py            # skills.sh search/install/publish
├── benchmarks/                 # Performance benchmarks
│   ├── BENCHMARK_RESULTS.md
│   ├── VORLIX_VS_CLAUDE.md
│   ├── vorlix_vs_claude.py
│   └── multi_step_workflows.py
├── tests/                      # Test suite (85+ tests)
│   ├── test_terminal_tier.py
│   ├── test_system_query_tier.py
│   ├── test_browser_bridge_tier.py
│   ├── test_computer_vision_tier.py
│   ├── test_file_io_tier.py
│   ├── test_time_reminders.py
│   ├── test_team_tier.py
│   ├── test_skills_registry.py
│   ├── test_skills_sh.py
│   ├── test_cli.py
│   ├── test_benchmark.py
│   └── smoke_test.py
├── pyproject.toml
└── README.md
```

## License

Vorlix Source-Available Commercial License v1.0 — see [LICENSE](./LICENSE) for full terms.

Personal, educational, and non-commercial use is free. Any commercial use (selling, sublicensing, or offering this software as part of a paid product or service) requires a separate license from the copyright holder. Contact: mohamedstngrly@gmail.com

---

**Author:** D4rk9hackr
**Part of:** The AI Hand project
